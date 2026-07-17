"""Minimal Decision Card HTTP API + decide_service tests."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from wildfire_front.product.api_server import start_background
from wildfire_front.product.decide_service import decide_from_request


def test_decide_service_empty_abstains():
    payload = decide_from_request({})
    assert payload["decision"] == "ABSTAIN"
    assert "latency_ms" in payload
    assert payload["api_version"] == "decide_api_v1"


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
