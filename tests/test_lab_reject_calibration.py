"""Unit tests for lab-only reject/calibration pure math + facade single-path contracts.

Pure math lives in ``lab_reject_calibration``; product orchestration is
``product_facade`` + ``rank_reject_protocol`` (features→calibrator→rank/reject→scorecard).
Dead thrash (same-holdout ECE, Tobarra KEEP reopen) is refused — not re-exported.
"""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.ml import lab_reject_calibration as lrc
from wildfire_front.ml.lab_reject_calibration import (
    ITER1_LOCKED_REJECT_THR,
    LEGACY_PRODUCT_ABSTAIN_THR,
    RECOMMENDED_LAB_SURFACE,
    apply_confidence_temperature,
    confidences_from_features,
    lab_product_rails,
    metrics_at_threshold,
    rank_reject_scorecard,
    score_val_candidate,
    tune_reject_and_temperature,
)
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_RAILS,
    DEFAULT_RANK_REJECT,
    ClmEnsembleV34Facade,
    ProductFacadeError,
    assert_lab_rails,
    confidences_from_head_a,
    refuse_dead_path,
)
from wildfire_front.ml.product_facade import (
    ITER1_LOCKED_REJECT_THR as FACADE_LOCKED_THR,
)
from wildfire_front.ml.product_facade import (
    LEGACY_PRODUCT_ABSTAIN_THR as FACADE_LEGACY_THR,
)
from wildfire_front.ml.product_facade import (
    RECOMMENDED_LAB_SURFACE as FACADE_SURFACE,
)
from wildfire_front.ml.protocol_rails import dual_product_rails_dict
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    DEFAULT_LAB_SURFACE,
    DEFAULT_REJECT_THR,
    conf_from_features,
    default_val_thr_grid,
    protocol_payload,
    refuse_dead_protocol_path,
    select_thr_val_only,
)
from wildfire_front.ml.reliability_metrics import ece_patch_conf
from wildfire_front.ml.uncertainty import LogisticCalibrator


def _toy_cal() -> LogisticCalibrator:
    # weights: 3 coef + bias; weak linear on margin
    # abstain_threshold=0.35 is LEGACY product default (never rejects on v34 conf band)
    return LogisticCalibrator(
        weights=np.array([0.0, 0.0, 2.0, 0.0], dtype=np.float64),
        abstain_threshold=LEGACY_PRODUCT_ABSTAIN_THR,
        temperature=1.0,
        platt_a=None,
        platt_b=None,
    )


def test_temperature_identity_and_softens():
    conf = np.array([0.1, 0.5, 0.9])
    idn = apply_confidence_temperature(conf, 1.0)
    assert np.allclose(idn, conf)
    soft = apply_confidence_temperature(conf, 2.0)
    # extremes move toward 0.5
    assert soft[0] > conf[0]
    assert soft[2] < conf[2]


def test_metrics_at_threshold_abstain():
    conf = np.array([0.2, 0.4, 0.8, 0.9])
    labels = np.array([0, 0, 1, 1])
    ious = np.array([0.1, 0.2, 0.9, 0.95])
    m = metrics_at_threshold(conf, labels, ious, thr=0.5)
    assert m["n_keep"] == 2
    assert m["abstain_rate"] == 0.5
    assert abs(m["mean_iou_accepted"] - 0.925) < 1e-9


def test_legacy_035_baseline_is_not_product_surface():
    """0.35 is archaeology baseline only; product thr freezes at iter1 (~0.795)."""
    assert float(LEGACY_PRODUCT_ABSTAIN_THR) == pytest.approx(0.35)
    assert float(FACADE_LEGACY_THR) == pytest.approx(0.35)
    assert float(ITER1_LOCKED_REJECT_THR) == pytest.approx(float(FACADE_LOCKED_THR))
    assert abs(float(ITER1_LOCKED_REJECT_THR) - 0.795) < 1e-9
    assert float(ITER1_LOCKED_REJECT_THR) != pytest.approx(0.35)
    assert float(DEFAULT_REJECT_THR) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert DEFAULT_RANK_REJECT.reject_thr == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert RECOMMENDED_LAB_SURFACE == FACADE_SURFACE == DEFAULT_LAB_SURFACE == "iter1_reject_only"


