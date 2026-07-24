"""Honest U1 promote rules: fit VAL → eval TEST; no VAL-only fusion recommend."""

from __future__ import annotations

from pathlib import Path

import pytest

from wildfire_front.ml.scorecard_schema import validate_ml_scorecard
from wildfire_front.ml.u1_eval import (
    CATALOG_HOLDOUT_TEST_IOU,
    assert_eval_split_path,
    assert_never_fit_on_test,
    compute_fusion_recommendation,
    primary_from_eval_ious,
)


def test_fusion_rec_true_only_test_frozen_u1_pass():
    rec = compute_fusion_recommendation(
        eval_split="test",
        calibrator_fit_split="val",
        u1_pass=True,
        frozen_calibrator=True,
        identity_calibrator=False,
    )
    assert rec["allow_ml_live_in_fusion_recommended"] is True
    assert rec["u1_test_honest"] is True
    assert rec["u1_val_lab_pass"] is False
    assert rec["u1_val_optimistic"] is False


def test_val_eval_u1_pass_recommended_false():
    """VAL lab pass must never recommend fusion (optimistic / not test)."""
    rec = compute_fusion_recommendation(
        eval_split="val",
        calibrator_fit_split="val",
        u1_pass=True,
        frozen_calibrator=True,
        identity_calibrator=False,
    )
    assert rec["allow_ml_live_in_fusion_recommended"] is False
    assert rec["u1_val_lab_pass"] is True
    assert rec["u1_val_optimistic"] is True
    assert rec["u1_test_honest"] is False
    assert "u1_not_eval_on_test" in rec["reasons"]


def test_test_eval_identity_cal_not_recommended():
    rec = compute_fusion_recommendation(
        eval_split="test",
        calibrator_fit_split="val",
        u1_pass=True,
        frozen_calibrator=False,
        identity_calibrator=True,
    )
    assert rec["allow_ml_live_in_fusion_recommended"] is False
    assert rec["u1_test_honest"] is False
    assert "calibrator_not_frozen" in rec["reasons"]


def test_protocol_refuse_fit_on_test():
    with pytest.raises(ValueError, match="never fit"):
        assert_never_fit_on_test("fit_uncertainty", "test")
    with pytest.raises(ValueError, match="never fit"):
        assert_never_fit_on_test("calibrate", "test")
    # report on test is fine
    assert_never_fit_on_test("report", "test")


def test_protocol_refuse_split_path_mismatch(tmp_path: Path):
    val = tmp_path / "holdout_v1" / "val"
    val.mkdir(parents=True)
    test = tmp_path / "holdout_v1" / "test"
    test.mkdir(parents=True)
    with pytest.raises(ValueError, match="val|test"):
        assert_eval_split_path(val, "test")
    with pytest.raises(ValueError, match="test|val"):
        assert_eval_split_path(test, "val")
    assert_eval_split_path(test, "test")
    assert_eval_split_path(val, "val")


def test_primary_iou_not_catalog_without_split_label():
    primary = primary_from_eval_ious([0.5, 0.6, 0.7], eval_split="test")
    assert primary["model_iou"] == pytest.approx(0.6)
    assert primary["model_iou_split"] == "test"
    assert primary["model_iou_source"] == "eval_split_mean"
    # Catalog reference value must not silently become unlabeled model_iou
    assert (
        primary["model_iou"] != CATALOG_HOLDOUT_TEST_IOU
        or primary["model_iou_source"] == "eval_split_mean"
    )


def test_scorecard_val_synthetic_pass_not_recommended():
    from scripts.ml_scorecard import build_scorecard

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="val",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        calibrator_fit_split="val",
        frozen_calibrator=True,
        identity_calibrator=False,
        u1_eval_split="val",
    )
    assert validate_ml_scorecard(doc) == []
    assert doc["gates"]["u1_val_lab_pass"] is True
    assert doc["gates"]["U1a_selective_ge_full_minus_eps"] is True
    assert doc["gates"]["U1_selective_beats_random"] is True
    assert doc["allow_ml_live_in_fusion_recommended"] is False
    assert doc["gates"]["u1_test_honest"] is False
    assert "u1_not_eval_on_test" in doc["gates"]["reasons"]
    assert doc["gates"]["ml_product_go"] is False
    # primary is eval mean, not bare catalog 0.8963
    assert doc["primary"]["model_iou_source"] == "eval_split_mean"
    assert doc["primary"]["model_iou_split"] == "val"
    assert "catalog_holdout_test_reference" in doc["provenance"]
    cat = doc["provenance"]["catalog_holdout_test_reference"]
    assert cat["test_iou"] == pytest.approx(CATALOG_HOLDOUT_TEST_IOU)


