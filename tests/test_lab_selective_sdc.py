"""Tests for Soft Dice Confidence proxy ranking (deep research S1).

Locks single product path via product_facade + rank_reject_protocol:
features→calibrator→rank/reject→scorecard. VAL-only thr; default surface
iter1_reject_only; dual rails (lab vs field_ops, IoU≠ROS, ml_product_go true,
fusion OFF); dead thrash sealed (ECE same-holdout, Tobarra KEEP re-promote).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.lab_selective_sdc import (
    bakeoff_rankings,
    decide_sdc_verdict,
    ranking_scores_from_head_a,
    run_selective_sdc_protocol,
    score_ranking,
)
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ClmEnsembleV34Facade,
    ProductFacadeError,
    assert_lab_rails,
    confidences_from_head_a,
    refuse_dead_path,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    DEFAULT_LAB_SURFACE,
    LOCKED_ITER1_THR,
    protocol_payload,
    refuse_dead_protocol_path,
)
from wildfire_front.ml.uncertainty import LogisticCalibrator

ROOT = Path(__file__).resolve().parents[1]


def _toy_cal() -> LogisticCalibrator:
    return LogisticCalibrator(
        weights=np.array([0.0, 0.0, 2.0, 0.0], dtype=np.float64),
        abstain_threshold=float(ITER1_LOCKED_REJECT_THR),
        temperature=1.0,
        platt_a=None,
        platt_b=None,
    )


def test_ranking_scores_shapes():
    rng = np.random.default_rng(0)
    feat = rng.uniform(0, 1, size=(50, 3))
    conf = rng.uniform(0.5, 0.95, size=50)
    scores = ranking_scores_from_head_a(feat, conf)
    assert set(scores) >= {
        "logistic_conf",
        "inv_entropy",
        "soft_dice_proxy",
        "multi_signal",
    }
    for s in scores.values():
        assert s.shape == (50,)
        assert np.all(np.isfinite(s))


def test_sdc_beats_noise_when_margin_tracks_iou():
    rng = np.random.default_rng(1)
    n = 120
    # margin high → iou high; entropy low → better
    margin = rng.uniform(0, 1, size=n)
    entropy = 1.0 - margin + rng.normal(0, 0.05, size=n)
    disagree = rng.uniform(0, 0.2, size=n)
    feat = np.stack([entropy, disagree, margin], axis=1)
    conf = 0.5 + 0.45 * margin
    ious = np.clip(0.2 + 0.7 * margin + rng.normal(0, 0.03, size=n), 0, 1)
    bake = bakeoff_rankings(feat, conf, ious)
    assert (
        bake["soft_dice_proxy"]["selective_iou_at_80"]
        >= bake["logistic_conf"]["full_mean_iou"] - 0.05
    )
    # AURC finite
    assert np.isfinite(bake["soft_dice_proxy"]["aurc"])


def test_decide_kill_when_no_lift():
    val = {
        "soft_dice_proxy": {"selective_iou_at_80": 0.90, "aurc": 0.10},
        "inv_entropy": {"selective_iou_at_80": 0.91, "aurc": 0.09},
    }
    v = decide_sdc_verdict(val, min_lift_sel80=0.02)
    assert v["verdict"] == "KILL_SDC_PROMOTE"
    # Product surface freezes iter1 even on KILL (shared protocol surface).
    assert v["recommended_lab_surface"] == "iter1_reject_only"
    assert v["recommended_lab_surface"] == RECOMMENDED_LAB_SURFACE == DEFAULT_LAB_SURFACE
    assert v["freeze_iter1_reject"] is True
    assert v["sdc_auto_promote_over_iter1"] is False


def test_decide_keep_when_lift():
    val = {
        "soft_dice_proxy": {"selective_iou_at_80": 0.94, "aurc": 0.08},
        "inv_entropy": {"selective_iou_at_80": 0.90, "aurc": 0.09},
    }
    v = decide_sdc_verdict(val, min_lift_sel80=0.02)
    assert v["verdict"] == "KEEP_SDC_PROXY_LAB"
    # KEEP is ranking-family only — never flips frozen reject surface / field.
    assert v["recommended_lab_surface"] == "iter1_reject_only"
    assert v["freeze_iter1_reject"] is True
    assert v["sdc_auto_promote_over_iter1"] is False


def test_aurc_lower_better_for_good_ranking():
    ious = np.array([0.9, 0.85, 0.8, 0.4, 0.3, 0.2])
    good = np.array([0.95, 0.9, 0.85, 0.2, 0.15, 0.1])
    bad = np.array([0.1, 0.15, 0.2, 0.85, 0.9, 0.95])
    g = score_ranking(good, ious)
    b = score_ranking(bad, ious)
    assert g["selective_iou_at_80"] > b["selective_iou_at_80"]
    assert g["aurc"] < b["aurc"]


def test_facade_rank_reject_protocol_iter1_freeze():
    """product_facade + rank_reject_protocol lock VAL thr + iter1 surface."""
    rails = assert_lab_rails(DEFAULT_RAILS)
    assert rails.ml_product_go is True
    assert rails.field_ops_allow_ml_live_in_fusion is False
    assert rails.iou_is_not_ros is True
    assert rails.val_only_threshold_selection is True
    assert rails.recommended_lab_surface == "iter1_reject_only"
    assert float(rails.locked_reject_thr) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert rails.stop_ece_thrash_on_same_test is True
    assert rails.tobarra_keep_reopen_forbidden is True

    assert RECOMMENDED_LAB_SURFACE == DEFAULT_LAB_SURFACE == "iter1_reject_only"
    assert float(ITER1_LOCKED_REJECT_THR) == pytest.approx(float(LOCKED_ITER1_THR))
    assert abs(float(ITER1_LOCKED_REJECT_THR) - 0.795) < 1e-9

    proto = protocol_payload(locked_reject_thr=float(ITER1_LOCKED_REJECT_THR))
    assert proto["product_facade"] == "wildfire_front.ml.product_facade"
    assert proto["pipeline"] == "features→calibrator→rank/reject→scorecard"
    assert proto.get("thr_tune_split") == "val"
    assert proto.get("freeze_iter1_reject") is True
    assert float(proto.get("locked_reject_thr") or proto.get("reject_thr")) == pytest.approx(
        float(ITER1_LOCKED_REJECT_THR)
    )
    assert proto.get("recommended_lab_surface") == "iter1_reject_only"
    assert "same_holdout_ece_retune" in set(proto.get("dead_paths") or DEAD_PROTOCOL_PATHS)

    cal = _toy_cal()
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal, rails=rails)
    assert isinstance(facade, ClmEnsembleV34Facade)
    assert abs(float(facade.rank_reject_cfg.reject_thr) - float(ITER1_LOCKED_REJECT_THR)) < 1e-9
    assert facade.rails.recommended_lab_surface == "iter1_reject_only"
    assert facade.rails.ml_product_go is True

    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
        "sdc_auto_promote_over_iter1",
    ):
        assert dead in DEAD_PATHS or dead in DEAD_PROTOCOL_PATHS
        with pytest.raises(ProductFacadeError):
            refuse_dead_path(dead)
        with pytest.raises(ValueError):
            refuse_dead_protocol_path(dead)


def test_run_selective_sdc_protocol_facade_path():
    """Offline bake-off path: facade conf + VAL thr + dual rails + multi-fire."""
    rng = np.random.default_rng(7)
    n_val, n_test = 40, 20
    val_f = np.column_stack(
        [
            rng.uniform(0.1, 0.9, n_val),
            rng.uniform(0.0, 0.3, n_val),
            rng.uniform(0.0, 0.5, n_val),
        ]
    )
    test_f = np.column_stack(
        [
            rng.uniform(0.1, 0.9, n_test),
            rng.uniform(0.0, 0.3, n_test),
            rng.uniform(0.0, 0.5, n_test),
        ]
    )
    cal = _toy_cal()
    conf_v = confidences_from_head_a(cal, val_f)
    val_iou = np.clip(0.2 + 0.7 * conf_v + rng.normal(0, 0.05, n_val), 0, 1)
    conf_t = confidences_from_head_a(cal, test_f)
    test_iou = np.clip(0.2 + 0.7 * conf_t + rng.normal(0, 0.05, n_test), 0, 1)

    out = run_selective_sdc_protocol(cal, val_f, val_iou, test_f, test_iou, min_lift_sel80=0.02)
    assert out.get("product_facade") == "wildfire_front.ml.product_facade"
    assert out.get("pipeline") == "features→calibrator→rank/reject→scorecard"
    assert out.get("dead_thrash_closed") is True
    assert isinstance(out.get("rank_reject_protocol"), dict)
    assert out["rank_reject_protocol"].get("product_facade") == ("wildfire_front.ml.product_facade")
    assert out["rank_reject_protocol"].get("thr_tune_split") == "val"
    assert out["rank_reject_protocol"].get("freeze_iter1_reject") is True
    rails = out["rails"]
    assert rails["ml_product_go"] is True
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails.get("field_ops_ml_live_fusion") == "OFF"
    assert rails["iou_is_not_ros"] is True
    assert rails["recommended_lab_surface"] == "iter1_reject_only"
    assert rails.get("freeze_iter1_reject") is True
    assert float(rails["locked_reject_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert rails.get("sdc_auto_promote_over_iter1") is False
    assert isinstance(out.get("multi_fire_honesty"), dict)
    verdict = out["sdc_verdict"]
    assert verdict["recommended_lab_surface"] == "iter1_reject_only"
    assert verdict["freeze_iter1_reject"] is True
    assert verdict["sdc_auto_promote_over_iter1"] is False
    crc = out["conformal_crc_lite"]
    assert float(crc["fallback_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert "val" in (crc.get("thr_source") or "")
    assert crc.get("recommended_lab_surface") == "iter1_reject_only"


def test_runner_with_real_caches_if_present():
    val = ROOT / "outputs" / "ml_eval" / "val_head_a_features.npz"
    test = ROOT / "outputs" / "ml_eval" / "test_head_a_features.npz"
    cal = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    if not (val.is_file() and test.is_file() and cal.is_file()):
        return
    import tempfile

    from scripts import run_lab_ml_loop_v34_selective_sdc as mod

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        rc = mod.main(
            [
                "--out-dir",
                str(tdp),
                "--no-md",
                "--val-npz",
                str(val),
                "--test-npz",
                str(test),
                "--calibrator",
                str(cal),
            ]
        )
        assert rc == 0
        data = json.loads(
            (tdp / "lab_loop_v34_selective_sdc_latest.json").read_text(encoding="utf-8")
        )
        # product_facade + rank_reject_protocol single path (VAL iter1 freeze)
        assert data.get("product_facade") == "wildfire_front.ml.product_facade"
        assert (
            data.get("facade_class") == "ClmEnsembleV34Facade"
            or data.get("pipeline") == "features→calibrator→rank/reject→scorecard"
        )
        assert data.get("pipeline") == "features→calibrator→rank/reject→scorecard"
        assert isinstance(data.get("rank_reject_protocol"), dict)
        assert data["rank_reject_protocol"].get("thr_tune_split") == "val"
        assert data["rank_reject_protocol"].get("freeze_iter1_reject") is True
        assert data["rank_reject_protocol"].get("locked_reject_thr") is not None
        assert data["rails"]["ml_product_go"] is True
        assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
        assert data["rails"].get("field_ops_ml_live_fusion") == "OFF"
        assert data["rails"]["iou_is_not_ros"] is True
        assert data["rails"]["recommended_lab_surface"] == "iter1_reject_only"
        assert data["rails"].get("freeze_iter1_reject") is True
        assert data["rails"].get("stop_ece_thrash_on_same_test") is True
        assert data["rails"].get("tobarra_keep_reopen_forbidden") is True
        assert data["rails"].get("sdc_auto_promote_over_iter1") is False
        assert float(data.get("locked_reject_thr") or data["rails"]["locked_reject_thr"]) == (
            pytest.approx(float(ITER1_LOCKED_REJECT_THR))
        )
        assert data.get("recommended_lab_surface") == "iter1_reject_only"
        assert data.get("freeze_iter1_reject") is True
        assert data.get("dead_thrash_closed") is True
        assert isinstance(data.get("multi_fire_honesty"), dict)
        assert data["verdict"] in ("KILL_SDC_PROMOTE", "KEEP_SDC_PROXY_LAB")
        sdc_v = data.get("sdc_verdict") or {}
        assert sdc_v.get("recommended_lab_surface") == "iter1_reject_only"
        assert sdc_v.get("freeze_iter1_reject") is True
        assert sdc_v.get("sdc_auto_promote_over_iter1") is False
        assert sdc_v.get("ml_product_go") is True
        # CRC thr is report-only; product surface stays facade iter1 lock.
        crc = data.get("conformal_crc_lite") or {}
        assert float(crc.get("fallback_thr") or ITER1_LOCKED_REJECT_THR) == pytest.approx(
            float(ITER1_LOCKED_REJECT_THR)
        )
        assert float(crc.get("product_surface_thr") or data["locked_reject_thr"]) == (
            pytest.approx(float(ITER1_LOCKED_REJECT_THR))
        )
        latest = json.loads((tdp / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
        assert latest.get("product_facade") == "wildfire_front.ml.product_facade"
        assert latest.get("recommended_lab_surface") == "iter1_reject_only"
        assert latest.get("freeze_iter1_reject") is True
        assert latest["rails"]["ml_product_go"] is True
        assert latest["rails"]["field_ops_allow_ml_live_in_fusion"] is False
        assert latest["rails"]["field_ops_ml_live_fusion"] == "OFF"
        assert latest["rails"]["recommended_lab_surface"] == "iter1_reject_only"
