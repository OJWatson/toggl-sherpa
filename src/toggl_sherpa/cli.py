from __future__ import annotations

import shutil
from pathlib import Path

import typer

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m1.daemon import (
    AlreadyRunningError,
    start_logger,
    stop_logger,
)
from toggl_sherpa.m1.daemon import (
    status as logger_status,
)
from toggl_sherpa.m1.gnome import GnomeShellEvalError, get_focus_sample
from toggl_sherpa.m1.logger import insert_sample
from toggl_sherpa.m1.paths import default_db_path, pidfile_path
from toggl_sherpa.m2.tab_server import serve as serve_tab_ingest
from toggl_sherpa.m3.query import day_bounds_utc, fetch_samples, fetch_tab_events, to_jsonable
from toggl_sherpa.m3.report import blocks_to_markdown
from toggl_sherpa.m3.summarise import summarise_blocks
from toggl_sherpa.m4.apply import load_blocks_json, merge_adjacent_blocks, write_toggl_csv
from toggl_sherpa.m4.review import interactive_review, write_reviewed_json
from toggl_sherpa.m5.apply import (
    _load_blocks,
    apply_plan,
    build_plan,
    load_config_from_env,
    print_plan,
)
from toggl_sherpa.m6.config import load_mapping
from toggl_sherpa.m6.ledger import list_applied
from toggl_sherpa.m6.ledger import stats as ledger_stats

app = typer.Typer(add_completion=False, no_args_is_help=True)
log_app = typer.Typer(add_completion=False, no_args_is_help=True)
web_app = typer.Typer(add_completion=False, no_args_is_help=True)
report_app = typer.Typer(add_completion=False, no_args_is_help=True)
ledger_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(log_app, name="log")
app.add_typer(web_app, name="web")
app.add_typer(report_app, name="report")
app.add_typer(ledger_app, name="ledger")


@app.callback()
def _root() -> None:
    """toggl-sherpa."""


@app.command()
def doctor() -> None:
    """Check environment prerequisites (GNOME + gdbus, etc.)."""
    missing: list[str] = []
    if shutil.which("gdbus") is None:
        missing.append("gdbus")

    if missing:
        typer.echo(f"missing dependencies: {', '.join(missing)}")
        raise typer.Exit(code=1)

    # Best-effort check that GNOME Shell Eval works.
    try:
        _ = get_focus_sample()
    except GnomeShellEvalError as e:
        typer.echo(f"warning: gnome-shell eval failed: {e}")

    typer.echo("ok")


@log_app.command("once")
def log_once(
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
) -> None:
    """Capture one focus+idle sample and store it in SQLite (for testing)."""
    conn = db_mod.connect(db)
    sample = get_focus_sample()
    insert_sample(conn, sample)
    typer.echo("logged")


@log_app.command("start")
def log_start(
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    interval_s: float = typer.Option(
        10.0,
        "--interval",
        min=1.0,
        help="Sampling interval (seconds)",
    ),  # noqa: B008
) -> None:
    """Start background logger process (writes pidfile)."""
    try:
        pid = start_logger(str(db), interval_s=interval_s)
    except AlreadyRunningError as e:
        typer.echo(str(e))
        raise typer.Exit(code=1) from e
    typer.echo(f"started (pid {pid})")


@log_app.command("stop")
def log_stop() -> None:
    """Stop background logger process."""
    stopped = stop_logger()
    if stopped:
        typer.echo("stopped")
    else:
        typer.echo("not running")


@log_app.command("status")
def log_status() -> None:
    """Show logger status."""
    running, pid = logger_status()
    pf = pidfile_path()
    if running:
        typer.echo(f"running (pid {pid}) pidfile={pf}")
    elif pid is not None:
        typer.echo(f"stale pidfile (pid {pid}) pidfile={pf}")
        raise typer.Exit(code=1)
    else:
        typer.echo(f"stopped pidfile={pf}")
        raise typer.Exit(code=1)


