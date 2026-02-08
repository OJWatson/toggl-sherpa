from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from toggl_sherpa.m3.model import SampleRow, TabEventRow


@dataclass(frozen=True)
class Suggestion:
    project: str | None
    tags: list[str]


def _hostname(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return (urlparse(url).hostname or "").lower() or None
    except ValueError:
        return None


def suggest_for_sample(
    sample: SampleRow,
    tab: TabEventRow | None,
) -> Suggestion:
    """Rule-based suggestions.

    Heuristics only (no ML). Designed to be safe + debuggable.

    Priority:
      1) allowlisted tab host/title
      2) window manager class + focus title
    """

    tags: set[str] = set()
    project: str | None = None

    host = _hostname(tab.url) if tab and tab.allowed else None
    title = (tab.title or "") if tab and tab.allowed else (sample.focus_title or "")
    wm = (sample.focus_wm_class or "").lower()

    if host:
        if host.endswith("github.com"):
            project = project or "dev"
            tags.update({"code", "github"})
        elif host.endswith("docs.google.com"):
            project = project or "admin"
            tags.update({"docs"})
        elif host.endswith("notion.so"):
            project = project or "planning"
            tags.update({"notes"})

    # App-based rules
    if "rstudio" in wm:
        project = project or "analysis"
        tags.update({"r"})
    if "code" in wm or "vscode" in wm:
        project = project or "dev"
        tags.update({"code"})
    if "slack" in wm or "discord" in wm or "element" in wm:
        project = project or "comms"
        tags.update({"comms"})

    # Title cues
    if re.search(r"\b(timesheet|invoice|expenses)\b", title, flags=re.I):
        project = project or "admin"
        tags.update({"admin"})
    if re.search(r"\b(pr|pull request|merge request|ci)\b", title, flags=re.I):
        project = project or "dev"
        tags.update({"review"})

    return Suggestion(project=project, tags=sorted(tags))
