from __future__ import annotations

import base64
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class TogglConfig:
    api_token: str
    workspace_id: int


class TogglApiError(RuntimeError):
    pass


def _auth_header(api_token: str) -> str:
    # Toggl Track API uses HTTP Basic auth, username = token, password = "api_token".
    raw = f"{api_token}:api_token".encode()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"Basic {b64}"


def create_time_entry(
    cfg: TogglConfig,
    *,
    start: str,
    stop: str,
    description: str,
    tags: list[str] | None = None,
    project_id: int | None = None,
) -> dict:
    url = f"https://api.track.toggl.com/api/v9/workspaces/{cfg.workspace_id}/time_entries"
    headers = {
        "Authorization": _auth_header(cfg.api_token),
        "Content-Type": "application/json",
    }

    payload: dict = {
        "created_with": "toggl-sherpa",
        "description": description,
        "start": start,
        "stop": stop,
    }
    if tags:
        payload["tags"] = tags
    if project_id is not None:
        payload["project_id"] = project_id

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code >= 400:
        raise TogglApiError(f"toggl api error {resp.status_code}: {resp.text}")

    data = resp.json()
    if not isinstance(data, dict):
        raise TogglApiError("unexpected response")
    return data
