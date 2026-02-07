from __future__ import annotations

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli


def test_doctor_ok(monkeypatch) -> None:
    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/gdbus")
    monkeypatch.setattr(cli, "get_focus_sample", lambda: object())

    runner = CliRunner()
    res = runner.invoke(get_command(cli.app), ["doctor"])
    assert res.exit_code == 0
    assert "ok" in res.stdout
