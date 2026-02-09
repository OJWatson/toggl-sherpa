# toggl-sherpa

Local activity logger + draft timesheet + approval gate for pushing entries to Toggl Track.

## Quick start

```bash
# 1) (Optional) start background logger (GNOME)
uv run toggl-sherpa log start --interval 10

# 2) Generate a one-day plan (dry-run by default)
uv run toggl-sherpa day --date 2026-02-09 --accept-all

# 3) Inspect local idempotency ledger
uv run toggl-sherpa ledger stats

# 4) Interactive review with tidy artifacts
uv run toggl-sherpa report review --date 2026-02-09 --out reviewed_timesheet.json --out-dir ./artifacts

# To actually create entries in Toggl Track, you must pass --yes and set env:
export TOGGL_API_TOKEN=...            # Toggl Track API token
export TOGGL_WORKSPACE_ID=123456      # workspace id
uv run toggl-sherpa apply --reviewed reviewed_timesheet.json --yes

# Debug helper:
uv run toggl-sherpa config show

# Notes:
# - TOGGL_API_TOKEN: Toggl Track web app → Profile settings → API token
# - TOGGL_WORKSPACE_ID: the numeric workspace id (often visible in Toggl URLs),
#   or fetch it via the API once you have a token.
# - To discover workspace/project ids via the API:
#   uv run toggl-sherpa toggl workspaces
#   uv run toggl-sherpa toggl projects --workspace-id <id>
#   uv run toggl-sherpa toggl tags --workspace-id <id>
```

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

Interactive review (writes approved blocks to JSON):

```bash
uv run toggl-sherpa report review --date 2026-02-08 --out reviewed_timesheet.json

# Keep artifacts tidy
uv run toggl-sherpa report review --date 2026-02-08 --out reviewed_timesheet.json --out-dir ./artifacts
```

Merge adjacent approved blocks (optional but recommended):

```bash
uv run toggl-sherpa report merge --in reviewed_timesheet.json --out merged_timesheet.json
```

Apply (generate a Toggl Track CSV import file):

```bash
uv run toggl-sherpa report apply --in merged_timesheet.json --out toggl_import.csv
```

## Milestone 5 (M5): Apply to Toggl Track (explicit approval gate)

### Milestone 8 (M8): One-shot day workflow

```bash
# Draft -> review -> plan (dry-run by default)
uv run toggl-sherpa day --date 2026-02-09

# Non-interactive (accept all blocks)
# If you omit --out, it writes reviewed_YYYY-MM-DD.json in the current directory.
uv run toggl-sherpa day --date 2026-02-09 --accept-all

# Custom reviewed JSON path
uv run toggl-sherpa day --date 2026-02-09 --accept-all --out reviewed_timesheet.json

# Drop very idle samples earlier/later
uv run toggl-sherpa day --date 2026-02-09 --idle-threshold-ms 120000

# Merge adjacent identical blocks before writing/applying
uv run toggl-sherpa day --date 2026-02-09 --merge --merge-gap-seconds 60

# Keep artifacts tidy (write default reviewed_YYYY-MM-DD.json under a directory)
uv run toggl-sherpa day --date 2026-02-09 --accept-all --out-dir ./artifacts

# Actually create entries (explicit approval gate)
export TOGGL_API_TOKEN=...            # your API token
export TOGGL_WORKSPACE_ID=123456
uv run toggl-sherpa day --date 2026-02-09 --accept-all --yes
```

### Idempotency ledger (what it is)

When you run `toggl-sherpa apply --yes`, toggl-sherpa writes a local *applied ledger* into the same SQLite DB.
This is used to make `apply` **idempotent** by default: re-running `apply` with the same reviewed blocks will skip entries that were already created.

Audit commands:

```bash
# List recently applied entries (most recent first)
uv run toggl-sherpa ledger list --limit 20

# Include fingerprints (useful for debugging idempotency)
uv run toggl-sherpa ledger list --limit 20 --show-fingerprint

# List entries applied since a UTC date
uv run toggl-sherpa ledger list --since 2026-02-09 --limit 200

# Summary stats
uv run toggl-sherpa ledger stats
uv run toggl-sherpa ledger stats --since 2026-02-09
```

```bash
# Dry run (default)
uv run toggl-sherpa apply --reviewed reviewed_timesheet.json

# Actually create entries in Toggl Track
export TOGGL_API_TOKEN=...            # your API token
export TOGGL_WORKSPACE_ID=123456
uv run toggl-sherpa apply --reviewed reviewed_timesheet.json --yes

# Optional mapping config (project_suggestion -> project_id; tag normalisation):
# ~/.config/toggl-sherpa/config.json
# {
#   "project_ids": {
#     "dev": 12345,
#     "admin": 67890
#   },
#   "tag_map": {
#     "Code": "code",
#     "Docs": "docs"
#   }
# }
#
# How to find ids:
#   uv run toggl-sherpa toggl workspaces
#   uv run toggl-sherpa toggl projects --workspace-id <id>
#   uv run toggl-sherpa toggl tags --workspace-id <id>
#
# Or pass explicitly:
#   uv run toggl-sherpa apply --reviewed reviewed_timesheet.json --yes --config /path/to/config.json
```

## Dev

```bash
uv sync --group dev
uv run ruff check .
uv run python -m pytest -q
```
