from __future__ import annotations

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli


def test_config_show_reports_env_missing(monkeypatch) -> None:
    monkeypatch.delenv("TOGGL_API_TOKEN", raising=False)
    monkeypatch.delenv("TOGGL_WORKSPACE_ID", raising=False)

    runner = CliRunner()
    res = runner.invoke(get_command(cli.app), ["config", "show"])
    assert res.exit_code == 0
    assert "TOGGL_API_TOKEN: missing" in res.stdout
    assert "TOGGL_WORKSPACE_ID: missing" in res.stdout
    assert "hint: set TOGGL_API_TOKEN" in res.stdout
    assert "hint: set TOGGL_WORKSPACE_ID" in res.stdout
