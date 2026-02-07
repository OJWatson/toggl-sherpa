from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Any


class GnomeShellEvalError(RuntimeError):
    pass


@dataclass(frozen=True)
class FocusSample:
    idle_ms: int | None
    title: str | None
    wm_class: str | None
    pid: int | None
    raw: dict[str, Any]


_JS = r"""
(() => {
  try {
    const w = global.display.focus_window;
    const idle = global.backend?.get_core_idle_monitor?.().get_idletime?.();
    if (!w) {
      return JSON.stringify({ idle_ms: idle ?? null, title: null, wm_class: null, pid: null });
    }
    return JSON.stringify({
      idle_ms: idle ?? null,
      title: w.get_title?.() ?? null,
      wm_class: w.get_wm_class?.() ?? null,
      pid: w.get_pid?.() ?? null,
    });
  } catch (e) {
    return JSON.stringify({ error: String(e) });
  }
})()
""".strip()


_GDBUS_TUPLE_RE = re.compile(r"^\((true|false),\s*(.*)\)\s*$", re.IGNORECASE | re.DOTALL)


def shell_eval(js: str) -> str:
    # Returns the *result* string produced by the Eval method.
    # gdbus output looks like: (true, '...') or (false, '')
    cp = subprocess.run(
        [
            "gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.Shell",
            "--object-path",
            "/org/gnome/Shell",
            "--method",
            "org.gnome.Shell.Eval",
            js,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    out = (cp.stdout or "").strip()
    if cp.returncode != 0:
        raise GnomeShellEvalError(cp.stderr.strip() or f"gdbus exit {cp.returncode}")

    m = _GDBUS_TUPLE_RE.match(out)
    if not m:
        raise GnomeShellEvalError(f"Unrecognised gdbus output: {out!r}")

    success = m.group(1).lower() == "true"
    payload = m.group(2).strip()
    # payload is a GVariant string, usually single-quoted with C escapes.
    try:
        # Convert GVariant string literal into python by abusing JSON: gdbus string escaping
        # is close to C; easiest robust approach: ask python to decode via unicode_escape
        if payload.startswith("'") and payload.endswith("'"):
            inner = payload[1:-1]
            inner = bytes(inner, "utf-8").decode("unicode_escape")
        elif payload.startswith('"') and payload.endswith('"'):
            inner = json.loads(payload)
        else:
            inner = payload
    except Exception as e:  # noqa: BLE001
        raise GnomeShellEvalError(f"Failed to parse Eval payload: {payload!r}") from e

    if not success:
        raise GnomeShellEvalError(inner)
    return inner


def get_focus_sample() -> FocusSample:
    raw_s = shell_eval(_JS)
    try:
        raw = json.loads(raw_s)
    except json.JSONDecodeError as e:
        raise GnomeShellEvalError(f"Eval did not return JSON: {raw_s!r}") from e

    if "error" in raw:
        raise GnomeShellEvalError(str(raw["error"]))

    idle_ms = raw.get("idle_ms")
    title = raw.get("title")
    wm_class = raw.get("wm_class")
    pid = raw.get("pid")

    return FocusSample(
        idle_ms=int(idle_ms) if idle_ms is not None else None,
        title=str(title) if title is not None else None,
        wm_class=str(wm_class) if wm_class is not None else None,
        pid=int(pid) if pid is not None else None,
        raw=raw,
    )
