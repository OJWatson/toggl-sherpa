from __future__ import annotations

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli


def test_toggl_clients_requires_token(monkeypatch) -> None:
    monkeypatch.delenv("TOGGL_API_TOKEN", raising=False)
    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        ["toggl", "clients", "--workspace-id", "1"],
    )
    assert res.exit_code == 2
    assert "missing TOGGL_API_TOKEN" in res.stdout


def test_toggl_clients_lists(monkeypatch) -> None:
    monkeypatch.setenv("TOGGL_API_TOKEN", "t")

    import toggl_sherpa.m5.toggl_api as api

    class Resp:
        status_code = 200
        text = "ok"

        def json(self):
            return [{"id": 3, "name": "Client"}]

    monkeypatch.setattr(api.requests, "get", lambda *a, **k: Resp())

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        ["toggl", "clients", "--workspace-id", "1"],
    )
    assert res.exit_code == 0
    assert "3\tClient" in res.stdout
