from __future__ import annotations

import unittest

from wildfire_front.evaluation import front_distance_metrics
from wildfire_front.geometry_speed import local_turn_angles
from wildfire_front.models import FrontObservation
from wildfire_front.quality import summarize_observation_quality


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float):
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
        (min_x, min_y),
    )


class EvaluationQualityTests(unittest.TestCase):
    def test_identical_front_has_zero_distance(self) -> None:
        metrics = front_distance_metrics(rectangle(0, 0, 10, 10), rectangle(0, 0, 10, 10))
        self.assertAlmostEqual(0.0, metrics["front_distance_mean"])
        self.assertAlmostEqual(0.0, metrics["front_hausdorff"])

    def test_shifted_front_distance_is_metric(self) -> None:
        metrics = front_distance_metrics(rectangle(0, 0, 10, 10), rectangle(2, 0, 12, 10), sample_spacing=0.5)
        self.assertGreater(metrics["front_distance_mean"], 0.0)
        self.assertAlmostEqual(2.0, metrics["front_hausdorff"], delta=0.05)

    def test_observation_quality_detects_area_decrease(self) -> None:
        common = {
            "event_id": "quality",
            "sensor_id": "thermal",
            "observed_at": "2026-06-10T12:00:00Z",
            "estimated_error_m": 1.0,
            "crs": "EPSG:32630",
            "coordinate_system": "projected_metric",
            "resolution_m": 1.0,
        }
        first = FrontObservation(observation_id="1", time_s=0, components=(rectangle(0, 0, 10, 10),), **common)
        second = FrontObservation(observation_id="2", time_s=60, components=(rectangle(0, 0, 8, 8),), **common)
        summary = summarize_observation_quality([first, second])
        self.assertEqual(1, summary["observed_area_decrease_count"])
        self.assertEqual(60.0, summary["interval_s_median"])

    def test_turn_angles_identify_rectangle_corners(self) -> None:
        import numpy as np

        points = np.asarray(rectangle(0, 0, 10, 10)[:-1], dtype=float)
        turns = local_turn_angles(points)
        self.assertTrue(all(abs(value - 90.0) < 1e-6 for value in turns))


if __name__ == "__main__":
    unittest.main()
