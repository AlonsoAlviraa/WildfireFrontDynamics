"""Cross-backend reproduction rails for final RCDA paper metrics."""

from __future__ import annotations

import pytest

from scripts.evaluate_rcda_paper_metrics import verify_cross_backend_reproduction


def _metrics(*, tp: int, tn: int, fp: int, fn: int, iou: float, macro: float) -> dict:
    return {
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "iou": iou,
        "event_macro_iou": macro,
    }


def test_cross_backend_reproduction_accepts_sub_ppm_threshold_jitter() -> None:
    remote = _metrics(
        tp=414_162,
        tn=105_909_447,
        fp=1_190_915,
        fn=685_412,
        iou=0.18081815717080502,
        macro=0.17834349063981222,
    )
    local = _metrics(
        tp=414_163,
        tn=105_909_457,
        fp=1_190_905,
        fn=685_411,
        iou=0.18081938319451957,
        macro=0.17834409614524283,
    )

    audit = verify_cross_backend_reproduction(local, remote, label="seed11")

    assert audit["within_tolerance"] is True
    assert audit["changed_predictions_upper_bound"] == 11
    assert audit["changed_prediction_fraction"] < 1e-6


def test_cross_backend_reproduction_rejects_material_prediction_change() -> None:
    remote = _metrics(tp=100, tn=900, fp=0, fn=0, iou=1.0, macro=1.0)
    local = _metrics(tp=90, tn=900, fp=0, fn=10, iou=0.9, macro=0.9)

    with pytest.raises(ValueError, match="predictions differ"):
        verify_cross_backend_reproduction(local, remote, label="bad")


def test_cross_backend_reproduction_rejects_different_pixel_totals() -> None:
    remote = _metrics(tp=10, tn=90, fp=0, fn=0, iou=1.0, macro=1.0)
    local = _metrics(tp=10, tn=89, fp=0, fn=0, iou=1.0, macro=1.0)

    with pytest.raises(ValueError, match="pixel totals differ"):
        verify_cross_backend_reproduction(local, remote, label="bad")
