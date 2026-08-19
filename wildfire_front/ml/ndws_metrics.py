"""NDWS-specific evaluation metrics for wildfire spread models.

The naive copy baseline (predict PrevFireMask as next-day fire) achieves IoU
~0.79 on dense-fire NDWS patches. On pixels where prev != target, naive copy
always scores IoU = 0 by definition — so ``model_iou - copy_iou`` on that subset
is not a meaningful "improvement". Use transition metrics and dilated-copy
baselines instead.

``model_growth`` and ``model_changed`` are retained with their historical
target-conditioned semantics so old scorecards remain reproducible.  New work
must use the ``*_transition`` metrics: they construct predicted and observed
state transitions independently and therefore penalize false growth/change
outside the observed transition.  The distinction matters because masking a
metric with ``target != prev`` leaks the answer into the evaluation support.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np

from wildfire_front.evaluation import (
    SegmentationMetrics,
    aggregate_segmentation_metrics,
    compute_segmentation_metrics,
)
from wildfire_front.ml.reliability_metrics import (
    ece_pixel_prob,
    pixel_risk_coverage_curve,
    pixel_selective_error_at_coverage,
)

# Default 1-pixel morphological dilation for a non-trivial dynamic baseline.
DEFAULT_DILATION_RADIUS = 1
DEFAULT_FCER_RADIUS = 3
DEFAULT_BOUNDARY_TOLERANCE = 1


def sanitize_fire_mask(mask: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Binarize NDWS fire masks, treating negative sentinels as no-fire."""
    m = np.asarray(mask, dtype=np.float64)
    m = np.where(m < 0.0, 0.0, m)
    if m.max() > 1.0 or m.min() < 0.0:
        m = 1.0 / (1.0 + np.exp(-m))
    return (m >= threshold).astype(np.float64)


def dilate_binary_mask(mask: np.ndarray, radius: int = DEFAULT_DILATION_RADIUS) -> np.ndarray:
    """Binary dilation via max-filter (square structuring element)."""
    m = np.asarray(mask, dtype=np.float64)
    if radius <= 0:
        return m.copy()
    padded = np.pad(m, radius, mode="constant", constant_values=0.0)
    h, w = m.shape
    out = np.zeros_like(m)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out = np.maximum(
                out,
                padded[radius + dy : radius + dy + h, radius + dx : radius + dx + w],
            )
    return out


def erode_binary_mask(mask: np.ndarray, radius: int = DEFAULT_DILATION_RADIUS) -> np.ndarray:
    """Binary erosion with zero padding and a square structuring element."""
    m = np.asarray(mask, dtype=np.float64)
    if radius <= 0:
        return m.copy()
    padded = np.pad(m, radius, mode="constant", constant_values=0.0)
    h, w = m.shape
    out = np.ones_like(m)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            out = np.minimum(
                out,
                padded[radius + dy : radius + dy + h, radius + dx : radius + dx + w],
            )
    return out


def fire_centered_growth_region(
    prev_fire: np.ndarray,
    threshold: float = 0.5,
    radius: int = DEFAULT_FCER_RADIUS,
) -> np.ndarray:
    """Eligible near-front growth ring derived from ``t0`` only.

    This is deliberately target-independent: using the observed ``t1`` mask
    to choose the evaluation support would leak the answer.  Global transition
    metrics remain mandatory companions because this ring does not include
    long-range growth or false positives outside it.
    """
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    return ((dilate_binary_mask(prev_bin, radius) > 0.5) & (prev_bin == 0)).astype(
        np.float64
    )


