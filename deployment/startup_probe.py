#!/usr/bin/env python3
"""Accept Zeabur HTTP probes while bench create/migrate still holds the main process.

The platform health check has no start period. If nothing answers on the public
port during first-site creation, Kubernetes kills the container and the pod
enters CrashLoopBackOff.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

HEALTH_PATH = "/api/method/crm.company_auth.health"


def probe_status(path: str) -> tuple[int, dict]:
    route = (path or "/").split("?", 1)[0].rstrip("/") or "/"
    if route == HEALTH_PATH:
        return 200, {"status": "starting"}
    return 503, {"status": "starting"}


class StartupProbe(BaseHTTPRequestHandler):
    def _reply(self):
        code, body = probe_status(self.path)
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def do_GET(self):
        self._reply()

    def do_HEAD(self):
        self._reply()

    def log_message(self, format, *args):
        return


def serve(port: int):
    HTTPServer(("0.0.0.0", port), StartupProbe).serve_forever()


if __name__ == "__main__":
    serve(int(os.environ.get("PORT", "8080")))
