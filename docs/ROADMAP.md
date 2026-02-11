# Roadmap

This roadmap is a lightweight plan for the project. Milestones are small and should remain independently testable.

## Principles

- Default to local-first workflows.
- Any action that creates remote time entries must be explicitly approved (dry-run by default, require `--yes`).
- Prefer small, CI-backed slices.

## Milestones (high level)

### M1 — Local activity logger
**Goal:** Collect focus/idle samples into SQLite.

**DoD:**
- CLI can log once and run as a background process.
- SQLite schema migrated automatically.
- Tests + CI green.

### M2 — Browser evidence ingest
**Goal:** Ingest active-tab events locally with redaction outside an allowlist.

**DoD:**
- Local HTTP ingest server + extension posting.
- Redaction rules + tests.
- CI green.

### M3 — Draft timesheet + evidence report
**Goal:** Summarise samples into draft blocks with attached evidence.

**DoD:**
- `report draft-timesheet` produces Markdown/JSON.
- Rule-based project/tag suggestions.
- Tests + CI green.

### M4 — Interactive review
**Goal:** Review/edit/accept blocks and write reviewed JSON.

**DoD:**
- `report review` writes accepted blocks.
- Test coverage for the review flow.
- CI green.

### M5 — Apply to Toggl (approval gate)
**Goal:** Create time entries via API only with explicit approval.

**DoD:**
- `apply` dry-runs by default; refuses without `--yes`.
- Mocked-HTTP happy-path test.
- CI green.

### M6 — Idempotency + mapping + audit
**Goal:** Make apply safe to re-run; support mapping suggestions to ids; audit applied entries.

**DoD:**
- Local applied ledger prevents duplicates by default.
- Optional mapping config for project ids + tag normalisation.
- Ledger list/stats commands.
- CI green.

### M7+ — Small usability improvements
Examples:
- Convenience workflow command(s) to reduce manual steps.
- Extra audit/debug helpers.

## Backlog ideas

- Pull project lists to help populate mapping config.
- Optional export formats (CSV/JSON variants).
- Stronger block-merging heuristics and labeling.