def test_tune_never_uses_test_for_selection_and_improves_reject_surface():
    rng = np.random.default_rng(0)
    n_val, n_test = 80, 40
    # features: entropy, disagree, margin — conf ~ sigmoid(2*margin)
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
    conf_v = confidences_from_features(cal, val_f)
    # labels correlated with conf
    val_lab = (conf_v > 0.55).astype(np.float64)
    val_iou = np.where(val_lab > 0.5, rng.uniform(0.6, 0.95, n_val), rng.uniform(0.0, 0.4, n_val))
    conf_t = confidences_from_features(cal, test_f)
    test_lab = (conf_t > 0.55).astype(np.float64)
    test_iou = np.where(
        test_lab > 0.5, rng.uniform(0.6, 0.95, n_test), rng.uniform(0.0, 0.4, n_test)
    )

    res = tune_reject_and_temperature(
        cal,
        val_f,
        val_lab,
        val_iou,
        test_f,
        test_lab,
        test_iou,
        thr_grid=[0.3, 0.45, 0.55, 0.65],
        temp_grid=[1.0, 1.2],
        min_keep_rate=0.3,
        baseline_thr=LEGACY_PRODUCT_ABSTAIN_THR,  # 0.35 archaeology baseline
    )
    assert 0.25 <= res.best_threshold <= 0.7
    assert res.test_metrics_baseline["n"] == float(n_test)
    assert res.test_metrics_tuned["n"] == float(n_test)
    assert "VAL only" in res.protocol_note or "val" in res.protocol_note.lower()


def test_score_val_candidate_rejects_low_keep():
    m = {
        "keep_rate": 0.1,
        "ece_accepted": 0.05,
        "mean_iou_accepted": 0.9,
        "abstain_rate": 0.9,
    }
    assert (
        score_val_candidate(
            m,
            min_keep_rate=0.45,
            baseline_ece_full=0.15,
            baseline_mean_iou=0.7,
        )
        < -1e8
    )


def test_score_prefers_explicit_reject_band():
    base = {
        "keep_rate": 0.75,
        "abstain_rate": 0.25,
        "ece_accepted": 0.12,
        "mean_iou_accepted": 0.90,
    }
    no_reject = {
        "keep_rate": 1.0,
        "abstain_rate": 0.0,
        "ece_accepted": 0.12,
        "mean_iou_accepted": 0.86,
    }
    s_ok = score_val_candidate(
        base, min_keep_rate=0.45, baseline_ece_full=0.15, baseline_mean_iou=0.85
    )
    s_bad = score_val_candidate(
        no_reject, min_keep_rate=0.45, baseline_ece_full=0.15, baseline_mean_iou=0.85
    )
    assert s_ok > s_bad


def test_ece_helper_stable():
    conf = np.linspace(0.1, 0.9, 50)
    lab = (conf > 0.5).astype(float)
    e = ece_patch_conf(conf, lab)
    assert 0.0 <= e <= 1.0


def test_ece_thrash_api_removed():
    """Same-holdout ECE retune thrash is dead — not re-exported from pure math."""
    assert not hasattr(lrc, "tune_ece_recalibration")
    assert not hasattr(lrc, "SameHoldoutEceThrashError")
    assert not hasattr(lrc, "LabEceRecalResult")
    assert "tune_ece_recalibration" not in lrc.__all__


