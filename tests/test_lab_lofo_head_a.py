"""Tests for LOFO Head A cache eval (product_facade + frozen rank/reject; no retrain).

Single product path: features -> calibrator -> rank/reject -> scorecard.
VAL-only thr freeze (iter1_reject_only); dual rails lab vs field_ops;
multi-fire honesty via product_facade.fire_honesty_tag (LOFO/W3 first-class).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.lab_lofo_head_a import (
    DEFAULT_CALIBRATOR_THR,
    FROZEN_ITER1_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    eval_fold_with_calibrator,
    frozen_rank_reject_protocol,
    multi_fire_honesty_for,
    summarize_lofo_head_a_evals,
)
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    ITER1_LOCKED_REJECT_THR,
    LEGACY_PRODUCT_ABSTAIN_THR,
    ProductFacadeError,
    fire_honesty_tag,
    refuse_dead_path,
)
from wildfire_front.ml.product_facade import (
    RECOMMENDED_LAB_SURFACE as FACADE_SURFACE,
)
from wildfire_front.ml.uncertainty import LogisticCalibrator

ROOT = Path(__file__).resolve().parents[1]


def _tiny_cal() -> LogisticCalibrator:
    # weights = [w_entropy, w_disagree, w_margin, bias]
    # abstain_threshold=legacy 0.35 is archaeology baseline only (not product surface).
    return LogisticCalibrator(
        weights=np.array([-1.0, -0.5, 2.0, 0.5], dtype=np.float64),
        feature_names=("mean_entropy", "member_disagreement", "mean_margin"),
        tau_iou=0.5,
        abstain_threshold=float(LEGACY_PRODUCT_ABSTAIN_THR),
        method="logistic",
        calibrator_id="test_tiny",
        fit_split="unit_test",
    )


def test_frozen_iter1_protocol_and_fire_honesty_tags():
    """product_facade thr freeze + fire_honesty_tag (no magic 0.35 product path)."""
    assert float(FROZEN_ITER1_REJECT_THR) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert abs(float(ITER1_LOCKED_REJECT_THR) - 0.795) < 1e-9
    assert float(DEFAULT_CALIBRATOR_THR) == pytest.approx(float(LEGACY_PRODUCT_ABSTAIN_THR))
    assert float(LEGACY_PRODUCT_ABSTAIN_THR) == pytest.approx(0.35)
    # Product surface is VAL iter1 reject, not legacy 0.35.
    assert float(ITER1_LOCKED_REJECT_THR) != pytest.approx(0.35)
    assert RECOMMENDED_LAB_SURFACE == FACADE_SURFACE == "iter1_reject_only"

    proto = frozen_rank_reject_protocol()
    assert proto["product_facade"] == "wildfire_front.ml.product_facade"
    assert proto["recommended_lab_surface"] == "iter1_reject_only"
    assert proto["thr_source"] == "val_iter1_reject_frozen"
    assert abs(float(proto["locked_reject_thr"]) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    assert proto["fit_on_eval_split"] is False
    assert "same_holdout_ece_retune" in DEAD_PATHS
    assert "tobarra_keep_reopen_same_recipe" in DEAD_PATHS
    for dead in ("same_holdout_ece_retune", "tobarra_keep_reopen_same_recipe"):
        with pytest.raises(ProductFacadeError):
            refuse_dead_path(dead)

    # Multi-fire honesty first-class via product_facade.fire_honesty_tag.
    cardoso = fire_honesty_tag("CARDOSO")
    assert cardoso["role"] == "easy_in_pack"
    assert cardoso.get("board") == "lofo_in_pack"
    tobarra = fire_honesty_tag("tobarra_20240802")
    assert tobarra["role"] == "hard_transfer"
    assert tobarra.get("keep_reopen") is False
    hellin = fire_honesty_tag("hellin_2024")
    assert hellin["role"] == "external_probe"
    assert hellin.get("board") == "w3_external"
    # lab_lofo_head_a overlay preserves facade roles.
    assert multi_fire_honesty_for("CARDOSO")["role"] == cardoso["role"]
    assert multi_fire_honesty_for("tobarra_20240802")["role"] == tobarra["role"]
    assert multi_fire_honesty_for("hellin_2024")["role"] == hellin["role"]


def test_eval_fold_and_summary(tmp_path):
    rng = np.random.default_rng(0)
    # features roughly in Head A ranges
    feats = np.column_stack(
        [
            rng.uniform(0.1, 0.5, 40),
            rng.uniform(0.0, 0.2, 40),
            rng.uniform(0.3, 0.8, 40),
        ]
    )
    ious = rng.uniform(0.4, 0.99, 40)
    labels = (ious >= 0.5).astype(np.int64)
    cache = tmp_path / "head_a_features.npz"
    np.savez_compressed(
        cache,
        features=feats,
        labels=labels,
        ious=ious,
    )
    cal = _tiny_cal()
    # Prefer real calibrator if present
    real = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    if real.is_file():
        cal = LogisticCalibrator.from_dict(json.loads(real.read_text(encoding="utf-8")))
    # Frozen VAL iter1 thr only (module/facade defaults); no hardcoded 0.35 product path.
    ev = eval_fold_with_calibrator(
        cache,
        cal,
        locked_thr=float(FROZEN_ITER1_REJECT_THR),
        default_thr=float(DEFAULT_CALIBRATOR_THR),
        fold="CARDOSO",
    )
    assert ev["n_patches"] == 40
    assert 0.0 <= ev["ece_full"] <= 1.0
    assert "thr_locked" in ev
    # product_facade + rank_reject single path (VAL iter1 freeze)
    assert ev.get("product_facade") == "wildfire_front.ml.product_facade"
    assert abs(float(ev["locked_thr"]) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    assert float(ev["default_thr"]) == pytest.approx(float(LEGACY_PRODUCT_ABSTAIN_THR))
    assert (ev.get("protocol") or {}).get("recommended_lab_surface") == "iter1_reject_only"
    assert (ev.get("protocol") or {}).get("product_facade") == ("wildfire_front.ml.product_facade")
    assert (ev.get("protocol") or {}).get("thr_source") == "val_iter1_reject_frozen"
    rails = ev.get("rails") or {}
    assert rails.get("ml_product_go") is True
    assert rails.get("field_ops_allow_ml_live_in_fusion") is False
    assert rails.get("iou_is_not_ros") is True
    assert rails.get("recommended_lab_surface") == "iter1_reject_only"
    assert rails.get("pipeline") == "features→calibrator→rank/reject→scorecard" or (
        ev.get("pipeline") == "features→calibrator→rank/reject→scorecard"
    )
    # multi-fire honesty via product_facade.fire_honesty_tag
    tag = fire_honesty_tag("CARDOSO")
    hon = ev.get("multi_fire_honesty") or {}
    assert hon.get("role") == tag["role"] == "easy_in_pack"
    tob_tag = fire_honesty_tag("tobarra_20240802")
    assert tob_tag.get("keep_reopen") is False
    summ = summarize_lofo_head_a_evals({"CARDOSO": ev}, holdout_ece=0.15, holdout_iou=0.85)
    assert summ["n_folds"] == 1
    assert summ["ece_mean"] == ev["ece_full"]
    assert summ.get("product_facade") == "wildfire_front.ml.product_facade"
    assert summ.get("recommended_lab_surface") == "iter1_reject_only"
    assert summ.get("multi_fire_honesty_surface") is True
    srails = summ.get("rails") or {}
    assert srails.get("ml_product_go") is True
    assert srails.get("field_ops_allow_ml_live_in_fusion") is False
    assert srails.get("iou_is_not_ros") is True


def test_iter_script_eval_only_missing_is_2(tmp_path):
    from scripts import run_lab_ml_loop_v34_lofo_head_a as mod

    # No caches under empty lofo out root -> exit 2
    rc = mod.main(
        [
            "--lofo-out-root",
            str(tmp_path / "lofo"),
            "--out-dir",
            str(tmp_path / "lab"),
            "--no-md",
            "--folds",
            "NOPE",
        ]
    )
    assert rc == 2