@web_app.command("tab-server")
def web_tab_server(
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    host: str = typer.Option("127.0.0.1", "--host", help="Bind host"),  # noqa: B008
    port: int = typer.Option(5055, "--port", help="Bind port"),  # noqa: B008
    allowlist: str = typer.Option(
        "",
        "--allowlist",
        help="Comma-separated host/domain allowlist (stores full URL+title only for allowed hosts)",
        envvar="TOGGL_SHERPA_TAB_ALLOWLIST",
    ),  # noqa: B008
) -> None:
    """Run a localhost HTTP server to ingest active tab events from the Chrome extension."""
    typer.echo(f"tab ingest server listening on http://{host}:{port} (db={db})")
    serve_tab_ingest(db_path=db, host=host, port=port, allowlist=allowlist or None)


@report_app.command("draft-timesheet")
def report_draft_timesheet(
    date: str = typer.Option(
        ..., "--date", help="UTC date (YYYY-MM-DD) to summarise"
    ),
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    format: str = typer.Option(
        "md",
        "--format",
        help="Output format: md|json",
    ),
    idle_threshold_ms: int = typer.Option(
        60_000,
        "--idle-threshold-ms",
        help="Treat samples as idle if idle_ms >= this",
    ),
) -> None:
    """Generate a draft timesheet + evidence report for one UTC day."""
    start_ts, end_ts = day_bounds_utc(date)
    conn = db_mod.connect(db)
    try:
        samples = fetch_samples(conn, start_ts, end_ts)
        tabs = fetch_tab_events(conn, start_ts, end_ts)
    finally:
        conn.close()

    blocks = summarise_blocks(samples, tabs, idle_threshold_ms=idle_threshold_ms)

    if format == "json":
        import json

        typer.echo(json.dumps(to_jsonable(blocks), ensure_ascii=False, indent=2))
        return

    if format != "md":
        typer.echo("format must be md or json")
        raise typer.Exit(code=2)

    typer.echo(blocks_to_markdown(blocks))


@report_app.command("review")
def report_review(
    date: str = typer.Option(
        ..., "--date", help="UTC date (YYYY-MM-DD) to summarise"
    ),
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    out: str = typer.Option(
        "reviewed_timesheet.json",
        "--out",
        help="Where to write reviewed blocks JSON (file name or full path)",
    ),  # noqa: B008
    out_dir: str = typer.Option(
        "",
        "--out-dir",
        help=(
            "Directory to write `--out` into when `--out` is a filename "
            "(default: current directory)"
        ),
    ),  # noqa: B008
    idle_threshold_ms: int = typer.Option(
        60_000,
        "--idle-threshold-ms",
        help="Treat samples as idle if idle_ms >= this",
    ),
) -> None:
    """Interactively review blocks and write an accepted/edited JSON file."""
    start_ts, end_ts = day_bounds_utc(date)
    conn = db_mod.connect(db)
    try:
        samples = fetch_samples(conn, start_ts, end_ts)
        tabs = fetch_tab_events(conn, start_ts, end_ts)
    finally:
        conn.close()

    blocks = summarise_blocks(samples, tabs, idle_threshold_ms=idle_threshold_ms)
    reviewed = interactive_review(blocks)

    out_path = str(Path(out_dir) / out) if out_dir and Path(out).name == out else out
    write_reviewed_json(out_path, reviewed)
    typer.echo(f"wrote {out_path} ({len(reviewed)} accepted block(s))")


@report_app.command("merge")
def report_merge(
    in_path: str = typer.Option(
        ..., "--in", help="Input reviewed blocks JSON (from report review)"
    ),
    out: str = typer.Option(
        "merged_timesheet.json",
        "--out",
        help="Where to write merged blocks JSON",
    ),  # noqa: B008
    gap_seconds: int = typer.Option(
        60,
        "--gap-seconds",
        help="Merge blocks if gap between them <= this (and label/project/tags match)",
    ),
) -> None:
    """Merge adjacent reviewed blocks into longer runs."""
    blocks = load_blocks_json(in_path)
    merged = merge_adjacent_blocks(blocks, gap_seconds=gap_seconds)
    write_reviewed_json(out, merged)
    typer.echo(f"wrote {out} ({len(merged)} block(s))")


