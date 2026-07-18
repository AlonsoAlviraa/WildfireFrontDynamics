"""Minimal Decision Card HTTP API + decide_service tests."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from wildfire_front.product.api_server import start_background
from wildfire_front.product.decide_service import (
    MAX_BODY_BYTES,
    PathNotAllowedError,
    _as_path,
    decide_from_request,
)


def test_decide_service_empty_abstains():
    payload = decide_from_request({})
    assert payload["decision"] == "ABSTAIN"
    assert "latency_ms" in payload
    assert payload["api_version"] == "decide_api_v1"
    # Honesty: no hard-coded reliability PASS on empty decide
    assert payload.get("system_reliability_pass") is False


def test_decide_service_inline_ops_can_go_or_hold():
    payload = decide_from_request(
        {
            "event_id": "t",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 10,
                "speed_vs_ref_ratio": 0.9,
            },
            "ml_metrics": {"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
        }
    )
    assert payload["decision"] in ("GO", "HOLD")
    assert payload["confidence_pred"] >= 0.4
    assert payload["latency_ms"] < 500
    assert payload.get("system_reliability_pass") is False


def test_http_api_health_and_decide(tmp_path: Path):
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8"))
        assert health["ok"] is True

        with urllib.request.urlopen(f"{base}/v1/openapi.json", timeout=5) as resp:
            oa = json.loads(resp.read().decode("utf-8"))
        assert "/v1/decide" in oa["paths"]

        body = json.dumps({"event_id": "empty"}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        assert card["decision"] == "ABSTAIN"
        assert "audit" in card
        assert isinstance(card.get("latency_ms"), (int, float))
        assert card.get("system_reliability_pass") is False
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_api_invalid_json():
    httpd, _thread, port = start_background(host="127.0.0.1", port=0)
    base = f"http://127.0.0.1:{port}"
    try:
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=b"not-json",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            detail = json.loads(exc.read().decode("utf-8"))
            assert detail.get("error") == "invalid_json"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_as_path_rejects_traversal(tmp_path: Path):
    """Path allowlist: ../ and absolute outside base/REPO_ROOT rejected."""
    base = tmp_path / "sandbox"
    base.mkdir()
    (base / "ok_pack").mkdir()
    # relative under base is fine
    ok = _as_path("ok_pack", base=base)
    assert ok is not None
    assert ok == (base / "ok_pack").resolve()

    with pytest.raises(PathNotAllowedError):
        _as_path("../../../Windows/System32", base=base)

    with pytest.raises(PathNotAllowedError):
        _as_path("..", base=base)

    # Absolute path outside allow roots
    outside = Path.cwd().anchor  # drive root on Windows, / on POSIX
    with pytest.raises(PathNotAllowedError):
        _as_path(outside, base=base)


def test_decide_service_path_traversal_rejected(tmp_path: Path):
    with pytest.raises(PathNotAllowedError):
        decide_from_request(
            {"event_id": "evil", "work_dir": "../../../etc/passwd"},
            base=tmp_path,
        )
    with pytest.raises(PathNotAllowedError):
        decide_from_request(
            {"event_id": "evil", "open_pack": str(Path(tmp_path.anchor) / "nope")},
            base=tmp_path,
        )


def test_http_api_path_traversal_400(tmp_path: Path):
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps({"event_id": "evil", "work_dir": "../../../etc/passwd"}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected HTTPError"
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            detail = json.loads(exc.read().decode("utf-8"))
            assert detail.get("error") == "path_not_allowed"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_api_body_too_large(tmp_path: Path):
    """413 via Content-Length pre-check (no multi-MiB send — Windows-safe)."""
    import socket

    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    try:
        # Server rejects before reading body when Content-Length > MAX_BODY_BYTES.
        # Raw socket avoids urllib/Windows ConnectionAbortedError on fat bodies.
        oversized = MAX_BODY_BYTES + 1
        req = (
            f"POST /v1/decide HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{port}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {oversized}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode("ascii")
        with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
            sock.sendall(req)
            # Do not send the declared body; server should 413 from header alone.
            chunks: list[bytes] = []
            while True:
                try:
                    data = sock.recv(4096)
                except OSError:
                    break
                if not data:
                    break
                chunks.append(data)
        raw = b"".join(chunks)
        assert raw, "expected HTTP response"
        status_line = raw.split(b"\r\n", 1)[0].decode("latin-1", errors="replace")
        assert "413" in status_line, f"expected 413, got {status_line!r}"
        # Body after headers
        if b"\r\n\r\n" in raw:
            body = raw.split(b"\r\n\r\n", 1)[1]
            try:
                detail = json.loads(body.decode("utf-8"))
                assert detail.get("error") == "body_too_large"
            except (UnicodeDecodeError, json.JSONDecodeError):
                assert b"body_too_large" in body
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_string_false_gate_flags_not_true():
    """_opt_bool must not treat string 'false' as True."""
    payload = decide_from_request(
        {
            "event_id": "str_bool",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 12,
                "speed_vs_ref_ratio": 0.9,
            },
            "ml_metrics": {"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
            "gates_ok": "false",
            "determinism_ok": "false",
            "abstention_enforced": "true",
            "provenance_ok": "0",
            "channel": "decide_service",
        }
    )
    assert payload["system_reliability_pass"] is False
    checks = (payload.get("audit") or {}).get("system_reliability", {}).get("checks") or {}
    # Strings ignored → unmeasured, not True
    assert checks.get("R1_determinism") is not True
    assert checks.get("R2_gates") is not True


def test_reliability_gate_path_outside_allowlist_rejected(tmp_path: Path):
    """reliability_gate absolute path outside base/REPO_ROOT raises."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    # Drive-root path is outside sandbox and (typically) REPO_ROOT.
    evil = Path(tmp_path.anchor) / "wfd_gate_not_allowed.json"
    with pytest.raises(PathNotAllowedError):
        decide_from_request(
            {
                "event_id": "gate_escape",
                "reliability_gate": str(evil),
                "channel": "decide_service",
            },
            base=sandbox,
        )


