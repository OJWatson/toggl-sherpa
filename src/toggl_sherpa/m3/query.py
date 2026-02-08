from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime

from toggl_sherpa.m3.model import SampleRow, TabEventRow


def parse_ts(ts: str) -> datetime:
    # Stored as ISO 8601 with timezone.
    return datetime.fromisoformat(ts)


def seconds_between(start_ts: str, end_ts: str) -> int:
    a = parse_ts(start_ts)
    b = parse_ts(end_ts)
    return int((b - a).total_seconds())


def day_bounds_utc(date_yyyy_mm_dd: str) -> tuple[str, str]:
    d = datetime.fromisoformat(date_yyyy_mm_dd).date()
    start = datetime(d.year, d.month, d.day, tzinfo=UTC)
    end = start.replace(hour=23, minute=59, second=59)
    return start.isoformat(), end.isoformat()


def fetch_samples(conn: sqlite3.Connection, start_ts_utc: str, end_ts_utc: str) -> list[SampleRow]:
    cur = conn.execute(
        """
        SELECT id, ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid
        FROM samples
        WHERE ts_utc >= ? AND ts_utc <= ?
        ORDER BY ts_utc ASC
        """,
        (start_ts_utc, end_ts_utc),
    )
    out: list[SampleRow] = []
    for r in cur.fetchall():
        out.append(
            SampleRow(
                id=int(r["id"]),
                ts_utc=str(r["ts_utc"]),
                idle_ms=r["idle_ms"],
                focus_title=r["focus_title"],
                focus_wm_class=r["focus_wm_class"],
                focus_pid=r["focus_pid"],
            )
        )
    return out


def fetch_tab_events(
    conn: sqlite3.Connection,
    start_ts_utc: str,
    end_ts_utc: str,
) -> list[TabEventRow]:
    cur = conn.execute(
        """
        SELECT id, ts_utc, sample_id, allowed, url, title, url_redacted, title_redacted
        FROM tab_events
        WHERE ts_utc >= ? AND ts_utc <= ?
        ORDER BY ts_utc ASC
        """,
        (start_ts_utc, end_ts_utc),
    )
    out: list[TabEventRow] = []
    for r in cur.fetchall():
        out.append(
            TabEventRow(
                id=int(r["id"]),
                ts_utc=str(r["ts_utc"]),
                sample_id=(int(r["sample_id"]) if r["sample_id"] is not None else None),
                allowed=bool(r["allowed"]),
                url=r["url"],
                title=r["title"],
                url_redacted=r["url_redacted"],
                title_redacted=r["title_redacted"],
            )
        )
    return out


def to_jsonable(obj):
    # Small helper for CLI output.
    if hasattr(obj, "__dataclass_fields__"):
        d = asdict(obj)
        # Preserve ordering for nicer diffs.
        return {k: to_jsonable(v) for k, v in d.items()}
    if isinstance(obj, list):
        return [to_jsonable(x) for x in obj]
    return obj
