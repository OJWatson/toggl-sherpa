from __future__ import annotations

import json

import toggl_sherpa.m1.gnome as gnome


def test_shell_eval_parses_success_single_quoted(monkeypatch) -> None:
    class CP:  # noqa: D401
        returncode = 0
        stdout = "(true, '{\"title\":\"X\"}')"
        stderr = ""

    monkeypatch.setattr(gnome.subprocess, "run", lambda *a, **k: CP())
    assert gnome.shell_eval("irrelevant") == '{"title":"X"}'


def test_get_focus_sample_decodes(monkeypatch) -> None:
    payload = {"idle_ms": 12, "title": "T", "wm_class": "W", "pid": 3}
    payload_s = json.dumps(payload).replace("'", "\\'")

    class CP:
        returncode = 0
        stdout = f"(true, '{payload_s}')"
        stderr = ""

    monkeypatch.setattr(gnome.subprocess, "run", lambda *a, **k: CP())
    s = gnome.get_focus_sample()
    assert s.idle_ms == 12
    assert s.title == "T"
    assert s.wm_class == "W"
    assert s.pid == 3
