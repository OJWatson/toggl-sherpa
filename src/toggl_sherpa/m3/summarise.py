from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from urllib.parse import urlparse

from toggl_sherpa.m3.model import EvidenceItem, SampleRow, TabEventRow, TimesheetBlock
from toggl_sherpa.m3.query import parse_ts, seconds_between
from toggl_sherpa.m3.suggest import suggest_for_sample


def _label_for(sample: SampleRow, tab: TabEventRow | None) -> str:
    if tab is not None:
        if tab.allowed and tab.url:
            host = urlparse(tab.url).hostname or "browser"
            # keep it short; evidence contains details.
            return f"browser:{host}"
        return "browser:[redacted]"

    wm = sample.focus_wm_class or "unknown"
    title = sample.focus_title or ""
    if title:
        return f"{wm}:{title[:80]}".strip()
    return wm


def _tab_by_sample_id(tab_events: Iterable[TabEventRow]) -> dict[int, TabEventRow]:
    # If multiple tab events point to the same sample, keep the latest by ts.
    out: dict[int, TabEventRow] = {}
    for t in tab_events:
        if t.sample_id is None:
            continue
        prev = out.get(t.sample_id)
        if prev is None or parse_ts(t.ts_utc) >= parse_ts(prev.ts_utc):
            out[t.sample_id] = t
    return out


def summarise_blocks(
    samples: list[SampleRow],
    tab_events: list[TabEventRow],
    *,
    idle_threshold_ms: int = 60_000,
    gap_threshold_s: int = 90,
    min_block_s: int = 60,
    assumed_interval_s: int = 10,
) -> list[TimesheetBlock]:
    """Create draft timesheet blocks from samples.

    - Drops samples deemed idle (idle_ms >= idle_threshold_ms)
    - Splits blocks when label changes or when there is a big time gap

    Assumes samples are ordered by ts_utc.
    """

    tab_map = _tab_by_sample_id(tab_events)

    active: list[tuple[SampleRow, TabEventRow | None]] = []
    for s in samples:
        if s.idle_ms is not None and s.idle_ms >= idle_threshold_ms:
            continue
        active.append((s, tab_map.get(s.id)))

    if not active:
        return []

    blocks: list[TimesheetBlock] = []

    cur_start = active[0][0].ts_utc
    cur_label = _label_for(active[0][0], active[0][1])
    cur_evidence: list[EvidenceItem] = []
    last_sample: SampleRow = active[0][0]
    last_tab: TabEventRow | None = active[0][1]

    def flush(end_ts: str) -> None:
        nonlocal cur_start, cur_label, cur_evidence, last_sample, last_tab
        secs = seconds_between(cur_start, end_ts)
        if secs < min_block_s:
            return

        sug = suggest_for_sample(last_sample, last_tab)

        blocks.append(
            TimesheetBlock(
                start_ts_utc=cur_start,
                end_ts_utc=end_ts,
                seconds=secs,
                label=cur_label,
                project_suggestion=sug.project,
                tags_suggestion=sug.tags,
                evidence=cur_evidence,
            )
        )

    prev_ts = active[0][0].ts_utc

    for i, (s, t) in enumerate(active):
        if i == 0:
            # Evidence belongs to the first (current) block.
            if t is not None:
                cur_evidence.append(
                    EvidenceItem(
                        ts_utc=t.ts_utc,
                        allowed=t.allowed,
                        url=t.url,
                        title=t.title,
                        url_redacted=t.url_redacted,
                        title_redacted=t.title_redacted,
                    )
                )
            continue

        this_label = _label_for(s, t)
        gap_s = seconds_between(prev_ts, s.ts_utc)

        if this_label != cur_label or gap_s > gap_threshold_s:
            # Close the current block at the *start* of this sample.
            flush(s.ts_utc)
            cur_start = s.ts_utc
            cur_label = this_label
            cur_evidence = []

        # Evidence belongs to the current block (after any boundary split).
        if t is not None:
            cur_evidence.append(
                EvidenceItem(
                    ts_utc=t.ts_utc,
                    allowed=t.allowed,
                    url=t.url,
                    title=t.title,
                    url_redacted=t.url_redacted,
                    title_redacted=t.title_redacted,
                )
            )

        prev_ts = s.ts_utc
        last_sample = s
        last_tab = t

    # Give the final sample a minimal duration, otherwise single-sample blocks
    # would collapse to 0 seconds.
    end_final = (parse_ts(prev_ts) + timedelta(seconds=assumed_interval_s)).isoformat()
    flush(end_final)

    return blocks
