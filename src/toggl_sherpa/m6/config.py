from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ApplyMapping:
    # project_suggestion -> toggl project_id
    project_ids: dict[str, int]
    # tag -> tag (normalisation / canonicalisation)
    tag_map: dict[str, str]

    def map_project_id(self, suggestion: str | None) -> int | None:
        if not suggestion:
            return None
        return self.project_ids.get(suggestion)

    def map_tags(self, tags: list[str]) -> list[str]:
        out: list[str] = []
        for t in tags:
            tt = self.tag_map.get(t, t)
            if tt and tt not in out:
                out.append(tt)
        return out


def default_config_path() -> Path:
    xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return xdg / "toggl-sherpa" / "config.json"


def load_mapping(path: Path | None) -> ApplyMapping:
    if path is None:
        path = default_config_path()

    if not path.exists():
        return ApplyMapping(project_ids={}, tag_map={})

    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("config must be a JSON object")

    raw_proj = obj.get("project_ids", {})
    raw_tags = obj.get("tag_map", {})

    if not isinstance(raw_proj, dict) or not isinstance(raw_tags, dict):
        raise ValueError("project_ids/tag_map must be objects")

    project_ids: dict[str, int] = {}
    for k, v in raw_proj.items():
        if isinstance(k, str) and isinstance(v, int):
            project_ids[k] = v

    tag_map: dict[str, str] = {}
    for k, v in raw_tags.items():
        if isinstance(k, str) and isinstance(v, str):
            tag_map[k] = v

    return ApplyMapping(project_ids=project_ids, tag_map=tag_map)
