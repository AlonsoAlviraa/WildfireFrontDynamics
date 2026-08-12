from __future__ import annotations

import numpy as np
import pytest

from wildfire_front.geometry_speed import (
    estimate_geometry_speeds,
    match_components,
    resample_closed_component,
    signed_area,
    summarize_geometry_speeds,
)
from wildfire_front.models import FrontObservation, GeometrySpeedConfig, Line


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float) -> Line:
    return ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y), (min_x, min_y))


def observation(
    time_s: float, components: tuple[Line, ...], error_m: float = 0.1
) -> FrontObservation:
    return FrontObservation(
        observation_id=f"obs_{time_s}",
        event_id="geometry_test",
        sensor_id="thermal",
        time_s=time_s,
        observed_at=f"2026-06-10T12:{int(time_s / 60):02d}:00Z",
        components=components,
        estimated_error_m=error_m,
        crs="EPSG:32630",
        coordinate_system="projected_metric",
        resolution_m=0.2,
        method="test_mask",
    )


class GeometrySpeedTests:
    def test_non_radial_rectangle_expansion_recovers_local_speed(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 20, 10),))
        current = observation(60.0, (rectangle(-2, -2, 22, 12),))
        result = estimate_geometry_speeds(
            [previous, current],
            GeometrySpeedConfig(sample_spacing_m=1.0, max_normal_distance_m=10.0),
        )
        summary = summarize_geometry_speeds(result)
        observable = [item.speed_m_min for item in result.estimates if item.observable]
        assert summary["observable_ratio"] > 0.8
        assert pytest.approx(float(np.median(observable)), abs=0.15) == 2.0
        assert summary["speed_status"] == "estimated"

    def test_sub_error_motion_abstains(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 20, 10),), error_m=1.0)
        current = observation(60.0, (rectangle(-0.2, -0.2, 20.2, 10.2),), error_m=1.0)
        result = estimate_geometry_speeds([previous, current])
        summary = summarize_geometry_speeds(result)
        assert summary["speed_status"] == "abstained"
        assert summary["num_observable"] == 0

    def test_inconsistent_normal_intersection_abstains(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 20, 10),))
        current = observation(60.0, (rectangle(-100, -20, 21, 11),))
        result = estimate_geometry_speeds(
            [previous, current],
            GeometrySpeedConfig(
                sample_spacing_m=1.0,
                max_normal_distance_m=50.0,
                max_turn_angle_deg=180.0,
                max_normal_to_nearest_ratio=1.1,
            ),
        )
        reasons = {item.abstention_reason for item in result.estimates}
        assert "normal_intersection_inconsistent_with_nearest_boundary" in reasons

    def test_new_ignition_is_unmatched_not_forced(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10),))
        current = observation(60.0, (rectangle(-2, -2, 12, 12), rectangle(500, 500, 510, 510)))
        result = estimate_geometry_speeds([previous, current])
        assert result.matched_component_pairs == 1
        assert result.unmatched_current_components == 1

    def test_component_matching_is_one_to_one(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10), rectangle(100, 100, 110, 110)))
        current = observation(60.0, (rectangle(-1, -1, 11, 11), rectangle(101, 101, 111, 111)))
        matches, missing_previous, missing_current = match_components(
            previous, current, GeometrySpeedConfig()
        )
        assert len(matches) == 2
        assert not missing_previous
        assert not missing_current

    def test_non_metric_crs_abstains_at_pair_level(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10),))
        current = observation(60.0, (rectangle(-1, -1, 11, 11),))
        current = FrontObservation(**{**current.__dict__, "coordinate_system": "geographic"})
        result = estimate_geometry_speeds([previous, current])
        assert len(result.estimates) == 0
        assert any(
            "geometry speed requires projected metric coordinates" in reason
            for reason in result.pair_abstentions
        ), f"Expected coordinate-system abstention, got {result.pair_abstentions}"

    def test_resampling_and_orientation_are_stable(self) -> None:
        ring = rectangle(0, 0, 20, 10)
        sampled = resample_closed_component(ring, 2.0)
        assert len(sampled) > 10
        assert signed_area(ring) > 0

    def test_local_cartesian_crs_none_is_accepted(self) -> None:
        """Synthetic data uses coordinate_system='local_cartesian_m' + crs=None.

        This must be accepted by the geometry-speed estimator (it's metric and
        both observations share the same None CRS).
        """
        previous = FrontObservation(
            observation_id="syn_prev",
            event_id="syn",
            sensor_id="thermal",
            time_s=0.0,
            observed_at="2026-07-09T12:00:00Z",
            components=(rectangle(0, 0, 20, 10),),
            estimated_error_m=0.1,
            crs=None,
            coordinate_system="local_cartesian_m",
            resolution_m=1.0,
            method="synthetic",
        )
        current = FrontObservation(
            observation_id="syn_cur",
            event_id="syn",
            sensor_id="thermal",
            time_s=60.0,
            observed_at="2026-07-09T12:01:00Z",
            components=(rectangle(-2, -2, 22, 12),),
            estimated_error_m=0.1,
            crs=None,
            coordinate_system="local_cartesian_m",
            resolution_m=1.0,
            method="synthetic",
        )
        result = estimate_geometry_speeds([previous, current])
        summary = summarize_geometry_speeds(result)
        assert summary["speed_status"] == "estimated"
        assert summary["num_observable"] > 0

    def test_mixed_crs_none_and_real_is_rejected(self) -> None:
        """crs=None mixed with a real EPSG code must be rejected."""
        previous = observation(0.0, (rectangle(0, 0, 10, 10),))
        current = FrontObservation(
            observation_id="syn_cur",
            event_id="syn",
            sensor_id="thermal",
            time_s=60.0,
            observed_at="2026-07-09T12:01:00Z",
            components=(rectangle(-1, -1, 11, 11),),
            estimated_error_m=0.1,
            crs=None,
            coordinate_system="local_cartesian_m",
            resolution_m=1.0,
            method="synthetic",
        )
        result = estimate_geometry_speeds([previous, current])
        assert len(result.estimates) == 0
        assert any("matching CRS" in reason for reason in result.pair_abstentions), (
            f"Expected CRS mismatch abstention, got {result.pair_abstentions}"
        )
