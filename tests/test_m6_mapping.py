from __future__ import annotations

from pathlib import Path

from toggl_sherpa.m3.model import TimesheetBlock
from toggl_sherpa.m5.apply import build_plan
from toggl_sherpa.m6.config import load_mapping


def test_load_mapping_missing_file_is_empty(tmp_path: Path) -> None:
    m = load_mapping(tmp_path / "nope.json")
    assert m.project_ids == {}
    assert m.tag_map == {}


def test_build_plan_applies_mapping() -> None:
    blocks = [
        TimesheetBlock(
            start_ts_utc="2026-02-08T00:00:00+00:00",
            end_ts_utc="2026-02-08T00:10:00+00:00",
            seconds=600,
            label="work",
            project_suggestion="dev",
            tags_suggestion=["Code", "code", ""],
            evidence=[],
        )
    ]
    plan = build_plan(
        blocks,
        project_ids={"dev": 99},
        tag_map={"Code": "code"},
    )

    assert plan[0].project_id == 99
    assert plan[0].tags == ["code"]
