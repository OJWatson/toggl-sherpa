from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli
from toggl_sherpa.m1 import db as db_mod


def _seed_samples(db_path: Path) -> None:
    conn = db_mod.connect(db_path)
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-09T12:00:00+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-09T12:01:10+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.commit()
    conn.close()


def test_day_dry_run_accept_all_writes_reviewed(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    out_path = tmp_path / "reviewed.json"
    _seed_samples(db_path)

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        [
            "day",
            "--date",
            "2026-02-09",
            "--db",
            str(db_path),
            "--out",
            str(out_path),
            "--accept-all",
        ],
    )

    assert res.exit_code == 0
    assert out_path.exists()
    assert "dry-run" in res.stdout


def test_day_yes_posts_with_mock(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setenv("TOGGL_API_TOKEN", "t")
    monkeypatch.setenv("TOGGL_WORKSPACE_ID", "1")

    db_path = tmp_path / "test.sqlite"
    out_path = tmp_path / "reviewed.json"
    _seed_samples(db_path)

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
    res = runner.invoke(
        get_command(cli.app),
        [
            "day",
            "--date",
            "2026-02-09",
            "--db",
            str(db_path),
            "--out",
            str(out_path),
            "--accept-all",
            "--yes",
        ],
    )

    assert res.exit_code == 0
    assert len(calls) == 1
    assert out_path.exists()
    assert "created 1" in res.stdout
