"""Local dashboard server (PRD §2, §7).

Serves the static UI and the in-memory report as JSON, bound to loopback only.
The scan/analysis runs once before serving (offline-guarded inside run_scan);
the HTTP server itself is a separate, post-analysis step.
"""
from __future__ import annotations

import json
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

from .models import ScanReport

WEB_DIR = Path(__file__).parent / "web"
_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class DashboardHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, report_json: bytes = b"{}", **kwargs):
        self._report_json = report_json
        super().__init__(*args, **kwargs)

    def log_message(self, fmt, *args):  # logs only to stderr (PRD §2)
        super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/api/report", "/api/report/"):
            self._send(200, self._report_json, _CONTENT_TYPES[".json"])
            return

        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (WEB_DIR / rel).resolve()
        # Prevent path traversal outside the web dir.
        if WEB_DIR.resolve() not in target.parents and target != WEB_DIR.resolve():
            self._send(403, b"forbidden", "text/plain")
            return
        if not target.is_file():
            self._send(404, b"not found", "text/plain")
            return
        ctype = _CONTENT_TYPES.get(target.suffix, "application/octet-stream")
        self._send(200, target.read_bytes(), ctype)


def serve(
    report: ScanReport,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Start the dashboard server (blocking). Bound to loopback by default."""
    report_json = json.dumps(report.to_dict(), ensure_ascii=False).encode("utf-8")
    handler = partial(DashboardHandler, report_json=report_json)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Dashboard en http://{host}:{port}  (Ctrl+C para salir)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor.")
    finally:
        httpd.server_close()
    return httpd
