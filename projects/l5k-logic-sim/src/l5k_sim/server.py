from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from l5k_sim.engine import ScanEngine
from l5k_sim.ir import Project
from l5k_sim.webserialize import serialize_ir, serialize_state

_STATIC = {"/app.js": "application/javascript", "/ladder.js": "application/javascript",
           "/style.css": "text/css"}


class SimService:
    def __init__(self, project: Project, scan_period_ms: int = 10) -> None:
        self.project = project
        self.scan_period_ms = scan_period_ms
        self.engine = ScanEngine(project, scan_period_ms)

    def ir(self) -> dict:
        return serialize_ir(self.project)

    def state(self) -> dict:
        return serialize_state(self.engine)

    def step(self) -> dict:
        self.engine.scan()
        return self.state()

    def run(self, n: int) -> dict:
        self.engine.run(int(n))
        return self.state()

    def reset(self) -> dict:
        self.engine = ScanEngine(self.project, self.scan_period_ms)
        return self.state()

    def force(self, scope: str, operand: str, value: Any) -> dict:
        self.engine.force(scope, operand, value)
        return self.state()

    def set(self, scope: str, operand: str, value: Any) -> dict:
        self.engine.set(scope, operand, value)
        return self.state()


def make_handler(service: SimService, web_dir: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence console noise
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _file(self, rel, content_type):
            path = os.path.join(web_dir, rel)
            try:
                with open(path, "rb") as fh:
                    body = fh.read()
            except OSError:
                self._json({"error": "not found"}, 404)
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            if not length:
                return {}
            return json.loads(self.rfile.read(length) or b"{}")

        def do_GET(self):
            if self.path == "/" or self.path == "/index.html":
                self._file("index.html", "text/html")
            elif self.path in _STATIC:
                self._file(self.path.lstrip("/"), _STATIC[self.path])
            elif self.path == "/api/ir":
                self._json(service.ir())
            elif self.path == "/api/state":
                self._json(service.state())
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            try:
                body = self._read_body()
            except (ValueError, json.JSONDecodeError):
                self._json({"error": "bad json"}, 400)
                return
            if self.path == "/api/step":
                self._json(service.step())
            elif self.path == "/api/run":
                self._json(service.run(body.get("n", 1)))
            elif self.path == "/api/reset":
                self._json(service.reset())
            elif self.path == "/api/force":
                self._json(service.force(body["scope"], body["operand"], body["value"]))
            elif self.path == "/api/set":
                self._json(service.set(body["scope"], body["operand"], body["value"]))
            else:
                self._json({"error": "not found"}, 404)

    return Handler


def serve(project: Project, web_dir: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    svc = SimService(project)
    httpd = ThreadingHTTPServer((host, port), make_handler(svc, web_dir))
    print(f"L5K Logic Sim UI on http://{host}:{port}")
    httpd.serve_forever()
