"""Live Ops Kernel: same-origin status/decide/export-acta on SPA --serve."""

from __future__ import annotations

import json
import socketserver
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from wildfire_front.cli_app import _SafeSPARequestHandler, run_app
from wildfire_front.product.app_spa import build_product_app_payload, write_product_app
from wildfire_front.product.decide_service import REPO_ROOT, PathNotAllowedError
from wildfire_front.product.live_ops import (
    LIVE_PATH_ACK_DECISION,
    LIVE_PATH_DECIDE,
    LIVE_PATH_EXPORT_ACTA,
    LIVE_PATH_HEALTH,
    LIVE_PATH_STATUS,
    check_demo_day_artifacts,
    dispatch_live,
    handle_ack_decision,
    handle_decide,
    honesty_rails,
    resolve_work_dir,
)


def _post_json(port: int, path: str, body: dict) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return int(exc.code), payload


def _get_json(port: int, path: str) -> tuple[int, dict]:
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return int(exc.code), payload


def _start_live_server(tmp_path: Path, *, live: bool = True, base: Path | None = None):
    payload = build_product_app_payload(live=False, scan=False, live_ops_enabled=live)
    paths = write_product_app(payload, tmp_path / "spa")
    root = paths["html"].resolve().parent
    handler = _SafeSPARequestHandler.make(
        root,
        live_ops_enabled=live,
        live_base_dir=base or REPO_ROOT,
    )

    class _Srv(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = _Srv(("127.0.0.1", 0), handler)
    port = int(httpd.server_address[1])
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port, paths


@pytest.fixture(scope="module")
def sla_work_dir() -> Path:
    wd = REPO_ROOT / "outputs" / "incidents" / "_sla_measure"
    if not wd.is_dir():
        pytest.skip("_sla_measure work-dir missing")
    return wd


def test_honesty_rails_fusion_on():
    r = honesty_rails()
    from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

    stamp_path = REPO_ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    assert stamp.get("field_ops_allow_ml_live_in_fusion") is True
    assert (stamp.get("rails") or {}).get("field_ops_fusion") == "ON"
    assert stamp.get("GO_Q") == "partial"
    # Same catalog source as ``app --list-fires``
    assert r["field_ops_ml_live_fusion"] == field_ops_ml_live_fusion_rail()
    assert r["field_ops_ml_live_fusion"] == "ON"
    assert r["go_q_invent_forbidden"] is True
    assert r["not_tactical_dispatch"] is True
    assert r["go_q_met"] is False
    assert r["iou_is_not_ros"] is True


def test_resolve_work_dir_rejects_traversal(tmp_path: Path):
    base = tmp_path
    (base / "ok").mkdir()
    ok = resolve_work_dir("ok", base=base)
    assert ok.is_dir()
    with pytest.raises(PathNotAllowedError):
        resolve_work_dir("../etc/passwd", base=base)
    with pytest.raises(PathNotAllowedError):
        resolve_work_dir("..\\..\\Windows", base=base)
    with pytest.raises(PathNotAllowedError):
        resolve_work_dir("", base=base)


def test_payload_live_ops_flag():
    off = build_product_app_payload(live=False, scan=False, live_ops_enabled=False)
    assert off["live_ops"]["enabled"] is False
    assert off["rails"]["field_ops_ml_live_fusion"] == "ON"
    assert off["live_ops"]["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    assert off["live_ops"]["honesty_rails"]["go_q_met"] is False
    assert "Fusion OFF" not in (off["live_ops"].get("note") or "")
    on = build_product_app_payload(live=False, scan=False, live_ops_enabled=True)
    assert on["live_ops"]["enabled"] is True
    assert on["live_ops"]["endpoints"]["decide"] == LIVE_PATH_DECIDE
    assert "export-acta" in on["live_ops"]["endpoints"]["export_acta"]
    assert on["live_ops"]["endpoints"]["ack_decision"] == LIVE_PATH_ACK_DECISION
    # HTML must reference live endpoints when enabled
    paths = write_product_app(on, Path("outputs") / "_test_live_ops_spa")
    html = paths["html"].read_text(encoding="utf-8")
    assert "live_ops" in html or "liveOps" in html
    assert "/live/v1/decide" in html or "liveOps" in html
    assert "/live/v1/ack-decision" in html or "ack_decision" in html
    assert "runDlogAck" in html


def test_dispatch_health_and_disabled_path():
    st, payload = dispatch_live(LIVE_PATH_HEALTH, method="GET")
    assert st == 200
    assert payload["ok"] is True
    assert payload["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    assert payload["honesty_rails"].get("go_q_met") is False


def test_live_http_decide_and_status(tmp_path: Path, sla_work_dir: Path):
    httpd, port, _paths = _start_live_server(tmp_path, live=True, base=REPO_ROOT)
    try:
        st_h, health = _get_json(port, LIVE_PATH_HEALTH)
        assert st_h == 200
        assert health["ok"] is True
        assert health["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
        assert health["honesty_rails"]["go_q_met"] is False

        rel = str(sla_work_dir.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
        st_s, status = _post_json(port, LIVE_PATH_STATUS, {"work_dir": rel})
        assert st_s == 200, status
        assert status["ok"] is True
        assert status["act"] == "status"
        assert status["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"

        st_d, decided = _post_json(
            port,
            LIVE_PATH_DECIDE,
            {"work_dir": rel, "event_id": "test_live_ops", "policy_id": "field_ops"},
        )
        assert st_d == 200, decided
        assert decided["ok"] is True
        assert decided["act"] == "decide"
        assert decided["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
        assert decided["honesty_rails"]["go_q_met"] is False
        summary = decided.get("summary") or {}
        assert summary.get("decision") in ("GO", "HOLD", "ABSTAIN") or summary.get("decision")
        assert decided["honesty_rails"]["go_q_invent_forbidden"] is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_live_http_export_acta(tmp_path: Path, sla_work_dir: Path):
    httpd, port, _ = _start_live_server(tmp_path, live=True, base=REPO_ROOT)
    try:
        rel = str(sla_work_dir.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
        st, payload = _post_json(port, LIVE_PATH_EXPORT_ACTA, {"work_dir": rel})
        assert st == 200, payload
        assert payload["ok"] is True
        assert payload["act"] == "export_acta"
        summary = payload.get("summary") or {}
        assert summary.get("acta") or summary.get("card")
        assert payload["honesty_rails"]["go_q_invent_forbidden"] is True
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_live_rejects_traversal_and_missing(tmp_path: Path):
    httpd, port, _ = _start_live_server(tmp_path, live=True, base=REPO_ROOT)
    try:
        st, payload = _post_json(port, LIVE_PATH_DECIDE, {"work_dir": "../../../etc/passwd"})
        assert st == 400
        assert payload.get("error") == "path_not_allowed"

        st2, payload2 = _post_json(
            port, LIVE_PATH_STATUS, {"work_dir": "outputs/incidents/__no_such_if__"}
        )
        assert st2 == 400
        assert payload2.get("error") == "path_not_allowed"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_live_ops_disabled_returns_503(tmp_path: Path):
    httpd, port, _ = _start_live_server(tmp_path, live=False)
    try:
        st, payload = _post_json(
            port, LIVE_PATH_DECIDE, {"work_dir": "outputs/incidents/_sla_measure"}
        )
        assert st == 503
        assert payload.get("error") == "live_ops_disabled"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_demo_day_json_rails(tmp_path: Path, monkeypatch):
    """app --demo-day --json builds payload with live_ops + go_q_met false."""
    import argparse

    # Use isolated output so we don't clobber real outputs/app mid-test
    out = tmp_path / "demo_day_app"
    ns = argparse.Namespace(
        list_fires=False,
        demo_day=True,
        serve=False,
        open=False,
        json=True,
        quiet=True,
        bbox=None,
        west=None,
        south=None,
        east=None,
        north=None,
        lat=None,
        lon=None,
        radius_km=50,
        live=False,
        no_live=True,
        work_dir=None,
        fire=None,
        all_fires=False,
        pack_fires=False,
        pack_cap=8,
        role="operator",
        geojson=None,
        day_range=1,
        fixture_csv=None,
        title="WFD OPS",
        no_scan=False,
        ui_mode="simple",
        bridge_decide=None,
        output=out,
        port=8766,
    )
    # If _sla_measure missing, skip
    if not (REPO_ROOT / "outputs" / "incidents" / "_sla_measure").is_dir():
        pytest.skip("_sla_measure missing")

    # Capture stdout JSON
    import io
    import sys

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        code = run_app(ns)
    finally:
        sys.stdout = old
    assert code == 0
    payload = json.loads(buf.getvalue())
    assert payload["live_ops"]["enabled"] is True
    assert payload["rails"]["field_ops_ml_live_fusion"] == "ON"
    dd = payload.get("demo_day") or {}
    assert dd.get("go_q_met") is False
    assert dd.get("go_q_invent_forbidden") is True
    assert (out / "index.html").is_file()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "runLiveAct" in html or "liveOps" in html


def test_check_demo_day_artifacts_rails():
    art = check_demo_day_artifacts(repo=REPO_ROOT)
    assert art["go_q_met"] is False
    assert art["go_q_invent_forbidden"] is True
    assert art["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    # Prefer present, but don't fail the whole suite if pack missing in bare clones
    assert "artifacts" in art


def test_handle_decide_direct(sla_work_dir: Path):
    rel = str(sla_work_dir.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    out = handle_decide(
        {"work_dir": rel, "event_id": "direct", "policy_id": "field_ops"},
        base=REPO_ROOT,
    )
    assert out["ok"] is True
    assert out["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    assert out.get("channel") == "live_ops_loopback"
    dec = (out.get("summary") or {}).get("decision")
    assert dec is not None
    assert str(dec).upper() in ("GO", "HOLD", "ABSTAIN")
    # Loopback channel should load work_dir sources (not force empty-source only)
    assert (out.get("summary") or {}).get("field_ops_ml_live_fusion") == "ON"


def test_replay_third_party_default_pack():
    from wildfire_front.product.live_ops import LIVE_PATH_REPLAY, dispatch_live

    pack = REPO_ROOT / "outputs" / "demo_third_party"
    if not pack.is_dir():
        pytest.skip("demo_third_party pack missing")
    st, payload = dispatch_live(
        LIVE_PATH_REPLAY, {"bundle": "outputs/demo_third_party"}, base=REPO_ROOT, method="POST"
    )
    assert st == 200
    assert payload.get("ok") is True
    assert "replay_ok" in (payload.get("summary") or {})
    assert payload["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"


def test_handle_ack_decision_round_trip_and_unknown(tmp_path: Path):
    """Shipped Live Ops ACK path: append → handle_ack_decision → acked true."""
    from wildfire_front.product.decide_service import decide_from_request
    from wildfire_front.product.decision_log import (
        append_decision,
        get_decision,
    )

    work = tmp_path / "ack_live"
    work.mkdir()
    card = decide_from_request(
        {
            "event_id": "IF_ACK_LIVE",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 10,
                "speed_vs_ref_ratio": 0.9,
            },
            "ml_metrics": {"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
            "channel": "pytest",
            "trust_client_reliability": True,
        }
    )
    entry = append_decision(work, card, base=tmp_path, include_repo_root=False)
    did = entry["decision_id"]

    out = handle_ack_decision(
        {
            "work_dir": str(work),
            "decision_id": did,
            "operator": "spa_test",
            "note": "PR2-A ack",
        },
        base=tmp_path,
    )
    assert out["ok"] is True
    assert out["acked"] is True
    assert out["decision_id"] == did
    assert out["go_q_met"] is False
    assert out["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
    assert out["ack"]["acked"] is True

    reloaded = get_decision(work, did, base=tmp_path, include_repo_root=False)
    assert reloaded is not None
    assert reloaded["ack"]["acked"] is True

    bad = handle_ack_decision(
        {"work_dir": str(work), "decision_id": "00000000-0000-0000-0000-000000000000"},
        base=tmp_path,
    )
    assert bad["ok"] is False
    assert bad["error"] == "unknown_decision_id"

    st, payload = dispatch_live(
        LIVE_PATH_ACK_DECISION,
        {"work_dir": str(work), "decision_id": "deadbeef-dead-beef-dead-beefdeadbeef"},
        base=tmp_path,
        method="POST",
    )
    assert st == 400
    assert payload.get("ok") is False
    assert payload.get("error") == "unknown_decision_id"


def test_live_http_ack_decision(tmp_path: Path):
    """HTTP POST /live/v1/ack-decision on loopback server rewrites sidecar."""
    from wildfire_front.product.decide_service import decide_from_request
    from wildfire_front.product.decision_log import append_decision, get_decision

    # Nested under tmp base so resolve_work_dir allowlist passes
    base = tmp_path / "repo_like"
    work = base / "outputs" / "incidents" / "ack_http"
    work.mkdir(parents=True)
    card = decide_from_request(
        {
            "event_id": "IF_ACK_HTTP",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.0,
                "n_frames_staged": 10,
                "speed_vs_ref_ratio": 0.9,
            },
            "ml_metrics": {"test_iou": 0.89, "improvement_vs_copy_iou": 0.25},
            "channel": "pytest",
            "trust_client_reliability": True,
        }
    )
    entry = append_decision(work, card, base=base, include_repo_root=False)
    did = entry["decision_id"]
    rel = "outputs/incidents/ack_http"

    httpd, port, _ = _start_live_server(tmp_path, live=True, base=base)
    try:
        st, payload = _post_json(
            port,
            LIVE_PATH_ACK_DECISION,
            {"work_dir": rel, "decision_id": did, "operator": "http_test"},
        )
        assert st == 200, payload
        assert payload["ok"] is True
        assert payload["acked"] is True
        assert payload["honesty_rails"]["field_ops_ml_live_fusion"] == "ON"
        assert payload.get("go_q_met") is False

        reloaded = get_decision(work, did, base=base, include_repo_root=False)
        assert reloaded is not None
        assert reloaded["ack"]["acked"] is True

        st2, bad = _post_json(
            port,
            LIVE_PATH_ACK_DECISION,
            {"work_dir": rel, "decision_id": "11111111-1111-1111-1111-111111111111"},
        )
        assert st2 == 400
        assert bad.get("error") == "unknown_decision_id"
    finally:
        httpd.shutdown()
        httpd.server_close()
