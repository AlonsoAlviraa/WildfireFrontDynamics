"""Conservative local spread-rate estimation for non-radial projected geometry."""

from __future__ import annotations

import math

import numpy as np

from .models import (
    FrontObservation,
    GeometrySpeedConfig,
    GeometrySpeedResult,
    Line,
    Point,
    SpeedEstimate,
)


def _open_ring(component: Line) -> np.ndarray:
    points = np.asarray(component, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("components must contain 2D points")
    if len(points) > 1 and np.allclose(points[0], points[-1]):
        points = points[:-1]
    if len(points) < 3 or not np.isfinite(points).all():
        raise ValueError("components require at least three finite unique points")
    keep = np.ones(len(points), dtype=bool)
    keep[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1) > 1e-9
    points = points[keep]
    if len(points) < 3:
        raise ValueError("component collapses after removing duplicate points")
    return points


def signed_area(component: Line) -> float:
    points = _open_ring(component)
    following = np.roll(points, -1, axis=0)
    return float(0.5 * np.sum(points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1]))


def component_centroid(component: Line) -> Point:
    points = _open_ring(component)
    area = signed_area(component)
    if abs(area) < 1e-9:
        center = np.mean(points, axis=0)
        return float(center[0]), float(center[1])
    following = np.roll(points, -1, axis=0)
    cross = points[:, 0] * following[:, 1] - following[:, 0] * points[:, 1]
    factor = 1.0 / (6.0 * area)
    center = factor * np.sum((points + following) * cross[:, None], axis=0)
    return float(center[0]), float(center[1])


def resample_closed_component(component: Line, spacing_m: float) -> np.ndarray:
    """Resample a closed ring approximately uniformly along arc length."""

    if spacing_m <= 0:
        raise ValueError("spacing_m must be positive")
    points = _open_ring(component)
    closed = np.vstack((points, points[0]))
    lengths = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    perimeter = float(np.sum(lengths))
    if perimeter <= spacing_m:
        return points
    cumulative = np.concatenate(([0.0], np.cumsum(lengths)))
    count = max(3, int(math.ceil(perimeter / spacing_m)))
    distances = np.linspace(0.0, perimeter, count, endpoint=False)
    result = np.empty((count, 2), dtype=float)
    segment_indices = np.searchsorted(cumulative, distances, side="right") - 1
    segment_indices = np.clip(segment_indices, 0, len(lengths) - 1)
    local = (distances - cumulative[segment_indices]) / lengths[segment_indices]
    result[:] = closed[segment_indices] + local[:, None] * (
        closed[segment_indices + 1] - closed[segment_indices]
    )
    return result


def outward_normals(sampled: np.ndarray, orientation_area: float) -> np.ndarray:
    previous = np.roll(sampled, 1, axis=0)
    following = np.roll(sampled, -1, axis=0)
    tangents = following - previous
    norms = np.linalg.norm(tangents, axis=1)
    valid = norms > 1e-9
    tangents[valid] /= norms[valid, None]
    tangents[~valid] = 0.0
    if orientation_area > 0:
        return np.column_stack((tangents[:, 1], -tangents[:, 0]))
    return np.column_stack((-tangents[:, 1], tangents[:, 0]))


def local_turn_angles(sampled: np.ndarray) -> np.ndarray:
    incoming = sampled - np.roll(sampled, 1, axis=0)
    outgoing = np.roll(sampled, -1, axis=0) - sampled
    incoming_norm = np.linalg.norm(incoming, axis=1)
    outgoing_norm = np.linalg.norm(outgoing, axis=1)
    valid = (incoming_norm > 1e-9) & (outgoing_norm > 1e-9)
    cosines = np.ones(len(sampled))
    cosines[valid] = np.sum(incoming[valid] * outgoing[valid], axis=1) / (
        incoming_norm[valid] * outgoing_norm[valid]
    )
    return np.degrees(np.arccos(np.clip(cosines, -1.0, 1.0)))


