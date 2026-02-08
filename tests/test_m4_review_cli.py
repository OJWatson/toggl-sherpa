from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli
from toggl_sherpa.m1 import db as db_mod


def test_report_review_accepts_and_writes_json(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    out_path = tmp_path / "out.json"
    conn = db_mod.connect(db_path)

    # Insert two samples 10s apart.
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-08T12:00:00+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-08T12:00:10+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.commit()
    conn.close()

    runner = CliRunner()
    # One block -> one prompt. Accept.
    res = runner.invoke(
        get_command(cli.app),
        [
            "report",
            "review",
            "--date",
            "2026-02-08",
            "--db",
            str(db_path),
            "--out",
            str(out_path),
        ],
        input="a\n",
    )

    assert res.exit_code == 0
    assert out_path.exists()
    assert "accepted" in res.stdout
