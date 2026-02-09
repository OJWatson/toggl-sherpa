from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli


def test_apply_is_idempotent_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("TOGGL_API_TOKEN", "t")
    monkeypatch.setenv("TOGGL_WORKSPACE_ID", "1")

    reviewed = tmp_path / "reviewed.json"
    reviewed.write_text(
        json.dumps(
            [
                {
                    "start_ts_utc": "2026-02-08T12:00:00+00:00",
                    "end_ts_utc": "2026-02-08T12:10:00+00:00",
                    "seconds": 600,
                    "label": "code:X",
                    "project_suggestion": None,
                    "tags_suggestion": ["code"],
                    "evidence": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    calls: list[dict] = []

    class Resp:
        status_code = 200

        def json(self):
            return {"id": 123}

        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json})
        return Resp()

    import toggl_sherpa.m5.toggl_api as api

    monkeypatch.setattr(api.requests, "post", fake_post)

    runner = CliRunner()
    res1 = runner.invoke(
        get_command(cli.app),
        ["apply", "--reviewed", str(reviewed), "--yes"],
    )
    assert res1.exit_code == 0

    res2 = runner.invoke(
        get_command(cli.app),
        ["apply", "--reviewed", str(reviewed), "--yes"],
    )
    assert res2.exit_code == 0

    # second run should not POST again
    assert len(calls) == 1
    assert "skipped 1" in res2.stdout
