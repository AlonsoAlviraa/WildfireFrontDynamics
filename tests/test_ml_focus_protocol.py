"""ML-focus protocol rails, reliability metrics, uncertainty, live Decision Card."""

from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.ml.protocol_rails import (
    ProtocolRailError,
    SplitContext,
    assert_split_role,
    reject_ros_keys_in_primary,
    validate_scorecard_tuning,
)
from wildfire_front.ml.reliability_metrics import (
    ece_patch_conf,
    random_selective_baseline,
    selective_beats_random,
    selective_iou_at_coverage,
    shuffle_conf_baseline,
)
from wildfire_front.ml.scorecard_schema import scorecard_gates_pass, validate_ml_scorecard
from wildfire_front.ml.uncertainty import (
    LogisticCalibrator,
    ensemble_diagnostics,
    features_from_diagnostics,
    fit_logistic_calibrator,
)
from wildfire_front.product.confidence import (
    ML_LIVE_SOURCE_ID,
    Decision,
    build_decision_card,
    score_ml_live_source,
)


def test_refuse_tune_mix_on_test():
    with pytest.raises(ProtocolRailError):
        assert_split_role("test", "tune_mix")
    with pytest.raises(ProtocolRailError):
        assert_split_role("lofo", "tune_temperature")


def test_val_tune_mix_ok():
    assert_split_role("val", "tune_mix")
    assert_split_role("test", "report")
    ctx = SplitContext(split="val", action="tune_mix")
    assert ctx.protocol


def test_reject_ros_in_primary():
    with pytest.raises(ProtocolRailError):
        reject_ros_keys_in_primary({"model_iou": 0.9, "primary_ros_m_min": 5.0})


def test_scorecard_tuning_must_be_val():
    fails = validate_scorecard_tuning(
        {
            "mix_split": "test",
            "temperature_split": "val",
            "uncertainty_calibration_split": "val",
        }
    )
    assert any("mix_split" in f for f in fails)


def test_scorecard_schema_gates():
    doc = {
        "schema": "ml_scorecard_v1",
        "product_id": "clm_ensemble_v34",
        "protocol": "clm_holdout_test_seed42_v1",
        "split": "test",
        "action": "report",
        "tuning": {
            "mix_split": "val",
            "temperature_split": "val",
            "uncertainty_calibration_split": "val",
        },
        "primary": {"model_iou": 0.8963, "improvement_vs_copy_iou": 0.2545},
        "uncertainty": {"ece_patch_conf": 0.05},
    }
    assert validate_ml_scorecard(doc) == []
    assert scorecard_gates_pass(doc)["pass"] is True
    bad = dict(doc)
    bad["primary"] = {"model_iou": 0.9, "vp_tactical": 7.0}
    assert scorecard_gates_pass(bad)["pass"] is False
    # split/action role must be consistent
    bad_role = dict(doc)
    bad_role["split"] = "test"
    bad_role["action"] = "tune_mix"
    fails = validate_ml_scorecard(bad_role)
    assert any("split_role" in f or "tune_mix" in f for f in fails)


def test_ensemble_diagnostics_pure():
    a = np.full((16, 16), 0.2)
    b = np.full((16, 16), 0.8)
    d = ensemble_diagnostics([a, b])
    assert d["n_members"] == 2.0
    assert d["member_disagreement"] > 0.3
    assert d["mean_entropy"] > 0
    feats = features_from_diagnostics(d)
    assert feats.shape == (3,)


def test_ece_and_selective():
    conf = [0.9, 0.8, 0.2, 0.1]
    y = [1, 1, 0, 0]
    ece = ece_patch_conf(conf, y, n_bins=4)
    assert 0.0 <= ece < 0.5
    ious = [0.9, 0.85, 0.1, 0.05]
    sel = selective_iou_at_coverage(ious, conf, coverage=0.5)
    assert sel["selective_iou"] > 0.8
    rnd = random_selective_baseline(ious, coverage=0.5, n_trials=20, seed=1)
    assert np.isfinite(rnd["random_selective_iou_mean"])
    shuf = shuffle_conf_baseline(ious, conf, coverage=0.5, n_trials=20, seed=1)
    assert np.isfinite(shuf["shuffle_selective_iou_mean"])
    util = selective_beats_random(ious, conf, coverage=0.5, n_trials=20, seed=1)
    assert util["beats_random"] is True
    assert util["margin"] == 0.01