def test_http_ignores_client_asserted_gates(tmp_path: Path):
    """HTTP cannot self-assert gates to defeat field_ops fail-closed."""
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps(
            {
                "event_id": "http_self_cert",
                "policy_id": "field_ops",
                "ops_metrics": {
                    "quality_grade": "A",
                    "primary_ros_m_min": 6.0,
                    "n_frames_staged": 20,
                    "speed_vs_ref_ratio": 0.9,
                    "area_ha_max": 50,
                },
                "open_metrics": {"max_area_ha": 2000, "n_timeline_steps": 5},
                "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
                "gates_ok": True,
                "determinism_ok": True,
                "abstention_enforced": True,
                "provenance_ok": True,
                "reliability_gate": {"ok": True},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        assert card.get("system_reliability_pass") is False
        assert card["decision"] == "ABSTAIN"
        assert any("fail_closed" in r for r in (card.get("reasons") or []))
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_reliability_gate_allowlisted_file_ok(tmp_path: Path):
    """HTTP may load reliability from a sandbox path with full checks + event_id."""
    report = {
        "ok": True,
        "event_id": "http_gate_file",
        "suite_only": False,
        "field_unlock": True,
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    gate_path = tmp_path / "RELIABILITY_GATE_REPORT.json"
    gate_path.write_text(json.dumps(report), encoding="utf-8")
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps(
            {
                "event_id": "http_gate_file",
                "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
                "reliability_gate": "RELIABILITY_GATE_REPORT.json",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        assert card.get("system_reliability_pass") is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_rejects_repo_docs_reliability_gate(tmp_path: Path):
    """HTTP with base_dir=tmp_path must not load docs/RELIABILITY_GATE_REPORT.json."""
    from wildfire_front.product.decide_service import REPO_ROOT

    docs_gate = REPO_ROOT / "docs" / "RELIABILITY_GATE_REPORT.json"
    assert docs_gate.is_file(), "checked-in docs sample must exist"

    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        # Absolute path under REPO_ROOT docs/ must be rejected (sandbox isolation).
        body = json.dumps(
            {
                "event_id": "http_docs_escape",
                "reliability_gate": str(docs_gate),
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req, timeout=5)
            raise AssertionError("expected HTTPError for docs gate path")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            detail = json.loads(exc.read().decode("utf-8"))
            assert detail.get("error") == "path_not_allowed"

        # Relative repo-style path also cannot resolve under sandbox base.
        body2 = json.dumps(
            {
                "event_id": "http_docs_rel",
                "reliability_gate": "docs/RELIABILITY_GATE_REPORT.json",
            }
        ).encode("utf-8")
        req2 = urllib.request.Request(
            f"{base}/v1/decide",
            data=body2,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        # Missing/unresolvable gate → no reliability PASS (not repo docs load).
        assert card.get("system_reliability_pass") is False
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_client_reliability_bools_require_allowlisted_channel():
    """Free-floating gates_ok only with trust_client_reliability + test channel."""
    strong = {
        "event_id": "bools",
        "ops_metrics": {
            "quality_grade": "A",
            "primary_ros_m_min": 6.0,
            "n_frames_staged": 20,
            "speed_vs_ref_ratio": 0.9,
            "area_ha_max": 50,
        },
        "open_metrics": {"max_area_ha": 2000, "n_timeline_steps": 5},
        "gates_ok": True,
        "determinism_ok": True,
        "abstention_enforced": True,
        "provenance_ok": True,
        "policy_id": "field_ops",
    }
    # Default decide_service channel: booleans ignored
    denied = decide_from_request({**strong, "channel": "decide_service"})
    assert denied.get("system_reliability_pass") is False
    # Explicit trust without allowlisted channel: still denied
    denied2 = decide_from_request(
        {**strong, "channel": "decide_service"},
        trust_client_reliability=True,
    )
    assert denied2.get("system_reliability_pass") is False
    # Test channel + trust: accepted
    ok = decide_from_request(
        {**strong, "channel": "test"},
        trust_client_reliability=True,
    )
    assert ok.get("system_reliability_pass") is True
