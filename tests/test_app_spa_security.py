"""SPA / serve security rails: loopback-only bridge, path traversal, bind host."""

from __future__ import annotations

import http.client
import http.server
import json
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

from wildfire_front.cli_app import (
    _SafeSPARequestHandler,
    _serve_static_spa,
    resolve_safe_spa_path,
)
from wildfire_front.product.app_spa import (
    build_product_app_payload,
    is_loopback_http_url,
    write_product_app,
)


def _start_handler(root: Path, *, bridge_upstream: str | None = None):
    """Bind 127.0.0.1:0, return (httpd, port, shutdown_callable)."""
    handler = _SafeSPARequestHandler.make(root, bridge_upstream=bridge_upstream)

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Srv(("127.0.0.1", 0), handler)
    port = int(httpd.server_address[1])
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def test_is_loopback_rejects_prefix_and_userinfo():
    assert is_loopback_http_url("http://127.0.0.1:1") is True
    assert is_loopback_http_url("http://localhost/v1") is True
    ipv6 = "http://[" + "::1" + "]"
    assert is_loopback_http_url(ipv6) is True
    # Evil suffix / DNS rebinding style
    assert is_loopback_http_url("http://127.0.0.1.nip.io") is False
    assert is_loopback_http_url("http://127.0.0.1.evil.com") is False
    assert is_loopback_http_url("http://localhost.evil.com") is False
    # Userinfo tricks (hostname is evil.example, not 127.0.0.1)
    assert is_loopback_http_url("http://127.0.0.1@evil.example/") is False
    assert is_loopback_http_url("http://user@127.0.0.1/") is True  # host still loopback
    assert is_loopback_http_url("https://evil.example/path?h=127.0.0.1") is False


def test_bridge_decide_strips_non_loopback_urls():
    """build_product_app_payload keeps only exact loopback bridge URLs."""
    for bad in (
        "http://evil.example/v1",
        "http://127.0.0.1.evil.example",
        "http://10.0.0.5:8765",
        "http://0.0.0.0:8765",
    ):
        p = build_product_app_payload(live=False, scan=False, bridge_decide=bad)
        bd = p["bridge_decide"]
        assert bd["enabled"] is False, bad
        assert bd["url"] is None, bad
        assert bd["proxy_path"] is None, bad

    p_ok = build_product_app_payload(
        live=False, scan=False, bridge_decide="http://127.0.0.1:8765/extra"
    )
    assert p_ok["bridge_decide"]["enabled"] is True
    assert p_ok["bridge_decide"]["url"] == "http://127.0.0.1:8765/extra"
    assert p_ok["bridge_decide"]["proxy_path"] == "/bridge/v1/decide"
    assert p_ok["bridge_decide"]["prefer_proxy"] is True
    # Honesty rails never flip with bridge
    assert p_ok["rails"]["field_ops_ml_live_fusion"] == "ON"
    assert p_ok["rails"]["go_q_invent_forbidden"] is True
    assert p_ok["rails"]["not_tactical_dispatch"] is True
    assert p_ok["brief"]["gates"].get("GO_Q") is not True


def test_serve_exit_codes_missing_and_non_loopback(tmp_path: Path):
    """_serve_static_spa returns exit 2 on missing SPA dir / non-loopback host."""
    missing = tmp_path / "nope" / "index.html"
    code_missing = _serve_static_spa(
        missing, port=0, open_browser=False, quiet=True
    )
    assert code_missing == 2

    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "spa")
    for host in ("0.0.0.0", "192.168.1.10", "example.com"):
        code = _serve_static_spa(
            paths["html"],
            port=0,
            open_browser=False,
            quiet=True,
            host=host,
        )
        assert code == 2, f"expected exit 2 for host={host}, got {code}"


def test_handler_path_traversal_403_and_loopback_200(tmp_path: Path):
    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "served")
    root = paths["html"].resolve().parent
    result: dict[str, object] = {}

    httpd, port = _start_handler(root)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            result["status"] = resp.status
            result["shell"] = "#0B1220" in body and "primary-acts" in body
            result["fusion_off"] = '"field_ops_ml_live_fusion": "ON"' in body
        for trav in (
            "/../../pyproject.toml",
            "/..%2F..%2Fpyproject.toml",
            "/foo/../../../pyproject.toml",
        ):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}{trav}", timeout=3)
                result[trav] = 200
            except urllib.error.HTTPError as exc:
                result[trav] = exc.code
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert result["status"] == 200
    assert result["shell"] is True
    assert result["fusion_off"] is True
    for trav in (
        "/../../pyproject.toml",
        "/..%2F..%2Fpyproject.toml",
        "/foo/../../../pyproject.toml",
    ):
        assert result[trav] == 403, f"{trav} → {result[trav]}"

    assert resolve_safe_spa_path(root, "/") is not None
    assert resolve_safe_spa_path(root, "/index.html") is not None
    assert resolve_safe_spa_path(root, "/../secrets") is None
    assert resolve_safe_spa_path(root, "/..%2Fetc/passwd") is None
    # Null-byte path blocked (handler + unit helper)
    assert resolve_safe_spa_path(root, "/index.html\x00.png") is None


