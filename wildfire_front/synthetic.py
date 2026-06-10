from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from .identity import build_observation_id
from .models import FrontObservation, ScenarioConfig


def _ellipse_points(a: float, b: float, angles: np.ndarray) -> np.ndarray:
    return np.column_stack((a * np.cos(angles), b * np.sin(angles)))


def generate_observations(config: ScenarioConfig) -> list[FrontObservation]:
    """Generate repeatable expanding elliptical fronts with noisy observations."""

    config.validate()
    rng = np.random.default_rng(config.seed)
    angles = np.linspace(0.0, 2.0 * np.pi, config.points_per_front, endpoint=False)
    start = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    observations: list[FrontObservation] = []
    for time_s in range(0, config.duration_s + 1, config.interval_s):
        minutes = time_s / 60.0
        east_radius = config.initial_radius_m + config.east_speed_m_min * minutes
        north_radius = config.initial_radius_m + config.north_speed_m_min * minutes
        truth = _ellipse_points(east_radius, north_radius, angles)
        noise = rng.normal(0.0, config.position_error_m, size=truth.shape)
        observed = truth + noise
        observed_at = (start + timedelta(seconds=time_s)).isoformat().replace("+00:00", "Z")
        observations.append(
            FrontObservation(
                observation_id=build_observation_id(config.event_id, config.sensor_id, observed_at),
                event_id=config.event_id,
                sensor_id=config.sensor_id,
                time_s=float(time_s),
                observed_at=observed_at,
                components=(tuple(map(tuple, observed.tolist())),),
                truth_components=(tuple(map(tuple, truth.tolist())),),
                estimated_error_m=config.position_error_m,
                coordinate_system="local_cartesian_m",
                resolution_m=config.grid_resolution_m,
                method="synthetic_noisy_ellipse",
                limitations=("synthetic_observation",),
            )
        )
    return observations
