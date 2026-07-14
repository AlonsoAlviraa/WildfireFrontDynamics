"""Tests for NDWS copy-baseline and changed-pixel metrics."""

import numpy as np
import pytest

from wildfire_front.ml.ndws_metrics import (
    aggregate_ndws_evaluation,
    changed_pixel_mask,
    copy_baseline_prediction,
    evaluate_sample,
    sanitize_fire_mask,
)


class TestSanitizeFireMask:
    def test_negative_sentinel_becomes_zero(self):
        mask = np.array([[-1.0, 0.0, 1.0]], dtype=np.float32)
        out = sanitize_fire_mask(mask)
        assert out.tolist() == [[0.0, 0.0, 1.0]]

    def test_threshold_at_half(self):
        mask = np.array([[0.4, 0.6]], dtype=np.float32)
        out = sanitize_fire_mask(mask)
        assert out.tolist() == [[0.0, 1.0]]


class TestCopyBaseline:
    def test_identical_masks_high_iou(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:6, 2:6] = 1.0
        target = prev.copy()
        sample = evaluate_sample(prev, prev, target, threshold=0.5)
        assert sample["copy_full"].iou == pytest.approx(1.0, abs=1e-6)

    def test_copy_beats_random_on_stable_patch(self):
        prev = np.zeros((16, 16), dtype=np.float32)
        prev[4:12, 4:12] = 1.0
        target = prev.copy()
        random_pred = np.random.rand(16, 16).astype(np.float32)
        copy_pred = copy_baseline_prediction(prev)
        copy_sample = evaluate_sample(copy_pred, prev, target)
        model_sample = evaluate_sample(random_pred, prev, target)
        assert copy_sample["model_full"].iou > model_sample["model_full"].iou


class TestChangedPixels:
    def test_changed_mask_detects_growth(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:5, 2:5] = 1.0
        target = prev.copy()
        target[5, 5] = 1.0
        change = changed_pixel_mask(prev, target)
        assert change[5, 5] == 1.0
        assert change[2, 2] == 0.0

    def test_metrics_on_changed_subset(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[1:4, 1:4] = 1.0
        target = prev.copy()
        target[4, 4] = 1.0
        pred = target.copy()
        sample = evaluate_sample(pred, prev, target)
        assert sample["model_full"].iou == pytest.approx(1.0, abs=1e-6)
        assert sample["model_changed"].iou == pytest.approx(1.0, abs=1e-6)


class TestAggregate:
    def test_improvement_vs_copy(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:6, 2:6] = 1.0
        target = prev.copy()
        target[6, 6] = 1.0

        perfect = evaluate_sample(target.astype(np.float32), prev, target)
        copy_only = evaluate_sample(prev, prev, target)

        agg_perfect = aggregate_ndws_evaluation([perfect])
        agg_copy = aggregate_ndws_evaluation([copy_only])

        assert agg_perfect["improvement_vs_copy_iou_changed"] > 0.0
        assert agg_copy["improvement_vs_copy_iou_changed"] == pytest.approx(0.0, abs=1e-6)