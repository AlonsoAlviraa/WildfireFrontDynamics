from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_data_validation_sprint import DEFAULT_DATASET_ID, build_parser
from scripts.verify_data_validation_milestone import verify_milestone


def write(path: Path, text: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def populate_candidate(dataset: Path, *, frames: int = 3, annotations: bool = True) -> None:
    write(dataset / "README.md")
    for index in range(frames):
        write(dataset / "images" / f"{index}.tif")
        write(dataset / "masks" / f"{index}.tif")
        if annotations:
            write(dataset / "annotations" / f"{index}.tif")


def populate_pipeline(pipeline: Path) -> None:
    for name in (
        "ingest_manifest.csv",
        "observations_manifest.csv",
        "fronts.geojson",
        "arrival_time.csv",
        "local_speeds.csv",
    ):
        write(pipeline / name)
    write(pipeline / "summary.json", json.dumps({"metrics": {"speed_status": "estimated"}}))


class DataValidationMilestoneTests(unittest.TestCase):
    def test_sprint_parser_defaults_to_semireal_candidate(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual(DEFAULT_DATASET_ID, args.dataset_id)
        self.assertFalse(args.skip_tests)

    def test_complete_candidate_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "data"
            audit = root / "audit"
            pipeline = root / "pipeline"
            doc = root / "docs" / "audit.md"
            populate_candidate(dataset, frames=3)
            write(
                audit / "candidate_audit.json",
                json.dumps(
                    {
                        "classification": "ready_for_dynamics",
                        "front_distance_metrics_available": True,
                        "non_increasing_timestamp_count": 0,
                        "annotations": "annotations",
                        "sensor_id": "thermal",
                        "observation_count": 3,
                        "accepted_inputs": 3,
                        "next_action": "continue",
                    }
                ),
            )
            populate_pipeline(pipeline)
            write(doc, "ready_for_dynamics")

            checks = verify_milestone(
                dataset_dir=dataset,
                audit_dir=audit,
                pipeline_dir=pipeline,
                audit_doc=doc,
            )
        self.assertTrue(all(check.passed for check in checks))

    def test_reference_metrics_without_annotations_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "data"
            audit = root / "audit"
            pipeline = root / "pipeline"
            doc = root / "docs" / "audit.md"
            populate_candidate(dataset, frames=3, annotations=False)
            write(
                audit / "candidate_audit.json",
                json.dumps(
                    {
                        "classification": "segmentation_only",
                        "front_distance_metrics_available": True,
                        "non_increasing_timestamp_count": 0,
                        "sensor_id": "thermal",
                        "observation_count": 3,
                        "accepted_inputs": 3,
                        "next_action": "continue",
                    }
                ),
            )
            populate_pipeline(pipeline)
            write(pipeline / "summary.json", json.dumps({"metrics": {"speed_status": "abstained"}}))
            write(doc, "segmentation_only")

            checks = verify_milestone(
                dataset_dir=dataset,
                audit_dir=audit,
                pipeline_dir=pipeline,
                audit_doc=doc,
            )
        failed = {check.name for check in checks if not check.passed}
        self.assertIn("reference_metric_policy", failed)

    def test_too_few_observations_fail_timestamp_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            dataset = root / "data"
            audit = root / "audit"
            pipeline = root / "pipeline"
            doc = root / "docs" / "audit.md"
            populate_candidate(dataset, frames=2)
            write(
                audit / "candidate_audit.json",
                json.dumps(
                    {
                        "classification": "ready_for_dynamics",
                        "front_distance_metrics_available": True,
                        "non_increasing_timestamp_count": 0,
                        "annotations": "annotations",
                        "sensor_id": "thermal",
                        "observation_count": 2,
                        "accepted_inputs": 2,
                        "next_action": "continue",
                    }
                ),
            )
            populate_pipeline(pipeline)
            write(doc, "ready_for_dynamics")

            checks = verify_milestone(
                dataset_dir=dataset,
                audit_dir=audit,
                pipeline_dir=pipeline,
                audit_doc=doc,
            )
        failed = {check.name for check in checks if not check.passed}
        self.assertIn("candidate_timestamp_window", failed)


if __name__ == "__main__":
    unittest.main()
