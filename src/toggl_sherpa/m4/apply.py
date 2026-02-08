from __future__ import annotations

import csv
import json
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from toggl_sherpa.m3.model import EvidenceItem, TimesheetBlock
from toggl_sherpa.m3.query import parse_ts


def load_blocks_json(path: str | Path) -> list[TimesheetBlock]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("expected a list of blocks")

    blocks: list[TimesheetBlock] = []
    for i, d in enumerate(data):
        if not isinstance(d, dict):
            raise ValueError(f"block[{i}] must be an object")
        ev = []
        for j, e in enumerate(d.get("evidence", [])):
            if not isinstance(e, dict):
                raise ValueError(f"block[{i}].evidence[{j}] must be an object")
            ev.append(
                EvidenceItem(
                    ts_utc=str(e["ts_utc"]),
                    allowed=bool(e["allowed"]),
                    url=e.get("url"),
                    title=e.get("title"),
                    url_redacted=e.get("url_redacted"),
                    title_redacted=e.get("title_redacted"),
                )
            )

        blocks.append(
            TimesheetBlock(
                start_ts_utc=str(d["start_ts_utc"]),
                end_ts_utc=str(d["end_ts_utc"]),
                seconds=int(d["seconds"]),
                label=str(d["label"]),
                project_suggestion=d.get("project_suggestion"),
                tags_suggestion=[str(x) for x in d.get("tags_suggestion", [])],
                evidence=ev,
            )
        )

    return blocks


def merge_adjacent_blocks(
    blocks: list[TimesheetBlock],
    *,
    gap_seconds: int = 60,
) -> list[TimesheetBlock]:
    """Merge adjacent blocks if they are effectively contiguous and identical enough.

    Criteria:
    - gap between end and next start <= gap_seconds
    - same label/project/tags

    Evidence is concatenated (stable order).
    """

    if not blocks:
        return []

    merged: list[TimesheetBlock] = [blocks[0]]
    for b in blocks[1:]:
        prev = merged[-1]
        gap = int((parse_ts(b.start_ts_utc) - parse_ts(prev.end_ts_utc)).total_seconds())

        if (
            gap <= gap_seconds
            and b.label == prev.label
            and b.project_suggestion == prev.project_suggestion
            and b.tags_suggestion == prev.tags_suggestion
        ):
            merged[-1] = replace(
                prev,
                end_ts_utc=b.end_ts_utc,
                seconds=prev.seconds + b.seconds + max(gap, 0),
                evidence=[*prev.evidence, *b.evidence],
            )
        else:
            merged.append(b)

    return merged


def _duration_hh_mm_ss(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def write_toggl_csv(path: str | Path, blocks: list[TimesheetBlock]) -> None:
    """Write a Toggl Track CSV import file.

    Uses UTC timestamps from the blocks.

    Columns follow Toggl's common import format:
    - Description
    - Project
    - Tags
    - Start date
    - Start time
    - Duration
    """

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "Description",
                "Project",
                "Tags",
                "Start date",
                "Start time",
                "Duration",
            ],
        )
        w.writeheader()

        for b in blocks:
            dt: datetime = parse_ts(b.start_ts_utc)
            w.writerow(
                {
                    "Description": b.label,
                    "Project": b.project_suggestion or "",
                    "Tags": ",".join(b.tags_suggestion),
                    "Start date": dt.date().isoformat(),
                    "Start time": dt.time().replace(microsecond=0).isoformat(),
                    "Duration": _duration_hh_mm_ss(b.seconds),
                }
            )
