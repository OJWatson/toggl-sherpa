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
from toggl_sherpa.m4.review import interactive_review, write_reviewed_json

app = typer.Typer(add_completion=False, no_args_is_help=True)
log_app = typer.Typer(add_completion=False, no_args_is_help=True)
web_app = typer.Typer(add_completion=False, no_args_is_help=True)
report_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(log_app, name="log")
app.add_typer(web_app, name="web")
app.add_typer(report_app, name="report")


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
        help="Where to write reviewed blocks JSON",
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
    write_reviewed_json(out, reviewed)
    typer.echo(f"wrote {out} ({len(reviewed)} accepted block(s))")


def main() -> None:
    app()