def binary_boundary_mask(mask: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """One-pixel inner boundary of a binary mask."""
    binary = sanitize_fire_mask(mask, threshold)
    return ((binary > 0.5) & (erode_binary_mask(binary, 1) < 0.5)).astype(np.float64)


def boundary_f1_score(
    prediction: np.ndarray,
    target: np.ndarray,
    threshold: float = 0.5,
    tolerance: int = DEFAULT_BOUNDARY_TOLERANCE,
) -> float:
    """Symmetric boundary F1 with a pixel tolerance band."""
    pred_boundary = binary_boundary_mask(prediction, threshold) > 0.5
    target_boundary = binary_boundary_mask(target, threshold) > 0.5
    n_pred = int(pred_boundary.sum())
    n_target = int(target_boundary.sum())
    if n_pred == 0 and n_target == 0:
        return 1.0
    if n_pred == 0 or n_target == 0:
        return 0.0
    target_near = dilate_binary_mask(target_boundary.astype(np.float64), tolerance) > 0.5
    pred_near = dilate_binary_mask(pred_boundary.astype(np.float64), tolerance) > 0.5
    precision = float(np.logical_and(pred_boundary, target_near).sum() / n_pred)
    recall = float(np.logical_and(target_boundary, pred_near).sum() / n_target)
    if precision + recall == 0.0:
        return 0.0
    return float(2.0 * precision * recall / (precision + recall))


def changed_pixel_mask(
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Boolean mask of pixels where prev and target disagree."""
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    tgt_bin = sanitize_fire_mask(target_fire, threshold)
    return (prev_bin != tgt_bin).astype(np.float64)


def growth_pixel_mask(
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Pixels where fire appears (prev=0, target=1)."""
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    tgt_bin = sanitize_fire_mask(target_fire, threshold)
    return ((prev_bin == 0) & (tgt_bin == 1)).astype(np.float64)


def shrink_pixel_mask(
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Pixels where fire retreats (prev=1, target=0)."""
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    tgt_bin = sanitize_fire_mask(target_fire, threshold)
    return ((prev_bin == 1) & (tgt_bin == 0)).astype(np.float64)


def transition_masks(
    prediction: np.ndarray,
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, np.ndarray]:
    """Build predicted and observed fire-state transitions independently.

    Unlike :func:`growth_pixel_mask`, these arrays can be compared over the
    full grid.  A predicted new-fire pixel outside the observed growth region
    is consequently counted as a false positive.
    """
    pred_bin = sanitize_fire_mask(prediction, threshold)
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    target_bin = sanitize_fire_mask(target_fire, threshold)
    return {
        "predicted_growth": ((pred_bin == 1) & (prev_bin == 0)).astype(np.float64),
        "observed_growth": ((target_bin == 1) & (prev_bin == 0)).astype(np.float64),
        "predicted_shrink": ((pred_bin == 0) & (prev_bin == 1)).astype(np.float64),
        "observed_shrink": ((target_bin == 0) & (prev_bin == 1)).astype(np.float64),
        "predicted_change": (pred_bin != prev_bin).astype(np.float64),
        "observed_change": (target_bin != prev_bin).astype(np.float64),
    }


def binary_average_precision(
    scores: np.ndarray,
    targets: np.ndarray,
    eligible_mask: np.ndarray | None = None,
) -> float | None:
    """Return non-interpolated binary average precision using NumPy only.

    Scores tied at the same value are evaluated as one threshold, matching the
    usual precision-recall definition and avoiding order-dependent results.
    ``None`` denotes an undefined sample (no eligible positive target).
    """
    score = np.asarray(scores, dtype=np.float64)
    target = np.asarray(targets, dtype=np.float64) > 0.5
    if score.shape != target.shape:
        raise ValueError(f"shape mismatch: scores={score.shape}, targets={target.shape}")
    eligible = np.ones(target.shape, dtype=bool)
    if eligible_mask is not None:
        eligible = np.asarray(eligible_mask, dtype=np.float64) > 0.5
        if eligible.shape != target.shape:
            raise ValueError(
                f"shape mismatch: eligible_mask={eligible.shape}, targets={target.shape}"
            )
    eligible &= np.isfinite(score)
    score = score[eligible]
    target = target[eligible]
    positives = int(target.sum())
    if score.size == 0 or positives == 0:
        return None

    order = np.argsort(-score, kind="mergesort")
    sorted_score = score[order]
    sorted_target = target[order]
    tp = np.cumsum(sorted_target, dtype=np.float64)
    fp = np.cumsum(~sorted_target, dtype=np.float64)
    threshold_ends = np.r_[np.flatnonzero(np.diff(sorted_score)), score.size - 1]
    precision = tp[threshold_ends] / (tp[threshold_ends] + fp[threshold_ends])
    recall = tp[threshold_ends] / positives
    recall_delta = np.diff(np.r_[0.0, recall])
    return float(np.sum(recall_delta * precision))


def growth_average_precision(
    prediction: np.ndarray,
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> float | None:
    """Average precision for new fire over pixels unburned at ``t0``."""
    pred = np.asarray(prediction, dtype=np.float64)
    if pred.max() > 1.0 or pred.min() < 0.0:
        pred = 1.0 / (1.0 + np.exp(-pred))
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    target_bin = sanitize_fire_mask(target_fire, threshold)
    observed_growth = ((target_bin == 1) & (prev_bin == 0)).astype(np.float64)
    return binary_average_precision(pred, observed_growth, eligible_mask=(prev_bin == 0))


def compute_segmentation_metrics_on_mask(
    prediction: np.ndarray,
    ground_truth: np.ndarray,
    pixel_mask: np.ndarray,
    threshold: float = 0.5,
    *,
    eps: float = 1e-7,
) -> SegmentationMetrics:
    """Segmentation metrics restricted to pixels where ``pixel_mask == 1``."""
    mask = np.asarray(pixel_mask, dtype=np.float64) > 0.5
    if not np.any(mask):
        return SegmentationMetrics(
            iou=0.0,
            dice=0.0,
            precision=0.0,
            recall=0.0,
            accuracy=0.0,
            specificity=0.0,
            tp=0,
            fp=0,
            fn=0,
            tn=0,
        )

    pred = np.asarray(prediction, dtype=np.float64)
    gt = np.asarray(ground_truth, dtype=np.float64)
    if pred.max() > 1.0 or pred.min() < 0.0:
        pred = 1.0 / (1.0 + np.exp(-pred))
    pred_bin = (pred >= threshold).astype(np.float64)
    gt_bin = sanitize_fire_mask(gt, threshold)

    pred_bin = pred_bin[mask]
    gt_bin = gt_bin[mask]

    tp = int(np.sum((pred_bin == 1) & (gt_bin == 1)))
    fp = int(np.sum((pred_bin == 1) & (gt_bin == 0)))
    fn = int(np.sum((pred_bin == 0) & (gt_bin == 1)))
    tn = int(np.sum((pred_bin == 0) & (gt_bin == 0)))
    total = tp + fp + fn + tn

    return SegmentationMetrics(
        iou=tp / (tp + fp + fn + eps),
        dice=(2 * tp) / (2 * tp + fp + fn + eps),
        precision=tp / (tp + fp + eps),
        recall=tp / (tp + fn + eps),
        accuracy=(tp + tn) / (total + eps) if total > 0 else 0.0,
        specificity=tn / (tn + fp + eps),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
    )


def copy_baseline_prediction(prev_fire: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Return the naive copy-baseline prediction (prev mask binarized)."""
    return sanitize_fire_mask(prev_fire, threshold)


def dilated_copy_baseline_prediction(
    prev_fire: np.ndarray,
    threshold: float = 0.5,
    radius: int = DEFAULT_DILATION_RADIUS,
) -> np.ndarray:
    """Copy baseline with 1-pixel dilation (catches adjacent growth)."""
    return dilate_binary_mask(copy_baseline_prediction(prev_fire, threshold), radius)


def evaluate_sample(
    prediction: np.ndarray,
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
    *,
    dilation_radius: int = DEFAULT_DILATION_RADIUS,
    fcer_radius: int = DEFAULT_FCER_RADIUS,
    boundary_tolerance: int = DEFAULT_BOUNDARY_TOLERANCE,
) -> dict[str, SegmentationMetrics | float | None]:
    """Per-sample metrics: full grid, dynamic subsets, and copy baselines."""
    change = changed_pixel_mask(prev_fire, target_fire, threshold)
    growth = growth_pixel_mask(prev_fire, target_fire, threshold)
    shrink = shrink_pixel_mask(prev_fire, target_fire, threshold)
    copy_pred = copy_baseline_prediction(prev_fire, threshold)
    dilated_copy_pred = dilated_copy_baseline_prediction(
        prev_fire, threshold, radius=dilation_radius
    )
    model_transition = transition_masks(prediction, prev_fire, target_fire, threshold)
    copy_transition = transition_masks(copy_pred, prev_fire, target_fire, threshold)
    dilated_transition = transition_masks(
        dilated_copy_pred, prev_fire, target_fire, threshold
    )
    fcer = fire_centered_growth_region(prev_fire, threshold, radius=fcer_radius)
    observed_growth_total = float(model_transition["observed_growth"].sum())
    observed_growth_fcer = float((model_transition["observed_growth"] * fcer).sum())
    prediction_prob = np.asarray(prediction, dtype=np.float64)
    if prediction_prob.max() > 1.0 or prediction_prob.min() < 0.0:
        prediction_prob = 1.0 / (1.0 + np.exp(-prediction_prob))
    fcer_pixels = float(fcer.sum())
    fcer_ece = ece_pixel_prob(
        prediction_prob,
        model_transition["observed_growth"],
        eligible_mask=fcer,
    )
    fcer_selective = pixel_selective_error_at_coverage(
        prediction_prob,
        model_transition["observed_growth"],
        coverage=0.8,
        eligible_mask=fcer,
        threshold=threshold,
    )
    fcer_curve = pixel_risk_coverage_curve(
        prediction_prob,
        model_transition["observed_growth"],
        eligible_mask=fcer,
        threshold=threshold,
    )

    return {
        "model_full": compute_segmentation_metrics(prediction, target_fire, threshold),
        "model_changed": compute_segmentation_metrics_on_mask(
            prediction, target_fire, change, threshold
        ),
        "model_growth": compute_segmentation_metrics_on_mask(
            prediction, target_fire, growth, threshold
        ),
        "model_shrink": compute_segmentation_metrics_on_mask(
            prediction, target_fire, shrink, threshold
        ),
        "copy_full": compute_segmentation_metrics(copy_pred, target_fire, threshold),
        "copy_changed": compute_segmentation_metrics_on_mask(
            copy_pred, target_fire, change, threshold
        ),
        "copy_growth": compute_segmentation_metrics_on_mask(
            copy_pred, target_fire, growth, threshold
        ),
        "dilated_copy_full": compute_segmentation_metrics(
            dilated_copy_pred, target_fire, threshold
        ),
        "dilated_copy_changed": compute_segmentation_metrics_on_mask(
            dilated_copy_pred, target_fire, change, threshold
        ),
        "dilated_copy_growth": compute_segmentation_metrics_on_mask(
            dilated_copy_pred, target_fire, growth, threshold
        ),
        "model_growth_transition": compute_segmentation_metrics(
            model_transition["predicted_growth"], model_transition["observed_growth"], threshold
        ),
        "model_shrink_transition": compute_segmentation_metrics(
            model_transition["predicted_shrink"], model_transition["observed_shrink"], threshold
        ),
        "model_change_transition": compute_segmentation_metrics(
            model_transition["predicted_change"], model_transition["observed_change"], threshold
        ),
        "copy_growth_transition": compute_segmentation_metrics(
            copy_transition["predicted_growth"], copy_transition["observed_growth"], threshold
        ),
        "copy_change_transition": compute_segmentation_metrics(
            copy_transition["predicted_change"], copy_transition["observed_change"], threshold
        ),
        "dilated_copy_growth_transition": compute_segmentation_metrics(
            dilated_transition["predicted_growth"],
            dilated_transition["observed_growth"],
            threshold,
        ),
        "dilated_copy_change_transition": compute_segmentation_metrics(
            dilated_transition["predicted_change"],
            dilated_transition["observed_change"],
            threshold,
        ),
        "model_growth_average_precision": growth_average_precision(
            prediction, prev_fire, target_fire, threshold
        ),
        "model_growth_fcer": compute_segmentation_metrics_on_mask(
            model_transition["predicted_growth"],
            model_transition["observed_growth"],
            fcer,
            threshold,
        ),
        "dilated_copy_growth_fcer": compute_segmentation_metrics_on_mask(
            dilated_transition["predicted_growth"],
            dilated_transition["observed_growth"],
            fcer,
            threshold,
        ),
        "model_growth_fcer_average_precision": binary_average_precision(
            np.asarray(prediction, dtype=np.float64),
            model_transition["observed_growth"],
            eligible_mask=fcer,
        ),
        "observed_growth_fcer_capture": (
            observed_growth_fcer / observed_growth_total
            if observed_growth_total > 0.0
            else None
        ),
        "model_front_boundary_f1": boundary_f1_score(
            prediction, target_fire, threshold, tolerance=boundary_tolerance
        ),
        "copy_front_boundary_f1": boundary_f1_score(
            copy_pred, target_fire, threshold, tolerance=boundary_tolerance
        ),
        "dilated_copy_front_boundary_f1": boundary_f1_score(
            dilated_copy_pred, target_fire, threshold, tolerance=boundary_tolerance
        ),
        "model_growth_fcer_ece": float(fcer_ece) if np.isfinite(fcer_ece) else None,
        "model_growth_fcer_selective_error_80": (
            float(fcer_selective["selective_error"])
            if np.isfinite(fcer_selective["selective_error"])
            else None
        ),
        "model_growth_fcer_aurc": (
            float(fcer_curve["aurc_normalized"])
            if np.isfinite(fcer_curve["aurc_normalized"])
            else None
        ),
        "observed_growth_fcer_prevalence": (
            observed_growth_fcer / fcer_pixels if fcer_pixels > 0.0 else None
        ),
    }


def aggregate_ndws_evaluation(
    per_sample: list[dict[str, SegmentationMetrics | float | None]],
) -> dict[str, Any]:
    """Aggregate per-sample NDWS metrics into summary dict for logging/JSON."""
    if not per_sample:
        return {"note": "no samples"}

    def _agg(key: str) -> dict[str, float | str]:
        metrics = [s[key] for s in per_sample]
        if not all(isinstance(metric, SegmentationMetrics) for metric in metrics):
            raise TypeError(f"{key} is not a SegmentationMetrics collection")
        return dict(
            aggregate_segmentation_metrics(cast(list[SegmentationMetrics], metrics))
        )

    model_full = _agg("model_full")
    model_changed = _agg("model_changed")
    model_growth = _agg("model_growth")
    model_shrink = _agg("model_shrink")
    copy_full = _agg("copy_full")
    copy_changed = _agg("copy_changed")
    copy_growth = _agg("copy_growth")
    dilated_copy_full = _agg("dilated_copy_full")
    dilated_copy_changed = _agg("dilated_copy_changed")
    dilated_copy_growth = _agg("dilated_copy_growth")
    model_growth_transition = _agg("model_growth_transition")
    model_shrink_transition = _agg("model_shrink_transition")
    model_change_transition = _agg("model_change_transition")
    copy_growth_transition = _agg("copy_growth_transition")
    copy_change_transition = _agg("copy_change_transition")
    dilated_copy_growth_transition = _agg("dilated_copy_growth_transition")
    dilated_copy_change_transition = _agg("dilated_copy_change_transition")
    model_growth_fcer = _agg("model_growth_fcer")
    dilated_copy_growth_fcer = _agg("dilated_copy_growth_fcer")

    model_iou = float(model_full.get("micro_iou", 0.0))
    copy_iou = float(copy_full.get("micro_iou", 0.0))
    dilated_copy_iou = float(dilated_copy_full.get("micro_iou", 0.0))
    model_iou_changed = float(model_changed.get("micro_iou", 0.0))
    naive_copy_iou_changed = float(copy_changed.get("micro_iou", 0.0))
    dilated_copy_iou_changed = float(dilated_copy_changed.get("micro_iou", 0.0))
    model_iou_growth = float(model_growth.get("micro_iou", 0.0))
    copy_iou_growth = float(copy_growth.get("micro_iou", 0.0))
    dilated_copy_iou_growth = float(dilated_copy_growth.get("micro_iou", 0.0))

    legacy_improvement_changed = model_iou_changed - naive_copy_iou_changed
    model_growth_transition_iou = float(model_growth_transition.get("micro_iou", 0.0))
    model_change_transition_iou = float(model_change_transition.get("micro_iou", 0.0))
    dilated_growth_transition_iou = float(
        dilated_copy_growth_transition.get("micro_iou", 0.0)
    )
    dilated_change_transition_iou = float(
        dilated_copy_change_transition.get("micro_iou", 0.0)
    )
    growth_ap_values = [
        cast(float, sample["model_growth_average_precision"])
        for sample in per_sample
        if sample.get("model_growth_average_precision") is not None
    ]
    fcer_ap_values = [
        cast(float, sample["model_growth_fcer_average_precision"])
        for sample in per_sample
        if sample.get("model_growth_fcer_average_precision") is not None
    ]
    fcer_capture_values = [
        cast(float, sample["observed_growth_fcer_capture"])
        for sample in per_sample
        if sample.get("observed_growth_fcer_capture") is not None
    ]
    model_boundary_values = [cast(float, sample["model_front_boundary_f1"]) for sample in per_sample]
    copy_boundary_values = [cast(float, sample["copy_front_boundary_f1"]) for sample in per_sample]
    dilated_boundary_values = [
        cast(float, sample["dilated_copy_front_boundary_f1"]) for sample in per_sample
    ]
    fcer_ece_values = [
        cast(float, sample["model_growth_fcer_ece"])
        for sample in per_sample
        if sample.get("model_growth_fcer_ece") is not None
    ]
    fcer_selective_error_values = [
        cast(float, sample["model_growth_fcer_selective_error_80"])
        for sample in per_sample
        if sample.get("model_growth_fcer_selective_error_80") is not None
    ]
    fcer_aurc_values = [
        cast(float, sample["model_growth_fcer_aurc"])
        for sample in per_sample
        if sample.get("model_growth_fcer_aurc") is not None
    ]
    fcer_prevalence_values = [
        cast(float, sample["observed_growth_fcer_prevalence"])
        for sample in per_sample
        if sample.get("observed_growth_fcer_prevalence") is not None
    ]
    model_fcer_iou = float(model_growth_fcer.get("micro_iou", 0.0))
    dilated_fcer_iou = float(dilated_copy_growth_fcer.get("micro_iou", 0.0))

    return {
        "model_full": model_full,
        "model_changed": model_changed,
        "model_growth": model_growth,
        "model_shrink": model_shrink,
        "copy_full": copy_full,
        "copy_changed": copy_changed,
        "copy_growth": copy_growth,
        "dilated_copy_full": dilated_copy_full,
        "dilated_copy_changed": dilated_copy_changed,
        "dilated_copy_growth": dilated_copy_growth,
        "model_growth_transition": model_growth_transition,
        "model_shrink_transition": model_shrink_transition,
        "model_change_transition": model_change_transition,
        "copy_growth_transition": copy_growth_transition,
        "copy_change_transition": copy_change_transition,
        "dilated_copy_growth_transition": dilated_copy_growth_transition,
        "dilated_copy_change_transition": dilated_copy_change_transition,
        "model_growth_fcer": model_growth_fcer,
        "dilated_copy_growth_fcer": dilated_copy_growth_fcer,
        "improvement_vs_copy_iou": model_iou - copy_iou,
        "improvement_vs_dilated_copy_iou": model_iou - dilated_copy_iou,
        "improvement_vs_dilated_copy_iou_changed": (model_iou_changed - dilated_copy_iou_changed),
        "improvement_vs_dilated_copy_iou_growth": (model_iou_growth - dilated_copy_iou_growth),
        "improvement_vs_copy_iou_growth": model_iou_growth - copy_iou_growth,
        # Redefined: meaningful dynamic baseline (was tautological vs naive copy).
        "improvement_vs_copy_iou_changed": (model_iou_changed - dilated_copy_iou_changed),
        "legacy_improvement_vs_naive_copy_iou_changed": legacy_improvement_changed,
        "copy_baseline_iou": copy_iou,
        "dilated_copy_baseline_iou": dilated_copy_iou,
        "copy_baseline_iou_changed": naive_copy_iou_changed,
        "dilated_copy_baseline_iou_changed": dilated_copy_iou_changed,
        "copy_baseline_iou_growth": copy_iou_growth,
        "dilated_copy_baseline_iou_growth": dilated_copy_iou_growth,
        "model_iou": model_iou,
        "model_iou_changed": model_iou_changed,
        "model_iou_growth": model_iou_growth,
        "model_iou_shrink": float(model_shrink.get("micro_iou", 0.0)),
        "model_growth_transition_iou": model_growth_transition_iou,
        "model_change_transition_iou": model_change_transition_iou,
        "model_shrink_transition_iou": float(
            model_shrink_transition.get("micro_iou", 0.0)
        ),
        "copy_growth_transition_iou": float(copy_growth_transition.get("micro_iou", 0.0)),
        "copy_change_transition_iou": float(copy_change_transition.get("micro_iou", 0.0)),
        "dilated_copy_growth_transition_iou": dilated_growth_transition_iou,
        "dilated_copy_change_transition_iou": dilated_change_transition_iou,
        "improvement_vs_dilated_copy_growth_transition_iou": (
            model_growth_transition_iou - dilated_growth_transition_iou
        ),
        "improvement_vs_dilated_copy_change_transition_iou": (
            model_change_transition_iou - dilated_change_transition_iou
        ),
        "model_growth_average_precision_macro": (
            float(np.mean(growth_ap_values)) if growth_ap_values else 0.0
        ),
        "model_growth_average_precision_n": len(growth_ap_values),
        "model_growth_fcer_iou": model_fcer_iou,
        "dilated_copy_growth_fcer_iou": dilated_fcer_iou,
        "improvement_vs_dilated_copy_growth_fcer_iou": (
            model_fcer_iou - dilated_fcer_iou
        ),
        "model_growth_fcer_average_precision_macro": (
            float(np.mean(fcer_ap_values)) if fcer_ap_values else 0.0
        ),
        "model_growth_fcer_average_precision_n": len(fcer_ap_values),
        "observed_growth_fcer_capture_macro": (
            float(np.mean(fcer_capture_values)) if fcer_capture_values else 0.0
        ),
        "observed_growth_fcer_capture_n": len(fcer_capture_values),
        "model_front_boundary_f1_macro": float(np.mean(model_boundary_values)),
        "copy_front_boundary_f1_macro": float(np.mean(copy_boundary_values)),
        "dilated_copy_front_boundary_f1_macro": float(np.mean(dilated_boundary_values)),
        "improvement_vs_dilated_copy_front_boundary_f1": float(
            np.mean(model_boundary_values) - np.mean(dilated_boundary_values)
        ),
        "model_growth_fcer_ece_macro": (
            float(np.mean(fcer_ece_values)) if fcer_ece_values else 0.0
        ),
        "model_growth_fcer_selective_error_80_macro": (
            float(np.mean(fcer_selective_error_values))
            if fcer_selective_error_values
            else 0.0
        ),
        "model_growth_fcer_aurc_macro": (
            float(np.mean(fcer_aurc_values)) if fcer_aurc_values else 0.0
        ),
        "observed_growth_fcer_prevalence_macro": (
            float(np.mean(fcer_prevalence_values)) if fcer_prevalence_values else 0.0
        ),
        "fcer_calibration_semantics": (
            "pixel_probability_ece_and_selective_error_on_t0_only_front_ring"
        ),
        "fcer_semantics": "t0_only_dilated_front_ring_global_transition_companion_required",
        "boundary_metric_semantics": "symmetric_boundary_f1_pixel_tolerance",
        "transition_metric_semantics": "v2_independent_predicted_vs_observed",
        "legacy_target_conditioned_metrics": ["model_changed", "model_growth", "model_shrink"],
        "naive_copy_iou_changed_is_tautological": True,
    }
