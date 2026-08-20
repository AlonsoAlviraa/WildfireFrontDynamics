#!/usr/bin/env python3
"""Compare two single-seed WFIGS source adaptations on VAL by regime."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import write_json  # noqa: E402
from wildfire_front.open_if.regional.base import utc_now  # noqa: E402


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _single_seed(report: dict[str, Any], seed: int) -> dict[str, Any]:
    rows = [
        row
        for row in report.get("reports") or []
        if int((row.get("config") or {}).get("seed")) == seed
    ]
    if not (
        report.get("test_used_for_selection") is False
        and report.get("wfigs_test_loaded") is False
        and len(rows) == 1
        and rows[0].get("threshold_selected_on") == "wfigs_validation"
        and rows[0].get("test_evaluated") is False
    ):
        raise ValueError(f"seed {seed} is not an isolated WFIGS VAL report")
    return rows[0]


def _aggregate(delta: np.ndarray) -> dict[str, Any]:
    return {
        "events": int(delta.size),
        "mean_delta": float(delta.mean()),
        "median_delta": float(np.median(delta)),
        "candidate_win_fraction": float((delta > 0).mean()),
        "tie_fraction": float((delta == 0).mean()),
    }


def compare_pilot_sources(
    candidate_path: Path,
    reference_path: Path,
    validation_manifest_path: Path,
    *,
    candidate_seed: int,
    reference_seed: int,
    bootstrap_resamples: int = 100_000,
    bootstrap_seed: int = 20260820,
) -> dict[str, Any]:
    candidate = _single_seed(_read(candidate_path), candidate_seed)
    reference = _single_seed(_read(reference_path), reference_seed)
    candidate_selected = candidate["validation"]["selected"]
    reference_selected = reference["validation"]["selected"]
    candidate_events = {
        str(event): float(row["iou"])
        for event, row in candidate_selected["per_event"].items()
    }
    reference_events = {
        str(event): float(row["iou"])
        for event, row in reference_selected["per_event"].items()
    }
    manifest = _read(validation_manifest_path)
    if manifest.get("split") != "validation":
        raise ValueError("comparison manifest is not WFIGS validation")
    samples = manifest.get("samples") or []
    metadata = {str(row["event_id"]): row for row in samples}
    if not candidate_events or set(candidate_events) != set(reference_events) or set(
        candidate_events
    ) != set(metadata):
        raise ValueError("source candidates do not use the same validation fires")
    events = sorted(candidate_events)
    delta = np.asarray(
        [candidate_events[event] - reference_events[event] for event in events],
        dtype=np.float64,
    )
    rng = np.random.default_rng(bootstrap_seed)
    draws = rng.integers(0, len(events), size=(bootstrap_resamples, len(events)))
    bootstrap = delta[draws].mean(axis=1)
    horizons = []
    for lower, upper, label in (
        (6.0, 12.0, "6-12h"),
        (12.0, 24.0, "12-24h"),
        (24.0, 48.000001, "24-48h"),
    ):
        values = np.asarray(
            [
                candidate_events[event] - reference_events[event]
                for event in events
                if lower <= float(metadata[event]["horizon_hours"]) < upper
            ]
        )
        horizons.append({"bin": label, **_aggregate(values)})
    growth_burden = {
        event: float(metadata[event]["growth_pixels"])
        / max(float(metadata[event]["extent_pixels"]), 1.0)
        for event in events
    }
    cutoffs = np.quantile(list(growth_burden.values()), [1 / 3, 2 / 3])
    growth_tertiles = []
    for index, (lower, upper) in enumerate(
        ((-np.inf, cutoffs[0]), (cutoffs[0], cutoffs[1]), (cutoffs[1], np.inf)),
        start=1,
    ):
        values = np.asarray(
            [
                candidate_events[event] - reference_events[event]
                for event in events
                if lower < growth_burden[event] <= upper
            ]
        )
        growth_tertiles.append({"tertile": index, **_aggregate(values)})
    candidate_vector = np.asarray([candidate_events[event] for event in events])
    reference_vector = np.asarray([reference_events[event] for event in events])
    return {
        "schema": "wfd_wfigs_source_pilot_comparison_v1",
        "generated_at": utc_now(),
        "selection_split": "wfigs_validation",
        "test_evaluated": False,
        "candidate": {
            "seed": candidate_seed,
            "event_macro_iou": float(candidate_selected["event_macro_iou"]),
        },
        "reference": {
            "seed": reference_seed,
            "event_macro_iou": float(reference_selected["event_macro_iou"]),
        },
        "paired": {
            **_aggregate(delta),
            "event_bootstrap_95_ci": np.quantile(
                bootstrap, [0.025, 0.975]
            ).tolist(),
            "bootstrap_resamples": bootstrap_resamples,
            "bootstrap_seed": bootstrap_seed,
            "per_event_pearson_r": float(
                np.corrcoef(candidate_vector, reference_vector)[0, 1]
            ),
        },
        "by_horizon": horizons,
        "by_growth_burden_tertile": growth_tertiles,
        "claims": {
            "aggregate_only": True,
            "event_identifiers_exposed": False,
            "formal_source_selection_requires_multi_seed_ensemble": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("validation_manifest", type=Path)
    parser.add_argument("--candidate-seed", type=int, required=True)
    parser.add_argument("--reference-seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare_pilot_sources(
        args.candidate,
        args.reference,
        args.validation_manifest,
        candidate_seed=args.candidate_seed,
        reference_seed=args.reference_seed,
    )
    write_json(args.output, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
