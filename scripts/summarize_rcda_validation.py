#!/usr/bin/env python3
"""Build a VAL-only, paired event-bootstrap scorecard for RCDA model selection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np


def _bootstrap_mean_ci(
    values: np.ndarray,
    *,
    n_resamples: int,
    rng: np.random.Generator,
) -> list[float]:
    means = np.empty(n_resamples, dtype=np.float64)
    for start in range(0, n_resamples, 500):
        count = min(500, n_resamples - start)
        indices = rng.integers(0, values.size, size=(count, values.size))
        means[start : start + count] = values[indices].mean(axis=1)
    return [float(value) for value in np.quantile(means, [0.025, 0.975])]


def build_validation_scorecard(
    summary_paths: list[Path],
    output_path: Path,
    *,
    n_resamples: int = 10_000,
    seed: int = 20260819,
) -> dict[str, Any]:
    """Summarize candidate uncertainty while enforcing that TEST stayed sealed."""

    reports: list[dict[str, Any]] = []
    sources: list[str] = []
    for path in summary_paths:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
        if (
            document.get("schema") != "wfd_rcda_paper_tune_v1"
            or document.get("selection_split") != "val"
            or document.get("test_evaluated") is not False
        ):
            raise ValueError(f"non-VAL tuning summary: {path}")
        for report in document.get("reports") or []:
            if (
                report.get("threshold_selected_on") != "val"
                or report.get("test_used_for_selection") is not False
                or report.get("test_evaluated") is not False
                or "test_once" in report
            ):
                raise ValueError("a tuning report violates TEST isolation")
            reports.append(report)
        sources.append(str(path))
    if len(reports) < 2:
        raise ValueError("validation scorecard requires at least two candidates")

    by_name = {str(report["config"]["run_name"]): report for report in reports}
    if len(by_name) != len(reports):
        raise ValueError("candidate run names are not unique")
    event_sets = [set(report["val"]["selected"]["per_event"]) for report in reports]
    if not event_sets[0] or any(events != event_sets[0] for events in event_sets[1:]):
        raise ValueError("validation candidates do not share the same event set")
    events = sorted(event_sets[0])
    values = {
        name: np.asarray(
            [float(report["val"]["selected"]["per_event"][event]["iou"]) for event in events],
            dtype=np.float64,
        )
        for name, report in by_name.items()
    }
    leader_name = max(values, key=lambda name: float(values[name].mean()))
    leader = values[leader_name]
    rng = np.random.default_rng(seed)
    rows = []
    for name, event_iou in values.items():
        delta = leader - event_iou
        rows.append(
            {
                "run_name": name,
                "event_macro_iou": float(event_iou.mean()),
                "event_median_iou": float(np.median(event_iou)),
                "event_bootstrap_95_ci": _bootstrap_mean_ci(
                    event_iou, n_resamples=n_resamples, rng=rng
                ),
                "leader_minus_candidate_paired_delta": float(delta.mean()),
                "leader_minus_candidate_bootstrap_95_ci": _bootstrap_mean_ci(
                    delta, n_resamples=n_resamples, rng=rng
                ),
                "leader_wins_event_fraction": float((delta > 0).mean()),
                "selected_threshold": float(by_name[name]["selected_threshold"]),
                "best_epoch": int(by_name[name]["best_epoch"]),
            }
        )
    rows.sort(key=lambda row: float(row["event_macro_iou"]), reverse=True)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
    result = {
        "schema": "wfd_rcda_validation_scorecard_v1",
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "uncertainty_unit": "fire_event",
        "bootstrap_resamples": n_resamples,
        "bootstrap_seed": seed,
        "events": len(events),
        "leader": leader_name,
        "ranking": rows,
        "sources": sources,
        "interpretation": (
            "Selection evidence only. Confidence intervals are descriptive after comparing "
            "multiple VAL candidates and are not final TEST uncertainty."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summaries", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=10_000)
    args = parser.parse_args()
    result = build_validation_scorecard(
        args.summaries,
        args.output,
        n_resamples=args.resamples,
    )
    print(json.dumps({"leader": result["leader"], "events": result["events"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
