from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import typer

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m3.model import TimesheetBlock
from toggl_sherpa.m5.toggl_api import TogglConfig, create_time_entry
from toggl_sherpa.m6.idempotency import (
    already_applied,
    fingerprint,
    record_applied,
)


@dataclass(frozen=True)
class ApplyPlanItem:
    start: str
    stop: str
    description: str
    tags: list[str]
    project_id: int | None


def _load_blocks(path: Path) -> list[TimesheetBlock]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError("expected a JSON array")

    blocks: list[TimesheetBlock] = []
    for b in obj:
        if not isinstance(b, dict):
            raise ValueError("expected array of objects")
        blocks.append(
            TimesheetBlock(
                start_ts_utc=str(b["start_ts_utc"]),
                end_ts_utc=str(b["end_ts_utc"]),
                seconds=int(b["seconds"]),
                label=str(b["label"]),
                project_suggestion=(b.get("project_suggestion") or None),
                tags_suggestion=list(b.get("tags_suggestion") or []),
                evidence=[],
            )
        )
    return blocks


def build_plan(blocks: list[TimesheetBlock]) -> list[ApplyPlanItem]:
    plan: list[ApplyPlanItem] = []
    for b in blocks:
        tags = list(b.tags_suggestion)
        proj_id = None
        # For M5 we keep mapping optional; embed suggestions in description.
        desc_parts = [b.label]
        if b.project_suggestion:
            desc_parts.append(f"[proj:{b.project_suggestion}]")
        if tags:
            desc_parts.append(f"[tags:{','.join(tags)}]")
        description = " ".join(desc_parts)

        plan.append(
            ApplyPlanItem(
                start=b.start_ts_utc,
                stop=b.end_ts_utc,
                description=description,
                tags=tags,
                project_id=proj_id,
            )
        )
    return plan


def print_plan(plan: list[ApplyPlanItem]) -> None:
    typer.echo(f"plan: {len(plan)} time entr(y/ies)")
    for i, p in enumerate(plan, start=1):
        tag_s = ",".join(p.tags) if p.tags else "-"
        typer.echo(f"{i:>2}. {p.start} → {p.stop} | {tag_s} | {p.description}")


def load_config_from_env() -> TogglConfig:
    tok = os.environ.get("TOGGL_API_TOKEN")
    wid = os.environ.get("TOGGL_WORKSPACE_ID")
    if not tok:
        raise typer.BadParameter("missing TOGGL_API_TOKEN")
    if not wid:
        raise typer.BadParameter("missing TOGGL_WORKSPACE_ID")
    try:
        wid_i = int(wid)
    except ValueError as e:
        raise typer.BadParameter("TOGGL_WORKSPACE_ID must be an int") from e
    return TogglConfig(api_token=tok, workspace_id=wid_i)


def apply_plan(
    plan: list[ApplyPlanItem],
    cfg: TogglConfig,
    *,
    ledger_db_path: Path,
    force: bool = False,
) -> list[dict]:
    """Apply plan to Toggl, with local idempotency ledger.

    If `force` is False, will skip any item already present in the ledger.
    """

    conn = db_mod.connect(ledger_db_path)
    try:
        created: list[dict] = []
        for p in plan:
            fp = fingerprint(start=p.start, stop=p.stop, description=p.description)
            if not force and already_applied(conn, fp):
                continue

            resp = create_time_entry(
                cfg,
                start=p.start,
                stop=p.stop,
                description=p.description,
                tags=p.tags or None,
                project_id=p.project_id,
            )
            created.append(resp)

            te_id = resp.get("id") if isinstance(resp, dict) else None
            record_applied(
                conn,
                fp=fp,
                start=p.start,
                stop=p.stop,
                description=p.description,
                toggl_time_entry_id=(int(te_id) if te_id is not None else None),
            )
    finally:
        conn.close()

    return created
