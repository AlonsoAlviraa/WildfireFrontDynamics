"""Cloud Run entry: bind PORT immediately, import Relator lazily."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

PORT = int(os.environ.get("PORT", "8080"))


class Boot(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print("relator " + (fmt % args), flush=True)

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("content-type", ctype)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        self._send(code, json.dumps(payload, default=str).encode(), "application/json")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/ready",):
            self._json(200, {"ok": True, "ready": True, "llm": False})
            return
        from . import server as app

        self.__class__ = app.Handler  # type: ignore[misc]
        app.Handler.do_GET(self)

    def do_POST(self) -> None:  # noqa: N802
        from . import server as app

        self.__class__ = app.Handler  # type: ignore[misc]
        app.Handler.do_POST(self)


def main() -> None:
    print(f"relator-boot listen 0.0.0.0:{PORT} llm=false", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Boot).serve_forever()


if __name__ == "__main__":
    main()
