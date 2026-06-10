from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.audit_dataset_candidate import (
    classify_candidate,
    summarize_reference_metrics,
    write_markdown_audit,
)
from wildfire_front.models import FrontObservation


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float):
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
        (min_x, min_y),
    )


def observation(observation_id: str, observed_at: str, component) -> FrontObservation:
    return FrontObservation(
        observation_id=observation_id,
        event_id="audit",
        sensor_id="thermal",
        time_s=0.0,
        observed_at=observed_at,
        components=(component,),
        estimated_error_m=1.0,
        crs="EPSG:32630",
        coordinate_system="projected_metric",
        resolution_m=1.0,
    )


class DatasetCandidateAuditTests(unittest.TestCase):
    def test_projected_temporal_sequence_is_ready_for_dynamics(self) -> None:
        records = [
            {"status": "accepted", "coordinate_system": "projected_metric", "reason": ""},
            {"status": "accepted", "coordinate_system": "projected_metric", "reason": ""},
        ]
        self.assertEqual("ready_for_dynamics", classify_candidate(records, observation_count=2))

    def test_single_metric_observation_is_segmentation_only(self) -> None:
        records = [{"status": "accepted", "coordinate_system": "projected_metric", "reason": ""}]
        self.assertEqual("segmentation_only", classify_candidate(records, observation_count=1))

    def test_non_projected_candidate_is_segmentation_only(self) -> None:
        records = [{"status": "review", "coordinate_system": "geographic", "reason": "crs_not_projected_metric"}]
        self.assertEqual("segmentation_only", classify_candidate(records, observation_count=0))

    def test_unusable_candidate_is_rejected(self) -> None:
        records = [{"status": "rejected", "coordinate_system": "unknown", "reason": "empty_mask"}]
        self.assertEqual("rejected", classify_candidate(records, observation_count=0))

    def test_reference_metrics_match_by_timestamp(self) -> None:
        observed = [observation("obs", "2026-06-10T12:00:00Z", rectangle(0, 0, 10, 10))]
        references = [observation("ref", "2026-06-10T12:00:00Z", rectangle(1, 0, 11, 10))]
        summary = summarize_reference_metrics(observed, references, sample_spacing=1.0)
        self.assertTrue(summary["front_distance_metrics_available"])
        self.assertEqual(1, summary["front_reference_match_count"])
        self.assertAlmostEqual(1.0, summary["reference_front_hausdorff_m"], delta=0.01)

    def test_markdown_audit_records_reference_status(self) -> None:
        summary = {
            "event_id": "candidate",
            "classification": "ready_for_dynamics",
            "images": "images",
            "masks": "masks",
            "annotations": "annotations",
            "input_count": 2,
            "accepted_inputs": 2,
            "review_inputs": 0,
            "rejected_inputs": 0,
            "observation_count": 2,
            "interval_s_median": 60.0,
            "positive_pixel_fraction_median": 0.1,
            "front_distance_metrics_available": True,
            "independent_reference_count": 2,
            "front_reference_match_count": 2,
            "reference_front_distance_mean_m": 1.2,
            "reference_front_distance_p95_m": 2.3,
            "reference_front_hausdorff_m": 3.4,
            "next_action": "continue",
        }
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "audit.md"
            write_markdown_audit(summary, output)
            text = output.read_text(encoding="utf-8")
        self.assertIn("Auditoría de candidato: candidate", text)
        self.assertIn("Independent reference metrics are available", text)
        self.assertIn("Hausdorff front distance m", text)


if __name__ == "__main__":
    unittest.main()
