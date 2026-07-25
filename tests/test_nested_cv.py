"""Offline nested CV + improved logistic fit tests (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.nested_cv import (
    HONEST_NESTED_ECE_NOTE,
    make_holdout_indices,
    make_kfold_indices,
    nested_cv_provenance_block,
    val_inner_outer_fit_eval,
    val_nested_fit_eval,
)
from wildfire_front.ml.protocol_rails import ProtocolRailError, SplitContext
from wildfire_front.ml.reliability_metrics import ece_patch_conf
from wildfire_front.ml.uncertainty import (
    fit_logistic_calibrator,
    fit_platt_on_logits,
    fit_temperature_on_logits,
    logistic_sigmoid,
    predict_proba_rows,
)


def _synthetic_features(n: int = 80, seed: int = 0):
    """Features with partial signal for IoU>=tau labels (calibratable)."""
    rng = np.random.default_rng(seed)
    quality = rng.uniform(0, 1, size=n)
    mean_entropy = (1.0 - quality) * 0.8 + rng.normal(0, 0.05, size=n)
    member_disagreement = (1.0 - quality) * 0.4 + rng.normal(0, 0.03, size=n)
    mean_margin = quality * 0.45 + rng.normal(0, 0.03, size=n)
    X = np.stack(
        [
            np.clip(mean_entropy, 0, 1),
            np.clip(member_disagreement, 0, 1),
            np.clip(mean_margin, 0, 1),
        ],
        axis=1,
    )
    p = 1.0 / (1.0 + np.exp(-(quality - 0.45) * 8.0))
    y = (rng.uniform(0, 1, size=n) < p).astype(int)
    ious = 0.2 + 0.7 * quality + rng.normal(0, 0.05, size=n)
    ious = np.clip(ious, 0, 1)
    rows = [X[i] for i in range(n)]
    return rows, y.tolist(), ious.tolist()


def test_kfold_indices_cover_all():
    pairs = make_kfold_indices(20, n_folds=5, seed=42)
    assert len(pairs) == 5
    all_outer = np.concatenate([te for _, te in pairs])
    assert sorted(all_outer.tolist()) == list(range(20))
    for tr, te in pairs:
        assert len(set(tr.tolist()) & set(te.tolist())) == 0
        assert len(tr) + len(te) == 20


def test_holdout_indices_frac():
    inner, outer = make_holdout_indices(100, inner_frac=0.7, seed=1)
    assert len(inner) + len(outer) == 100
    assert abs(len(inner) / 100 - 0.7) <= 0.02
    assert len(set(inner.tolist()) & set(outer.tolist())) == 0


def test_nested_refuses_test_context():
    rows, labels, ious = _synthetic_features(30)
    with pytest.raises(ProtocolRailError):
        val_nested_fit_eval(
            rows,
            labels,
            split_context=SplitContext(split="test", action="report"),
            ious=ious,
            n_folds=3,
        )
    with pytest.raises(ProtocolRailError):
        val_nested_fit_eval(
            rows,
            labels,
            split_context=SplitContext(split="val", action="report"),
            ious=ious,
            n_folds=3,
        )


def test_val_nested_fit_eval_reports_ece():
    rows, labels, ious = _synthetic_features(100, seed=7)
    ctx = SplitContext(split="val", action="fit_uncertainty")
    base_ece = ece_patch_conf([0.9] * len(labels), labels, n_bins=10)

    m = val_nested_fit_eval(
        rows,
        labels,
        split_context=ctx,
        ious=ious,
        n_folds=5,
        seed=42,
        n_iter=400,
        class_weight=True,
        second_stage="none",
        l2_grid=(1e-2, 1e-1),
    )
    assert m["k"] == 5
    assert m["n_patches"] == 100
    assert np.isfinite(m["nested_val_ece_mean"])
    assert m["nested_val_ece_mean"] >= 0.0
    assert m["nested_logistic_ece_mean"] == m["nested_val_ece_mean"]
    assert m["second_stage_in_nested_scoring"] is False
    assert "recommended_l2" in m
    assert m["mean_u1b"] is not None
    prov = nested_cv_provenance_block(m)
    assert prov["k"] == 5
    assert prov["mean_ece"] == m["mean_ece"]
    assert prov["second_stage_in_nested_scoring"] is False
    _ = base_ece


def test_nested_platt_does_not_fit_second_stage_on_outer():
    """Protocol b: nested ECE is logistic-only even when second_stage=platt."""
    rows, labels, ious = _synthetic_features(80, seed=3)
    ctx = SplitContext(split="val", action="fit_uncertainty")
    m_none = val_nested_fit_eval(
        rows,
        labels,
        split_context=ctx,
        ious=ious,
        n_folds=4,
        seed=1,
        n_iter=300,
        class_weight=False,
        second_stage="none",
        l2_grid=(5e-2,),
    )
    m_platt = val_nested_fit_eval(
        rows,
        labels,
        split_context=ctx,
        ious=ious,
        n_folds=4,
        seed=1,
        n_iter=300,
        class_weight=False,
        second_stage="platt",
        l2_grid=(5e-2,),
    )
    # Nested ECE must be identical: second_stage must not touch outer scoring
    assert m_platt["nested_val_ece_mean"] == pytest.approx(m_none["nested_val_ece_mean"], abs=1e-12)
    assert m_platt["second_stage"] == "platt"
    assert m_platt["second_stage_in_nested_scoring"] is False
    assert all(f.get("second_stage_fit_on_outer") is False for f in m_platt["folds"])
    assert "logistic-only" in m_platt["honesty"].lower() or "logistic" in m_platt["honesty"].lower()
    assert (
        HONEST_NESTED_ECE_NOTE.split("(")[0] in m_platt["honesty"]
        or "outer never" in m_platt["honesty"]
    )


def test_nested_with_temperature_second_stage_label_only():
    rows, labels, ious = _synthetic_features(60, seed=3)
    ctx = SplitContext(split="val", action="calibrate")
    m = val_nested_fit_eval(
        rows,
        labels,
        split_context=ctx,
        ious=ious,
        n_folds=3,
        seed=0,
        n_iter=300,
        second_stage="temperature",
        l2_grid=(1e-2,),
    )
    assert m["second_stage"] == "temperature"
    assert m["second_stage_in_nested_scoring"] is False
    assert np.isfinite(m["nested_val_ece_mean"])


def test_inner_outer_protocol_separates_logistic_and_second_stage_ece():
    rows, labels, ious = _synthetic_features(50, seed=2)
    ctx = SplitContext(split="val", action="fit_uncertainty")
    m = val_inner_outer_fit_eval(
        rows,
        labels,
        split_context=ctx,
        ious=ious,
        inner_frac=0.7,
        second_stage="platt",
        n_iter=300,
    )
    assert m["mode"] == "inner_outer"
    assert np.isfinite(m["nested_val_ece_mean"])
    assert m["nested_val_ece_mean"] == m["outer_logistic_ece"]
    assert "outer_second_stage_ece" in m
    assert m.get("calibrator") is not None
    # nested-style ECE is logistic, not the optimistic same-outer second-stage ECE
    assert m["nested_val_ece_mean"] == m["outer_logistic_ece"]


def test_class_weight_and_more_iters_fit():
    rows, labels, _ = _synthetic_features(40, seed=11)
    labels = [1] * 35 + [0] * 5
    ctx = SplitContext(split="val", action="fit_uncertainty")
    cal = fit_logistic_calibrator(
        rows,
        labels,
        split_context=ctx,
        n_iter=500,
        class_weight=True,
        l2=0.05,
    )
    assert cal.weights.size == 4
    confs = predict_proba_rows(cal, rows)
    assert all(0.0 <= c <= 1.0 for c in confs)


def test_temperature_and_platt_helpers():
    logits = [3.0, 2.5, 2.0, -0.1, -0.2, 2.8, 0.0, 1.5]
    labels = [1, 1, 0, 0, 0, 1, 0, 1]
    t = fit_temperature_on_logits(logits, labels, n_iter=100)
    assert t > 0
    a, b = fit_platt_on_logits(logits, labels, n_iter=150)
    assert np.isfinite(a) and np.isfinite(b)
    p_raw = [logistic_sigmoid(z) for z in logits]
    p_t = [logistic_sigmoid(z / t) for z in logits]
    assert len(p_t) == len(p_raw)


def test_promote_refuses_catalog_holdout_iou():
    """A7: primary.model_iou ≈ 0.8963 or catalog/missing source → refuse."""
    from scripts.promote_ml_live_fusion import validate_promote_eligibility

    base = {
        "schema": "ml_scorecard_v1",
        "product_id": "clm_ensemble_v34",
        "split": "test",
        "u1_eval_split": "test",
        "calibrator_fit_split": "val",
        "allow_ml_live_in_fusion_recommended": True,
        "gates": {"u1_test_honest": True, "ml_product_go": False},
        "primary": {
            "model_iou": 0.8963,
            "model_iou_source": "eval_split_mean",
            "n_patches": 100,
        },
        "uncertainty": {"n_patches": 100},
        "provenance": {
            "offline": False,
            "frozen_calibrator": True,
            "identity_calibrator": False,
            "eval_dir": "data/clm/test",
        },
        "schema_validation": {"pass": True},
    }
    fails = validate_promote_eligibility(base, allow_lab_synthetic=True)
    assert any("catalog_holdout" in f or "0.8963" in f for f in fails)

    missing_src = dict(base)
    missing_src["primary"] = {
        "model_iou": 0.85,
        "n_patches": 100,
    }
    fails2 = validate_promote_eligibility(missing_src, allow_lab_synthetic=True)
    assert any("model_iou_source_missing_or_catalog" in f for f in fails2)

    catalog_src = dict(base)
    catalog_src["primary"] = {
        "model_iou": 0.85,
        "model_iou_source": "catalog",
        "n_patches": 100,
    }
    fails3 = validate_promote_eligibility(catalog_src, allow_lab_synthetic=True)
    assert any("model_iou_source_missing_or_catalog" in f for f in fails3)


def test_promote_still_refuses_without_u1_test_honest(tmp_path: Path):
    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import main, validate_promote_eligibility

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="val",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        frozen_calibrator=True,
        calibrator_fit_split="val",
        u1_eval_split="val",
        nested_cv={"k": 5, "mean_ece": 0.1, "mean_u1b": 1.0},
    )
    assert doc["provenance"]["nested_cv"]["k"] == 5
    fails = validate_promote_eligibility(doc)
    assert any("u1_test_honest" in f for f in fails)
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps(doc), encoding="utf-8")
    rc = main(
        [
            "--scorecard",
            str(sc),
            "--promote-record",
            str(tmp_path / "rec.json"),
            "--product-scorecard",
            str(tmp_path / "prod.json"),
            "--write-docs-scorecard",
            "--apply-policy",
        ]
    )
    assert rc == 2
    assert not (tmp_path / "prod.json").is_file()


def test_promote_rejects_synthetic_without_allow_flag(tmp_path: Path):
    """BUG2: offline/synthetic scorecards must not promote or apply-policy by default."""
    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import main, validate_promote_eligibility

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="test",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        frozen_calibrator=True,
        identity_calibrator=False,
        calibrator_fit_split="val",
        u1_eval_split="test",
    )
    fails = validate_promote_eligibility(doc, allow_lab_synthetic=False)
    assert any("offline_or_synthetic" in f for f in fails)
    # Even with allow_lab_synthetic, offline is OK for lab tests
    fails_lab = validate_promote_eligibility(doc, allow_lab_synthetic=True)
    assert fails_lab == []

    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps(doc), encoding="utf-8")
    rc = main(
        [
            "--scorecard",
            str(sc),
            "--promote-record",
            str(tmp_path / "rec.json"),
            "--product-scorecard",
            str(tmp_path / "prod.json"),
            "--write-docs-scorecard",
            "--apply-policy",
        ]
    )
    assert rc == 2
    assert not (tmp_path / "prod.json").is_file()


def test_promote_eligible_real_like_and_lab_synthetic_flag(tmp_path: Path):
    """Lab synthetic path requires --allow-lab-synthetic; field_ops never enabled."""
    import scripts.promote_ml_live_fusion as promo
    from scripts.ml_scorecard import build_scorecard

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="test",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        frozen_calibrator=True,
        identity_calibrator=False,
        calibrator_fit_split="val",
        u1_eval_split="test",
        nested_cv={
            "k": 5,
            "nested_val_ece_mean": 0.08,
            "mean_u1b": 0.8,
            "second_stage_in_nested_scoring": False,
        },
    )
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps(doc), encoding="utf-8")

    policy = {
        "schema": "decision_policies_v1",
        "policies": {
            "field_ops": {"id": "field_ops", "allow_ml_live_in_fusion": False},
            "research_open": {"id": "research_open", "allow_ml_live_in_fusion": False},
        },
    }
    pol = tmp_path / "pol.json"
    pol.write_text(json.dumps(policy), encoding="utf-8")
    orig = promo.POLICY_PATH
    promo.POLICY_PATH = pol
    try:
        rc = promo.main(
            [
                "--scorecard",
                str(sc),
                "--promote-record",
                str(tmp_path / "rec.json"),
                "--product-scorecard",
                str(tmp_path / "ML_PRODUCT_SCORECARD.json"),
                "--write-docs-scorecard",
                "--apply-policy",
                "--allow-lab-synthetic",
            ]
        )
    finally:
        promo.POLICY_PATH = orig

    assert rc == 0
    prod = json.loads((tmp_path / "ML_PRODUCT_SCORECARD.json").read_text(encoding="utf-8"))
    assert prod["gates"]["ml_product_go"] is False
    assert prod["gates"]["u1_test_honest"] is True
    assert prod["claim_surface"]["not_ros"] is True
    assert prod["claim_surface"]["research_open_live_fusion"] == "experimental"
    assert "nested_cv" in prod["provenance"]
    assert "primary_ros_m_min" not in (prod.get("primary") or {})
    pol_after = json.loads(pol.read_text(encoding="utf-8"))
    assert pol_after["policies"]["research_open"]["allow_ml_live_in_fusion"] is True
    assert pol_after["policies"]["field_ops"]["allow_ml_live_in_fusion"] is False
    rec = json.loads((tmp_path / "rec.json").read_text(encoding="utf-8"))
    assert rec["policy"]["field_ops_always_false"] is True


def test_promote_accepts_real_scorecard_shape(tmp_path: Path):
    """Real-ish scorecard: offline false, n_patches>=50, eval_dir with test."""
    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import main, validate_promote_eligibility

    # Start from a U1-passing fixture shape, then mark as real holdout provenance
    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="test",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        frozen_calibrator=True,
        identity_calibrator=False,
        calibrator_fit_split="val",
        u1_eval_split="test",
        eval_dir=str(tmp_path / "holdout_v1" / "test"),
    )
    doc["primary"]["n_patches"] = 200
    doc["uncertainty"]["n_patches"] = 200
    doc["provenance"]["offline"] = False
    doc["provenance"]["synthetic_mode"] = None
    doc["provenance"]["eval_dir"] = str(tmp_path / "holdout_v1" / "test")
    doc["provenance"]["frozen_calibrator"] = True
    doc["provenance"]["identity_calibrator"] = False
    fails = validate_promote_eligibility(doc, allow_lab_synthetic=False)
    assert fails == [], fails

    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps(doc), encoding="utf-8")
    rc = main(
        [
            "--scorecard",
            str(sc),
            "--promote-record",
            str(tmp_path / "rec.json"),
            "--product-scorecard",
            str(tmp_path / "prod.json"),
        ]
    )
    assert rc == 0
    assert (tmp_path / "prod.json").is_file()
