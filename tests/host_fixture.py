from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
from typing import Callable

URL_VARIABLE = "SKILL_HOST_URL"
TOKEN_VARIABLE = "SKILL_HOST_TOKEN"
TOKEN = "test-token"


class HostAnswer(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


class FakeHost:
    def __init__(self, decide: Callable[[dict], dict] | None = None, generate: Callable[[dict], dict] | None = None, tools: dict[str, Callable[[dict], dict]] | None = None):
        self.routes = {"decide": decide, "generate": generate} | {f"tools/{name}": answer for name, answer in (tools or {}).items()}
        self.requests: list[tuple[str, dict]] = []
        self.lock = threading.Lock()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler_class())
        self.saved: dict[str, str | None] = {}

    def requests_to(self, route: str) -> list[dict]:
        with self.lock:
            return [body for asked, body in self.requests if asked == route]

    def handler_class(self):
        host = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                route = self.path.strip("/")
                with host.lock:
                    host.requests.append((route, body))
                status, document = host.answer(route, body, self.headers.get("Authorization", ""))
                encoded = json.dumps(document).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, *arguments):
                pass

        return Handler

    def answer(self, route: str, body: dict, authorization: str) -> tuple[int, dict]:
        if authorization != "Bearer " + TOKEN:
            return 401, {"error": "this token belongs to no running command"}
        answer = self.routes.get(route)
        if answer is None:
            return 501, {"error": "this host has no model for that question"}
        try:
            return 200, answer(body)
        except HostAnswer as refusal:
            return refusal.status, {"error": refusal.message}

    def __enter__(self) -> "FakeHost":
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{self.server.server_address[1]}"
        for name, value in ((URL_VARIABLE, url), (TOKEN_VARIABLE, TOKEN)):
            self.saved[name] = os.environ.get(name)
            os.environ[name] = value
        return self

    def __exit__(self, *arguments) -> None:
        self.server.shutdown()
        self.server.server_close()
        for name, value in self.saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
