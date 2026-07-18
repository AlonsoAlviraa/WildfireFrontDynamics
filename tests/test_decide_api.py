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
        body = json.dumps(
            {"event_id": "evil", "work_dir": "../../../etc/passwd"}
        ).encode("utf-8")
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
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        # Advertise oversized Content-Length without sending full body
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(MAX_BODY_BYTES + 10),
            },
            method="POST",
        )
        # urllib may recompute Content-Length from data; force via custom handler
        class _LenOverride(urllib.request.Request):
            pass

        # Use raw connection-style: set header after body so server sees big length
        # BaseHTTPRequestHandler trusts Content-Length header first.
        try:
            urllib.request.urlopen(req, timeout=5)
            # If urllib rewrote Content-Length to 2, re-try with a fat body
        except urllib.error.HTTPError as exc:
            if exc.code == 413:
                detail = json.loads(exc.read().decode("utf-8"))
                assert detail.get("error") == "body_too_large"
                return
        fat = b"{" + b'"x":"' + (b"a" * (MAX_BODY_BYTES + 100)) + b'"}'
        req2 = urllib.request.Request(
            f"{base}/v1/decide",
            data=fat,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req2, timeout=5)
            assert False, "expected HTTPError 413"
        except urllib.error.HTTPError as exc:
            assert exc.code == 413
            detail = json.loads(exc.read().decode("utf-8"))
            assert detail.get("error") == "body_too_large"
    finally:
        httpd.shutdown()
        httpd.server_close()
