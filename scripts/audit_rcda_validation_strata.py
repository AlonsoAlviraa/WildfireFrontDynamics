#!/usr/bin/env python3
"""Audit a VAL-only RCDA candidate across event duration and growth strata."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_rcda_paper_tuning import validate_tuning_report  # noqa: E402


def audit_validation_strata(
    *,
    tuning_summary_path: Path,
    val_manifest_path: Path,
    dataset_root: Path,
    run_name: str,
    output_path: Path,
) -> dict[str, Any]:
    summary = json.loads(Path(tuning_summary_path).read_text(encoding="utf-8"))
    if summary.get("selection_split") != "val" or summary.get("test_evaluated") is not False:
        raise ValueError("strata audit requires a VAL-only tuning summary")
    matches = [
        report
        for report in summary.get("reports") or []
        if report["config"]["run_name"] == run_name
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one report for {run_name!r}")
    report = matches[0]
    validate_tuning_report(report)
    per_event = report["val"]["selected"]["per_event"]
    manifest = json.loads(Path(val_manifest_path).read_text(encoding="utf-8"))
    if manifest.get("split") != "val":
        raise ValueError("strata audit manifest is not VAL")
    durations = Counter(str(row["uid"]) for row in manifest["samples"])
    growth_support: dict[str, int] = defaultdict(int)
    dataset_root = Path(dataset_root)
    for row in manifest["samples"]:
        inputs = np.load(dataset_root / row["input"], mmap_mode="r", allow_pickle=False)
        label = np.load(dataset_root / row["label"], mmap_mode="r", allow_pickle=False)
        growth_support[str(row["uid"])] += int(
            np.logical_and(np.asarray(label) > 0.5, np.asarray(inputs[0]) <= 0.5).sum()
        )
    events = sorted(set(per_event).intersection(durations, growth_support))
    if len(events) != len(per_event):
        raise ValueError("candidate metrics and VAL manifest event sets differ")
    iou = np.asarray([float(per_event[event]["iou"]) for event in events])
    days = np.asarray([float(durations[event]) for event in events])
    growth = np.asarray([float(growth_support[event]) for event in events])

    def stratum(label: str, mask: np.ndarray) -> dict[str, Any]:
        return {
            "label": label,
            "events": int(mask.sum()),
            "event_macro_iou": float(iou[mask].mean()),
            "event_median_iou": float(np.median(iou[mask])),
            "mean_growth_pixels": float(growth[mask].mean()),
        }

    duration_rows = [
        stratum("1-2d", days <= 2),
        stratum("3-5d", (days >= 3) & (days <= 5)),
        stratum("6-13d", (days >= 6) & (days <= 13)),
        stratum("14+d", days >= 14),
    ]
    quartiles = np.quantile(growth, [0.25, 0.5, 0.75])
    growth_rows = []
    for index, (low, high) in enumerate(
        zip([-1.0, *quartiles], [*quartiles, float("inf")], strict=True),
        start=1,
    ):
        growth_rows.append(stratum(f"Q{index}", (growth > low) & (growth <= high)))
    duration_rho, duration_p = spearmanr(days, iou)
    growth_rho, growth_p = spearmanr(np.log1p(growth), iou)
    result = {
        "schema": "wfd_rcda_val_strata_audit_v1",
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "run_name": run_name,
        "events": len(events),
        "selected_threshold": float(report["selected_threshold"]),
        "duration_spearman": {"rho": float(duration_rho), "p_value": float(duration_p)},
        "growth_support_spearman": {"rho": float(growth_rho), "p_value": float(growth_p)},
        "duration_strata": duration_rows,
        "growth_pixel_quartile_edges": [float(value) for value in quartiles],
        "growth_strata": growth_rows,
        "interpretation": (
            "Descriptive VAL-only subgroup audit. It does not establish subgroup causality "
            "and cannot replace final event-level TEST uncertainty."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tuning-summary", type=Path, required=True)
    parser.add_argument("--val-manifest", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_validation_strata(
        tuning_summary_path=args.tuning_summary,
        val_manifest_path=args.val_manifest,
        dataset_root=args.dataset_root,
        run_name=args.run_name,
        output_path=args.output,
    )
    print(json.dumps({"run_name": result["run_name"], "events": result["events"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
