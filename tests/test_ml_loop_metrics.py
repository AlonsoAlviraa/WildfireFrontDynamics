"""Tests for multi-objective early-stop scores used by the 3-way ML loop."""

from __future__ import annotations

from wildfire_front.ml.unet_train import _early_stop_score


def test_multi_full_growth_prefers_full_delta():
    low_full = {
        "improvement_vs_copy_iou": 0.10,
        "model_iou_growth": 0.99,
    }
    high_full = {
        "improvement_vs_copy_iou": 0.25,
        "model_iou_growth": 0.50,
    }
    # multi_full_growth uses λ=0.35 → 0.10+0.35*0.99=0.4465 vs 0.25+0.35*0.50=0.425
    # so pure high growth can win — check multi_full_growth_025 prefers full more
    s_low = _early_stop_score(low_full, "multi_full_growth_025")
    s_high = _early_stop_score(high_full, "multi_full_growth_025")
    # 0.10 + 0.25*0.99 = 0.3475 ; 0.25 + 0.25*0.50 = 0.375
    assert s_high > s_low


def test_multi_full_growth_not_growth_only():
    """Growth-only would pick pure growth; multi score must use full delta."""
    a = {"improvement_vs_copy_iou": 0.20, "model_iou_growth": 0.40}
    b = {"improvement_vs_copy_iou": 0.05, "model_iou_growth": 0.99}
    # multi_full_growth_025: a=0.20+0.10=0.30 ; b=0.05+0.2475=0.2975
    assert _early_stop_score(a, "multi_full_growth_025") > _early_stop_score(
        b, "multi_full_growth_025"
    )


def test_val_loss_negated():
    assert _early_stop_score({"loss": 1.0}, "val_loss") == -1.0