def test_ece_known_bins():
    """Exact ECE unit test: perfect calibration → ECE ≈ 0."""
    conf = [0.0, 0.0, 1.0, 1.0]
    y = [0, 0, 1, 1]
    ece = ece_patch_conf(conf, y, n_bins=2)
    assert ece == pytest.approx(0.0, abs=1e-9)
    # Fully miscalibrated: conf always 1, labels always 0
    ece_bad = ece_patch_conf([1.0, 1.0, 1.0, 1.0], [0, 0, 0, 0], n_bins=2)
    assert ece_bad == pytest.approx(1.0, abs=1e-9)


def test_selective_coverage_edge():
    ious = [0.9, 0.5, 0.1]
    conf = [0.9, 0.5, 0.1]
    empty = selective_iou_at_coverage(ious, conf, coverage=0.0)
    assert empty["n_keep"] == 0
    assert not np.isfinite(empty["selective_iou"])
    full = selective_iou_at_coverage(ious, conf, coverage=1.0)
    assert full["n_keep"] == 3


def test_logistic_calibrator_fit_3_features():
    """3-feature Head A path (design freeze)."""
    rows = [
        np.array([0.1, 0.05, 0.4]),
        np.array([0.9, 0.4, 0.05]),
        np.array([0.2, 0.1, 0.35]),
        np.array([0.8, 0.35, 0.1]),
        np.array([0.15, 0.08, 0.38]),
        np.array([0.85, 0.38, 0.08]),
    ]
    labels = [1, 0, 1, 0, 1, 0]
    ctx = SplitContext(split="val", action="fit_uncertainty")
    cal = fit_logistic_calibrator(rows, labels, split_context=ctx, n_iter=120)
    assert cal.method == "logistic"
    assert cal.weights.size == 4  # 3 features + bias
    p_hi = cal.predict_proba(
        {
            "mean_entropy": 0.1,
            "member_disagreement": 0.05,
            "mean_margin": 0.4,
        }
    )
    p_lo = cal.predict_proba(
        {
            "mean_entropy": 0.9,
            "member_disagreement": 0.4,
            "mean_margin": 0.05,
        }
    )
    assert p_hi > p_lo


def test_fit_logistic_requires_split_context():
    with pytest.raises(TypeError):
        fit_logistic_calibrator([np.array([0.1, 0.1, 0.1])], [1])
    with pytest.raises(ProtocolRailError):
        fit_logistic_calibrator(
            [np.array([0.1, 0.1, 0.1])],
            [1],
            split_context=SplitContext(split="test", action="fit_uncertainty"),
        )


def test_calibrator_rejects_wrong_weight_length():
    cal = LogisticCalibrator(weights=np.array([0.1, 0.2]))  # too short for 3 features
    with pytest.raises(ValueError, match="weight length"):
        cal.predict_proba({"mean_entropy": 0.1, "member_disagreement": 0.1, "mean_margin": 0.3})


def test_identity_calibrator_safe_default():
    cal = LogisticCalibrator.identity()
    conf = cal.predict_proba(
        {"mean_entropy": 0.05, "member_disagreement": 0.01, "mean_margin": 0.45}
    )
    assert conf == pytest.approx(0.5)


