from __future__ import annotations

import json
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m1.gnome import FocusSample, GnomeShellEvalError, get_focus_sample


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def insert_sample(conn, sample: FocusSample) -> None:
    conn.execute(
        """
        INSERT INTO samples(ts_utc, idle_ms, focus_title, focus_wm_class, focus_pid, raw_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            utc_now_iso(),
            sample.idle_ms,
            sample.title,
            sample.wm_class,
            sample.pid,
            json.dumps(sample.raw, ensure_ascii=False, sort_keys=True),
        ),
    )
    conn.commit()


def run_loop(db_path: Path, interval_s: float = 10.0) -> None:
    conn = db_mod.connect(db_path)

    stopping = False

    def _handle(_sig, _frame):  # noqa: ANN001
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    while not stopping:
        try:
            sample = get_focus_sample()
        except GnomeShellEvalError as e:
            # Still log something so we can debug later.
            sample = FocusSample(
                idle_ms=None,
                title=None,
                wm_class=None,
                pid=None,
                raw={"error": str(e)},
            )

        insert_sample(conn, sample)
        time.sleep(interval_s)


def _main(argv: list[str]) -> int:
    # Minimal internal entrypoint for the detached process.
    # Usage: python -m toggl_sherpa.m1.logger <db_path> <interval_s>
    if len(argv) < 2:
        raise SystemExit("usage: python -m toggl_sherpa.m1.logger <db_path> [interval_s]")
    db_path = Path(argv[1])
    interval_s = float(argv[2]) if len(argv) >= 3 else 10.0

    # Ensure we don't die on SIGHUP in detached mode.
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    run_loop(db_path=db_path, interval_s=interval_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
