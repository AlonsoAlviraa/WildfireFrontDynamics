"""Tests for lab next-signal readiness gate."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.ml.lab_next import build_next_gate, format_next_gate_human

ROOT = Path(__file__).resolve().parents[1]


def test_build_next_gate_rails():
    pack = build_next_gate(ROOT)
    assert pack["schema"] == "wfd_ml_lab_next_v1"
    assert pack["rails"]["ml_product_go"] is True
    assert pack["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert pack["verdict"]["auto_unfreeze"] is False
    assert pack["verdict"]["metric_retune_allowed"] is False
    assert pack["verdict"]["next_gate_built"] is True
    assert pack["recommended_next"]
    ids = {w["id"] for w in pack["work_items"]}
    assert "W1_lofo_head_a_caches" in ids
    assert "W4_human_ml_product_go" in ids
    # W3 still recommended when W1/W2 done; never Tobarra reopen as READY
    w3 = next(w for w in pack["work_items"] if w["id"] == "W3_new_features_or_data")
    assert "tobarra_finetune_keep_reopen" in (w3.get("closed_paths") or [])
    sub = w3.get("sub_items") or []
    sub_ids = {s["id"] for s in sub}
    assert "E0_instrumentation" in sub_ids
    assert "E2_schema_clean12_subset" in sub_ids
    assert "E3a_hellin_train_pool" in sub_ids
    assert "E4_curriculum_weak_floor" in sub_ids
    assert "T2_north_star" in sub_ids
    # Tobarra KEEP reopen never READY next
    assert pack["verdict"]["tobarra_keep_reopen_allowed"] is False
    text = format_next_gate_human(pack)
    assert "recommended_next" in text
    assert "OFF" in text


def test_next_script(tmp_path):
    from scripts import run_lab_ml_loop_v34_next_gate as mod

    rc = mod.main(["--repo", str(ROOT), "--out-dir", str(tmp_path), "--no-md"])
    assert rc == 0
    data = json.loads((tmp_path / "lab_loop_v34_next_gate_latest.json").read_text(encoding="utf-8"))
    assert data["iteration"] == 10
    assert data["rails"]["ml_product_go"] is True
    latest = json.loads((tmp_path / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "10_next_gate" in latest["iterations"]
    # Repo may already have W1 caches; only assert W1 blocker when none exist
    n_ha = data["gate"]["lofo_fold_probe"]["counts"]["n_head_a_caches"]
    rec = data["verdict"].get("recommended_next") or data["gate"].get("recommended_next")
    if n_ha == 0:
        assert data["verdict"]["primary_blocker"] == "W1_lofo_head_a_caches"
    else:
        assert rec in (
            "W2_lofo_ece_reject_eval",
            "W3_new_features_or_data",
            "W1_lofo_head_a_caches",
        )