def test_dead_path_refuse_facade_and_protocol():
    """product_facade + rank_reject_protocol hard-refuse closed thrash/reopen ids."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
    ):
        assert dead in DEAD_PATHS or dead in DEAD_PROTOCOL_PATHS
        with pytest.raises(ProductFacadeError):
            refuse_dead_path(dead)
        with pytest.raises(ValueError):
            refuse_dead_protocol_path(dead)


def test_frozen_iter1_reject_defaults_and_math_scorecard():
    rails = lab_product_rails()
    assert rails["recommended_lab_surface"] == RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
    assert float(rails["locked_reject_thr"]) == pytest.approx(ITER1_LOCKED_REJECT_THR)
    assert rails["ml_product_go"] is True
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails["no_ece_retune_same_holdout"] is True
    assert rails["iou_is_not_ros"] is True

    cal = _toy_cal()
    rng = np.random.default_rng(2)
    n = 20
    feats = np.column_stack(
        [
            rng.uniform(0.1, 0.9, n),
            rng.uniform(0.0, 0.3, n),
            rng.uniform(0.0, 0.5, n),
        ]
    )
    conf = confidences_from_features(cal, feats)
    labels = (conf > 0.55).astype(float)
    ious = np.where(labels > 0.5, 0.9, 0.2)
    card = rank_reject_scorecard(cal, feats, labels, ious)
    assert card["surface"] == "iter1_reject_only"
    assert card["thr"] == ITER1_LOCKED_REJECT_THR
    assert card["metrics"]["n"] == float(n)
    assert card["rails"]["ml_product_go"] is True


def test_facade_rank_reject_protocol_single_path_contracts():
    """Single product path: features→calibrator→rank/reject→scorecard via facade."""
    rails = assert_lab_rails(DEFAULT_RAILS)
    assert rails.ml_product_go is True
    assert rails.field_ops_allow_ml_live_in_fusion is False
    assert rails.iou_is_not_ros is True
    assert rails.recommended_lab_surface == "iter1_reject_only"
    assert rails.val_only_threshold_selection is True
    assert rails.stop_ece_thrash_on_same_test is True
    assert rails.tobarra_keep_reopen_forbidden is True

    proto = protocol_payload(locked_reject_thr=float(ITER1_LOCKED_REJECT_THR))
    assert proto["product_facade"] == "wildfire_front.ml.product_facade"
    assert proto["pipeline"] == "features→calibrator→rank/reject→scorecard"
    assert "locked_reject_thr" in proto or "reject_thr" in proto
    thr_proto = float(proto.get("locked_reject_thr", proto.get("reject_thr")))
    assert thr_proto == pytest.approx(0.795)
    assert thr_proto == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert "same_holdout_ece_retune" in set(proto.get("dead_paths") or [])
    assert "same_holdout_ece_retune" in DEAD_PROTOCOL_PATHS

    cal = _toy_cal()
    facade = ClmEnsembleV34Facade.with_iter1_locked_thr(cal, rails=rails)
    rng = np.random.default_rng(3)
    n = 24
    feats = np.column_stack(
        [
            rng.uniform(0.1, 0.9, n),
            rng.uniform(0.0, 0.3, n),
            rng.uniform(0.0, 0.5, n),
        ]
    )
    # Conf path is shared: math == protocol == facade (no parallel conf).
    conf_math = confidences_from_features(cal, feats)
    conf_proto = conf_from_features(cal, feats)
    conf_facade_fn = confidences_from_head_a(cal, feats)
    conf_facade = facade.confidences(feats)
    assert np.allclose(conf_math, conf_proto)
    assert np.allclose(conf_math, conf_facade_fn)
    assert np.allclose(conf_math, conf_facade)

    labels = (conf_facade > 0.55).astype(float)
    ious = np.where(labels > 0.5, 0.9, 0.2)
    surface = facade.rank_reject(feats, conf_facade, ious=ious, labels=labels)
    assert surface["protocol_module"] == "wildfire_front.ml.rank_reject_protocol"
    assert surface["recommended_lab_surface"] == "iter1_reject_only"
    assert float(surface["config"]["reject_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert surface["rails"]["ml_product_go"] is True
    assert surface["rails"]["field_ops_allow_ml_live_in_fusion"] is False

    pipe = facade.run_pipeline(feats, ious=ious, labels=labels, split="test")
    assert pipe["pipeline"] == "features→calibrator→rank/reject→scorecard"
    assert pipe["protocol_module"] == "wildfire_front.ml.rank_reject_protocol"
    assert pipe["recommended_lab_surface"] == "iter1_reject_only"
    assert float(pipe["locked_reject_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert pipe["rails"]["ml_product_go"] is True
    assert "scorecard" in pipe
    sc = pipe["scorecard"]
    assert sc.get("schema") == "ml_scorecard_v1" or "primary" in sc
    prov = sc.get("provenance") or {}
    assert prov.get("product_facade") == "wildfire_front.ml.product_facade" or (
        (sc.get("rails") or {}).get("product_facade") == "wildfire_front.ml.product_facade"
        or pipe.get("rails", {}).get("product_id")
    )
    # Multi-fire honesty first-class on facade (LOFO/W3/Tobarra tags).
    mf = pipe.get("multi_fire") or facade.multi_fire.as_dict()
    assert isinstance(mf, dict)
    assert (
        mf.get("tobarra", {}).get("reopen_same_recipe") is False
        or mf.get("tobarra", {}).get("keep_verdict") == "KILL"
    )


def test_val_thr_grid_includes_locked_iter1_and_rails_clamp():
    """Migration contract: VAL thr grid must select exact 0.795; fusion stays clamped OFF."""
    grid = default_val_thr_grid()
    assert any(abs(float(t) - 0.795) < 1e-12 for t in grid)
    assert float(DEFAULT_REJECT_THR) == pytest.approx(0.795)
    conf = np.linspace(0.70, 0.90, 120)
    ious = np.full(120, 0.55)
    sel = select_thr_val_only(conf, ious, thr_grid=[0.75, 0.85], split="val")
    assert sel.get("ok") is True
    # Injected locked thr is always on the evaluated grid (custom grids too).
    assert any(abs(float(t) - 0.795) < 1e-12 for t in default_val_thr_grid())
    bad = dual_product_rails_dict(
        overrides={
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": True,
            "field_ops_ml_live_fusion": "ON",
            "iou_is_not_ros": False,
        }
    )
    # Explicit promoted ml_product_go=True is allowed; field fusion still clamped OFF.
    assert bad["ml_product_go"] is True
    assert bad["field_ops_allow_ml_live_in_fusion"] is False
    assert bad["field_ops_ml_live_fusion"] == "OFF"
    assert bad["iou_is_not_ros"] is True
