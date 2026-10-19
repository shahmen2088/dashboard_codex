from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server.history_store import HistoryStore


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


class DashboardHandler(BaseHTTPRequestHandler):
    store = HistoryStore()

    def log_message(self, format: str, *args) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, value: object, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/api/overview":
                self._json(self.store.overview())
                return
            if path == "/api/sessions":
                self._json(self.store.list_sessions(
                    query=query.get("q", [""])[0],
                    group=query.get("group", [""])[0],
                    value=query.get("value", [""])[0],
                    limit=int(query.get("limit", [100])[0]),
                ))
                return
            if path.startswith("/api/projects/"):
                project = unquote(path.removeprefix("/api/projects/"))
                self._json(self.store.project_summary(project))
                return
            asset = "index.html" if path in {"", "/"} else path.removeprefix("/")
            if asset not in {"index.html", "styles.css", "app.js"}:
                self._json({"error": "Not found"}, 404)
                return
            path_obj = DASHBOARD / asset
            content_type = {
                "index.html": "text/html; charset=utf-8",
                "styles.css": "text/css; charset=utf-8",
                "app.js": "text/javascript; charset=utf-8",
            }[asset]
            self._send(200, path_obj.read_bytes(), content_type)
        except (ValueError, OSError) as exc:
            self._json({"error": str(exc)}, 500)


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    DashboardHandler.store = HistoryStore()
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Codex History Organizer: http://{host}:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    run(port=int(os.environ.get("CODEX_HISTORY_PORT", "8787")))