def test_bridge_proxy_503_when_not_configured(tmp_path: Path):
    """POST /bridge/v1/decide without upstream → 503, not open proxy."""
    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "no_bridge")
    root = paths["html"].resolve().parent
    got: dict[str, object] = {}

    httpd, port = _start_handler(root)
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/bridge/v1/decide",
            data=b'{"policy_id":"field_ops"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            got["code"] = 200
        except urllib.error.HTTPError as exc:
            got["code"] = exc.code
            got["body"] = exc.read().decode("utf-8", errors="replace")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert got["code"] == 503
    body = json.loads(str(got.get("body") or "{}"))
    assert body.get("error") == "bridge_not_configured"


def test_handler_strips_non_loopback_bridge_upstream(tmp_path: Path):
    """Non-loopback bridge_upstream is ignored at handler factory (no open SSRF)."""
    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "ssrf")
    root = paths["html"].resolve().parent
    got: dict[str, object] = {}

    httpd, port = _start_handler(root, bridge_upstream="http://evil.example:9999")
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/bridge/v1/decide",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=3)
            got["code"] = 200
        except urllib.error.HTTPError as exc:
            got["code"] = exc.code
            got["body"] = exc.read().decode("utf-8", errors="replace")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert got["code"] == 503
    assert "bridge_not_configured" in str(got.get("body") or "")


def test_bridge_proxy_502_upstream_unreachable(tmp_path: Path):
    """Configured loopback upstream that is down → 502 bridge_upstream_unreachable."""
    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "up_down")
    root = paths["html"].resolve().parent

    # Reserve a free port then do not listen — connection refused
    class _Tmp(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with _Tmp(("127.0.0.1", 0), http.server.BaseHTTPRequestHandler) as tmp:
        closed_port = int(tmp.server_address[1])
    # tmp closed → nothing listening

    got: dict[str, object] = {}
    httpd, port = _start_handler(
        root, bridge_upstream=f"http://127.0.0.1:{closed_port}"
    )
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/bridge/v1/decide",
            data=b'{"policy_id":"field_ops"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            got["code"] = 200
        except urllib.error.HTTPError as exc:
            got["code"] = exc.code
            got["body"] = exc.read().decode("utf-8", errors="replace")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert got["code"] == 502
    body = json.loads(str(got.get("body") or "{}"))
    assert body.get("error") == "bridge_upstream_unreachable"


def test_bridge_proxy_413_body_too_large(tmp_path: Path):
    """Content-Length > 2_000_000 → 413 body_too_large (checked before read)."""
    payload = build_product_app_payload(live=False, scan=False)
    paths = write_product_app(payload, tmp_path / "big_body")
    root = paths["html"].resolve().parent

    # Upstream not required — 413 is local
    httpd, port = _start_handler(root, bridge_upstream="http://127.0.0.1:1")
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        conn.putrequest("POST", "/bridge/v1/decide")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", "2000001")
        conn.endheaders()
        # Do not send 2MB; handler rejects on header before full read
        conn.send(b"{}")
        resp = conn.getresponse()
        body = resp.read().decode("utf-8", errors="replace")
        code = resp.status
        conn.close()
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert code == 413
    data = json.loads(body or "{}")
    assert data.get("error") == "body_too_large"


def test_payload_rails_honesty_invariant():
    """build_product_app_payload always emits industrial honesty rails."""
    p = build_product_app_payload(live=False, scan=False)
    rails = p["rails"]
    assert rails["field_ops_ml_live_fusion"] == "ON"
    assert rails["lab_go_ne_field_fusion"] is True
    assert rails["go_q_invent_forbidden"] is True
    assert rails["not_tactical_dispatch"] is True
    assert p["brief"]["gates"].get("GO_Q") is not True
    assert "Not validated tactical dispatch" in p["disclaimer"]
