"""Minimal Decision Card HTTP API (stdlib only).

  python -m wildfire_front serve-decide --host 127.0.0.1 --port 8765

Endpoints:
  GET  /health
  GET  /v1/openapi.json
  POST /v1/decide
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .decide_service import API_VERSION, PRODUCT_ID, REPO_ROOT, decide_from_request
from .forensics import render_acta_md, render_radio_bridge, replay_decision
from .policy import list_policies, load_policy_catalog

OPENAPI: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "WildfireFrontDynamics Decision Card API",
        "version": API_VERSION,
        "description": (
            "Minimal Fire Decision Card API (GO/HOLD/ABSTAIN). "
            "Not a tactical dispatch service. Empty sources → ABSTAIN. "
            "Also: radio-bridge text, acta MD, forensic replay."
        ),
    },
    "paths": {
        "/health": {
            "get": {
                "summary": "Liveness",
                "responses": {"200": {"description": "ok"}},
            }
        },
        "/v1/decide": {
            "post": {
                "summary": "Build Fire Decision Card",
                "requestBody": {
                    "required": False,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "event_id": {"type": "string"},
                                    "use_ml_v34": {"type": "boolean"},
                                    "work_dir": {"type": "string"},
                                    "open_pack": {"type": "string"},
                                    "require_ops_for_go": {"type": "boolean"},
                                    "ml_metrics": {"type": "object"},
                                    "ops_metrics": {"type": "object"},
                                    "open_metrics": {"type": "object"},
                                    "include_radio": {"type": "boolean"},
                                    "include_acta": {"type": "boolean"},
                                    "policy_id": {
                                        "type": "string",
                                        "description": "default|field_ops|research_open|demo",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Decision Card JSON + latency_ms"},
                    "400": {"description": "Invalid JSON"},
                },
            }
        },
        "/v1/policies": {
            "get": {
                "summary": "List decision policy profiles",
                "responses": {"200": {"description": "policy catalog"}},
            }
        },
        "/v1/replay": {
            "post": {
                "summary": "Replay decision from stored sources (forensic)",
                "responses": {"200": {"description": "replay_ok + card"}},
            }
        },
    },
}


def _json_bytes(obj: Any, *, status: int = 200) -> tuple[int, bytes, str]:
    raw = json.dumps(obj, indent=2, default=str).encode("utf-8")
    return status, raw, "application/json; charset=utf-8"


class DecideHandler(BaseHTTPRequestHandler):
    server_version = f"WFD-Decide/{API_VERSION}"

    def log_message(self, fmt: str, *args: Any) -> None:  # quieter default
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-WFD-API", API_VERSION)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/health", "/v1/health"):
            status, body, ctype = _json_bytes(
                {
                    "ok": True,
                    "product": PRODUCT_ID,
                    "api_version": API_VERSION,
                    "repo_root": str(REPO_ROOT),
                }
            )
            self._send(status, body, ctype)
            return
        if path in ("/v1/openapi.json", "/openapi.json"):
            status, body, ctype = _json_bytes(OPENAPI)
            self._send(status, body, ctype)
            return
        if path in ("/v1/policies", "/policies"):
            status, body, ctype = _json_bytes(
                {
                    "default_policy": (load_policy_catalog() or {}).get("default_policy"),
                    "policies": list_policies(),
                }
            )
            self._send(status, body, ctype)
            return
        if path == "/":
            status, body, ctype = _json_bytes(
                {
                    "product": PRODUCT_ID,
                    "api_version": API_VERSION,
                    "endpoints": [
                        "GET /health",
                        "GET /v1/openapi.json",
                        "GET /v1/policies",
                        "POST /v1/decide",
                        "POST /v1/replay",
                    ],
                    "disclaimer": "Not tactical dispatch. Empty sources → ABSTAIN.",
                }
            )
            self._send(status, body, ctype)
            return
        status, body, ctype = _json_bytes({"error": "not_found", "path": path}, status=404)
        self._send(status, body, ctype)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            req = json.loads(raw.decode("utf-8") or "{}")
            if req is None:
                req = {}
            if not isinstance(req, dict):
                raise ValueError("body must be a JSON object")
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            status, body, ctype = _json_bytes(
                {"error": "invalid_json", "detail": str(exc)}, status=400
            )
            self._send(status, body, ctype)
            return

        base = Path(getattr(self.server, "base_dir", REPO_ROOT))

        if path == "/v1/replay":
            result = replay_decision(req, base=base)
            status, body, ctype = _json_bytes(result)
            self._send(status, body, ctype)
            return

        if path != "/v1/decide":
            status, body, ctype = _json_bytes({"error": "not_found", "path": path}, status=404)
            self._send(status, body, ctype)
            return

        req.setdefault("channel", "http_api")
        payload = decide_from_request(req, base=base)
        if req.get("include_radio", True):
            payload["radio_bridge"] = render_radio_bridge(payload)
        if req.get("include_acta"):
            payload["acta_md"] = render_acta_md(payload)
        status, body, ctype = _json_bytes(payload)
        self._send(status, body, ctype)


class DecideHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        base_dir: Path | None = None,
        verbose: bool = False,
    ) -> None:
        super().__init__(server_address, DecideHandler)
        self.base_dir = Path(base_dir) if base_dir else REPO_ROOT
        self.verbose = verbose


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    base_dir: Path | None = None,
    verbose: bool = False,
) -> DecideHTTPServer:
    """Blocking serve (Ctrl+C to stop)."""
    httpd = DecideHTTPServer((host, port), base_dir=base_dir, verbose=verbose)
    print(
        f"decide API {API_VERSION} on http://{host}:{port}  "
        f"(POST /v1/decide · GET /health)",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down decide API", flush=True)
    finally:
        httpd.server_close()
    return httpd


def start_background(
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    base_dir: Path | None = None,
) -> tuple[DecideHTTPServer, threading.Thread, int]:
    """Start server in a daemon thread. port=0 → ephemeral. Returns (server, thread, port)."""
    httpd = DecideHTTPServer((host, port), base_dir=base_dir, verbose=False)
    actual_port = int(httpd.server_address[1])
    thread = threading.Thread(target=httpd.serve_forever, name="decide-api", daemon=True)
    thread.start()
    return httpd, thread, actual_port
