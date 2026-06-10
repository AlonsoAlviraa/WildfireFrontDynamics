from __future__ import annotations

import math

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

from .models import FrontObservation, ScenarioConfig, SpeedEstimate


def estimate_local_speeds(
    observations: list[FrontObservation], config: ScenarioConfig
) -> list[SpeedEstimate]:
    """Estimate radial local speeds and abstain when movement is not observable."""

    estimates: list[SpeedEstimate] = []
    combined_error = math.sqrt(2.0) * config.position_error_m
    for previous, current in zip(observations, observations[1:]):
        p0 = np.asarray(previous.points)
        p1 = np.asarray(current.points)
        if previous.truth_points is None or current.truth_points is None:
            raise ValueError("radial speed estimator requires optional ground truth and is synthetic-only")
        t0 = np.asarray(previous.truth_points)
        t1 = np.asarray(current.truth_points)
        dt_min = (current.time_s - previous.time_s) / 60.0
        radii0 = np.linalg.norm(p0, axis=1)
        radii1 = np.linalg.norm(p1, axis=1)
        truth_displacement = np.linalg.norm(t1, axis=1) - np.linalg.norm(t0, axis=1)
        for index, (start_radius, end_radius) in enumerate(zip(radii0, radii1)):
            displacement = float(end_radius - start_radius)
            observable = displacement > config.observability_ratio * combined_error
            speed = displacement / dt_min if observable else None
            point = tuple(map(float, p1[index]))
            estimates.append(
                SpeedEstimate(
                    time_start_s=previous.time_s,
                    time_end_s=current.time_s,
                    angle_deg=index * 360.0 / len(p1),
                    point=point,
                    displacement_m=displacement,
                    speed_m_min=speed,
                    truth_speed_m_min=float(truth_displacement[index] / dt_min),
                    uncertainty_m_min=combined_error / dt_min,
                    observable=observable,
                    abstention_reason=None if observable else "movement_below_observability_threshold",
                )
            )
    return estimates


def reconstruct_arrival_grid(
    observations: list[FrontObservation], config: ScenarioConfig
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Assign each grid cell the first observed time inside an observed front."""

    all_points = np.vstack([np.asarray(item.points) for item in observations])
    limit = math.ceil(float(np.abs(all_points).max()) + config.grid_resolution_m * 2)
    axis = np.arange(-limit, limit + config.grid_resolution_m, config.grid_resolution_m)
    xx, yy = np.meshgrid(axis, axis)
    arrival = np.full(xx.shape, np.nan)
    angles = np.arctan2(yy, xx)

    for observation in observations:
        points = np.asarray(observation.points)
        point_angles = np.arctan2(points[:, 1], points[:, 0])
        point_radii = np.linalg.norm(points, axis=1)
        order = np.argsort(point_angles)
        sorted_angles = point_angles[order]
        sorted_radii = point_radii[order]
        extended_angles = np.concatenate((sorted_angles - 2 * np.pi, sorted_angles, sorted_angles + 2 * np.pi))
        extended_radii = np.tile(sorted_radii, 3)
        boundary = np.interp(angles.ravel(), extended_angles, extended_radii).reshape(angles.shape)
        inside = np.hypot(xx, yy) <= boundary
        arrival[np.isnan(arrival) & inside] = observation.time_s
    return xx, yy, arrival


def reconstruct_arrival_from_components(
    observations: list[FrontObservation], resolution: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rasterize arbitrary closed observed components into first-arrival times."""

    if not observations:
        raise ValueError("at least one observation is required")
    if resolution <= 0:
        raise ValueError("resolution must be positive")
    all_points = np.vstack(
        [np.asarray(component) for observation in observations for component in observation.components]
    )
    min_x, min_y = np.min(all_points, axis=0) - resolution
    max_x, max_y = np.max(all_points, axis=0) + resolution
    width = max(1, int(math.ceil((max_x - min_x) / resolution)))
    height = max(1, int(math.ceil((max_y - min_y) / resolution)))
    transform = from_origin(float(min_x), float(max_y), resolution, resolution)
    arrival = np.full((height, width), np.nan)
    for observation in sorted(observations, key=lambda item: item.time_s):
        geometries = [
            {"type": "Polygon", "coordinates": [[list(point) for point in component]]}
            for component in observation.components
            if len(component) >= 4
        ]
        if not geometries:
            continue
        inside = rasterize(geometries, out_shape=arrival.shape, transform=transform, fill=0, default_value=1)
        arrival[np.isnan(arrival) & (inside == 1)] = observation.time_s
    xs = min_x + (np.arange(width) + 0.5) * resolution
    ys = max_y - (np.arange(height) + 0.5) * resolution
    xx, yy = np.meshgrid(xs, ys)
    return xx, yy, arrival


def real_speed_abstention(observations: list[FrontObservation]) -> dict[str, object]:
    """Explain why the current radial speed estimator is not used on real geometry."""

    reasons: list[str] = []
    if len(observations) < 2:
        reasons.append("insufficient_observations")
    if any(not item.observed_at for item in observations):
        reasons.append("missing_timestamp")
    if any(not item.crs for item in observations):
        reasons.append("missing_crs")
    if any(item.coordinate_system != "projected_metric" for item in observations):
        reasons.append("crs_not_projected_metric")
    reasons.append("non_radial_real_geometry_speed_estimator_not_implemented")
    return {"speed_status": "abstained", "speed_abstention_reasons": sorted(set(reasons))}


def summarize(estimates: list[SpeedEstimate], arrival: np.ndarray) -> dict[str, float | int]:
    observable = [item for item in estimates if item.observable and item.speed_m_min is not None]
    errors = [
        abs(float(item.speed_m_min) - item.truth_speed_m_min)
        for item in observable
        if item.truth_speed_m_min is not None
    ]
    result: dict[str, float | int] = {
        "num_speed_estimates": len(estimates),
        "num_observable": len(observable),
        "observable_ratio": len(observable) / len(estimates) if estimates else 0.0,
        "arrival_cells_observed": int(np.count_nonzero(~np.isnan(arrival))),
    }
    if errors:
        result["speed_mae_m_min"] = float(np.mean(errors))
    return result
