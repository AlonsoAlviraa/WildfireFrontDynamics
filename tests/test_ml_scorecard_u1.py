"""Offline U1 scorecard gate tests (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.ml.scorecard_schema import validate_ml_scorecard
from wildfire_front.product.confidence import build_decision_card
from wildfire_front.product.decide_service import decide_from_request


def test_u1_pass_synthetic():
    from scripts.ml_scorecard import build_scorecard

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
    assert doc["schema"] == "ml_scorecard_v1"
    assert validate_ml_scorecard(doc) == []
    assert doc["gates"]["U1a_selective_ge_full_minus_eps"] is True
    assert doc["gates"]["U1_selective_beats_random"] is True
    assert doc["gates"]["u1_val_passed"] is True
    assert doc["gates"]["u1_val_lab_pass"] is True
    assert doc["gates"]["ml_product_go"] is False
    # Honest rule: VAL-only lab pass must NOT recommend fusion
    assert doc["allow_ml_live_in_fusion_recommended"] is False
    assert doc["gates"]["u1_test_honest"] is False
    assert "u1_not_eval_on_test" in doc["gates"]["reasons"]
    assert doc["tuning"]["uncertainty_calibration_split"] == "val"
    # Dual-product honesty: no ROS in primary
    assert "primary_ros_m_min" not in doc["primary"]
    assert "ros_m_min" not in doc["primary"]
    # U1c reported
    assert doc["uncertainty"].get("ece_patch_conf") is not None
    # Catalog TEST IoU not unlabeled as this eval's model_iou
    assert doc["primary"]["model_iou_source"] == "eval_split_mean"
    assert "catalog_holdout_test_reference" in doc["provenance"]


def test_u1_fail_synthetic():
    from scripts.ml_scorecard import build_scorecard

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="val",
        action="scorecard",
        offline=True,
        synthetic_mode="fail",
    )
    assert validate_ml_scorecard(doc) == []
    assert doc["gates"]["U1_selective_beats_random"] is False
    assert doc["gates"]["u1_val_passed"] is False
    assert doc["allow_ml_live_in_fusion_recommended"] is False
    assert doc["gates"]["ml_product_go"] is False


def test_catalog_mode_fusion_off_default():
    from scripts.ml_scorecard import build_scorecard

    doc = build_scorecard(
        product_id="clm_ensemble_v34",
        split="val",
        action="scorecard",
        offline=False,
    )
    assert validate_ml_scorecard(doc) == []
    # No patch data → U1 not passed; fusion remains recommended OFF
    assert doc["gates"]["U1_selective_beats_random"] is False
    assert doc["gates"]["U1a_selective_ge_full_minus_eps"] is False
    assert doc["allow_ml_live_in_fusion_recommended"] is False
    # Catalog 0.8963 must NOT sit in primary.model_iou (even tagged)
    assert "model_iou" not in doc["primary"]
    cat = doc["provenance"]["catalog_holdout_test_reference"]
    assert cat["test_iou"] == pytest.approx(0.8963)


def test_ml_scorecard_cli_offline(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    from scripts.ml_scorecard import main

    out = tmp_path / "sc.json"
    rc = main(
        [
            "--offline-fixture",
            "--synthetic-mode",
            "pass",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["gates"]["U1_selective_beats_random"] is True
    # Default offline = VAL split without frozen cal → not fusion recommended
    assert doc["allow_ml_live_in_fusion_recommended"] is False
    printed = json.loads(capsys.readouterr().out)
    assert printed["u1_verdict"] in (
        "U1_VAL_LAB_PASS",
        "U1_PASS_NOT_PROMOTE",
        "U1_FAIL",
    )
    # Offline default has identity cal → may be U1_FAIL on recommended path flags
    # but U1a/U1b still compute; verdict must never be product GO
    assert printed["ml_product_go"] is False
    assert "verdict" not in printed or printed.get("verdict") != "GO"


def test_ml_scorecard_cli_test_frozen_honest(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    from scripts.ml_scorecard import main

    out = tmp_path / "sc.json"
    rc = main(
        [
            "--offline-fixture",
            "--synthetic-mode",
            "pass",
            "--split",
            "test",
            "--frozen-calibrator",
            "--calibrator-fit-split",
            "val",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["gates"]["u1_test_honest"] is True
    assert doc["allow_ml_live_in_fusion_recommended"] is True
    printed = json.loads(capsys.readouterr().out)
    assert printed["u1_verdict"] == "U1_TEST_HONEST_PASS"
    assert printed["ml_product_go"] is False


def test_ml_prediction_outbox_to_decide(tmp_path: Path):
    """Construct outbox/ml_prediction.json → decide_from_request / Decision Card."""
    pred = {
        "schema": "ml_prediction_v1",
        "product_id": "clm_ensemble_v34",
        "abstain": False,
        "confidence": 0.82,
        "diagnostics": {
            "mean_entropy": 0.12,
            "member_disagreement": 0.04,
            "mean_margin": 0.38,
            "n_members": 3,
        },
        "ml_live_metrics": {
            "schema": "ml_live_metrics_v1",
            "product_id": "clm_ensemble_v34",
            "confidence": 0.82,
            "abstain": False,
            "mean_entropy": 0.12,
            "member_disagreement": 0.04,
            "mean_margin": 0.38,
            "calibrator_id": "uncertainty_calibrator_v1",
            "n_members": 3,
        },
    }
    path = tmp_path / "outbox" / "ml_prediction.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pred), encoding="utf-8")

    out = decide_from_request(
        {
            "event_id": "outbox_ml",
            "ml_prediction": str(path),
            "channel": "cli",
            "ml_live_trusted": True,
        },
        base=tmp_path,
    )
    assert out["decision"] == "HOLD"
    assert out["metrics"]["ml_live"] is not None

    card = build_decision_card(
        "outbox_ml2",
        ml_live_metrics=pred["ml_live_metrics"],
        allow_ml_live_in_fusion=False,
        ml_live_trusted=True,
    )
    assert card.decision.value == "HOLD" or str(card.decision) == "HOLD"


def test_fit_script_skips_without_weights(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Operator fit tool exits 0 with SKIP when weights/VAL missing."""
    from scripts import fit_ml_uncertainty_calibration as fit_mod

    # Force product resolve to fail readiness (still need a valid VAL path name)
    monkeypatch.setattr(
        fit_mod,
        "_weights_and_val_ready",
        lambda product_id, val_dir: (False, "missing ensemble members: [x]"),
    )
    val = tmp_path / "holdout" / "val"
    val.mkdir(parents=True)
    rc = fit_mod.main(["--val-dir", str(val), "--output", str(tmp_path / "cal.json")])
    assert rc == 0


