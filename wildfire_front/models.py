from __future__ import annotations

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
