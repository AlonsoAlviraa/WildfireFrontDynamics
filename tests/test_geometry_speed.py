from __future__ import annotations

import unittest

import numpy as np

from wildfire_front.geometry_speed import (
    estimate_geometry_speeds,
    match_components,
    resample_closed_component,
    signed_area,
    summarize_geometry_speeds,
)
from wildfire_front.models import FrontObservation, GeometrySpeedConfig, Line


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float) -> Line:
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
        (min_x, min_y),
    )


def observation(time_s: float, components: tuple[Line, ...], error_m: float = 0.1) -> FrontObservation:
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


class GeometrySpeedTests(unittest.TestCase):
    def test_non_radial_rectangle_expansion_recovers_local_speed(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 20, 10),))
        current = observation(60.0, (rectangle(-2, -2, 22, 12),))
        result = estimate_geometry_speeds(
            [previous, current],
            GeometrySpeedConfig(sample_spacing_m=1.0, max_normal_distance_m=10.0),
        )
        summary = summarize_geometry_speeds(result)
        observable = [item.speed_m_min for item in result.estimates if item.observable]
        self.assertGreater(summary["observable_ratio"], 0.8)
        self.assertAlmostEqual(2.0, float(np.median(observable)), delta=0.15)
        self.assertEqual("estimated", summary["speed_status"])

    def test_sub_error_motion_abstains(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 20, 10),), error_m=1.0)
        current = observation(60.0, (rectangle(-0.2, -0.2, 20.2, 10.2),), error_m=1.0)
        result = estimate_geometry_speeds([previous, current])
        summary = summarize_geometry_speeds(result)
        self.assertEqual("abstained", summary["speed_status"])
        self.assertEqual(0, summary["num_observable"])

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
        self.assertIn("normal_intersection_inconsistent_with_nearest_boundary", reasons)

    def test_new_ignition_is_unmatched_not_forced(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10),))
        current = observation(
            60.0,
            (rectangle(-2, -2, 12, 12), rectangle(500, 500, 510, 510)),
        )
        result = estimate_geometry_speeds([previous, current])
        self.assertEqual(1, result.matched_component_pairs)
        self.assertEqual(1, result.unmatched_current_components)

    def test_component_matching_is_one_to_one(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10), rectangle(100, 100, 110, 110)))
        current = observation(60.0, (rectangle(-1, -1, 11, 11), rectangle(101, 101, 111, 111)))
        matches, missing_previous, missing_current = match_components(previous, current, GeometrySpeedConfig())
        self.assertEqual(2, len(matches))
        self.assertFalse(missing_previous)
        self.assertFalse(missing_current)

    def test_non_metric_crs_abstains_at_pair_level(self) -> None:
        previous = observation(0.0, (rectangle(0, 0, 10, 10),))
        current = observation(60.0, (rectangle(-1, -1, 11, 11),))
        current = FrontObservation(**{**current.__dict__, "coordinate_system": "geographic"})
        result = estimate_geometry_speeds([previous, current])
        self.assertEqual(0, len(result.estimates))
        self.assertIn("geometry speed requires projected metric coordinates", result.pair_abstentions)

    def test_resampling_and_orientation_are_stable(self) -> None:
        ring = rectangle(0, 0, 20, 10)
        sampled = resample_closed_component(ring, 2.0)
        self.assertGreater(len(sampled), 10)
        self.assertGreater(signed_area(ring), 0)


if __name__ == "__main__":
    unittest.main()