def test_score_ml_live_orthogonal_flags():
    # high conf, fusion off → actionable but weight 0
    s = score_ml_live_source(
        {
            "schema": "ml_live_metrics_v1",
            "confidence": 0.8,
            "abstain": False,
            "mean_entropy": 0.2,
            "member_disagreement": 0.05,
            "mean_margin": 0.3,
        },
        allow_ml_live_in_fusion=False,
    )
    assert s["id"] == ML_LIVE_SOURCE_ID
    assert s["id"] == "ml_live_reliability"
    assert s["role"] == "live_ml"
    assert s["source_type"] == "live_prediction"
    assert s["available"] is True
    assert s["actionable"] is True
    assert s["weight"] == 0.0
    # low conf → abstained
    s2 = score_ml_live_source(
        {"schema": "ml_live_metrics_v1", "confidence": 0.1, "abstain": False},
        allow_ml_live_in_fusion=True,
    )
    assert s2["abstained"] is True
    assert s2["actionable"] is False
    assert s2["weight"] == 0.0
    # untrusted: available for audit, not actionable
    s3 = score_ml_live_source(
        {"schema": "ml_live_metrics_v1", "confidence": 0.9},
        trusted=False,
    )
    assert s3["available"] is True
    assert s3["actionable"] is False
    assert s3["weight"] == 0.0
    # wrong schema rejected
    s4 = score_ml_live_source({"confidence": 0.9, "schema": "other"})
    assert s4["available"] is False


def test_ml_live_reliability_id_lookup():
    """id=ml_live_reliability is the design source id used by card packing."""
    card = build_decision_card(
        "id_lookup",
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.75,
            "abstain": False,
            "mean_entropy": 0.15,
            "member_disagreement": 0.04,
            "mean_margin": 0.35,
            "product_id": "clm_ensemble_v34",
        },
        allow_ml_live_in_fusion=False,
        ml_live_trusted=True,
    )
    assert any(s.get("id") == "ml_live_reliability" for s in card.sources)
    assert card.metrics.get("ml_live") is not None


def test_ml_only_live_hold_fusion_off():
    """Issue 15: live HOLD without fusion weight."""
    card = build_decision_card(
        "ml_live_evt",
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.75,
            "abstain": False,
            "mean_entropy": 0.15,
            "member_disagreement": 0.04,
            "mean_margin": 0.35,
            "product_id": "clm_ensemble_v34",
        },
        allow_ml_live_in_fusion=False,
        ml_live_trusted=True,
    )
    assert card.decision == Decision.HOLD
    assert any(s.get("id") == "ml_live_reliability" and s.get("actionable") for s in card.sources)
    assert any(
        s.get("id") == "ml_live_reliability" and s.get("weight") == 0.0 for s in card.sources
    )
    assert card.metrics.get("live_ok") is True


def test_ml_live_abstain_low_conf():
    card = build_decision_card(
        "ml_live_ab",
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.1,
            "abstain": True,
        },
        allow_ml_live_in_fusion=False,
    )
    assert card.decision == Decision.ABSTAIN
    assert card.confidence_pred == 0.0


def test_live_abstained_plus_holdout_conf_zero():
    """Live abstained + holdout present → ABSTAIN and confidence_pred == 0 (never holdout)."""
    card = build_decision_card(
        "live_ab_holdout",
        ml_metrics={
            "test_iou": 0.8963,
            "improvement_vs_copy_iou": 0.2545,
        },
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.12,
            "abstain": True,
            "mean_entropy": 0.7,
            "member_disagreement": 0.3,
            "mean_margin": 0.05,
        },
        allow_ml_live_in_fusion=False,
        ml_live_trusted=True,
    )
    assert card.decision == Decision.ABSTAIN
    assert card.confidence_pred == 0.0
    assert card.confidence_pred_label in ("VERY_LOW", "LOW")
    assert "ml_live_abstained_conf_zero" in " ".join(card.reasons)
    assert "ml_holdout_quality_display" not in " ".join(card.reasons)


def test_untrusted_live_plus_holdout_no_catalog_hold():
    """Untrusted live channel present + holdout → must not HOLD from catalog."""
    card = build_decision_card(
        "untrusted_holdout",
        ml_metrics={
            "test_iou": 0.8963,
            "improvement_vs_copy_iou": 0.2545,
        },
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.9,
            "abstain": False,
        },
        allow_ml_live_in_fusion=False,
        ml_live_trusted=False,
    )
    assert card.decision == Decision.ABSTAIN
    live = next(s for s in card.sources if s.get("id") == "ml_live_reliability")
    assert live["available"] is True
    assert live["actionable"] is False
    assert card.confidence_pred == 0.0
    assert "ml_live_untrusted_conf_zero" in " ".join(card.reasons)
    assert "ml_holdout_quality_display" not in " ".join(card.reasons)


