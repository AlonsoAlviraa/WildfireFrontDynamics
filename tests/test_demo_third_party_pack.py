"""Smoke tests for Graph v6.1 E1/E3 third-party pack + replay."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _env() -> dict[str, str]:
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    return e


def test_run_third_party_replay_forensic_demo():
    """E3 wrapper runs on known forensic_demo bundle when present."""
    bundle = ROOT / "outputs" / "forensic_demo"
    if not (bundle / "replay_sources.json").is_file():
        pytest.skip("outputs/forensic_demo not present")
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_third_party_replay.py"),
            "--bundle",
            str(bundle),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert "replay_ok:" in proc.stdout
    # forensic_demo may be stale vs code; accept 0 or 2 but script must run
    assert proc.returncode in (0, 2)


def test_run_third_party_replay_detects_tamper(tmp_path: Path):
    from wildfire_front.product.decide_service import decide_from_request
    from wildfire_front.product.forensics import write_forensic_bundle

    card = decide_from_request(
        {
            "event_id": "e3_tamper",
            "ops_metrics": {
                "quality_grade": "A",
                "primary_ros_m_min": 5.7,
                "n_frames_staged": 12,
                "speed_vs_ref_ratio": 0.85,
                "area_ha_max": 40,
            },
            "require_ops_for_go": True,
            "channel": "test",
            "gates_ok": True,
            "determinism_ok": True,
            "abstention_enforced": True,
            "provenance_ok": True,
        },
        base=ROOT,
        trust_client_reliability=True,
    )
    write_forensic_bundle(
        tmp_path,
        card,
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 12,
            "speed_vs_ref_ratio": 0.85,
            "area_ha_max": 40,
        },
        require_ops_for_go=True,
    )
    # Good replay
    good = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_third_party_replay.py"),
            "--bundle",
            str(tmp_path),
            "--quiet",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert good.returncode == 0, good.stdout + good.stderr
    assert "replay_ok: True" in good.stdout

    # Tamper expected decision
    src_path = tmp_path / "replay_sources.json"
    src = json.loads(src_path.read_text(encoding="utf-8"))
    src["expected_decision"] = "ABSTAIN" if src.get("expected_decision") != "ABSTAIN" else "GO"
    src_path.write_text(json.dumps(src, indent=2), encoding="utf-8")
    bad = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_third_party_replay.py"),
            "--bundle",
            str(tmp_path),
            "--quiet",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert bad.returncode == 2
    assert "replay_ok: False" in bad.stdout


def test_build_demo_third_party_pack(tmp_path: Path):
    """E1 builder produces field_ops card + replay_ok without ML-live fusion claim."""
    mod = _load("build_demo_third_party_pack", "scripts/build_demo_third_party_pack.py")
    out = tmp_path / "demo_third_party"
    summary = mod.build_pack(out, make_zip=False)
    assert summary["self_replay_ok"] is True
    assert summary["allow_ml_live_in_fusion"] is False
    assert (out / "fire_decision_card.json").is_file()
    assert (out / "fire_decision_card.md").is_file()
    assert (out / "replay_sources.json").is_file()
    assert (out / "replay_manifest.json").is_file()
    assert (out / "README.md").is_file()
    assert (out / "run_replay.ps1").is_file()
    assert (out / "RESEARCH_CITATIONS.md").is_file()
    assert (out / "sample_data" / "ops_metrics_tobarra.json").is_file()

    card = json.loads((out / "fire_decision_card.json").read_text(encoding="utf-8"))
    policy = (card.get("metrics") or {}).get("policy_id") or (card.get("audit") or {}).get(
        "policy_id"
    )
    assert policy == "field_ops"
    assert (card.get("metrics") or {}).get("allow_ml_live_in_fusion") is False
    md = (out / "fire_decision_card.md").read_text(encoding="utf-8")
    assert "Uncertainty band" in md

    # Honesty: area_ha_max is observed mask max, not INFOCAM 39 ha alone
    sample_ops = json.loads(
        (out / "sample_data" / "ops_metrics_tobarra.json").read_text(encoding="utf-8")
    )
    assert sample_ops.get("area_ha_max") is not None
    assert float(sample_ops["area_ha_max"]) > 40.0  # observed ~52, not mislabeled 39
    assert (
        sample_ops.get("reference_area_ha") == 39.0
        or float(sample_ops.get("reference_area_ha") or 0) == 39.0
    )
    sample_readme = (out / "sample_data" / "README.md").read_text(encoding="utf-8")
    assert "INFOCAM" in sample_readme or "reference_area" in sample_readme
    assert "not" in sample_readme.lower() and (
        "co-incident" in sample_readme.lower() or "Tobarra" in sample_readme
    )
    pack_readme = (out / "README.md").read_text(encoding="utf-8")
    assert "consistencia forense" in pack_readme or "internal" in pack_readme.lower()

    # E3 on built pack
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_third_party_replay.py"),
            "--bundle",
            str(out),
            "--quiet",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=_env(),
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_humanize_decision_reason_and_uncertainty_notes():
    from wildfire_front.incident.pipeline import (
        _humanize_decision_reason,
        _uncertainty_band_notes,
        render_decision_card_md,
    )

    assert "ABSTAIN" in _humanize_decision_reason("ml_only_blocked_by_policy")
    card = {
        "event_id": "t",
        "decision": "ABSTAIN",
        "confidence_pred": 0.1,
        "confidence_pred_label": "VERY_LOW",
        "system_reliability_pass": False,
        "sources": [],
        "metrics": {"policy_id": "field_ops", "ops": None, "allow_ml_live_in_fusion": False},
        "reasons": ["ml_only_blocked_by_policy", "policy:field_ops"],
        "disclaimers": ["Not a tactical dispatch order."],
        "audit": {
            "schema": "fire_decision_card_v1",
            "input_hash": "a" * 40,
            "output_hash": "b" * 40,
        },
    }
    notes = _uncertainty_band_notes(card)
    assert any("u_data" in n for n in notes)
    assert any("u_model" in n or "epistémica" in n for n in notes)
    md = render_decision_card_md(card)
    assert "Uncertainty band" in md
    assert "Reasons" in md
