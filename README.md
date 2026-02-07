# toggl-sherpa

Local activity logger + draft timesheet + approval gate for pushing entries to Toggl Track.

## Milestone 1 (M1): GNOME focus + idle logger

Commands:

```bash
# One-shot sample to SQLite (good for testing)
uv run toggl-sherpa log once

# Background logger (writes a pidfile under XDG_CACHE_HOME)
uv run toggl-sherpa log start --interval 10
uv run toggl-sherpa log status
uv run toggl-sherpa log stop
```

Data is stored in SQLite under `XDG_DATA_HOME/toggl-sherpa/toggl-sherpa.sqlite3` by default.

## Dev

```bash
uv sync --group dev
uv run ruff check .
uv run python -m pytest -q
```