def test_bad_schema_live_blocks_holdout_fallthrough():
    """ml_live_metrics requested with bad schema → conf=0, no holdout HOLD."""
    card = build_decision_card(
        "bad_schema",
        ml_metrics={
            "test_iou": 0.8963,
            "improvement_vs_copy_iou": 0.2545,
        },
        ml_live_metrics={"confidence": 0.95},  # no schema / wrong
        allow_ml_live_in_fusion=False,
        ml_live_trusted=True,
    )
    assert card.decision == Decision.ABSTAIN
    assert card.confidence_pred == 0.0
    assert "ml_live_invalid_schema_conf_zero" in " ".join(card.reasons)
    assert "ml_holdout_quality_display" not in " ".join(card.reasons)


def test_confidence_only_schema_rejected():
    """Blob with only confidence key is not a live source."""
    s = score_ml_live_source({"confidence": 0.99})
    assert s["available"] is False
    assert s["actionable"] is False
    assert s.get("invalid_schema") is True


def test_score_mix_from_cache_test_tune_mix_raises():
    from wildfire_front.ml.clm_eval import score_mix_from_cache

    cache = {
        "n_members": 2,
        "n_patches": 1,
        "weights": ["a", "b"],
        "growth": [np.zeros((1, 4, 4)), np.zeros((1, 4, 4))],
        "prev": [np.zeros((4, 4))],
        "target": [np.ones((4, 4))],
    }
    with pytest.raises(ProtocolRailError):
        score_mix_from_cache(
            cache,
            [0.5, 0.5],
            split_context=SplitContext(split="test", action="tune_mix"),
            threshold=0.5,
        )


def test_sweep_mix_requires_split_context():
    from wildfire_front.ml.clm_eval import sweep_mix_threshold_from_cache

    cache = {
        "n_members": 2,
        "n_patches": 1,
        "weights": ["a", "b"],
        "growth": [np.zeros((1, 4, 4)), np.zeros((1, 4, 4))],
        "prev": [np.zeros((4, 4))],
        "target": [np.ones((4, 4))],
    }
    with pytest.raises(TypeError):
        sweep_mix_threshold_from_cache(cache, [[0.5, 0.5]])  # type: ignore[call-arg]
    with pytest.raises(ProtocolRailError):
        sweep_mix_threshold_from_cache(
            cache,
            [[0.5, 0.5]],
            thresholds=[0.5],
            split_context=SplitContext(split="test", action="tune_mix"),
        )


def test_pack_by_id_not_index():
    """Ops metrics must resolve by id even if source list order changes."""
    card = build_decision_card(
        "ops_id",
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 4.0,
            "n_frames_staged": 10,
        },
        open_metrics={"max_area_ha": 800, "n_timeline_steps": 4},
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.6,
            "abstain": False,
        },
        allow_ml_live_in_fusion=False,
    )
    assert card.metrics["ops"] is not None
    assert "quality_grade" in card.metrics["ops"]
    assert card.metrics["ml_live"] is not None
    # reorder should not matter — build always packs by id
    assert card.decision in (Decision.GO, Decision.HOLD)


def test_logistic_rejects_isotonic():
    with pytest.raises(ValueError):
        LogisticCalibrator(weights=[0.1, 0.2], method="isotonic")


def test_input_hash_includes_ml_live():
    a = build_decision_card(
        "h1",
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.7,
            "abstain": False,
        },
    )
    b = build_decision_card(
        "h1",
        ml_live_metrics={
            "schema": "ml_live_metrics_v1",
            "confidence": 0.2,
            "abstain": True,
        },
    )
    assert a.audit["input_hash"] != b.audit["input_hash"]


