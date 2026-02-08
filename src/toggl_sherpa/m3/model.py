from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleRow:
    id: int
    ts_utc: str
    idle_ms: int | None
    focus_title: str | None
    focus_wm_class: str | None
    focus_pid: int | None


@dataclass(frozen=True)
class TabEventRow:
    id: int
    ts_utc: str
    sample_id: int | None
    allowed: bool
    url: str | None
    title: str | None
    url_redacted: str | None
    title_redacted: str | None


@dataclass(frozen=True)
class EvidenceItem:
    ts_utc: str
    allowed: bool
    url: str | None
    title: str | None
    url_redacted: str | None
    title_redacted: str | None

    def display_url(self) -> str:
        if self.allowed and self.url:
            return self.url
        return self.url_redacted or ""

    def display_title(self) -> str:
        if self.allowed and self.title:
            return self.title
        return self.title_redacted or ""


@dataclass(frozen=True)
class TimesheetBlock:
    start_ts_utc: str
    end_ts_utc: str
    seconds: int
    label: str
    project_suggestion: str | None
    tags_suggestion: list[str]
    evidence: list[EvidenceItem]
