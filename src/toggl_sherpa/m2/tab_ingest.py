from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from toggl_sherpa.m2.redaction import RedactedTab, redact_tab


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class TabPayload:
    url: str | None
    title: str | None
    ts_utc: str | None = None
    user_agent: str | None = None


def _nearest_sample_id(conn: sqlite3.Connection, ts_utc: str, max_age_s: int = 60) -> int | None:
    # Compare via Unix seconds; SQLite can parse ISO 8601.
    cur = conn.execute(
        """
        SELECT id
        FROM samples
        WHERE ABS(strftime('%s', ts_utc) - strftime('%s', ?)) <= ?
        ORDER BY ABS(strftime('%s', ts_utc) - strftime('%s', ?)) ASC
        LIMIT 1
        """,
        (ts_utc, max_age_s, ts_utc),
    )
    row = cur.fetchone()
    return int(row["id"]) if row is not None else None


def insert_tab_event(
    conn: sqlite3.Connection,
    payload: TabPayload,
    allow_hosts: set[str],
    *,
    max_link_age_s: int = 60,
) -> RedactedTab:
    ts_utc = payload.ts_utc or utc_now_iso()
    red: RedactedTab = redact_tab(payload.url, payload.title, allow_hosts)
    sample_id = _nearest_sample_id(conn, ts_utc, max_age_s=max_link_age_s)

    raw = {
        "url": payload.url,
        "title": payload.title,
        "ts_utc": payload.ts_utc,
        "user_agent": payload.user_agent,
    }

    conn.execute(
        """
        INSERT INTO tab_events(
            ts_utc, sample_id, url, title, url_redacted, title_redacted, allowed, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts_utc,
            sample_id,
            red.url,
            red.title,
            red.url_redacted,
            red.title_redacted,
            1 if red.allowed else 0,
            json.dumps(raw, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()
    return red
