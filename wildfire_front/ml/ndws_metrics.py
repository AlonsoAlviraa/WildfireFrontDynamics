"""NDWS-specific evaluation metrics for wildfire spread models.

The naive copy baseline (predict PrevFireMask as next-day fire) achieves IoU
~0.79 on dense-fire NDWS patches. On pixels where prev != target, naive copy
always scores IoU = 0 by definition — so ``model_iou - copy_iou`` on that subset
is not a meaningful "improvement". Use dilated-copy and growth-only baselines
instead (see ``improvement_vs_dilated_copy_iou_changed``).
"""

from __future__ import annotations

import numpy as np

from wildfire_front.evaluation import (
    SegmentationMetrics,
    aggregate_segmentation_metrics,
    compute_segmentation_metrics,
)

# Default 1-pixel morphological dilation for a non-trivial dynamic baseline.
DEFAULT_DILATION_RADIUS = 1


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
) -> dict[str, SegmentationMetrics]:
    """Per-sample metrics: full grid, dynamic subsets, and copy baselines."""
    change = changed_pixel_mask(prev_fire, target_fire, threshold)
    growth = growth_pixel_mask(prev_fire, target_fire, threshold)
    shrink = shrink_pixel_mask(prev_fire, target_fire, threshold)
    copy_pred = copy_baseline_prediction(prev_fire, threshold)
    dilated_copy_pred = dilated_copy_baseline_prediction(
        prev_fire, threshold, radius=dilation_radius
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
    }


def aggregate_ndws_evaluation(
    per_sample: list[dict[str, SegmentationMetrics]],
) -> dict[str, float | str | dict[str, float | str]]:
    """Aggregate per-sample NDWS metrics into summary dict for logging/JSON."""
    if not per_sample:
        return {"note": "no samples"}

    def _agg(key: str) -> dict[str, float | str]:
        return dict(aggregate_segmentation_metrics([s[key] for s in per_sample]))

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
        "naive_copy_iou_changed_is_tautological": True,
    }
