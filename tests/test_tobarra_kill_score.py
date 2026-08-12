"""Tests for Tobarra K1–K5 scorer (no train; product_facade rails)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_score_tobarra_kill_writes(tmp_path):
    from scripts.score_tobarra_kill_criteria import main

    out = tmp_path / "score.json"
    leak = tmp_path / "leak.json"
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out",
            str(out),
            "--leak-out",
            str(leak),
        ]
    )
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == "tobarra_kill_scorecard_v1"
    assert data["verdict"] in ("KEEP", "KILL", "INCONCLUSIVE")
    assert data["field_product"] is False
    # product_facade + rank_reject_protocol (VAL iter1 freeze; dual rails)
    assert data.get("product_facade") == "wildfire_front.ml.product_facade"
    assert isinstance(data.get("rank_reject_protocol"), dict)
    assert data["rank_reject_protocol"].get("thr_tune_split") == "val"
    assert data["rails"]["no_ece_retune_same_holdout"] is True
    assert data["rails"]["ml_product_go"] is True
    assert data.get("ml_product_go") is True
    assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert data["checks"]["K5_no_field_rails"]["pass"] is True
    assert data["checks"]["K5_no_field_rails"]["field_ops_fusion_off"] is True
    assert data["checks"]["K5_no_field_rails"]["ml_product_go"] is True
    assert data["rails"]["recommended_lab_surface"] == "iter1_reject_only"
    assert data["rails"]["iou_is_not_ros"] is True
    assert data.get("re_promote_kill_weights") is False
    assert data.get("tobarra_keep_reopen_forbidden") is True
    seal = data.get("tobarra_keep_seal") or {}
    assert seal.get("re_promote_kill_weights") is False
    assert isinstance(data.get("multi_fire_honesty"), dict)
    assert "K1_test_iou_lift" in data["checks"]
    assert "K3_zero_target_leak" in data["checks"]
    assert data["checks"]["K5_no_field_rails"].get("source") == ("wildfire_front.ml.product_facade")
    leak_d = json.loads(leak.read_text(encoding="utf-8"))
    assert "n_leaked_train_val" in leak_d
