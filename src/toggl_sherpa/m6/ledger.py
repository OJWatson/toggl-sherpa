from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


def _since_ts_utc(date_yyyy_mm_dd: str) -> str:
    d = datetime.fromisoformat(date_yyyy_mm_dd).date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC).isoformat()


@dataclass(frozen=True)
class LedgerRow:
    ts_utc: str
    start_ts_utc: str
    end_ts_utc: str
    description: str
    toggl_time_entry_id: int | None


def list_applied(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    limit: int = 50,
) -> list[LedgerRow]:
    if limit <= 0:
        return []

    if since:
        since_ts = _since_ts_utc(since)
        cur = conn.execute(
            """
            SELECT ts_utc, start_ts_utc, end_ts_utc, description, toggl_time_entry_id
            FROM applied_entries
            WHERE ts_utc >= ?
            ORDER BY ts_utc DESC
            LIMIT ?
            """,
            (since_ts, limit),
        )
    else:
        cur = conn.execute(
            """
            SELECT ts_utc, start_ts_utc, end_ts_utc, description, toggl_time_entry_id
            FROM applied_entries
            ORDER BY ts_utc DESC
            LIMIT ?
            """,
            (limit,),
        )

    out: list[LedgerRow] = []
    for r in cur.fetchall():
        out.append(
            LedgerRow(
                ts_utc=str(r["ts_utc"]),
                start_ts_utc=str(r["start_ts_utc"]),
                end_ts_utc=str(r["end_ts_utc"]),
                description=str(r["description"]),
                toggl_time_entry_id=(
                    int(r["toggl_time_entry_id"]) if r["toggl_time_entry_id"] is not None else None
                ),
            )
        )
    return out


@dataclass(frozen=True)
class LedgerStats:
    count: int
    min_ts_utc: str | None
    max_ts_utc: str | None
    unique_time_entry_ids: int


def stats(conn: sqlite3.Connection, *, since: str | None = None) -> LedgerStats:
    where = ""
    args: tuple = ()
    if since:
        where = "WHERE ts_utc >= ?"
        args = (_since_ts_utc(since),)

    row = conn.execute(
        f"""
        SELECT
            COUNT(*) AS n,
            MIN(ts_utc) AS min_ts,
            MAX(ts_utc) AS max_ts,
            COUNT(DISTINCT toggl_time_entry_id) AS uniq_ids
        FROM applied_entries
        {where}
        """,
        args,
    ).fetchone()

    assert row is not None
    return LedgerStats(
        count=int(row["n"]),
        min_ts_utc=(str(row["min_ts"]) if row["min_ts"] is not None else None),
        max_ts_utc=(str(row["max_ts"]) if row["max_ts"] is not None else None),
        unique_time_entry_ids=int(row["uniq_ids"]),
    )
