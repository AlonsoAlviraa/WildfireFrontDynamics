"""Tests for risk–coverage curve helpers + iter6 runner (no field rails flip)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wildfire_front.ml.lab_reject_calibration import (
    conf_band_summary,
    risk_coverage_curve,
    thr_operating_points,
)

ROOT = Path(__file__).resolve().parents[1]


def test_risk_coverage_curve_monotonic_ish():
    rng = np.random.default_rng(0)
    conf = rng.uniform(0.5, 0.9, size=100)
    # Higher conf → higher IoU (ranking useful)
    ious = 0.3 + 0.7 * conf + rng.normal(0, 0.02, size=100)
    ious = np.clip(ious, 0, 1)
    rows = risk_coverage_curve(conf, ious, coverages=[1.0, 0.8, 0.5])
    assert len(rows) == 3
    by_c = {r["coverage_target"]: r["selective_iou"] for r in rows}
    assert by_c[0.5] >= by_c[1.0] - 1e-9  # selective should not be worse than full much
    assert by_c[0.8] >= by_c[1.0] - 0.05


def test_conf_band_and_thr_points():
    conf = np.array([0.76, 0.78, 0.80, 0.79, 0.77])
    labels = np.array([1, 1, 0, 1, 1], dtype=float)
    ious = np.array([0.9, 0.85, 0.4, 0.88, 0.7])
    band = conf_band_summary(conf)
    assert band["n"] == 5
    assert band["min"] <= band["p50"] <= band["max"]
    pts = thr_operating_points(conf, labels, ious, [0.35, 0.785])
    assert pts[0]["abstain_rate"] == 0.0  # all conf > 0.35
    assert pts[1]["abstain_rate"] > 0.0


def test_risk_curve_script_with_real_caches_if_present():
    val = ROOT / "outputs" / "ml_eval" / "val_head_a_features.npz"
    test = ROOT / "outputs" / "ml_eval" / "test_head_a_features.npz"
    cal = ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
    if not (val.is_file() and test.is_file() and cal.is_file()):
        return  # skip lightly if assets missing
    from scripts import run_lab_ml_loop_v34_risk_curve as mod

    ROOT / "outputs" / "ml_eval" / "lab_loop"
    # Run with --no-md into real out dir is OK (product intent); use tmp for isolation
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        # Need reject latest for locked thr — copy minimal
        tdp = Path(td)
        # Script reads reject from out-dir; write stub
        (tdp / "lab_loop_v34_reject_latest.json").write_text(
            json.dumps({"tuned": {"abstain_threshold": 0.795}}),
            encoding="utf-8",
        )
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
        data = json.loads((tdp / "lab_loop_v34_risk_curve_latest.json").read_text(encoding="utf-8"))
        assert data["iteration"] == 6
        assert data["rails"]["ml_product_go"] is True
        assert data["rails"]["field_ops_allow_ml_live_in_fusion"] is False
        assert data["verdict"]["risk_coverage_curve_built"] is True
        assert len(data["selective_curve"]["test"]) >= 3
        latest = json.loads((tdp / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
        assert "6_risk_curve" in latest["iterations"]
