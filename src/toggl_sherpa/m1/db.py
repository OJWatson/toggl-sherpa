from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 3


def connect(db_path: Path, *, check_same_thread: bool = True) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=check_same_thread)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )

    cur = conn.execute("SELECT value FROM meta WHERE key='schema_version'")
    row = cur.fetchone()
    if row is None:
        version = 0
        conn.execute(
            "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
            ("0",),
        )
        conn.commit()
    else:
        try:
            version = int(row["value"])
        except (TypeError, ValueError):
            version = 0

    # v1: samples
    if version < 1:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                idle_ms INTEGER,
                focus_title TEXT,
                focus_wm_class TEXT,
                focus_pid INTEGER,
                raw_json TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts_utc)")
        version = 1

    # v2: active browser tab events (from Chrome extension)
    if version < 2:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tab_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                sample_id INTEGER,
                url TEXT,
                title TEXT,
                url_redacted TEXT,
                title_redacted TEXT,
                allowed INTEGER NOT NULL DEFAULT 0,
                raw_json TEXT,
                FOREIGN KEY(sample_id) REFERENCES samples(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tab_events_ts ON tab_events(ts_utc)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tab_events_sample_id ON tab_events(sample_id)"
        )
        version = 2

    # v3: applied ledger for idempotent Toggl API writes
    if version < 3:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS applied_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_utc TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                start_ts_utc TEXT NOT NULL,
                end_ts_utc TEXT NOT NULL,
                description TEXT NOT NULL,
                toggl_time_entry_id INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_applied_entries_ts
            ON applied_entries(ts_utc)
            """
        )
        version = 3

    conn.execute(
        "UPDATE meta SET value=? WHERE key='schema_version'",
        (str(version),),
    )
    conn.commit()
