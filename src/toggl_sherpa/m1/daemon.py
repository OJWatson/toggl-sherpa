from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from toggl_sherpa.m1.paths import pidfile_path


class AlreadyRunningError(RuntimeError):
    pass


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def read_pid(pidfile: Path | None = None) -> int | None:
    pidfile = pidfile or pidfile_path()
    try:
        pid_s = pidfile.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if not pid_s:
        return None
    try:
        return int(pid_s)
    except ValueError:
        return None


def status(pidfile: Path | None = None) -> tuple[bool, int | None]:
    pid = read_pid(pidfile)
    if pid is None:
        return (False, None)
    return (_pid_is_running(pid), pid)


def start_logger(db_path: str, interval_s: float = 10.0, pidfile: Path | None = None) -> int:
    pidfile = pidfile or pidfile_path()
    pidfile.parent.mkdir(parents=True, exist_ok=True)

    running, pid = status(pidfile)
    if running:
        raise AlreadyRunningError(f"logger already running (pid {pid})")

    proc = subprocess.Popen(
        [sys.executable, "-m", "toggl_sherpa.m1.logger", db_path, str(interval_s)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
    )
    pidfile.write_text(str(proc.pid), encoding="utf-8")
    return proc.pid


def stop_logger(pidfile: Path | None = None, timeout_s: float = 3.0) -> bool:
    pidfile = pidfile or pidfile_path()
    pid = read_pid(pidfile)
    if pid is None:
        return False

    if not _pid_is_running(pid):
        try:
            pidfile.unlink(missing_ok=True)
        except TypeError:  # py<3.8 compat; not relevant but safe
            if pidfile.exists():
                pidfile.unlink()
        return False

    os.kill(pid, signal.SIGTERM)

    # Wait briefly.
    import time

    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if not _pid_is_running(pid):
            break
        time.sleep(0.1)

    if _pid_is_running(pid):
        os.kill(pid, signal.SIGKILL)

    try:
        pidfile.unlink(missing_ok=True)
    except TypeError:
        if pidfile.exists():
            pidfile.unlink()
    return True
