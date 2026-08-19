#!/usr/bin/env python3
"""Compare two sealed VAL-only RCDA reruns without opening TEST."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import (  # noqa: E402
    validate_single_run_val_summary,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_report(summary: dict[str, Any], run_name: str) -> dict[str, Any]:
    validate_single_run_val_summary(summary, run_name)
    matches = [
        report
        for report in summary["reports"]
        if report.get("config", {}).get("run_name") == run_name
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one report for {run_name!r}")
    return matches[0]


def compare_reproducibility(
    first_summary_path: Path,
    rerun_summary_path: Path,
    first_checkpoint_path: Path,
    rerun_checkpoint_path: Path,
    *,
    run_name: str,
) -> dict[str, Any]:
    first_summary = json.loads(Path(first_summary_path).read_text(encoding="utf-8"))
    rerun_summary = json.loads(Path(rerun_summary_path).read_text(encoding="utf-8"))
    first_report = _run_report(first_summary, run_name)
    rerun_report = _run_report(rerun_summary, run_name)
    first_selected = first_report["val"]["selected"]
    rerun_selected = rerun_report["val"]["selected"]
    first_events = first_selected["per_event"]
    rerun_events = rerun_selected["per_event"]
    if set(first_events) != set(rerun_events):
        raise ValueError("reruns do not contain identical VAL event ids")
    event_differences = {
        event_id: abs(
            float(first_events[event_id]["iou"])
            - float(rerun_events[event_id]["iou"])
        )
        for event_id in first_events
    }
    first_checkpoint_sha = sha256_file(first_checkpoint_path)
    rerun_checkpoint_sha = sha256_file(rerun_checkpoint_path)
    event_macro_difference = abs(
        float(first_selected["event_macro_iou"])
        - float(rerun_selected["event_macro_iou"])
    )
    threshold_difference = abs(
        float(first_selected["threshold"]) - float(rerun_selected["threshold"])
    )
    max_event_difference = max(event_differences.values(), default=0.0)
    checkpoint_exact = first_checkpoint_sha == rerun_checkpoint_sha
    metrics_exact = (
        event_macro_difference == 0.0
        and threshold_difference == 0.0
        and max_event_difference == 0.0
    )
    return {
        "schema": "wfd_rcda_val_reproducibility_v1",
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "run_name": run_name,
        "events": len(first_events),
        "checkpoint_exact": checkpoint_exact,
        "checkpoint_sha256": {
            "first": first_checkpoint_sha,
            "rerun": rerun_checkpoint_sha,
        },
        "summary_sha256": {
            "first": sha256_file(first_summary_path),
            "rerun": sha256_file(rerun_summary_path),
        },
        "summary_exact": sha256_file(first_summary_path)
        == sha256_file(rerun_summary_path),
        "event_macro_iou": {
            "first": float(first_selected["event_macro_iou"]),
            "rerun": float(rerun_selected["event_macro_iou"]),
            "absolute_difference": event_macro_difference,
        },
        "threshold": {
            "first": float(first_selected["threshold"]),
            "rerun": float(rerun_selected["threshold"]),
            "absolute_difference": threshold_difference,
        },
        "max_absolute_event_iou_difference": max_event_difference,
        "metrics_exact": metrics_exact,
        "reproducible": checkpoint_exact and metrics_exact,
        "interpretation": (
            "Checkpoint and all selected VAL metrics are exact across independent reruns; "
            "summary metadata may differ."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-summary", type=Path, required=True)
    parser.add_argument("--rerun-summary", type=Path, required=True)
    parser.add_argument("--first-checkpoint", type=Path, required=True)
    parser.add_argument("--rerun-checkpoint", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_reproducibility(
        args.first_summary,
        args.rerun_summary,
        args.first_checkpoint,
        args.rerun_checkpoint,
        run_name=args.run_name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
