from __future__ import annotations

from toggl_sherpa.m3.model import EvidenceItem, TimesheetBlock
from toggl_sherpa.m3.report import blocks_to_markdown


def test_blocks_to_markdown_smoke() -> None:
    md = blocks_to_markdown(
        [
            TimesheetBlock(
                start_ts_utc="2026-02-08T00:00:00+00:00",
                end_ts_utc="2026-02-08T00:10:00+00:00",
                seconds=600,
                label="browser:github.com",
                project_suggestion="dev",
                tags_suggestion=["code"],
                evidence=[
                    EvidenceItem(
                        ts_utc="2026-02-08T00:05:00+00:00",
                        allowed=False,
                        url=None,
                        title=None,
                        url_redacted="https://secret.com/…",
                        title_redacted="[REDACTED]",
                    )
                ],
            )
        ]
    )
    assert "Draft timesheet" in md
    assert "Evidence" in md
    assert "secret.com" in md
