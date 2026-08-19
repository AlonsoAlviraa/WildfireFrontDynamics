"""Minimal Decision Card HTTP API (stdlib only).

  python -m wildfire_front serve-decide --host 127.0.0.1 --port 8765 --base-dir /path/sandbox

Endpoints:
  GET  /health
  GET  /v1/openapi.json
  POST /v1/decide

Path sandbox
------------
Unauthenticated HTTP only loads ``work_dir`` / ``open_pack`` / ``reliability_gate``
paths under ``base_dir``. Default ``base_dir`` is an empty temp sandbox (not the
repository root). Setting ``base_dir`` to the repo root is insecure for any
exposed listener — every repo path becomes allowlisted.
"""

from __future__ import annotations

import json
import tempfile
import threading
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .decide_service import (
    API_VERSION,
    MAX_BODY_BYTES,
    PRODUCT_ID,
    REPO_ROOT,
    PathNotAllowedError,
    UntrustedInlineMetricsError,
    decide_from_request,
)
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
                                    "reliability_gate": {
                                        "type": "string",
                                        "description": (
                                            "Path to reliability gate JSON under server "
                                            "base_dir only (not REPO_ROOT, not docs/). "
                                            "Inline reports and client-asserted gates_ok "
                                            "flags are ignored on this unauthenticated "
                                            "HTTP channel."
                                        ),
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {
                    "200": {"description": "Decision Card JSON + latency_ms"},
                    "400": {
                        "description": (
                            "Invalid JSON, or path_not_allowed "
                            "(work_dir/open_pack/reliability_gate outside allowlist)"
                        )
                    },
                    "413": {"description": "Request body too large"},
                },
            }
        },
        "/v1/policies": {
            "get": {
                "summary": "List decision policy profiles",
                "responses": {"200": {"description": "policy catalog"}},
            }
        },
        "/v1/flags": {
            "get": {
                "summary": "Read-only release flags (does not flip stamps)",
                "responses": {"200": {"description": "GO_Q / fusion / not_claims"}},
            }
        },
        "/v1/catalog": {
            "get": {
                "summary": "ML products + holdout_only (RCDA/Caldor not ready)",
                "responses": {"200": {"description": "catalog"}},
            }
        },
        "/v1/card": {
            "get": {
                "summary": "Last Decision Card for work_dir",
                "parameters": [{"name": "work_dir", "in": "query", "schema": {"type": "string"}}],
                "responses": {"200": {"description": "card"}, "400": {"description": "missing"}},
            }
        },
        "/v1/status": {
            "get": {
                "summary": "Lightweight incident outbox status",
                "parameters": [{"name": "work_dir", "in": "query", "schema": {"type": "string"}}],
                "responses": {"200": {"description": "status"}},
            }
        },
        "/v1/snapshot": {
            "get": {
                "summary": "Shareable read-only incident snapshot (card + source board + rails)",
                "parameters": [{"name": "work_dir", "in": "query", "schema": {"type": "string"}}],
                "responses": {"200": {"description": "snapshot"}},
            },
            "post": {
                "summary": "Shareable read-only incident snapshot",
                "responses": {"200": {"description": "snapshot"}},
            },
        },
        "/v1/compare": {
            "post": {
                "summary": "Compare two cards/snapshots (local flip alert; not SMS)",
                "responses": {"200": {"description": "compare"}},
            }
        },
        "/v1/export-acta": {
            "post": {
                "summary": "Write forensic acta + radio + replay sources",
                "responses": {"200": {"description": "bundle paths"}},
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
    from .surface_api import dumps_compact

    return status, dumps_compact(obj), "application/json; charset=utf-8"


def _query_map(path: str) -> dict[str, str]:
    return {key: vals[-1] for key, vals in parse_qs(urlparse(path).query).items() if vals}


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

    def _work_dir_from_query(self) -> Path | None:
        from .decide_service import _as_path

        query = _query_map(self.path)
        raw = query.get("work_dir")
        if not raw:
            return None
        base = Path(getattr(self.server, "base_dir", REPO_ROOT))
        return _as_path(raw, base=base)

    def do_GET(self) -> None:  # noqa: N802
        from .surface_api import (
            surface_card,
            surface_catalog,
            surface_flags,
            surface_health,
            surface_snapshot,
            surface_status,
        )

        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/health", "/v1/health"):
            payload = surface_health()
            payload["repo_root"] = str(REPO_ROOT)
            status, body, ctype = _json_bytes(payload)
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
        if path in ("/v1/flags", "/flags"):
            status, body, ctype = _json_bytes(surface_flags())
            self._send(status, body, ctype)
            return
        if path in ("/v1/catalog", "/catalog"):
            status, body, ctype = _json_bytes(surface_catalog())
            self._send(status, body, ctype)
            return
        if path in ("/v1/snapshot", "/snapshot"):
            try:
                work = self._work_dir_from_query()
            except PathNotAllowedError as exc:
                status, body, ctype = _json_bytes(
                    {"error": "path_not_allowed", "detail": str(exc)}, status=400
                )
                self._send(status, body, ctype)
                return
            if work is None:
                status, body, ctype = _json_bytes(
                    {"error": "work_dir_required", "detail": "pass ?work_dir="},
                    status=400,
                )
                self._send(status, body, ctype)
                return
            payload = surface_snapshot(work)
            code = 200 if payload.get("ok", True) else 400
            status, body, ctype = _json_bytes(payload, status=code)
            self._send(status, body, ctype)
            return
        if path in ("/v1/card", "/card", "/v1/status", "/status"):
            try:
                work = self._work_dir_from_query()
            except PathNotAllowedError as exc:
                status, body, ctype = _json_bytes(
                    {"error": "path_not_allowed", "detail": str(exc)}, status=400
                )
                self._send(status, body, ctype)
                return
            if work is None:
                status, body, ctype = _json_bytes(
                    {"error": "work_dir_required", "detail": "pass ?work_dir="},
                    status=400,
                )
                self._send(status, body, ctype)
                return
            payload = surface_card(work) if "card" in path else surface_status(work)
            code = 200 if payload.get("ok", True) else 400
            status, body, ctype = _json_bytes(payload, status=code)
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
                        "GET /v1/flags",
                        "GET /v1/catalog",
                        "GET /v1/card?work_dir=",
                        "GET /v1/status?work_dir=",
                        "GET /v1/snapshot?work_dir=",
                        "POST /v1/decide",
                        "POST /v1/snapshot",
                        "POST /v1/compare",
                        "POST /v1/export-acta",
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
        if length > MAX_BODY_BYTES:
            status, body, ctype = _json_bytes(
                {
                    "error": "body_too_large",
                    "detail": f"Content-Length {length} exceeds max {MAX_BODY_BYTES}",
                    "max_body_bytes": MAX_BODY_BYTES,
                },
                status=413,
            )
            self._send(status, body, ctype)
            return
        raw = self.rfile.read(length) if length > 0 else b"{}"
        if len(raw) > MAX_BODY_BYTES:
            status, body, ctype = _json_bytes(
                {
                    "error": "body_too_large",
                    "max_body_bytes": MAX_BODY_BYTES,
                },
                status=413,
            )
            self._send(status, body, ctype)
            return
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

        if path in ("/v1/snapshot", "/snapshot"):
            from .decide_service import _as_path
            from .surface_api import surface_snapshot

            work_raw = req.get("work_dir")
            if not work_raw:
                status, body, ctype = _json_bytes(
                    {"error": "work_dir_required"}, status=400
                )
                self._send(status, body, ctype)
                return
            try:
                work = _as_path(str(work_raw), base=base)
            except PathNotAllowedError as exc:
                status, body, ctype = _json_bytes(
                    {"error": "path_not_allowed", "detail": str(exc)}, status=400
                )
                self._send(status, body, ctype)
                return
            persist = bool(req.get("save"))
            payload = surface_snapshot(work, persist=persist)
            code = 200 if payload.get("ok", True) else 400
            status, body, ctype = _json_bytes(payload, status=code)
            self._send(status, body, ctype)
            return

        if path in ("/v1/compare", "/compare"):
            from .decide_service import _as_path
            from .surface_api import compare_from_request

            def _resolve(raw: str):
                return _as_path(raw, base=base)

            payload = compare_from_request(req, resolve_work_dir=_resolve)
            code = 200 if payload.get("ok", True) else 400
            status, body, ctype = _json_bytes(payload, status=code)
            self._send(status, body, ctype)
            return

        if path in ("/v1/export-acta", "/export-acta"):
            from .surface_api import surface_export_acta

            work_raw = req.get("work_dir")
            if not work_raw:
                status, body, ctype = _json_bytes(
                    {"error": "work_dir_required"}, status=400
                )
                self._send(status, body, ctype)
                return
            try:
                from .decide_service import _as_path

                work = _as_path(str(work_raw), base=base)
            except PathNotAllowedError as exc:
                status, body, ctype = _json_bytes(
                    {"error": "path_not_allowed", "detail": str(exc)}, status=400
                )
                self._send(status, body, ctype)
                return
            payload = surface_export_acta(work, operator=req.get("operator"))
            code = 200 if payload.get("ok", True) else 400
            status, body, ctype = _json_bytes(payload, status=code)
            self._send(status, body, ctype)
            return

        if path == "/v1/replay":
            try:
                result = replay_decision(req, base=base)
            except PathNotAllowedError as exc:
                status, body, ctype = _json_bytes(
                    {"error": "path_not_allowed", "detail": str(exc)}, status=400
                )
                self._send(status, body, ctype)
                return
            status, body, ctype = _json_bytes(result)
            self._send(status, body, ctype)
            return

        if path != "/v1/decide":
            status, body, ctype = _json_bytes({"error": "not_found", "path": path}, status=404)
            self._send(status, body, ctype)
            return

        # Force untrusted HTTP channel (clients cannot spoof trust via body).
        req["channel"] = "http_api"
        try:
            payload = decide_from_request(req, base=base, trust_client_reliability=False)
        except PathNotAllowedError as exc:
            status, body, ctype = _json_bytes(
                {"error": "path_not_allowed", "detail": str(exc)}, status=400
            )
            self._send(status, body, ctype)
            return
        except UntrustedInlineMetricsError as exc:
            status, body, ctype = _json_bytes(
                {"error": "untrusted_inline_metrics", "detail": str(exc)}, status=400
            )
            self._send(status, body, ctype)
            return
        if req.get("include_radio", True):
            payload["radio_bridge"] = render_radio_bridge(payload)
        if req.get("include_acta"):
            payload["acta_md"] = render_acta_md(payload)
        status, body, ctype = _json_bytes(payload)
        self._send(status, body, ctype)


def _default_http_sandbox() -> Path:
    """Empty temp sandbox for unauthenticated HTTP (never REPO_ROOT by default)."""
    return Path(tempfile.mkdtemp(prefix="wfd_decide_api_sandbox_"))


def _resolve_http_base_dir(base_dir: Path | None) -> Path:
    if base_dir is None:
        return _default_http_sandbox()
    resolved = Path(base_dir).resolve()
    try:
        if resolved == REPO_ROOT.resolve():
            warnings.warn(
                "decide HTTP base_dir is REPO_ROOT — every repository path is "
                "allowlisted on the unauthenticated API. Prefer an empty sandbox "
                "outside the repo for multi-tenant or exposed listeners.",
                UserWarning,
                stacklevel=3,
            )
    except OSError:
        pass
    return resolved


class DecideHTTPServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        *,
        base_dir: Path | None = None,
        verbose: bool = False,
    ) -> None:
        super().__init__(server_address, DecideHandler)
        # Default: empty temp sandbox. Explicit REPO_ROOT is allowed but warned.
        self.base_dir = _resolve_http_base_dir(base_dir)
        self.verbose = verbose


def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    base_dir: Path | None = None,
    verbose: bool = False,
) -> DecideHTTPServer:
    """Blocking serve (Ctrl+C to stop).

    Prefer an explicit ``base_dir`` sandbox. Default is a temp empty directory
    (not REPO_ROOT). ``base_dir=REPO_ROOT`` is insecure for exposed listeners.
    """
    httpd = DecideHTTPServer((host, port), base_dir=base_dir, verbose=verbose)
    print(
        f"decide API {API_VERSION} on http://{host}:{port}  "
        f"(POST /v1/decide · GET /health · base_dir={httpd.base_dir})",
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
