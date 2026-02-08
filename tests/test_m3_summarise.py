from __future__ import annotations

from pathlib import Path

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m2.tab_ingest import TabPayload, insert_tab_event
from toggl_sherpa.m3.query import fetch_samples, fetch_tab_events
from toggl_sherpa.m3.summarise import summarise_blocks


def test_summarise_splits_on_label_and_ignores_idle(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = db_mod.connect(db_path)

    # Three active samples (two in same "activity"), one idle.
    rows = [
        ("2026-02-08T12:00:00+00:00", 0, "X", "code", 1),
        ("2026-02-08T12:00:30+00:00", 0, "X", "code", 1),
        ("2026-02-08T12:01:00+00:00", 120_000, "idle", "code", 1),
        ("2026-02-08T12:02:00+00:00", 0, "Y", "code", 1),
    ]
    for ts, idle, title, wm, pid in rows:
        conn.execute(
            """
            INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
            VALUES (?, ?, ?, ?, ?, '{}')
            """,
            (ts, idle, title, wm, pid),
        )
    conn.commit()

    # Attach an allowlisted tab event to the last sample to force label change.
    allow = {"github.com"}
    _ = insert_tab_event(
        conn,
        TabPayload(
            url="https://github.com/OJWatson/toggl-sherpa",
            title="Repo",
            ts_utc="2026-02-08T12:02:00+00:00",
        ),
        allow,
    )

    samples = fetch_samples(conn, "2026-02-08T00:00:00+00:00", "2026-02-08T23:59:59+00:00")
    tabs = fetch_tab_events(conn, "2026-02-08T00:00:00+00:00", "2026-02-08T23:59:59+00:00")

    blocks = summarise_blocks(samples, tabs, idle_threshold_ms=60_000, min_block_s=10)
    assert len(blocks) == 2

    assert blocks[0].label.startswith("code:")
    assert blocks[0].seconds >= 30

    assert blocks[1].label == "browser:github.com"
    assert blocks[1].project_suggestion == "dev"
    assert "github" in blocks[1].tags_suggestion
