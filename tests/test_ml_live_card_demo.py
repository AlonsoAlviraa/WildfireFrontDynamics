"""Offline tests for Sprint 1 ML live → Decision Card demo (no weights)."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_ml_live_card_demo.py"
FIXTURE_HOLD = ROOT / "tests" / "fixtures" / "ml" / "ml_prediction_hold.json"


def _load_demo_mod():
    spec = importlib.util.spec_from_file_location("run_ml_live_card_demo", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _live_source(card: dict) -> dict:
    for s in card.get("sources") or []:
        if s.get("id") in {"ml_live_reliability", "ml_live"}:
            return s
    raise AssertionError("ml_live_reliability source missing from card.sources")


def test_offline_hold_produces_hold_card(tmp_path: Path):
    mod = _load_demo_mod()
    summary = mod.run_demo(
        mode="offline",
        scenario="hold",
        out_dir=tmp_path,
        event_id="test_hold",
        policy_id="research_open",
    )
    assert summary["decision"] == "HOLD"
    assert summary["confidence_pred"] > 0.4
    card_path = tmp_path / "decision_card.json"
    pred_path = tmp_path / "ml_prediction.json"
    assert card_path.is_file()
    assert pred_path.is_file()
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert card["decision"] == "HOLD"
    assert card.get("disclaimers")
    assert card.get("reasons")
    metrics = card.get("metrics") or {}
    assert metrics.get("live_ok") is True
    assert metrics.get("live_available") is True
    # research_open: experimental fusion may weight live; live_ok is orthogonal to weight
    assert metrics.get("allow_ml_live_in_fusion") is True
    live_src = _live_source(card)
    assert live_src.get("available") is True
    assert live_src.get("abstained") is False
    assert live_src.get("actionable") is True
    assert float(live_src.get("weight") or 0.0) > 0.0  # fusion ON under research_open
    # dual-product: no invented ROS keys on live metrics
    live = metrics.get("ml_live") or {}
    live_blob = json.dumps(live)
    assert "primary_ros_m_min" not in live_blob
    assert "ros_m_min" not in live_blob
    # HOLD note: ECE residual in lab_context, not "prefer ABSTAIN" in reasons
    note = json.loads((tmp_path / "abstain_ece_note.json").read_text(encoding="utf-8"))
    assert "lab_context" in note
    prefer = [r for r in (note.get("reasons") or []) if "prefer ABSTAIN" in r]
    assert prefer == []


def test_offline_abstain_and_identity(tmp_path: Path):
    mod = _load_demo_mod()
    ab = mod.run_demo(
        mode="offline",
        scenario="abstain",
        out_dir=tmp_path / "ab",
        event_id="test_ab",
        policy_id="research_open",
    )
    assert ab["decision"] == "ABSTAIN"
    assert ab["confidence_pred"] == 0.0
    card_ab = json.loads((tmp_path / "ab" / "decision_card.json").read_text(encoding="utf-8"))
    metrics_ab = card_ab.get("metrics") or {}
    assert metrics_ab.get("live_available") is True
    assert metrics_ab.get("live_ok") is False
    live_ab = _live_source(card_ab)
    assert live_ab.get("available") is True
    assert live_ab.get("abstained") is True
    assert live_ab.get("actionable") is False
    assert float(live_ab.get("weight") or 0.0) == 0.0

    note_ab = json.loads((tmp_path / "ab" / "abstain_ece_note.json").read_text(encoding="utf-8"))
    reasons_ab = " ".join(note_ab.get("reasons") or [])
    assert "Explicit live abstain" in reasons_ab
    assert "ml_live_abstain_below" in reasons_ab or "below policy" in reasons_ab
    assert note_ab.get("lab_context")
    assert any("prefer ABSTAIN" in r for r in (note_ab.get("reasons") or []))

    ident = mod.run_demo(
        mode="offline",
        scenario="identity",
        out_dir=tmp_path / "id",
        event_id="test_id",
        policy_id="research_open",
    )
    assert ident["decision"] == "ABSTAIN"
    note = json.loads((tmp_path / "id" / "abstain_ece_note.json").read_text(encoding="utf-8"))
    assert note.get("identity_calibrator") is True
    assert note.get("u1_ece_patch_conf") is not None
    # identity conf=0.5 is NOT below research_open floor (0.25); must not claim conf-below-floor alone
    assert note.get("conf_below_policy_floor") is False
    reasons_id = note.get("reasons") or []
    assert any("Identity calibrator" in r for r in reasons_id)
    assert any("Explicit live abstain" in r for r in reasons_id)
    # Compound "below reliability floor or explicit abstain" must be gone
    assert not any("below reliability floor or explicit" in r for r in reasons_id)

    card_id = json.loads((tmp_path / "id" / "decision_card.json").read_text(encoding="utf-8"))
    live_id = _live_source(card_id)
    assert live_id.get("available") is True
    assert live_id.get("abstained") is True
    assert live_id.get("actionable") is False
    assert float(live_id.get("weight") or 0.0) == 0.0


def test_from_json_fixture(tmp_path: Path):
    mod = _load_demo_mod()
    summary = mod.run_demo(
        mode="from-json",
        ml_prediction_path=FIXTURE_HOLD,
        out_dir=tmp_path,
        event_id="from_json",
        policy_id="research_open",
    )
    assert summary["decision"] == "HOLD"
    assert summary["mode"] == "from-json"


def test_u1_honesty_snapshot_has_expected_keys():
    mod = _load_demo_mod()
    u1 = mod.load_u1_honesty_snapshot()
    assert "mean_iou_eval" in u1
    assert "selective_iou_at_80" in u1
    assert "ece_patch_conf" in u1
    assert "catalog_holdout_iou_provenance" in u1
    assert u1["field_ops_fusion"] is False
    # Must not present catalog 0.8963 as the only / primary live claim
    assert abs(float(u1["catalog_holdout_iou_provenance"]) - 0.8963) < 1e-3
    # Honest eval mean is distinct and ~0.86 when scorecard present
    assert 0.5 < float(u1["mean_iou_eval"]) < 0.95


def test_field_ops_does_not_enable_fusion_from_demo(tmp_path: Path):
    mod = _load_demo_mod()
    # Explicit field_ops policy: fusion must stay off even with strong live conf
    summary = mod.run_demo(
        mode="offline",
        scenario="hold",
        out_dir=tmp_path,
        policy_id="field_ops",
        event_id="field_ops_ml_only",
    )
    # ML-only under field_ops → ABSTAIN (allow_ml_only_hold false)
    assert summary["decision"] == "ABSTAIN"
    card = json.loads((tmp_path / "decision_card.json").read_text(encoding="utf-8"))
    snap = (card.get("audit") or {}).get("policy_snapshot") or {}
    assert snap.get("allow_ml_live_in_fusion") is False
    metrics = card.get("metrics") or {}
    assert metrics.get("allow_ml_live_in_fusion") is False
    # Live may still be available/actionable for audit, but weight 0 and no ML-only HOLD
    live_src = _live_source(card)
    assert live_src.get("available") is True
    assert live_src.get("actionable") is True  # high conf hold fixture, not abstained
    assert float(live_src.get("weight") or 0.0) == 0.0
    assert metrics.get("live_ok") is True
    assert metrics.get("live_available") is True


def test_missing_open_pack_errors(tmp_path: Path):
    """Allowlisted but missing/incomplete pack must error (not silent ML-only)."""
    mod = _load_demo_mod()
    # Path under REPO_ROOT allowlist so _as_path succeeds; pack/scorecard absent.
    missing = ROOT / "outputs" / "_missing_open_pack_demo_fixture"
    if missing.exists():
        # Do not delete unknown content; pick a unique non-existent sibling.
        missing = ROOT / "outputs" / f"_missing_open_pack_demo_{tmp_path.name}"
    try:
        mod.run_demo(
            mode="offline",
            scenario="hold",
            out_dir=tmp_path / "out",
            open_pack=missing,
            allow_missing_open_pack=False,
        )
        raise AssertionError("expected FileNotFoundError for missing open pack")
    except FileNotFoundError as exc:
        assert "open-pack" in str(exc).lower() or "scorecard" in str(exc).lower()

    # Explicit opt-out continues ML-only
    summary = mod.run_demo(
        mode="offline",
        scenario="hold",
        out_dir=tmp_path / "out2",
        open_pack=missing,
        allow_missing_open_pack=True,
    )
    assert summary["decision"] == "HOLD"


def test_cli_help_and_offline_smoke(tmp_path: Path):
    help_r = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_r.returncode == 0
    assert "offline" in help_r.stdout.lower() or "mode" in help_r.stdout.lower()
    assert "allow-missing-open-pack" in help_r.stdout

    out = tmp_path / "cli_out"
    smoke = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "offline",
            "--scenario",
            "hold",
            "--out-dir",
            str(out),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert smoke.returncode == 0, smoke.stderr
    payload = json.loads(smoke.stdout)
    assert payload["decision"] in {"HOLD", "ABSTAIN", "GO"}
    assert (out / "decision_card.json").is_file()


def test_build_offline_scenarios_schemas():
    mod = _load_demo_mod()
    for sc in ("hold", "abstain", "identity"):
        doc = mod.build_offline_ml_prediction(scenario=sc)
        assert doc["schema"] == "ml_prediction_v1"
        live = doc["ml_live_metrics"]
        assert live["schema"] == "ml_live_metrics_v1"
        assert "mean_entropy" in live
        assert "member_disagreement" in live
        assert "mean_margin" in live
        # no ROS invention
        blob = json.dumps(doc)
        assert "primary_ros" not in blob
        assert "ros_m_min" not in blob
