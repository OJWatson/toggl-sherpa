from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def fingerprint(*, start: str, stop: str, description: str) -> str:
    """Deterministic idempotency key for a time entry."""
    payload = {"start": start, "stop": stop, "description": description}
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode()).hexdigest()


def already_applied(conn: sqlite3.Connection, fp: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM applied_entries WHERE fingerprint=? LIMIT 1",
        (fp,),
    ).fetchone()
    return row is not None


def record_applied(
    conn: sqlite3.Connection,
    *,
    fp: str,
    start: str,
    stop: str,
    description: str,
    toggl_time_entry_id: int | None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO applied_entries(
            ts_utc, fingerprint, start_ts_utc, end_ts_utc, description, toggl_time_entry_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (utc_now_iso(), fp, start, stop, description, toggl_time_entry_id),
    )
    conn.commit()
