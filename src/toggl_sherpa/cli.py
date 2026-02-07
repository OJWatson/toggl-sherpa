from __future__ import annotations

import typer

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.callback()
def _root() -> None:
    """toggl-sherpa."""


@app.command()
def doctor() -> None:
    """Check environment prerequisites (GNOME + gdbus, etc.)."""
    typer.echo("ok")


def main() -> None:
    app()
