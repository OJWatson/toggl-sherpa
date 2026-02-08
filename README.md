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

## Milestone 2 (M2): Chrome active-tab evidence (extension + localhost)

1) Start the ingest server:

```bash
# Allow storing full URL+title only for these domains; everything else is redacted.
export TOGGL_SHERPA_TAB_ALLOWLIST="github.com,docs.python.org"
uv run toggl-sherpa web tab-server --port 5055
```

2) Load the extension (Chrome): `chrome://extensions` → enable *Developer mode* → *Load unpacked* → select `./extension/`.

The extension will POST the active tab URL/title to `http://127.0.0.1:5055/v1/active_tab` periodically and on tab/window changes.

## Milestone 3 (M3): Draft timesheet + evidence + suggestions

Generate a draft report for a UTC day:

```bash
uv run toggl-sherpa report draft-timesheet --date 2026-02-08
# or JSON:
uv run toggl-sherpa report draft-timesheet --date 2026-02-08 --format json
```

Interactive review (writes reviewed blocks to JSON):

```bash
uv run toggl-sherpa report review --date 2026-02-08 --out reviewed_timesheet.json
```

## Dev

```bash
uv sync --group dev
uv run ruff check .
uv run python -m pytest -q
```
