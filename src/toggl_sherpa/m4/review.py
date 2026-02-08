from __future__ import annotations

import json
from dataclasses import replace

import typer

from toggl_sherpa.m3.model import TimesheetBlock
from toggl_sherpa.m3.query import to_jsonable


def _fmt_block(b: TimesheetBlock, i: int, n: int) -> str:
    mins = round(b.seconds / 60)
    proj = b.project_suggestion or "(unsuggested)"
    tags = ", ".join(b.tags_suggestion) if b.tags_suggestion else "(none)"
    return (
        f"[{i}/{n}] {b.start_ts_utc} → {b.end_ts_utc} ({mins} min)\n"
        f"  label: {b.label}\n"
        f"  project: {proj}\n"
        f"  tags: {tags}\n"
        f"  evidence: {len(b.evidence)} item(s)\n"
    )


def interactive_review(
    blocks: list[TimesheetBlock],
    *,
    default_action: str = "accept",
) -> list[TimesheetBlock]:
    """Interactively accept/edit/skip blocks.

    Returns the accepted blocks (possibly edited).
    """

    accepted: list[TimesheetBlock] = []
    n = len(blocks)

    for idx, b in enumerate(blocks, start=1):
        typer.echo(_fmt_block(b, idx, n))

        action = typer.prompt(
            "action [a]ccept/[e]dit/[s]kip",
            default=default_action[0].lower(),
            show_default=True,
        ).strip().lower()

        if action in {"s", "skip"}:
            typer.echo("skipped\n")
            continue

        if action in {"a", "accept"}:
            accepted.append(b)
            typer.echo("accepted\n")
            continue

        if action not in {"e", "edit"}:
            typer.echo("unrecognised action; skipping\n")
            continue

        new_label = typer.prompt("label", default=b.label)
        new_project = typer.prompt(
            "project (blank for none)",
            default=b.project_suggestion or "",
            show_default=True,
        )
        new_tags = typer.prompt(
            "tags (comma-separated)",
            default=", ".join(b.tags_suggestion),
            show_default=True,
        )

        proj = new_project.strip() or None
        tags = [t.strip() for t in new_tags.split(",") if t.strip()]

        accepted.append(
            replace(
                b,
                label=new_label.strip(),
                project_suggestion=proj,
                tags_suggestion=tags,
            )
        )
        typer.echo("accepted (edited)\n")

    return accepted


def write_reviewed_json(path: str, blocks: list[TimesheetBlock]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_jsonable(blocks), f, ensure_ascii=False, indent=2)
        f.write("\n")