def test_input_hash_includes_fusion_and_trust_flags():
    base = {
        "schema": "ml_live_metrics_v1",
        "confidence": 0.7,
        "abstain": False,
        "mean_entropy": 0.2,
        "member_disagreement": 0.05,
        "mean_margin": 0.3,
    }
    a = build_decision_card(
        "h2", ml_live_metrics=base, allow_ml_live_in_fusion=False, ml_live_trusted=True
    )
    b = build_decision_card(
        "h2", ml_live_metrics=base, allow_ml_live_in_fusion=True, ml_live_trusted=True
    )
    c = build_decision_card(
        "h2", ml_live_metrics=base, allow_ml_live_in_fusion=False, ml_live_trusted=False
    )
    assert a.audit["input_hash"] != b.audit["input_hash"]
    assert a.audit["input_hash"] != c.audit["input_hash"]


def test_fusion_weight_positive_with_diags():
    s = score_ml_live_source(
        {
            "schema": "ml_live_metrics_v1",
            "confidence": 0.8,
            "abstain": False,
            "mean_entropy": 0.2,
            "member_disagreement": 0.05,
            "mean_margin": 0.3,
        },
        allow_ml_live_in_fusion=True,
        ml_live_max_weight=0.25,
        trusted=True,
    )
    assert s["actionable"] is True
    assert s["weight"] == pytest.approx(0.25)
    # missing diags → actionable ok, fusion weight 0
    s2 = score_ml_live_source(
        {
            "schema": "ml_live_metrics_v1",
            "confidence": 0.8,
            "abstain": False,
        },
        allow_ml_live_in_fusion=True,
        ml_live_max_weight=0.25,
        trusted=True,
    )
    assert s2["actionable"] is True
    assert s2["weight"] == 0.0


def test_holdout_actionable_false():
    from wildfire_front.product.confidence import score_ml_source

    s = score_ml_source({"test_iou": 0.9, "improvement_vs_copy_iou": 0.25})
    assert s["available"] is True
    assert s["actionable"] is False
    assert s["weight"] == 0.0
    assert s["role"] == "holdout_quality"


def test_fit_logistic_rejects_report_action():
    with pytest.raises(ProtocolRailError):
        fit_logistic_calibrator(
            [np.array([0.1, 0.1, 0.1])],
            [1],
            split_context=SplitContext(split="val", action="report"),
        )


def test_decide_from_request_http_untrusted():
    from wildfire_front.product.decide_service import decide_from_request

    live = {
        "schema": "ml_live_metrics_v1",
        "confidence": 0.9,
        "abstain": False,
        "mean_entropy": 0.1,
        "member_disagreement": 0.02,
        "mean_margin": 0.4,
    }
    # Trusted CLI channel → may HOLD ML-only
    trusted = decide_from_request(
        {
            "event_id": "cli_live",
            "ml_live_metrics": live,
            "channel": "cli",
            "ml_live_trusted": True,
        }
    )
    assert trusted["decision"] == "HOLD"
    # HTTP forces untrusted → ABSTAIN even with high conf + holdout
    http = decide_from_request(
        {
            "event_id": "http_live",
            "ml_live_metrics": live,
            "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
            "channel": "http_api",
        }
    )
    assert http["decision"] == "ABSTAIN"
    assert float(http["confidence_pred"]) == 0.0
    live_src = next(s for s in http["sources"] if s.get("id") == "ml_live_reliability")
    assert live_src["available"] is True
    assert live_src["actionable"] is False


def test_decide_from_request_ml_prediction_path(tmp_path):
    import json

    from wildfire_front.product.decide_service import decide_from_request

    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "schema": "ml_live_metrics_v1",
                "confidence": 0.78,
                "abstain": False,
                "mean_entropy": 0.12,
                "member_disagreement": 0.03,
                "mean_margin": 0.36,
            }
        ),
        encoding="utf-8",
    )
    out = decide_from_request(
        {
            "event_id": "path_live",
            "ml_prediction": str(path),
            "channel": "cli",
        },
        base=tmp_path,
    )
    assert out["decision"] == "HOLD"
    assert out["metrics"]["ml_live"] is not None
