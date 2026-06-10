"""Geometry-first evaluation metrics expressed in source coordinate units."""

from __future__ import annotations

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
    projections[:, valid] = np.sum(offsets[:, valid, :] * segments[None, valid, :], axis=2) / lengths_sq[valid]
    projections = np.clip(projections, 0.0, 1.0)
    nearest = starts[None, :, :] + projections[:, :, None] * segments[None, :, :]
    distances = np.linalg.norm(points[:, None, :] - nearest, axis=2)
    return np.min(distances, axis=1)


def front_distance_metrics(observed: Line, reference: Line, sample_spacing: float = 1.0) -> dict[str, float]:
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