@report_app.command("apply")
def report_apply(
    in_path: str = typer.Option(
        ..., "--in", help="Input blocks JSON (typically from report merge)"
    ),
    out: str = typer.Option(
        "toggl_import.csv",
        "--out",
        help="Where to write Toggl Track CSV import",
    ),  # noqa: B008
) -> None:
    """Convert approved blocks to a Toggl Track CSV import file."""
    blocks = load_blocks_json(in_path)
    write_toggl_csv(out, blocks)
    typer.echo(f"wrote {out} ({len(blocks)} row(s))")


@app.command("apply")
def apply(
    reviewed: str = typer.Option(
        "reviewed_timesheet.json",
        "--reviewed",
        help="Reviewed blocks JSON file (from `toggl-sherpa report review`)",
    ),  # noqa: B008
    config: str = typer.Option(
        "",
        "--config",
        help="Optional config.json for project/tag mapping (default: XDG config path)",
    ),  # noqa: B008
    explain_skips: bool = typer.Option(
        False,
        "--explain-skips",
        help="Print the entries skipped due to idempotency",
    ),  # noqa: B008
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run (prints what would be created; default)",
    ),  # noqa: B008
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Actually create entries in Toggl (explicit approval gate)",
    ),  # noqa: B008
    ledger_db: str = typer.Option(
        "",
        "--ledger-db",
        help="SQLite DB used for local idempotency ledger (default: main DB)",
    ),  # noqa: B008
    force: bool = typer.Option(
        False,
        "--force",
        help="Disable idempotency checks (re-post even if already applied)",
    ),  # noqa: B008
) -> None:
    """Apply reviewed blocks to Toggl Track.

    Refuses to create anything unless `--yes` is provided.
    """

    if yes:
        dry_run = False

    if not dry_run and not yes:
        typer.echo("refusing: pass --yes to create entries")
        raise typer.Exit(code=2)

    blocks = _load_blocks(Path(reviewed))
    mapping = load_mapping(Path(config) if config else None)
    plan = build_plan(blocks, project_ids=mapping.project_ids, tag_map=mapping.tag_map)
    print_plan(plan)

    if dry_run:
        typer.echo("dry-run: not creating anything")
        return

    cfg = load_config_from_env()
    ledger_path = Path(ledger_db) if ledger_db else default_db_path()
    created, skipped, skipped_items = apply_plan(
        plan,
        cfg,
        ledger_db_path=ledger_path,
        force=force,
    )
    typer.echo(f"created {len(created)} time entr(y/ies)")
    if skipped:
        typer.echo(f"skipped {skipped} already-applied entr(y/ies)")
        if explain_skips:
            for p in skipped_items[:20]:
                typer.echo(f"- {p.start} → {p.stop} | {p.description}")
            if len(skipped_items) > 20:
                typer.echo(f"- … ({len(skipped_items) - 20} more)")


