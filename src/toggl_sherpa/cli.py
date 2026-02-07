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

app = typer.Typer(add_completion=False, no_args_is_help=True)
log_app = typer.Typer(add_completion=False, no_args_is_help=True)
web_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(log_app, name="log")
app.add_typer(web_app, name="web")


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


def main() -> None:
    app()
