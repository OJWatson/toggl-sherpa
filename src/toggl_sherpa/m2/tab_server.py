from __future__ import annotations

import json
import os
import sqlite3
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from toggl_sherpa.m1 import db as db_mod
from toggl_sherpa.m2.redaction import parse_allowlist
from toggl_sherpa.m2.tab_ingest import TabPayload, insert_tab_event


class TabIngestHandler(BaseHTTPRequestHandler):
    server: TabIngestHTTPServer  # type: ignore[assignment]

    def _json_response(self, status: int, obj: dict[str, Any]) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # Simple CORS for extension.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/active_tab":
            self._json_response(HTTPStatus.NOT_FOUND, {"error": "not found"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        body = self.rfile.read(length) if length else b""
        try:
            payload_obj = json.loads(body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "invalid json"})
            return

        url = payload_obj.get("url")
        title = payload_obj.get("title")
        ts_utc = payload_obj.get("ts_utc")

        if url is not None and not isinstance(url, str):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "url must be a string"})
            return
        if title is not None and not isinstance(title, str):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "title must be a string"})
            return
        if ts_utc is not None and not isinstance(ts_utc, str):
            self._json_response(HTTPStatus.BAD_REQUEST, {"error": "ts_utc must be a string"})
            return

        ua = self.headers.get("User-Agent")

        try:
            red = insert_tab_event(
                self.server.conn,
                TabPayload(url=url, title=title, ts_utc=ts_utc, user_agent=ua),
                self.server.allow_hosts,
            )
        except sqlite3.Error as e:
            self._json_response(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(e)})
            return

        self._json_response(
            HTTPStatus.OK,
            {
                "ok": True,
                "allowed": red.allowed,
                "url_redacted": red.url_redacted,
                "title_redacted": red.title_redacted,
            },
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        # Quiet by default; opt-in with TOGGL_SHERPA_TAB_SERVER_LOG=1
        if os.environ.get("TOGGL_SHERPA_TAB_SERVER_LOG") == "1":
            super().log_message(fmt, *args)


class TabIngestHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        conn,
        allow_hosts: set[str],
    ):
        super().__init__(server_address, TabIngestHandler)
        self.conn = conn
        self.allow_hosts = allow_hosts


def serve(
    db_path: Path,
    host: str = "127.0.0.1",
    port: int = 5055,
    allowlist: str | None = None,
) -> None:
    allow_hosts = parse_allowlist(allowlist)
    conn = db_mod.connect(db_path, check_same_thread=False)
    httpd = TabIngestHTTPServer((host, port), conn=conn, allow_hosts=allow_hosts)
    try:
        httpd.serve_forever(poll_interval=0.25)
    finally:
        conn.close()