@app.command("day")
def day(
    date: str = typer.Option(
        ..., "--date", help="UTC date (YYYY-MM-DD) to summarise"
    ),
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    out: str = typer.Option(
        "",
        "--out",
        help="Where to write reviewed blocks JSON (default: reviewed_<date>.json)",
    ),  # noqa: B008
    accept_all: bool = typer.Option(
        False,
        "--accept-all",
        help="Accept all blocks without prompting (non-interactive)",
    ),  # noqa: B008
    idle_threshold_ms: int = typer.Option(
        60_000,
        "--idle-threshold-ms",
        help="Treat samples as idle if idle_ms >= this",
    ),  # noqa: B008
    out_dir: str = typer.Option(
        "",
        "--out-dir",
        help="Directory to write default outputs into (default: current directory)",
    ),  # noqa: B008
    merge: bool = typer.Option(
        False,
        "--merge",
        help="Merge adjacent identical blocks before writing/applying",
    ),  # noqa: B008
    merge_gap_seconds: int = typer.Option(
        60,
        "--merge-gap-seconds",
        help="Merge blocks if gap between them <= this (when --merge is set)",
    ),  # noqa: B008
    config: str = typer.Option(
        "",
        "--config",
        help="Optional config.json for project/tag mapping (default: XDG config path)",
    ),  # noqa: B008
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--no-dry-run",
        help="Dry-run (prints what would be created; default)",
    ),  # noqa: B008
    yes: bool = typer.Option(
        False,
        "--yes",
        help="Actually create entries in Toggl (explicit approval gate)",
    ),  # noqa: B008
    ledger_db: str = typer.Option(
        "",
        "--ledger-db",
        help="SQLite DB used for local idempotency ledger (default: main DB)",
    ),  # noqa: B008
    force: bool = typer.Option(
        False,
        "--force",
        help="Disable idempotency checks (re-post even if already applied)",
    ),  # noqa: B008
) -> None:
    """One-shot day workflow: draft -> review -> (dry-run/apply)."""

    if yes:
        dry_run = False

    if not dry_run and not yes:
        typer.echo("refusing: pass --yes to create entries")
        raise typer.Exit(code=2)

    start_ts, end_ts = day_bounds_utc(date)
    conn = db_mod.connect(db)
    try:
        samples = fetch_samples(conn, start_ts, end_ts)
        tabs = fetch_tab_events(conn, start_ts, end_ts)
    finally:
        conn.close()

    blocks = summarise_blocks(samples, tabs, idle_threshold_ms=idle_threshold_ms)
    reviewed = blocks if accept_all else interactive_review(blocks)

    if merge:
        reviewed = merge_adjacent_blocks(reviewed, gap_seconds=merge_gap_seconds)

    if out:
        out_path = out
    else:
        fname = f"reviewed_{date}.json"
        out_path = str(Path(out_dir) / fname) if out_dir else fname

    write_reviewed_json(out_path, reviewed)
    typer.echo(f"wrote {out_path} ({len(reviewed)} accepted block(s))")

    mapping = load_mapping(Path(config) if config else None)
    plan = build_plan(reviewed, project_ids=mapping.project_ids, tag_map=mapping.tag_map)
    print_plan(plan)

    if dry_run:
        typer.echo("dry-run: not creating anything")
        return

    cfg = load_config_from_env()
    ledger_path = Path(ledger_db) if ledger_db else default_db_path()
    created, skipped, _skipped_items = apply_plan(
        plan,
        cfg,
        ledger_db_path=ledger_path,
        force=force,
    )
    typer.echo(f"created {len(created)} time entr(y/ies)")
    if skipped:
        typer.echo(f"skipped {skipped} already-applied entr(y/ies)")


@ledger_app.command("list")
def ledger_list(
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only show entries applied since this UTC date (YYYY-MM-DD)",
    ),
    limit: int = typer.Option(50, "--limit", help="Max rows to show"),  # noqa: B008
    show_fingerprint: bool = typer.Option(
        False,
        "--show-fingerprint",
        help="Include the idempotency fingerprint in output",
    ),  # noqa: B008
) -> None:
    """List applied time entries (local idempotency ledger)."""
    conn = db_mod.connect(db)
    try:
        rows = list_applied(conn, since=since, limit=limit)
    finally:
        conn.close()

    for r in rows:
        te_id = r.toggl_time_entry_id if r.toggl_time_entry_id is not None else "-"
        fp = f" fp={r.fingerprint}" if show_fingerprint else ""
        typer.echo(
            f"{r.ts_utc} | {r.start_ts_utc} → {r.end_ts_utc} | id={te_id} | {r.description}{fp}"
        )


@ledger_app.command("stats")
def ledger_stats_cmd(
    db: Path = typer.Option(default_db_path, "--db", help="SQLite DB path"),  # noqa: B008
    since: str | None = typer.Option(
        None,
        "--since",
        help="Only consider entries applied since this UTC date (YYYY-MM-DD)",
    ),
) -> None:
    """Show summary stats for the local ledger."""
    conn = db_mod.connect(db)
    try:
        s = ledger_stats(conn, since=since)
    finally:
        conn.close()

    typer.echo(f"count: {s.count}")
    typer.echo(f"min_ts_utc: {s.min_ts_utc or '-'}")
    typer.echo(f"max_ts_utc: {s.max_ts_utc or '-'}")
    typer.echo(f"unique_time_entry_ids: {s.unique_time_entry_ids}")


def main() -> None:
    app()
