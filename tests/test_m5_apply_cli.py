from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli


def test_apply_refuses_without_yes(tmp_path: Path) -> None:
    reviewed = tmp_path / "reviewed.json"
    reviewed.write_text(
        json.dumps(
            [
                {
                    "start_ts_utc": "2026-02-08T12:00:00+00:00",
                    "end_ts_utc": "2026-02-08T12:10:00+00:00",
                    "seconds": 600,
                    "label": "code:X",
                    "project_suggestion": "dev",
                    "tags_suggestion": ["code"],
                    "evidence": [],
                }
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        [
            "apply",
            "--reviewed",
            str(reviewed),
            "--no-dry-run",
        ],
    )
    assert res.exit_code == 2
    assert "refusing" in res.stdout


def test_apply_yes_posts_with_mock(monkeypatch, tmp_path: Path) -> None:
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

    monkeypatch.setenv("TOGGL_API_TOKEN", "t")
    monkeypatch.setenv("TOGGL_WORKSPACE_ID", "1")

    calls: list[dict] = []

    class Resp:
        status_code = 200

        def json(self):
            return {"id": 123}

        text = "ok"

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        return Resp()

    import toggl_sherpa.m5.toggl_api as api

    monkeypatch.setattr(api.requests, "post", fake_post)

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        [
            "apply",
            "--reviewed",
            str(reviewed),
            "--yes",
        ],
    )

    assert res.exit_code == 0
    assert len(calls) == 1
    assert "/workspaces/1/time_entries" in calls[0]["url"]
    assert calls[0]["json"]["description"].startswith("code:X")
