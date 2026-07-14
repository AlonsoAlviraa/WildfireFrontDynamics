"""NDWS-specific evaluation metrics for wildfire spread models.

The copy baseline (predict PrevFireMask as next-day fire) achieves IoU ~0.79 on
NDWS. Absolute-mask IoU (~0.24) is misleading because ~87% of pixels are
stable day-to-day. These metrics expose whether the model beats copy where it
matters: on pixels that actually change.
"""

from __future__ import annotations

import numpy as np

from wildfire_front.evaluation import (
    SegmentationMetrics,
    aggregate_segmentation_metrics,
    compute_segmentation_metrics,
)


def sanitize_fire_mask(mask: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Binarize NDWS fire masks, treating negative sentinels as no-fire."""
    m = np.asarray(mask, dtype=np.float64)
    m = np.where(m < 0.0, 0.0, m)
    if m.max() > 1.0 or m.min() < 0.0:
        m = 1.0 / (1.0 + np.exp(-m))
    return (m >= threshold).astype(np.float64)


def changed_pixel_mask(
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> np.ndarray:
    """Boolean mask of pixels where prev and target disagree."""
    prev_bin = sanitize_fire_mask(prev_fire, threshold)
    tgt_bin = sanitize_fire_mask(target_fire, threshold)
    return (prev_bin != tgt_bin).astype(np.float64)


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
    """Return the copy-baseline prediction (prev mask binarized)."""
    return sanitize_fire_mask(prev_fire, threshold)


def evaluate_sample(
    prediction: np.ndarray,
    prev_fire: np.ndarray,
    target_fire: np.ndarray,
    threshold: float = 0.5,
) -> dict[str, SegmentationMetrics]:
    """Per-sample metrics: full grid, changed pixels only, and copy baseline."""
    change = changed_pixel_mask(prev_fire, target_fire, threshold)
    copy_pred = copy_baseline_prediction(prev_fire, threshold)

    return {
        "model_full": compute_segmentation_metrics(prediction, target_fire, threshold),
        "model_changed": compute_segmentation_metrics_on_mask(
            prediction, target_fire, change, threshold
        ),
        "copy_full": compute_segmentation_metrics(copy_pred, target_fire, threshold),
        "copy_changed": compute_segmentation_metrics_on_mask(
            copy_pred, target_fire, change, threshold
        ),
    }


def aggregate_ndws_evaluation(
    per_sample: list[dict[str, SegmentationMetrics]],
) -> dict[str, float | str]:
    """Aggregate per-sample NDWS metrics into summary dict for logging/JSON."""
    if not per_sample:
        return {"note": "no samples"}

    def _agg(key: str) -> dict[str, float | str]:
        return aggregate_segmentation_metrics([s[key] for s in per_sample])

    model_full = _agg("model_full")
    model_changed = _agg("model_changed")
    copy_full = _agg("copy_full")
    copy_changed = _agg("copy_changed")

    model_iou = float(model_full.get("micro_iou", 0.0))
    copy_iou = float(copy_full.get("micro_iou", 0.0))
    model_iou_changed = float(model_changed.get("micro_iou", 0.0))
    copy_iou_changed = float(copy_changed.get("micro_iou", 0.0))

    return {
        "model_full": model_full,
        "model_changed": model_changed,
        "copy_full": copy_full,
        "copy_changed": copy_changed,
        "improvement_vs_copy_iou": model_iou - copy_iou,
        "improvement_vs_copy_iou_changed": model_iou_changed - copy_iou_changed,
        "copy_baseline_iou": copy_iou,
        "copy_baseline_iou_changed": copy_iou_changed,
        "model_iou": model_iou,
        "model_iou_changed": model_iou_changed,
    }