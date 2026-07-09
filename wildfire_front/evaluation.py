"""Geometry-first evaluation metrics expressed in source coordinate units.

This module provides two families of metrics:

1. **Segmentation metrics** (pixel-level): IoU, F1/Dice, Precision, Recall,
   Accuracy and confusion-matrix counts.  These operate on binary
   ``numpy.ndarray`` masks and are the workhorse for evaluating the ML model's
   per-cell neighbour-spread predictions.
2. **Front-geometry metrics** (coordinate-level): point-to-segment distances,
   Hausdorff distance, and propagation speed/direction errors.  These operate
   on ``Line`` objects (ordered coordinate arrays) in source CRS units.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .geometry_speed import resample_closed_component
from .models import Line


def point_to_segments_distance(points: np.ndarray, component: Line) -> np.ndarray:
    target = np.asarray(component, dtype=float)
    if len(target) > 1 and np.allclose(target[0], target[-1]):
        target = target[:-1]
    starts = target
    ends = np.roll(target, -1, axis=0)
    segments = ends - starts
    lengths_sq = np.sum(segments * segments, axis=1)
    offsets = points[:, None, :] - starts[None, :, :]
    projections = np.zeros((len(points), len(starts)))
    valid = lengths_sq > 1e-12
    projections[:, valid] = (
        np.sum(offsets[:, valid, :] * segments[None, valid, :], axis=2) / lengths_sq[valid]
    )
    projections = np.clip(projections, 0.0, 1.0)
    nearest = starts[None, :, :] + projections[:, :, None] * segments[None, :, :]
    distances = np.linalg.norm(points[:, None, :] - nearest, axis=2)
    return np.min(distances, axis=1)


def front_distance_metrics(
    observed: Line, reference: Line, sample_spacing: float = 1.0
) -> dict[str, float]:
    observed_samples = resample_closed_component(observed, sample_spacing)
    reference_samples = resample_closed_component(reference, sample_spacing)
    observed_to_reference = point_to_segments_distance(observed_samples, reference)
    reference_to_observed = point_to_segments_distance(reference_samples, observed)
    symmetric = np.concatenate((observed_to_reference, reference_to_observed))
    return {
        "front_distance_mean": float(np.mean(symmetric)),
        "front_distance_p95": float(np.percentile(symmetric, 95)),
        "front_hausdorff": float(np.max(symmetric)),
    }


# ---------------------------------------------------------------------------
# 1. Segmentation metrics (pixel-level)
# ---------------------------------------------------------------------------


@dataclass
class SegmentationMetrics:
    """Container for binary segmentation quality metrics."""

    iou: float
    dice: float
    precision: float
    recall: float
    accuracy: float
    specificity: float
    tp: int
    fp: int
    fn: int
    tn: int

    def as_dict(self) -> dict[str, float | int]:
        """Return a flat dictionary suitable for JSON serialisation / logging."""
        return {
            "iou": self.iou,
            "dice_f1": self.dice,
            "precision": self.precision,
            "recall": self.recall,
            "accuracy": self.accuracy,
            "specificity": self.specificity,
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "tn": self.tn,
        }


def compute_segmentation_metrics(
    prediction: np.ndarray,
    ground_truth: np.ndarray,
    threshold: float = 0.5,
    *,
    eps: float = 1e-7,
) -> SegmentationMetrics:
    """Compute pixel-level segmentation metrics on binary masks.

    Parameters
    ----------
    prediction
        Predicted mask, either probabilistic ``[0, 1]`` or already binary.
    ground_truth
        Reference binary mask ``{0, 1}``.
    threshold
        Binarisation threshold applied to *prediction* when its values
        exceed the range ``{0, 1}``.
    eps
        Small epsilon to avoid division by zero.

    Returns
    -------
    SegmentationMetrics
        Dataclass with IoU, Dice/F1, precision, recall, accuracy,
        specificity and raw confusion-matrix counts.
    """
    pred = np.asarray(prediction, dtype=np.float64)
    gt = np.asarray(ground_truth, dtype=np.float64)

    # Binarise prediction
    if pred.max() > 1.0 or pred.min() < 0.0:
        pred = 1.0 / (1.0 + np.exp(-pred))  # sigmoid if logits
    pred_bin = (pred >= threshold).astype(np.float64)
    gt_bin = (gt >= threshold).astype(np.float64)

    tp = int(np.sum((pred_bin == 1) & (gt_bin == 1)))
    fp = int(np.sum((pred_bin == 1) & (gt_bin == 0)))
    fn = int(np.sum((pred_bin == 0) & (gt_bin == 1)))
    tn = int(np.sum((pred_bin == 0) & (gt_bin == 0)))

    total = tp + fp + fn + tn

    iou = tp / (tp + fp + fn + eps)
    dice = (2 * tp) / (2 * tp + fp + fn + eps)
    precision = tp / (tp + fp + eps)
    recall = tp / (tp + fn + eps)
    accuracy = (tp + tn) / (total + eps) if total > 0 else 0.0
    specificity = tn / (tn + fp + eps)

    return SegmentationMetrics(
        iou=iou,
        dice=dice,
        precision=precision,
        recall=recall,
        accuracy=accuracy,
        specificity=specificity,
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
    )


def aggregate_segmentation_metrics(
    metrics_list: list[SegmentationMetrics],
) -> dict[str, float]:
    """Aggregate a list of per-sample metrics into mean ± std summaries.

    Handles the common case where some patches have zero active fire
    (TP=FP=FN=0) by excluding them from IoU/Dice means.
    """
    if not metrics_list:
        return {}

    valid = [m for m in metrics_list if (m.tp + m.fp + m.fn) > 0]
    if not valid:
        return {"iou_mean": 0.0, "note": "no active fire in any sample"}

    keys = ["iou", "dice", "precision", "recall", "accuracy", "specificity"]
    agg: dict[str, float] = {}
    for key in keys:
        values = np.array([getattr(m, key) for m in valid])
        agg[f"{key}_mean"] = float(np.mean(values))
        agg[f"{key}_std"] = float(np.std(values))

    # Micro averages (pool all TP/FP/FN)
    total_tp = sum(m.tp for m in metrics_list)
    total_fp = sum(m.fp for m in metrics_list)
    total_fn = sum(m.fn for m in metrics_list)
    total_tn = sum(m.tn for m in metrics_list)
    agg["micro_iou"] = total_tp / (total_tp + total_fp + total_fn + 1e-7)
    agg["micro_dice"] = (2 * total_tp) / (2 * total_tp + total_fp + total_fn + 1e-7)
    agg["micro_precision"] = total_tp / (total_tp + total_fp + 1e-7)
    agg["micro_recall"] = total_tp / (total_tp + total_fn + 1e-7)
    agg["n_samples"] = float(len(metrics_list))
    agg["n_valid"] = float(len(valid))

    return agg


# ---------------------------------------------------------------------------
# 2. Front propagation metrics (physics-level)
# ---------------------------------------------------------------------------


@dataclass
class FrontPropagationMetrics:
    """Container for fire-front propagation quality metrics.

    All distance/speed values are expressed in source CRS units (typically
    metres).  Direction errors are in degrees ``[0, 180]``.
    """

    speed_rmse: float
    speed_mae: float
    speed_bias: float
    direction_mae: float
    arrival_time_rmse: float
    n_fronts_compared: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "speed_rmse": self.speed_rmse,
            "speed_mae": self.speed_mae,
            "speed_bias": self.speed_bias,
            "direction_mae": self.direction_mae,
            "arrival_time_rmse": self.arrival_time_rmse,
            "n_fronts_compared": self.n_fronts_compared,
        }


def compute_front_propagation_metrics(
    predicted_speeds: np.ndarray,
    observed_speeds: np.ndarray,
    predicted_directions: np.ndarray | None = None,
    observed_directions: np.ndarray | None = None,
    predicted_arrival_times: np.ndarray | None = None,
    observed_arrival_times: np.ndarray | None = None,
) -> FrontPropagationMetrics:
    """Compute physics-level propagation metrics between predicted and
    observed fire fronts.

    Parameters
    ----------
    predicted_speeds, observed_speeds
        Arrays of front propagation speeds (m/s or consistent CRS units).
    predicted_directions, observed_directions
        Optional arrays of propagation directions in degrees.
    predicted_arrival_times, observed_arrival_times
        Optional arrays of fire arrival times (seconds or consistent units).

    Returns
    -------
    FrontPropagationMetrics
    """
    pred_s = np.asarray(predicted_speeds, dtype=np.float64)
    obs_s = np.asarray(observed_speeds, dtype=np.float64)

    n = min(len(pred_s), len(obs_s))
    pred_s, obs_s = pred_s[:n], obs_s[:n]

    speed_errors = pred_s - obs_s
    speed_rmse = float(np.sqrt(np.mean(speed_errors**2))) if n > 0 else 0.0
    speed_mae = float(np.mean(np.abs(speed_errors))) if n > 0 else 0.0
    speed_bias = float(np.mean(speed_errors)) if n > 0 else 0.0

    direction_mae = 0.0
    if predicted_directions is not None and observed_directions is not None:
        pred_d = np.asarray(predicted_directions, dtype=np.float64)[:n]
        obs_d = np.asarray(observed_directions, dtype=np.float64)[:n]
        # Circular difference (shortest arc)
        diff = np.abs(((pred_d - obs_d + 180.0) % 360.0) - 180.0)
        direction_mae = float(np.mean(diff)) if n > 0 else 0.0

    arrival_rmse = 0.0
    if predicted_arrival_times is not None and observed_arrival_times is not None:
        pred_t = np.asarray(predicted_arrival_times, dtype=np.float64)[:n]
        obs_t = np.asarray(observed_arrival_times, dtype=np.float64)[:n]
        t_errors = pred_t - obs_t
        arrival_rmse = float(np.sqrt(np.mean(t_errors**2))) if n > 0 else 0.0

    return FrontPropagationMetrics(
        speed_rmse=speed_rmse,
        speed_mae=speed_mae,
        speed_bias=speed_bias,
        direction_mae=direction_mae,
        arrival_time_rmse=arrival_rmse,
        n_fronts_compared=n,
    )
