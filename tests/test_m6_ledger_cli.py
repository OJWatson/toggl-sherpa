from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from typer.main import get_command

import toggl_sherpa.cli as cli
from toggl_sherpa.m1 import db as db_mod


def _seed_ledger(db_path: Path) -> None:
    conn = db_mod.connect(db_path)
    conn.execute(
        """
        INSERT INTO applied_entries(
            ts_utc, fingerprint, start_ts_utc, end_ts_utc, description, toggl_time_entry_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-02-09T00:00:00+00:00",
            "fp1",
            "2026-02-08T12:00:00+00:00",
            "2026-02-08T12:10:00+00:00",
            "A",
            101,
        ),
    )
    conn.execute(
        """
        INSERT INTO applied_entries(
            ts_utc, fingerprint, start_ts_utc, end_ts_utc, description, toggl_time_entry_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-02-08T00:00:00+00:00",
            "fp2",
            "2026-02-07T12:00:00+00:00",
            "2026-02-07T12:10:00+00:00",
            "B",
            102,
        ),
    )
    conn.commit()
    conn.close()


def test_ledger_list_limit_and_since(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    _seed_ledger(db_path)

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        ["ledger", "list", "--db", str(db_path), "--since", "2026-02-09", "--limit", "10"],
    )
    assert res.exit_code == 0
    assert "| id=101 | A" in res.stdout
    assert "| id=102 | B" not in res.stdout


def test_ledger_list_show_fingerprint(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    _seed_ledger(db_path)

    runner = CliRunner()
    res = runner.invoke(
        get_command(cli.app),
        ["ledger", "list", "--db", str(db_path), "--limit", "1", "--show-fingerprint"],
    )
    assert res.exit_code == 0
    assert "fp=" in res.stdout


def test_ledger_stats_smoke(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    _seed_ledger(db_path)

    runner = CliRunner()
    res = runner.invoke(get_command(cli.app), ["ledger", "stats", "--db", str(db_path)])
    assert res.exit_code == 0
    assert "count: 2" in res.stdout
    assert "unique_time_entry_ids: 2" in res.stdout