def test_scorecard_test_synthetic_frozen_recommended():
    from scripts.ml_scorecard import build_scorecard

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="test",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        calibrator_fit_split="val",
        frozen_calibrator=True,
        identity_calibrator=False,
        u1_eval_split="test",
    )
    assert validate_ml_scorecard(doc) == []
    assert doc["gates"]["u1_test_honest"] is True
    assert doc["allow_ml_live_in_fusion_recommended"] is True
    assert doc["gates"]["ml_product_go"] is False
    assert doc["primary"]["model_iou_split"] == "test"
    assert abs(float(doc["primary"]["model_iou"]) - CATALOG_HOLDOUT_TEST_IOU) > 0.01


def test_promote_refuses_val_only_scorecard(tmp_path: Path):
    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import main, validate_promote_eligibility

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="val",
        action="scorecard",
        offline=True,
        synthetic_mode="pass",
        frozen_calibrator=True,
        identity_calibrator=False,
        calibrator_fit_split="val",
        u1_eval_split="val",
    )
    fails = validate_promote_eligibility(doc)
    assert any("u1_test_honest" in f for f in fails)

    sc = tmp_path / "sc.json"
    sc.write_text(__import__("json").dumps(doc), encoding="utf-8")
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
    assert rc == 2


def test_promote_accepts_test_honest(tmp_path: Path):
    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import main

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
    sc = tmp_path / "sc.json"
    sc.write_text(__import__("json").dumps(doc), encoding="utf-8")
    rec = tmp_path / "rec.json"
    prod = tmp_path / "prod.json"
    rc = main(
        [
            "--scorecard",
            str(sc),
            "--promote-record",
            str(rec),
            "--product-scorecard",
            str(prod),
            "--allow-lab-synthetic",  # offline fixture scorecard — lab only
        ]
    )
    assert rc == 0
    assert rec.is_file()
    assert prod.is_file()
    prod_doc = __import__("json").loads(prod.read_text(encoding="utf-8"))
    assert prod_doc["gates"]["ml_product_go"] is False


def test_promote_apply_policy_never_enables_field_ops(tmp_path: Path):
    """--apply-policy may flip research_open only; field_ops stays false."""
    import json

    from scripts.ml_scorecard import build_scorecard
    from scripts.promote_ml_live_fusion import apply_research_open_policy, main

    # Isolated policy file
    policy = {
        "schema": "decision_policies_v1",
        "default_policy": "default",
        "policies": {
            "field_ops": {
                "id": "field_ops",
                "allow_ml_live_in_fusion": False,
                "notes": "strict",
            },
            "research_open": {
                "id": "research_open",
                "allow_ml_live_in_fusion": False,
                "notes": "lab",
            },
            "default": {
                "id": "default",
                "allow_ml_live_in_fusion": False,
            },
        },
    }
    policy_path = tmp_path / "decision_policies.json"
    policy_path.write_text(json.dumps(policy, indent=2), encoding="utf-8")

    result = apply_research_open_policy(policy_path)
    assert result["research_open.allow_ml_live_in_fusion"] is True
    assert result["field_ops.allow_ml_live_in_fusion"] is False
    written = json.loads(policy_path.read_text(encoding="utf-8"))
    assert written["policies"]["research_open"]["allow_ml_live_in_fusion"] is True
    assert written["policies"]["field_ops"]["allow_ml_live_in_fusion"] is False
    # default profile must not be silently flipped by this helper
    assert written["policies"]["default"]["allow_ml_live_in_fusion"] is False

    # End-to-end promote CLI with --apply-policy against tmp policy via monkeypatch
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
    sc = tmp_path / "sc.json"
    sc.write_text(json.dumps(doc), encoding="utf-8")

    # Reset field_ops/research for CLI path through apply_research_open_policy monkeypatch
    policy2 = {
        "schema": "decision_policies_v1",
        "policies": {
            "field_ops": {"id": "field_ops", "allow_ml_live_in_fusion": False},
            "research_open": {"id": "research_open", "allow_ml_live_in_fusion": False},
        },
    }
    policy_path2 = tmp_path / "pol2.json"
    policy_path2.write_text(json.dumps(policy2), encoding="utf-8")

    import scripts.promote_ml_live_fusion as promo

    orig = promo.POLICY_PATH
    promo.POLICY_PATH = policy_path2
    try:
        rc = main(
            [
                "--scorecard",
                str(sc),
                "--promote-record",
                str(tmp_path / "rec2.json"),
                "--product-scorecard",
                str(tmp_path / "prod2.json"),
                "--apply-policy",
                "--allow-lab-synthetic",  # offline fixture — lab only
            ]
        )
    finally:
        promo.POLICY_PATH = orig

    assert rc == 0
    pol_after = json.loads(policy_path2.read_text(encoding="utf-8"))
    assert pol_after["policies"]["research_open"]["allow_ml_live_in_fusion"] is True
    assert pol_after["policies"]["field_ops"]["allow_ml_live_in_fusion"] is False
    prod2 = json.loads((tmp_path / "prod2.json").read_text(encoding="utf-8"))
    assert prod2["gates"]["ml_product_go"] is False
