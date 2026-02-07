from __future__ import annotations

import os
from pathlib import Path


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def xdg_cache_home() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))


def default_db_path() -> Path:
    return xdg_data_home() / "toggl-sherpa" / "toggl-sherpa.sqlite3"


def pidfile_path() -> Path:
    return xdg_cache_home() / "toggl-sherpa" / "logger.pid"
