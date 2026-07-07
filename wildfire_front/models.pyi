"""Type stubs for the public API of wildfire_front.models.

These stubs declare the public types exported via ``wildfire_front/__init__.py``
so that static type checkers (mypy, pyright) can verify downstream usage without
importing the dataclasses at analysis time.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Geometric primitives
# ---------------------------------------------------------------------------

Point: tuple[float, float]
Line: tuple[Point, ...]
MultiLine: tuple[Line, ...]


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------

class ScenarioConfig:
    event_id: str
    sensor_id: str
    duration_s: int
    interval_s: int
    points_per_front: int
    initial_radius_m: float
    east_speed_m_min: float
    north_speed_m_min: float
    position_error_m: float
    grid_resolution_m: float
    seed: int
    observability_ratio: float

    def __init__(
        self,
        *,
        event_id: str = ...,
        sensor_id: str = ...,
        duration_s: int = ...,
        interval_s: int = ...,
        points_per_front: int = ...,
        initial_radius_m: float = ...,
        east_speed_m_min: float = ...,
        north_speed_m_min: float = ...,
        position_error_m: float = ...,
        grid_resolution_m: float = ...,
        seed: int = ...,
        observability_ratio: float = ...,
    ) -> None: ...
    def validate(self) -> None: ...


class FrontObservation:
    observation_id: str
    event_id: str
    sensor_id: str
    time_s: float
    observed_at: str
    components: MultiLine
    estimated_error_m: float
    status: str
    truth_components: MultiLine | None
    crs: str | None
    coordinate_system: str | None
    resolution_m: float | None
    source_uri: str | None
    source_sha256: str | None
    method: str
    limitations: tuple[str, ...]

    @property
    def points(self) -> Line: ...
    @property
    def truth_points(self) -> Line | None: ...
    def validate(self) -> None: ...


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
    abstention_reason: str | None
    component_index: int
    method: str
    match_distance_m: float | None
    quality_score: float | None


class GeometrySpeedConfig:
    sample_spacing_m: float
    max_normal_distance_m: float
    max_component_centroid_distance_m: float
    observability_ratio: float
    min_component_area_m2: float
    min_valid_fraction: float
    max_turn_angle_deg: float
    max_normal_to_nearest_ratio: float

    def __init__(
        self,
        *,
        sample_spacing_m: float = ...,
        max_normal_distance_m: float = ...,
        max_component_centroid_distance_m: float = ...,
        observability_ratio: float = ...,
        min_component_area_m2: float = ...,
        min_valid_fraction: float = ...,
        max_turn_angle_deg: float = ...,
        max_normal_to_nearest_ratio: float = ...,
    ) -> None: ...
    def validate(self) -> None: ...


class GeometrySpeedResult:
    estimates: tuple[SpeedEstimate, ...]
    matched_component_pairs: int
    unmatched_previous_components: int
    unmatched_current_components: int
    pair_abstentions: tuple[str, ...]