def _cross_2d(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    return left[..., 0] * right[..., 1] - left[..., 1] * right[..., 0]


def normal_ray_distance(point: np.ndarray, normal: np.ndarray, target: Line, max_distance_m: float) -> float | None:
    """Return nearest forward ray intersection with a target closed ring."""

    target_points = _open_ring(target)
    starts = target_points
    ends = np.roll(target_points, -1, axis=0)
    segments = ends - starts
    denominators = _cross_2d(np.broadcast_to(normal, segments.shape), segments)
    non_parallel = np.abs(denominators) > 1e-9
    offsets = starts - point
    ray_t = np.full(len(segments), np.nan)
    segment_u = np.full(len(segments), np.nan)
    ray_t[non_parallel] = _cross_2d(offsets[non_parallel], segments[non_parallel]) / denominators[non_parallel]
    segment_u[non_parallel] = _cross_2d(offsets[non_parallel], np.broadcast_to(normal, segments.shape)[non_parallel]) / denominators[non_parallel]
    valid = (
        non_parallel
        & (ray_t >= 0.0)
        & (ray_t <= max_distance_m)
        & (segment_u >= -1e-9)
        & (segment_u <= 1.0 + 1e-9)
    )
    return float(np.min(ray_t[valid])) if np.any(valid) else None


def nearest_boundary_distance(point: np.ndarray, target: Line) -> float:
    target_points = _open_ring(target)
    starts = target_points
    ends = np.roll(target_points, -1, axis=0)
    segments = ends - starts
    lengths_sq = np.sum(segments * segments, axis=1)
    offsets = point - starts
    parameters = np.zeros(len(segments))
    valid = lengths_sq > 1e-12
    parameters[valid] = np.sum(offsets[valid] * segments[valid], axis=1) / lengths_sq[valid]
    parameters = np.clip(parameters, 0.0, 1.0)
    nearest = starts + parameters[:, None] * segments
    return float(np.min(np.linalg.norm(point - nearest, axis=1)))


def match_components(
    previous: FrontObservation,
    current: FrontObservation,
    config: GeometrySpeedConfig,
) -> tuple[list[tuple[int, int, float]], set[int], set[int]]:
    """Greedy one-to-one matching by centroid distance with an explicit gate."""

    candidates: list[tuple[float, int, int]] = []
    for previous_index, previous_component in enumerate(previous.components):
        previous_center = np.asarray(component_centroid(previous_component))
        for current_index, current_component in enumerate(current.components):
            current_center = np.asarray(component_centroid(current_component))
            distance = float(np.linalg.norm(current_center - previous_center))
            if distance <= config.max_component_centroid_distance_m:
                candidates.append((distance, previous_index, current_index))
    matched_previous: set[int] = set()
    matched_current: set[int] = set()
    matches: list[tuple[int, int, float]] = []
    for distance, previous_index, current_index in sorted(candidates):
        if previous_index in matched_previous or current_index in matched_current:
            continue
        matches.append((previous_index, current_index, distance))
        matched_previous.add(previous_index)
        matched_current.add(current_index)
    return (
        matches,
        set(range(len(previous.components))) - matched_previous,
        set(range(len(current.components))) - matched_current,
    )


def _validate_observation_pair(previous: FrontObservation, current: FrontObservation) -> float:
    previous.validate()
    current.validate()
    if previous.coordinate_system != "projected_metric" or current.coordinate_system != "projected_metric":
        raise ValueError("geometry speed requires projected metric coordinates")
    if not previous.crs or previous.crs != current.crs:
        raise ValueError("geometry speed requires matching non-empty CRS")
    dt_min = (current.time_s - previous.time_s) / 60.0
    if dt_min <= 0:
        raise ValueError("geometry speed requires strictly increasing timestamps")
    return dt_min


def estimate_geometry_speeds(
    observations: list[FrontObservation],
    config: GeometrySpeedConfig | None = None,
) -> GeometrySpeedResult:
    """Estimate local outward displacement by normal-ray intersections."""

    config = config or GeometrySpeedConfig()
    config.validate()
    estimates: list[SpeedEstimate] = []
    pair_abstentions: list[str] = []
    matched_pairs = 0
    unmatched_previous_total = 0
    unmatched_current_total = 0
    for previous, current in zip(observations, observations[1:]):
        try:
            dt_min = _validate_observation_pair(previous, current)
        except ValueError as exc:
            pair_abstentions.append(str(exc))
            continue
        matches, unmatched_previous, unmatched_current = match_components(previous, current, config)
        unmatched_previous_total += len(unmatched_previous)
        unmatched_current_total += len(unmatched_current)
        matched_pairs += len(matches)
        combined_error = math.sqrt(
            previous.estimated_error_m**2
            + current.estimated_error_m**2
            + ((previous.resolution_m or 0.0) ** 2 + (current.resolution_m or 0.0) ** 2) / 12.0
        )
        for previous_index, current_index, centroid_distance in matches:
            previous_component = previous.components[previous_index]
            current_component = current.components[current_index]
            area = abs(signed_area(previous_component))
            if area < config.min_component_area_m2:
                pair_abstentions.append("component_below_minimum_area")
                continue
            sampled = resample_closed_component(previous_component, config.sample_spacing_m)
            normals = outward_normals(sampled, signed_area(previous_component))
            turn_angles = local_turn_angles(sampled)
            distances = [
                normal_ray_distance(point, normal, current_component, config.max_normal_distance_m)
                for point, normal in zip(sampled, normals)
            ]
            nearest_distances = [nearest_boundary_distance(point, current_component) for point in sampled]
            valid_count = sum(distance is not None for distance in distances)
            valid_fraction = valid_count / len(distances)
            if valid_fraction < config.min_valid_fraction:
                pair_abstentions.append("insufficient_normal_intersections")
            for point, normal, distance, nearest_distance, turn_angle in zip(
                sampled, normals, distances, nearest_distances, turn_angles
            ):
                angle_deg = float((math.degrees(math.atan2(normal[1], normal[0])) + 360.0) % 360.0)
                reason: str | None = None
                observable = True
                if distance is None:
                    observable = False
                    reason = "no_forward_normal_intersection"
                    displacement = 0.0
                else:
                    displacement = distance
                    if turn_angle > config.max_turn_angle_deg:
                        observable = False
                        reason = "high_local_curvature"
                    elif distance > config.max_normal_to_nearest_ratio * max(
                        nearest_distance,
                        previous.resolution_m or 1e-6,
                    ):
                        observable = False
                        reason = "normal_intersection_inconsistent_with_nearest_boundary"
                    elif distance <= config.observability_ratio * combined_error:
                        observable = False
                        reason = "movement_below_observability_threshold"
                    elif valid_fraction < config.min_valid_fraction:
                        observable = False
                        reason = "component_match_below_quality_threshold"
                estimates.append(
                    SpeedEstimate(
                        time_start_s=previous.time_s,
                        time_end_s=current.time_s,
                        angle_deg=angle_deg,
                        point=(float(point[0]), float(point[1])),
                        displacement_m=float(displacement),
                        speed_m_min=float(displacement / dt_min) if observable else None,
                        truth_speed_m_min=None,
                        uncertainty_m_min=float(combined_error / dt_min),
                        observable=observable,
                        abstention_reason=reason,
                        component_index=previous_index,
                        method="normal_ray_intersection",
                        match_distance_m=centroid_distance,
                        quality_score=valid_fraction,
                    )
                )
    return GeometrySpeedResult(
        estimates=tuple(estimates),
        matched_component_pairs=matched_pairs,
        unmatched_previous_components=unmatched_previous_total,
        unmatched_current_components=unmatched_current_total,
        pair_abstentions=tuple(sorted(set(pair_abstentions))),
    )


def summarize_geometry_speeds(result: GeometrySpeedResult) -> dict[str, object]:
    observable = [item for item in result.estimates if item.observable and item.speed_m_min is not None]
    speeds = np.asarray([item.speed_m_min for item in observable], dtype=float)
    reasons: dict[str, int] = {}
    for item in result.estimates:
        if item.abstention_reason:
            reasons[item.abstention_reason] = reasons.get(item.abstention_reason, 0) + 1
    return {
        "speed_status": "estimated" if observable else "abstained",
        "num_speed_estimates": len(result.estimates),
        "num_observable": len(observable),
        "observable_ratio": len(observable) / len(result.estimates) if result.estimates else 0.0,
        "speed_median_m_min": float(np.median(speeds)) if len(speeds) else None,
        "speed_p95_m_min": float(np.percentile(speeds, 95)) if len(speeds) else None,
        "matched_component_pairs": result.matched_component_pairs,
        "unmatched_previous_components": result.unmatched_previous_components,
        "unmatched_current_components": result.unmatched_current_components,
        "speed_abstention_reasons": reasons,
        "pair_abstentions": list(result.pair_abstentions),
    }
