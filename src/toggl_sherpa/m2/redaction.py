from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class RedactedTab:
    allowed: bool
    url: str | None
    title: str | None
    url_redacted: str | None
    title_redacted: str | None


def parse_allowlist(patterns: str | None) -> set[str]:
    """Parse a comma-separated allowlist of hosts/domains.

    Entries are normalized to lowercase and stripped.
    """

    if not patterns:
        return set()
    out: set[str] = set()
    for part in patterns.split(","):
        p = part.strip().lower()
        if not p:
            continue
        out.add(p)
    return out


def _host_matches(host: str, allow: Iterable[str]) -> bool:
    host = host.lower().strip(".")
    for pat in allow:
        pat = pat.lower().strip(".")
        if host == pat or host.endswith("." + pat):
            return True
    return False


def redact_tab(
    url: str | None,
    title: str | None,
    allow_hosts: set[str],
) -> RedactedTab:
    if not url:
        return RedactedTab(
            allowed=False,
            url=None,
            title=None,
            url_redacted=None,
            title_redacted=None,
        )

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    allowed = bool(host) and _host_matches(host, allow_hosts)

    if allowed:
        return RedactedTab(
            allowed=True,
            url=url,
            title=title,
            url_redacted=url,
            title_redacted=title,
        )

    # Redact path/query/fragment; keep scheme+host for weak evidence.
    scheme = parsed.scheme or "https"
    red_url = f"{scheme}://{host}/…" if host else None
    red_title = "[REDACTED]" if title else None

    return RedactedTab(
        allowed=False,
        url=None,
        title=None,
        url_redacted=red_url,
        title_redacted=red_title,
    )
