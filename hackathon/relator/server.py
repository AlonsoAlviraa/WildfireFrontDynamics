"""Cloud Run HTTP: events, persisted boards, /e2e, /ui. No LLM.

Stdlib-only at import so the process binds PORT before loading Relator.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


def _resolve(incident_id: str) -> dict[str, Any]:
    from .board import empty_board
    from .store import load_board

    return load_board(incident_id) or empty_board(incident_id=incident_id)


def _apply(ev: dict[str, Any]) -> dict[str, Any]:
    from .agent import handle_event
    from .store import load_board, save_board

    iid = str(ev.get("incident_id") or "nijar_demo")
    board = handle_event(load_board(iid), ev)
    save_board(board)
    return board


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"relator {self.command} {self.path} " + (fmt % args), flush=True)

    def _cors(self) -> None:
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET,POST,OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")

    def _send(self, code: int, payload: dict[str, Any] | list[Any], *, ctype: str = "application/json") -> None:
        if ctype == "application/json":
            raw = json.dumps(payload, default=str).encode("utf-8")
        else:
            raw = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("content-type", ctype)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _html(self, html: str, *, code: int = 200) -> None:
        self._send(code, html.encode("utf-8"), ctype="text/html; charset=utf-8")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)
        if path in ("/health", "/ready"):
            from .gcp import settings as gcp_settings
            from .store import list_incidents

            self._send(
                200,
                {
                    "ok": True,
                    "product": "relator",
                    "not_tactical_dispatch": True,
                    "go_q_met": False,
                    "llm": False,
                    "gcp": gcp_settings(),
                    "incidents": list_incidents(),
                },
            )
            return
        if path in ("/e2e", "/v1/e2e"):
            from .e2e import run_e2e
            from .store import save_board

            aoi = (q.get("aoi") or ["nijar"])[0]
            report = run_e2e(aoi=aoi)
            save_board(report["last"])
            self._send(200 if report["ok"] else 500, report)
            return
        if path in ("/", "/ui") or path.startswith("/ui/"):
            from .render import page

            iid = path.split("/", 2)[-1] if path.startswith("/ui/") and len(path) > 4 else (
                (q.get("incident") or ["nijar_e2e"])[0]
            )
            board = _resolve(iid)
            self._html(page([board]))
            return
        if path.startswith("/board/"):
            iid = path.split("/", 2)[-1] or "nijar_demo"
            self._send(200, _resolve(iid))
            return
        self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        n = int(self.headers.get("content-length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            ev = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"ok": False, "error": "bad_json"})
            return
        if isinstance(ev, dict) and "message" in ev and "data" in (ev.get("message") or {}):
            import base64

            try:
                ev = json.loads(base64.b64decode(ev["message"]["data"]).decode("utf-8"))
            except (ValueError, json.JSONDecodeError, KeyError):
                self._send(400, {"ok": False, "error": "bad_pubsub"})
                return
        if path in ("/e2e", "/v1/e2e"):
            from .e2e import run_e2e
            from .store import save_board

            aoi = str((ev or {}).get("aoi") or "nijar")
            report = run_e2e(aoi=aoi)
            save_board(report["last"])
            self._send(200 if report["ok"] else 500, report)
            return
        if path not in ("/events", "/v1/events"):
            self._send(404, {"ok": False, "error": "not_found"})
            return
        if not isinstance(ev, dict):
            self._send(400, {"ok": False, "error": "bad_event"})
            return
        try:
            board = _apply(ev)
        except Exception as exc:
            self._send(500, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:240]})
            return
        self._send(200, board)


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    import os

    bind = int(os.environ.get("PORT", port or 8080))
    httpd = ThreadingHTTPServer((host, bind), Handler)
    print(f"relator listening on {host}:{bind} · llm=false · not tactical dispatch", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    serve()
