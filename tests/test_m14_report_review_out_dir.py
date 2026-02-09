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


def test_report_review_out_dir(monkeypatch, tmp_path: Path) -> None:
    # Avoid prompting by stubbing interactive_review.
    monkeypatch.setattr(cli, "interactive_review", lambda blocks: blocks)

    db_path = tmp_path / "test.sqlite"
    _seed_samples(db_path)

    runner = CliRunner()
    with runner.isolated_filesystem():
        out_dir = Path("out")
        out_dir.mkdir()
        res = runner.invoke(
            get_command(cli.app),
            [
                "report",
                "review",
                "--date",
                "2026-02-09",
                "--db",
                str(db_path),
                "--out",
                "reviewed.json",
                "--out-dir",
                str(out_dir),
            ],
        )

        assert res.exit_code == 0
        assert (out_dir / "reviewed.json").exists()
        assert "wrote out/reviewed.json" in res.stdout
