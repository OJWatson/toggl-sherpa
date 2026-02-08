from __future__ import annotations

from toggl_sherpa.m3.model import TimesheetBlock


def blocks_to_markdown(blocks: list[TimesheetBlock]) -> str:
    if not blocks:
        return "# Draft timesheet\n\n(no activity in range)\n"

    lines: list[str] = []
    lines.append("# Draft timesheet")
    lines.append("")

    for b in blocks:
        mins = round(b.seconds / 60)
        proj = b.project_suggestion or "(unsuggested)"
        tags = ", ".join(b.tags_suggestion) if b.tags_suggestion else "(none)"
        lines.append(f"## {b.start_ts_utc} → {b.end_ts_utc} ({mins} min)")
        lines.append("")
        lines.append(f"- label: {b.label}")
        lines.append(f"- project suggestion: {proj}")
        lines.append(f"- tags suggestion: {tags}")
        lines.append("")

        if b.evidence:
            lines.append("Evidence:")
            for ev in b.evidence[:20]:
                title = ev.display_title()
                url = ev.display_url()
                if title and url:
                    lines.append(f"- {ev.ts_utc} — {title} ({url})")
                elif url:
                    lines.append(f"- {ev.ts_utc} — {url}")
                elif title:
                    lines.append(f"- {ev.ts_utc} — {title}")
                else:
                    lines.append(f"- {ev.ts_utc} — (redacted)")
            if len(b.evidence) > 20:
                lines.append(f"- … ({len(b.evidence) - 20} more)")
            lines.append("")

    return "\n".join(lines) + "\n"
