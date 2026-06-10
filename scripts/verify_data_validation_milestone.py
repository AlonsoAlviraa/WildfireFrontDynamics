"""Verify that a dataset candidate satisfies the data-validation milestone."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    evidence: str


PIPELINE_ARTIFACTS = (
    "ingest_manifest.csv",
    "observations_manifest.csv",
    "fronts.geojson",
    "arrival_time.csv",
    "local_speeds.csv",
    "summary.json",
)


def _matching_files(directory: Path, suffix: str = ".tif") -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.iterdir() if path.suffix.lower() == suffix)


def _nonempty_files(directory: Path, suffix: str = ".tif") -> bool:
    return bool(_matching_files(directory, suffix))


def _read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def verify_milestone(
    *,
    dataset_dir: Path,
    audit_dir: Path,
    pipeline_dir: Path,
    audit_doc: Path,
) -> list[CheckResult]:
    audit = _read_json(audit_dir / "candidate_audit.json")
    pipeline_summary = _read_json(pipeline_dir / "summary.json")
    metrics = pipeline_summary.get("metrics", {}) if isinstance(pipeline_summary.get("metrics"), dict) else {}
    images = _matching_files(dataset_dir / "images")
    masks = _matching_files(dataset_dir / "masks")
    annotations = _matching_files(dataset_dir / "annotations")
    has_annotations = bool(annotations)
    has_reference_metrics = bool(audit.get("front_distance_metrics_available"))
    speed_status = str(metrics.get("speed_status", ""))
    non_increasing = audit.get("non_increasing_timestamp_count")
    observation_count = int(audit.get("observation_count") or 0)
    accepted_inputs = int(audit.get("accepted_inputs") or 0)
    coordinate_ready = audit.get("classification") == "ready_for_dynamics"
    artifact_paths = [pipeline_dir / name for name in PIPELINE_ARTIFACTS]
    audit_doc_text = audit_doc.read_text(encoding="utf-8") if audit_doc.exists() else ""

    checks = [
        CheckResult(
            "candidate_readme",
            (dataset_dir / "README.md").exists(),
            str(dataset_dir / "README.md"),
        ),
        CheckResult(
            "candidate_images",
            len(images) >= 3,
            f"{len(images)} GeoTIFF images in {dataset_dir / 'images'}",
        ),
        CheckResult(
            "candidate_masks",
            len(masks) == len(images) and len(masks) >= 3,
            f"{len(masks)} masks for {len(images)} images",
        ),
        CheckResult(
            "candidate_timestamp_window",
            3 <= observation_count <= 10,
            f"observation_count={observation_count}",
        ),
        CheckResult(
            "accepted_input_count",
            accepted_inputs == observation_count and accepted_inputs >= 3,
            f"accepted_inputs={accepted_inputs}, observation_count={observation_count}",
        ),
        CheckResult(
            "audit_json",
            bool(audit),
            str(audit_dir / "candidate_audit.json"),
        ),
        CheckResult(
            "pipeline_artifacts",
            all(path.exists() and path.stat().st_size > 0 for path in artifact_paths),
            ", ".join(str(path) for path in artifact_paths),
        ),
        CheckResult(
            "annotation_count",
            not has_annotations or len(annotations) >= 2,
            f"{len(annotations)} annotation masks",
        ),
        CheckResult(
            "annotation_pairing",
            not has_annotations or len(annotations) == len(images),
            f"{len(annotations)} annotations for {len(images)} images",
        ),
        CheckResult(
            "reference_metric_policy",
            (has_annotations and has_reference_metrics) or (not has_annotations and not has_reference_metrics),
            "reference metrics only appear when annotations exist",
        ),
        CheckResult(
            "speed_policy",
            speed_status != "estimated" or (coordinate_ready and non_increasing == 0),
            f"speed_status={speed_status}, classification={audit.get('classification')}, non_increasing={non_increasing}",
        ),
        CheckResult(
            "scientific_separation",
            "ground_truth" not in str(audit.get("sensor_id", "")) and bool(audit.get("annotations", "") or not has_reference_metrics),
            "observed masks and independent annotations are separate inputs",
        ),
        CheckResult(
            "audit_markdown",
            audit_doc.exists() and str(audit.get("classification", "")) in audit_doc_text,
            str(audit_doc),
        ),
        CheckResult(
            "next_action",
            bool(audit.get("next_action")),
            str(audit.get("next_action", "")),
        ),
    ]
    return checks


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the data-validation milestone for one candidate.")
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--pipeline-dir", type=Path, required=True)
    parser.add_argument("--audit-doc", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    checks = verify_milestone(
        dataset_dir=args.dataset_dir,
        audit_dir=args.audit_dir,
        pipeline_dir=args.pipeline_dir,
        audit_doc=args.audit_doc,
    )
    payload = {
        "passed": all(check.passed for check in checks),
        "checks": [check.__dict__ for check in checks],
    }
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    if not payload["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