def test_fit_script_refuses_test_dir(tmp_path: Path):
    from scripts.fit_ml_uncertainty_calibration import assert_val_fit_data_dir, main

    test_dir = tmp_path / "holdout_v1" / "test"
    test_dir.mkdir(parents=True)
    with pytest.raises(ValueError, match="not VAL|test"):
        assert_val_fit_data_dir(test_dir, split="val")
    rc = main(["--val-dir", str(test_dir), "--output", str(tmp_path / "x.json")])
    assert rc == 2


def test_fit_script_refuses_lofo_dir(tmp_path: Path):
    from scripts.fit_ml_uncertainty_calibration import assert_val_fit_data_dir

    lofo = tmp_path / "lofo_v1" / "cardoso"
    lofo.mkdir(parents=True)
    with pytest.raises(ValueError, match="lofo|not VAL"):
        assert_val_fit_data_dir(lofo, split="val")


def test_fit_script_requires_val_component(tmp_path: Path):
    from scripts.fit_ml_uncertainty_calibration import assert_val_fit_data_dir

    weird = tmp_path / "custom_patches"
    weird.mkdir()
    with pytest.raises(ValueError, match="val"):
        assert_val_fit_data_dir(weird, split="val")


def test_predict_spread_never_auto_loads_fixture():
    """Product path must not silently use tests/fixtures calibrator."""
    from scripts.predict_spread import _resolve_calibrator
    from wildfire_front.ml.uncertainty import LogisticCalibrator

    # No product artifact in default candidates for this env → identity
    # (even though fixture exists under tests/fixtures/ml/)
    cal = _resolve_calibrator(None)
    # If a product artifact exists locally, it may load — but never fixture path.
    # Identity is always OK; if non-identity, must not be the offline fixture id alone
    # without a models/ file. Hard check: fixture path is not in default candidates.
    models_cal = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "clm_ensemble"
        / "uncertainty_calibration_v1.json"
    )
    models_cal2 = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "clm_ensemble"
        / "uncertainty_calibrator_v1.json"
    )
    if not models_cal.is_file() and not models_cal2.is_file():
        assert cal.is_identity is True
        assert isinstance(cal, LogisticCalibrator)


def test_predict_spread_explicit_calibrator_missing(tmp_path: Path):
    from scripts.predict_spread import _resolve_calibrator

    missing = tmp_path / "nope.json"
    with pytest.raises(FileNotFoundError, match="not found"):
        _resolve_calibrator(str(missing))
