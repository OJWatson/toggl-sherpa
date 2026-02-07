from __future__ import annotations

from pathlib import Path

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m2.redaction import parse_allowlist, redact_tab
from toggl_sherpa.m2.tab_ingest import TabPayload, insert_tab_event


def test_parse_allowlist() -> None:
    assert parse_allowlist("") == set()
    assert parse_allowlist(None) == set()
    assert parse_allowlist("Example.com, foo.bar ") == {"example.com", "foo.bar"}


def test_redaction_allowlisted() -> None:
    allow = {"example.com"}
    red = redact_tab("https://example.com/path?q=1", "Hello", allow)
    assert red.allowed is True
    assert red.url == "https://example.com/path?q=1"
    assert red.title == "Hello"


def test_redaction_not_allowlisted() -> None:
    allow = {"example.com"}
    red = redact_tab("https://secret.com/a/b", "Top secret", allow)
    assert red.allowed is False
    assert red.url is None
    assert red.title is None
    assert red.url_redacted == "https://secret.com/…"
    assert red.title_redacted == "[REDACTED]"


def test_insert_tab_event_links_to_nearest_sample(tmp_path: Path) -> None:
    db_path = tmp_path / "test.sqlite"
    conn = db_mod.connect(db_path)

    # Insert a sample at a known timestamp.
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES (?, NULL, NULL, NULL, NULL, '{}')
        """,
        ("2026-02-07T12:00:00+00:00",),
    )
    sample_id = conn.execute("SELECT id FROM samples").fetchone()["id"]

    allow = {"example.com"}
    _ = insert_tab_event(
        conn,
        TabPayload(
            url="https://example.com/alpha",
            title="Alpha",
            ts_utc="2026-02-07T12:00:10+00:00",
        ),
        allow,
        max_link_age_s=60,
    )

    row = conn.execute("SELECT sample_id, allowed, url, title FROM tab_events").fetchone()
    assert row["sample_id"] == sample_id
    assert row["allowed"] == 1
    assert row["url"] == "https://example.com/alpha"
    assert row["title"] == "Alpha"
