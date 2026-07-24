"""Offline tests for Head A calibrator fixture + load_calibrator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.uncertainty import (
    LogisticCalibrator,
    load_calibrator,
    save_calibrator,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ml" / "uncertainty_calibrator_v1.json"


def test_fixture_exists():
    assert FIXTURE.is_file(), f"missing fixture {FIXTURE}"


def test_load_calibrator_fixture_predict_proba_finite():
    cal = load_calibrator(FIXTURE)
    assert cal.method == "logistic"
    assert cal.calibrator_id == "uncertainty_calibration_v1"
    assert cal.weights.size == 4  # 3 features + bias
    assert cal.feature_names == (
        "mean_entropy",
        "member_disagreement",
        "mean_margin",
    )
    assert cal.abstain_threshold == pytest.approx(0.35)
    hi = cal.predict_proba(
        {
            "mean_entropy": 0.1,
            "member_disagreement": 0.05,
            "mean_margin": 0.4,
        }
    )
    lo = cal.predict_proba(
        {
            "mean_entropy": 0.9,
            "member_disagreement": 0.4,
            "mean_margin": 0.05,
        }
    )
    assert np.isfinite(hi) and np.isfinite(lo)
    assert 0.0 <= hi <= 1.0
    assert 0.0 <= lo <= 1.0
    assert hi > lo


def test_load_calibrator_rejects_wrong_method(tmp_path: Path):
    bad = tmp_path / "iso.json"
    bad.write_text(
        '{"method": "isotonic", "weights": [0.1, 0.2, 0.3, 0.0]}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="logistic"):
        load_calibrator(bad)


def test_load_calibrator_params_coef_form(tmp_path: Path):
    path = tmp_path / "params_form.json"
    path.write_text(
        """
        {
          "method": "logistic",
          "feature_names": ["mean_entropy", "member_disagreement", "mean_margin"],
          "params": {"coef": [-1.0, -1.0, 2.0], "intercept": 0.0},
          "fit_split": "val",
          "tau_iou": 0.5
        }
        """,
        encoding="utf-8",
    )
    cal = load_calibrator(path)
    p = cal.predict_proba({"mean_entropy": 0.1, "member_disagreement": 0.1, "mean_margin": 0.4})
    assert np.isfinite(p)


def test_save_load_roundtrip(tmp_path: Path):
    cal = LogisticCalibrator(
        weights=np.array([-1.0, -2.0, 3.0, 0.1], dtype=np.float64),
        calibrator_id="roundtrip",
    )
    path = save_calibrator(cal, tmp_path / "cal.json")
    loaded = load_calibrator(path)
    assert loaded.calibrator_id == "roundtrip"
    assert np.allclose(loaded.weights, cal.weights)
