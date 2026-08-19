"""Tests for NDWS copy-baseline and changed-pixel metrics."""

import numpy as np
import pytest

from wildfire_front.ml.ndws_metrics import (
    aggregate_ndws_evaluation,
    binary_average_precision,
    boundary_f1_score,
    changed_pixel_mask,
    copy_baseline_prediction,
    dilated_copy_baseline_prediction,
    evaluate_sample,
    fire_centered_growth_region,
    growth_average_precision,
    growth_pixel_mask,
    sanitize_fire_mask,
    transition_masks,
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

    def test_naive_copy_iou_changed_is_always_zero(self):
        prev = np.zeros((16, 16), dtype=np.float32)
        prev[4:12, 4:12] = 1.0
        target = prev.copy()
        target[12, 12] = 1.0
        copy_pred = copy_baseline_prediction(prev)
        sample = evaluate_sample(copy_pred, prev, target)
        assert sample["copy_changed"].iou == pytest.approx(0.0, abs=1e-6)

    def test_dilated_copy_can_score_on_adjacent_growth(self):
        prev = np.zeros((16, 16), dtype=np.float32)
        prev[4:12, 4:12] = 1.0
        target = prev.copy()
        target[12, 8] = 1.0
        dilated = dilated_copy_baseline_prediction(prev)
        sample = evaluate_sample(dilated, prev, target)
        assert sample["dilated_copy_growth"].iou > 0.0


class TestChangedPixels:
    def test_changed_mask_detects_growth(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:5, 2:5] = 1.0
        target = prev.copy()
        target[5, 5] = 1.0
        change = changed_pixel_mask(prev, target)
        assert change[5, 5] == 1.0
        assert change[2, 2] == 0.0

    def test_growth_mask_only_new_fire(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:5, 2:5] = 1.0
        target = prev.copy()
        target[5, 5] = 1.0
        target[2, 2] = 0.0
        growth = growth_pixel_mask(prev, target)
        assert growth[5, 5] == 1.0
        assert growth[2, 2] == 0.0

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
    def test_improvement_vs_dilated_copy_changed(self):
        prev = np.zeros((12, 12), dtype=np.float32)
        prev[2:6, 2:6] = 1.0
        target = prev.copy()
        # Growth far from prev fire: dilated copy misses, perfect model hits.
        target[10, 10] = 1.0

        perfect = evaluate_sample(target.astype(np.float32), prev, target)
        copy_only = evaluate_sample(prev, prev, target)

        agg_perfect = aggregate_ndws_evaluation([perfect])
        agg_copy = aggregate_ndws_evaluation([copy_only])

        assert agg_perfect["improvement_vs_copy_iou_changed"] > 0.0
        assert agg_copy["improvement_vs_copy_iou_changed"] <= 0.0
        assert agg_perfect["legacy_improvement_vs_naive_copy_iou_changed"] == pytest.approx(
            agg_perfect["model_iou_changed"], abs=1e-6
        )
        assert agg_copy["copy_baseline_iou_changed"] == pytest.approx(0.0, abs=1e-6)


class TestTransitionMetricsV2:
    def test_false_growth_outside_target_is_penalized(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        prev[2:4, 2:4] = 1.0
        target = prev.copy()
        target[4, 3] = 1.0
        prediction = target.copy()
        prediction[7, 7] = 1.0

        sample = evaluate_sample(prediction, prev, target)

        # The historical target-conditioned metric cannot see the false growth.
        assert sample["model_growth"].iou == pytest.approx(1.0, abs=1e-6)
        # The v2 transition metric compares independently constructed masks.
        assert sample["model_growth_transition"].iou == pytest.approx(0.5, abs=1e-6)

    def test_transition_masks_cover_growth_shrink_and_change(self):
        prev = np.zeros((6, 6), dtype=np.float32)
        prev[1, 1] = 1.0
        target = prev.copy()
        target[1, 1] = 0.0
        target[4, 4] = 1.0
        transitions = transition_masks(target, prev, target)

        assert transitions["predicted_growth"][4, 4] == 1.0
        assert transitions["predicted_shrink"][1, 1] == 1.0
        assert transitions["predicted_change"].sum() == 2.0
        assert np.array_equal(
            transitions["predicted_change"], transitions["observed_change"]
        )

    def test_average_precision_ties_equal_prevalence(self):
        scores = np.zeros(4, dtype=np.float32)
        targets = np.array([1, 0, 0, 1], dtype=np.float32)
        assert binary_average_precision(scores, targets) == pytest.approx(0.5)

    def test_growth_average_precision_excludes_already_burned_pixels(self):
        prev = np.zeros((2, 3), dtype=np.float32)
        prev[0, 0] = 1.0
        target = prev.copy()
        target[1, 2] = 1.0
        scores = np.array([[0.99, 0.1, 0.2], [0.3, 0.4, 0.9]], dtype=np.float32)

        assert growth_average_precision(scores, prev, target) == pytest.approx(1.0)

    def test_aggregate_exposes_v2_semantics(self):
        prev = np.zeros((8, 8), dtype=np.float32)
        target = prev.copy()
        target[3, 3] = 1.0
        sample = evaluate_sample(target, prev, target)
        aggregate = aggregate_ndws_evaluation([sample])

        assert aggregate["model_growth_transition_iou"] == pytest.approx(1.0, abs=1e-6)
        assert aggregate["model_change_transition_iou"] == pytest.approx(1.0, abs=1e-6)
        assert aggregate["model_growth_average_precision_macro"] == pytest.approx(1.0)
        assert aggregate["transition_metric_semantics"] == (
            "v2_independent_predicted_vs_observed"
        )


class TestFireCenteredAndBoundaryMetrics:
    def test_fcer_support_uses_prev_only(self):
        prev = np.zeros((11, 11), dtype=np.float32)
        prev[5, 5] = 1.0

        region_a = fire_centered_growth_region(prev, radius=2)
        region_b = fire_centered_growth_region(prev, radius=2)

        assert np.array_equal(region_a, region_b)
        assert region_a[5, 5] == 0.0
        assert region_a[5, 7] == 1.0
        assert region_a[0, 0] == 0.0

    def test_fcer_capture_reports_growth_outside_ring(self):
        prev = np.zeros((12, 12), dtype=np.float32)
        prev[5, 5] = 1.0
        target = prev.copy()
        target[5, 6] = 1.0
        target[11, 11] = 1.0
        sample = evaluate_sample(target, prev, target, fcer_radius=1)

        assert sample["model_growth_fcer"].iou == pytest.approx(1.0, abs=1e-6)
        assert sample["observed_growth_fcer_capture"] == pytest.approx(0.5)

    def test_global_transition_still_penalizes_fcer_external_false_positive(self):
        prev = np.zeros((12, 12), dtype=np.float32)
        prev[5, 5] = 1.0
        target = prev.copy()
        target[5, 6] = 1.0
        prediction = target.copy()
        prediction[11, 11] = 1.0
        sample = evaluate_sample(prediction, prev, target, fcer_radius=1)

        assert sample["model_growth_fcer"].iou == pytest.approx(1.0, abs=1e-6)
        assert sample["model_growth_transition"].iou == pytest.approx(0.5, abs=1e-6)

    def test_boundary_f1_is_one_for_exact_and_zero_for_missing(self):
        target = np.zeros((10, 10), dtype=np.float32)
        target[3:7, 3:7] = 1.0

        assert boundary_f1_score(target, target, tolerance=1) == pytest.approx(1.0)
        assert boundary_f1_score(np.zeros_like(target), target, tolerance=1) == 0.0

    def test_aggregate_exposes_fcer_and_boundary_semantics(self):
        prev = np.zeros((10, 10), dtype=np.float32)
        prev[4:6, 4:6] = 1.0
        target = prev.copy()
        target[6, 5] = 1.0
        aggregate = aggregate_ndws_evaluation([evaluate_sample(target, prev, target)])

        assert aggregate["model_growth_fcer_iou"] == pytest.approx(1.0, abs=1e-6)
        assert aggregate["model_front_boundary_f1_macro"] == pytest.approx(1.0)
        assert aggregate["observed_growth_fcer_capture_macro"] == pytest.approx(1.0)
        assert aggregate["model_growth_fcer_ece_macro"] >= 0.0
        assert aggregate["model_growth_fcer_selective_error_80_macro"] == pytest.approx(0.0)
        assert aggregate["model_growth_fcer_aurc_macro"] == pytest.approx(0.0)
