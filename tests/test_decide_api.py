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
    UntrustedInlineMetricsError,
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


def test_http_surface_flags_catalog_card(tmp_path: Path):
    outbox = tmp_path / "inc" / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "fire_decision_card.json").write_text(
        json.dumps(
            {
                "event_id": "http_card",
                "decision": "HOLD",
                "confidence_pred": 0.4,
                "system_reliability_pass": False,
            }
        ),
        encoding="utf-8",
    )
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        with urllib.request.urlopen(f"{base}/v1/flags", timeout=5) as resp:
            flags = json.loads(resp.read().decode("utf-8"))
        assert flags["ok"] is True
        assert str(flags["GO_Q"]).lower() == "partial"
        with urllib.request.urlopen(f"{base}/v1/catalog", timeout=5) as resp:
            catalog = json.loads(resp.read().decode("utf-8"))
        assert "rcda_net" in catalog["not_ready_ids"]
        with urllib.request.urlopen(f"{base}/v1/card?work_dir=inc", timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        assert card["ok"] is True
        assert card["summary"]["decision"] == "HOLD"
        with urllib.request.urlopen(f"{base}/v1/status?work_dir=inc", timeout=5) as resp:
            status = json.loads(resp.read().decode("utf-8"))
        assert status.get("ok") is True
        with urllib.request.urlopen(f"{base}/v1/snapshot?work_dir=inc", timeout=5) as resp:
            snap = json.loads(resp.read().decode("utf-8"))
        assert snap["ok"] is True
        assert snap["decision"] == "HOLD"
        assert "ops" in snap["source_board"]
        assert snap["rails"]["not_tactical_dispatch"] is True
        cmp_body = json.dumps({"work_dir": "inc"}).encode("utf-8")
        cmp_req = urllib.request.Request(
            f"{base}/v1/compare",
            data=cmp_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(cmp_req, timeout=5) as resp:
            cmp = json.loads(resp.read().decode("utf-8"))
        assert cmp["ok"] is True
        assert cmp["flipped"] is False
        assert cmp["alert"]["delivered"] is False
        save_req = urllib.request.Request(
            f"{base}/v1/snapshot",
            data=json.dumps({"work_dir": "inc", "save": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(save_req, timeout=5) as resp:
            saved = json.loads(resp.read().decode("utf-8"))
        assert saved["saved"] is True
        assert (tmp_path / "inc" / "outbox" / "incident_snapshot.json").is_file()
        with urllib.request.urlopen(f"{base}/", timeout=5) as resp:
            root = json.loads(resp.read().decode("utf-8"))
        assert any("flags" in item for item in root["endpoints"])
        assert any("snapshot" in item for item in root["endpoints"])
    finally:
        httpd.shutdown()
        httpd.server_close()


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


def test_http_auth_headers_cannot_unlock_field_ops(tmp_path: Path):
    """Authorization / token headers must not bypass field_ops fail-closed."""
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        body = json.dumps(
            {
                "event_id": "http_token",
                "policy_id": "field_ops",
                "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
                "gates_ok": True,
                "determinism_ok": True,
                "abstention_enforced": True,
                "provenance_ok": True,
                "trust_client_reliability": True,
                "channel": "test",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/v1/decide",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer supersecret",
                "X-WFD-Token": "supersecret",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            card = json.loads(resp.read().decode("utf-8"))
        assert card.get("policy_id") == "field_ops"
        assert card.get("system_reliability_pass") is False
        assert card["decision"] != "GO"
        assert card["decision"] == "ABSTAIN"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_ignores_client_asserted_gates(tmp_path: Path):
    """HTTP cannot self-assert gates to defeat field_ops fail-closed.

    Inline ops/open metrics are rejected (A2); free-floating gate bools also ignored.
    File-based gate only under sandbox still cannot invent ops quality.
    """
    httpd, _thread, port = start_background(host="127.0.0.1", port=0, base_dir=tmp_path)
    base = f"http://127.0.0.1:{port}"
    try:
        # A2: inline ops_metrics on HTTP must be rejected (not silently fused).
        body_inline = json.dumps(
            {
                "event_id": "http_self_cert_inline",
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
            }
        ).encode("utf-8")
        req_inline = urllib.request.Request(
            f"{base}/v1/decide",
            data=body_inline,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(req_inline, timeout=5)
            raise AssertionError("expected HTTPError for inline ops on http_api")
        except urllib.error.HTTPError as exc:
            assert exc.code == 400
            detail = json.loads(exc.read().decode("utf-8"))
            assert detail.get("error") == "untrusted_inline_metrics"

        # Without inline ops: free-floating gates + inline reliability still fail-closed.
        body = json.dumps(
            {
                "event_id": "http_self_cert",
                "policy_id": "field_ops",
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


def test_untrusted_without_base_fails_closed_on_repo_paths():
    """include_repo_root=False + base=None must not fall back to REPO_ROOT."""
    from wildfire_front.product.decide_service import REPO_ROOT

    docs_gate = REPO_ROOT / "docs" / "RELIABILITY_GATE_REPORT.json"
    with pytest.raises(PathNotAllowedError):
        decide_from_request(
            {
                "event_id": "no_base",
                "channel": "http_api",
                "reliability_gate": str(docs_gate),
            },
            base=None,
            trust_client_reliability=False,
        )


def test_http_default_base_is_not_repo_root():
    """Unauthenticated server defaults to a temp sandbox, not REPO_ROOT."""
    from wildfire_front.product.api_server import DecideHTTPServer
    from wildfire_front.product.decide_service import REPO_ROOT

    httpd, _thread, _port = start_background(host="127.0.0.1", port=0)
    try:
        assert isinstance(httpd, DecideHTTPServer)
        assert httpd.base_dir.resolve() != REPO_ROOT.resolve()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_http_api_rejects_inline_ops_metrics():
    """A2: channel=http_api must refuse inline ops_metrics dicts."""
    with pytest.raises(UntrustedInlineMetricsError, match="ops_metrics"):
        decide_from_request(
            {
                "event_id": "a2_ops",
                "channel": "http_api",
                "ops_metrics": {
                    "quality_grade": "A",
                    "primary_ros_m_min": 5.0,
                    "n_frames_staged": 10,
                },
            },
            trust_client_reliability=False,
        )


def test_http_api_rejects_inline_open_metrics():
    """A2: channel=http_api must refuse inline open_metrics dicts."""
    with pytest.raises(UntrustedInlineMetricsError, match="open_metrics"):
        decide_from_request(
            {
                "event_id": "a2_open",
                "channel": "http_api",
                "open_metrics": {"max_area_ha": 1000, "n_timeline_steps": 3},
            },
            trust_client_reliability=False,
        )


def test_cli_channel_still_allows_inline_ops():
    """A2: trusted CLI/default channel may pass inline ops for tests/CLI."""
    payload = decide_from_request(
        {
            "event_id": "a2_cli",
            "channel": "decide_service",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 10,
                "speed_vs_ref_ratio": 0.9,
            },
        }
    )
    assert payload["decision"] in ("GO", "HOLD", "ABSTAIN")
    ops_src = next(s for s in payload["sources"] if s.get("id") == "ops_thermal_front")
    assert ops_src.get("available") is True


def test_normalize_ml_live_does_not_invent_schema():
    """A5: thin confidence+diag wrapper must not invent schema ml_live_metrics_v1."""
    from wildfire_front.product.decide_service import _normalize_ml_live_payload

    thin = {
        "confidence": 0.8,
        "mean_entropy": 0.1,
        "member_disagreement": 0.05,
        "mean_margin": 0.3,
    }
    out = _normalize_ml_live_payload(thin)
    assert out.get("schema") != "ml_live_metrics_v1"
    assert "schema" not in out or out.get("schema") is None

    proper = {
        "schema": "ml_live_metrics_v1",
        "confidence": 0.8,
        "mean_entropy": 0.1,
        "member_disagreement": 0.05,
        "mean_margin": 0.3,
    }
    assert _normalize_ml_live_payload(proper)["schema"] == "ml_live_metrics_v1"

    nested = {
        "schema": "ml_prediction_v1",
        "ml_live_metrics": {
            "schema": "ml_live_metrics_v1",
            "confidence": 0.7,
            "mean_entropy": 0.1,
            "member_disagreement": 0.05,
            "mean_margin": 0.3,
        },
    }
    assert _normalize_ml_live_payload(nested)["schema"] == "ml_live_metrics_v1"


def test_load_infocam_anchor_fails_closed_outside_allowlist(tmp_path: Path):
    """A6: PathNotAllowedError must not fall through to arbitrary filesystem."""
    from wildfire_front.product.decide_service import load_infocam_anchor

    # Absolute path outside sandbox + no repo root → refuse (return None)
    evil = Path(tmp_path.anchor) / "wfd_anchors_not_allowed.json"
    assert (
        load_infocam_anchor(evil, "tobarra_20240802", base=tmp_path, include_repo_root=False)
        is None
    )
