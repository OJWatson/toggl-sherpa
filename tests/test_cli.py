from __future__ import annotations

from click.testing import CliRunner
from typer.main import get_command

from toggl_sherpa.cli import app


def test_doctor() -> None:
    runner = CliRunner()
    res = runner.invoke(get_command(app), ["doctor"])
    assert res.exit_code == 0
    assert "ok" in res.stdout
