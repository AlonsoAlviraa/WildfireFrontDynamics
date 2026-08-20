#!/usr/bin/env python3
"""Aggregate fixed-seed RCDA VAL replications without reading TEST."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import (  # noqa: E402
    utc_now,
    validate_single_run_val_summary,
    write_json,
)

SCHEMA = "wfd_rcda_val_replication_summary_v1"


def _local_checkpoint(summary_path: Path, report: dict[str, Any]) -> Path:
    checkpoint = Path(str(report.get("checkpoint") or ""))
    if checkpoint.is_file():
        return checkpoint.resolve()
    downloaded = summary_path.parent / checkpoint.name
    if downloaded.is_file():
        return downloaded.resolve()
    raise FileNotFoundError(f"replication checkpoint is missing: {checkpoint.name}")


def summarize_replications(
    summary_paths: list[Path],
    *,
    run_name: str,
    expected_seeds: tuple[int, ...],
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260824,
) -> dict[str, Any]:
    if len(summary_paths) != len(expected_seeds):
        raise ValueError("one validation summary is required for every expected seed")
    reports: list[dict[str, Any]] = []
    per_event_by_seed: list[dict[str, float]] = []
    observed_seeds: list[int] = []
    canonical_config: dict[str, Any] | None = None
    for summary_path in summary_paths:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        validate_single_run_val_summary(summary, run_name)
        matching = [
            row
            for row in summary.get("reports") or []
            if str((row.get("config") or {}).get("run_name")) == run_name
        ]
        if len(matching) != 1:
            raise ValueError("replication summary must contain exactly one report")
        source = matching[0]
        config = dict(source.get("config") or {})
        seed = int(config.get("seed"))
        observed_seeds.append(seed)
        config_without_seed = {key: value for key, value in config.items() if key != "seed"}
        if canonical_config is None:
            canonical_config = config_without_seed
        elif config_without_seed != canonical_config:
            raise ValueError("replication configurations differ beyond the seed")
        selected = (source.get("val") or {}).get("selected") or {}
        per_event = {
            str(event): float(row["iou"])
            for event, row in (selected.get("per_event") or {}).items()
        }
        if not per_event:
            raise ValueError("replication report is missing per-event VAL metrics")
        reported_macro = selected.get("event_macro_iou")
        if reported_macro is not None and not np.isclose(
            float(reported_macro), statistics.mean(per_event.values())
        ):
            raise ValueError("replication event macro disagrees with per-event VAL rows")
        per_event_by_seed.append(per_event)
        localized = dict(source)
        localized["local_checkpoint"] = str(_local_checkpoint(summary_path, source))
        localized["threshold_selected_on"] = "val"
        localized["test_used_for_selection"] = False
        localized["test_evaluated"] = False
        reports.append(localized)
    if tuple(observed_seeds) != expected_seeds or len(set(observed_seeds)) != len(
        observed_seeds
    ):
        raise ValueError("replication seeds differ from the registered order")
    event_sets = [set(row) for row in per_event_by_seed]
    if any(events != event_sets[0] for events in event_sets[1:]):
        raise ValueError("replication VAL event cohorts differ")
    events = sorted(event_sets[0])
    matrix = np.asarray(
        [[row[event] for event in events] for row in per_event_by_seed],
        dtype=np.float64,
    )
    event_seed_mean = matrix.mean(axis=0)
    rng = np.random.default_rng(bootstrap_seed)
    draws = rng.integers(0, len(events), size=(bootstrap_resamples, len(events)))
    bootstrap = event_seed_mean[draws].mean(axis=1)
    seed_scores = matrix.mean(axis=1).tolist()
    return {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "run_name": run_name,
        "seeds": observed_seeds,
        "selection_split": "val",
        "test_used_for_selection": False,
        "test_evaluated": False,
        "counts": {"seeds": len(observed_seeds), "validation_events": len(events)},
        "validation": {
            "event_macro_iou_seed_mean": float(event_seed_mean.mean()),
            "event_macro_iou_by_seed": seed_scores,
            "sample_std_across_seeds": statistics.stdev(seed_scores),
            "event_bootstrap_95_ci": np.quantile(
                bootstrap, [0.025, 0.975]
            ).tolist(),
            "uncertainty_unit": "fire_event",
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": bootstrap_seed,
        },
        "reports": reports,
        "claims": {
            "validation_replicated_across_registered_seeds": True,
            "historical_test_sealing_restored": False,
            "ready_as_test_free_wfigs_adaptation_source": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path, nargs="+")
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = summarize_replications(
        args.summary,
        run_name=args.run_name,
        expected_seeds=tuple(args.seed or [11, 29, 47]),
    )
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
