from __future__ import annotations

import csv
from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli
from toggl_sherpa.m1 import db as db_mod


def test_m4_happy_path_review_merge_apply(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    reviewed_path = tmp_path / "reviewed.json"
    merged_path = tmp_path / "merged.json"
    csv_path = tmp_path / "import.csv"

    conn = db_mod.connect(db_path)

    # Two blocks: X (12:00-12:00:10) then X again (12:00:10-12:00:20)
    # summariser should yield two adjacent blocks with same label, allowing merge.
    # Ensure blocks are >= 60s (summariser min_block_s).
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-08T12:00:00+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-08T12:01:00+00:00', 0, 'X', 'code', 1, '{}')
        """
    )
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES ('2026-02-08T12:02:00+00:00', 0, 'X', 'code', 1, '{}')
        """
    )

    conn.commit()
    conn.close()

    runner = CliRunner()

    # Review: accept all prompts.
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
            str(reviewed_path),
        ],
        input="a\n",
    )
    assert res.exit_code == 0
    assert reviewed_path.exists()

    # Merge -> should reduce block count (or keep same if summariser behaviour changes)
    res = runner.invoke(
        get_command(cli.app),
        ["report", "merge", "--in", str(reviewed_path), "--out", str(merged_path)],
    )
    assert res.exit_code == 0
    assert merged_path.exists()

    # Apply -> write CSV import
    res = runner.invoke(
        get_command(cli.app),
        ["report", "apply", "--in", str(merged_path), "--out", str(csv_path)],
    )
    assert res.exit_code == 0
    assert csv_path.exists()

    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
    assert len(rows) >= 1
    assert set(rows[0].keys()) == {
        "Description",
        "Project",
        "Tags",
        "Start date",
        "Start time",
        "Duration",
    }
