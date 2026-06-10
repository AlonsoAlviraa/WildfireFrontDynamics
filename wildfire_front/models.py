from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]
Line = tuple[Point, ...]
MultiLine = tuple[Line, ...]


@dataclass(frozen=True)
class ScenarioConfig:
    event_id: str = "synthetic_burn_001"
    sensor_id: str = "synthetic_thermal"
    duration_s: int = 600
    interval_s: int = 60
    points_per_front: int = 120
    initial_radius_m: float = 8.0
    east_speed_m_min: float = 3.0
    north_speed_m_min: float = 1.8
    position_error_m: float = 0.6
    grid_resolution_m: float = 2.0
    seed: int = 7
    observability_ratio: float = 2.0

    def validate(self) -> None:
        if self.duration_s <= 0 or self.interval_s <= 0:
            raise ValueError("duration_s and interval_s must be positive")
        if self.interval_s > self.duration_s:
            raise ValueError("interval_s cannot exceed duration_s")
        if self.points_per_front < 12:
            raise ValueError("points_per_front must be at least 12")
        if min(self.initial_radius_m, self.east_speed_m_min, self.north_speed_m_min) <= 0:
            raise ValueError("radius and speeds must be positive")
        if self.position_error_m < 0 or self.grid_resolution_m <= 0:
            raise ValueError("position_error_m cannot be negative and grid_resolution_m must be positive")
        if self.observability_ratio <= 0:
            raise ValueError("observability_ratio must be positive")


@dataclass(frozen=True)
class FrontObservation:
    observation_id: str
    event_id: str
    sensor_id: str
    time_s: float
    observed_at: str
    components: MultiLine
    estimated_error_m: float
    status: str = "observed"
    truth_components: MultiLine | None = None
    crs: str | None = None
    coordinate_system: str | None = None
    resolution_m: float | None = None
    source_uri: str | None = None
    source_sha256: str | None = None
    method: str = "unknown"
    limitations: tuple[str, ...] = ()

    def validate(self) -> None:
        if not self.observation_id or not self.event_id or not self.sensor_id:
            raise ValueError("observation identity fields cannot be empty")
        if not math.isfinite(self.time_s):
            raise ValueError("observation time_s must be finite")
        if self.estimated_error_m < 0 or not math.isfinite(self.estimated_error_m):
            raise ValueError("estimated_error_m must be finite and non-negative")
        if not self.components:
            raise ValueError("observation requires at least one component")
        for component in self.components:
            if len(component) < 4:
                raise ValueError("each closed component requires at least four points")
            if any(not math.isfinite(value) for point in component for value in point):
                raise ValueError("component coordinates must be finite")
        if self.coordinate_system == "projected_metric" and (
            self.resolution_m is None or self.resolution_m <= 0
        ):
            raise ValueError("projected metric observations require positive resolution_m")

    @property
    def points(self) -> Line:
        """Primary component retained for the synthetic radial estimator."""

        return self.components[0]

    @property
    def truth_points(self) -> Line | None:
        return self.truth_components[0] if self.truth_components else None


@dataclass(frozen=True)
class SpeedEstimate:
    time_start_s: float
    time_end_s: float
    angle_deg: float
    point: Point
    displacement_m: float
    speed_m_min: float | None
    truth_speed_m_min: float | None
    uncertainty_m_min: float
    observable: bool
    abstention_reason: str | None = None
    component_index: int = 0
    method: str = "radial_synthetic"
    match_distance_m: float | None = None
    quality_score: float | None = None


@dataclass(frozen=True)
class GeometrySpeedConfig:
    sample_spacing_m: float = 2.0
    max_normal_distance_m: float = 100.0
    max_component_centroid_distance_m: float = 250.0
    observability_ratio: float = 2.0
    min_component_area_m2: float = 4.0
    min_valid_fraction: float = 0.25
    max_turn_angle_deg: float = 60.0
    max_normal_to_nearest_ratio: float = 2.0

    def validate(self) -> None:
        values = (
            self.sample_spacing_m,
            self.max_normal_distance_m,
            self.max_component_centroid_distance_m,
            self.observability_ratio,
            self.min_component_area_m2,
            self.min_valid_fraction,
            self.max_turn_angle_deg,
            self.max_normal_to_nearest_ratio,
        )
        if any(value <= 0 for value in values):
            raise ValueError("geometry speed configuration values must be positive")
        if self.min_valid_fraction > 1:
            raise ValueError("min_valid_fraction must be in (0, 1]")
        if self.max_turn_angle_deg > 180:
            raise ValueError("max_turn_angle_deg must be in (0, 180]")


@dataclass(frozen=True)
class GeometrySpeedResult:
    estimates: tuple[SpeedEstimate, ...]
    matched_component_pairs: int
    unmatched_previous_components: int
    unmatched_current_components: int
    pair_abstentions: tuple[str, ...]
