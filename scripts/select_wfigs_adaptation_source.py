#!/usr/bin/env python3
"""Freeze the best multi-seed WFIGS adaptation source using VAL only."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import utc_now, write_json  # noqa: E402

SCHEMA = "wfd_wfigs_adaptation_source_freeze_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _candidate(name: str, path: Path) -> tuple[dict[str, Any], dict[str, float]]:
    report = json.loads(path.read_text(encoding="utf-8"))
    ensemble = report.get("ensemble") or {}
    selected = (ensemble.get("validation") or {}).get("selected") or {}
    per_event = {
        str(event): float(row["iou"])
        for event, row in (selected.get("per_event") or {}).items()
    }
    if not (
        report.get("test_used_for_selection") is False
        and report.get("wfigs_test_loaded") is False
        and len(report.get("reports") or []) >= 3
        and ensemble.get("threshold_selected_on") == "wfigs_validation"
        and ensemble.get("test_used_for_selection") is False
        and ensemble.get("test_evaluated") is False
        and per_event
    ):
        raise ValueError(f"candidate {name} is not an isolated multi-seed VAL report")
    score = float(np.mean(list(per_event.values())))
    reported_score = selected.get("event_macro_iou")
    if reported_score is not None and not np.isclose(score, float(reported_score)):
        raise ValueError(f"candidate {name} VAL macro disagrees with per-event rows")
    row = {
        "name": name,
        "val_event_macro_iou": score,
        "selected_threshold": ensemble.get("selected_threshold"),
        "members": ensemble.get("members"),
        "train_events": (report.get("counts") or {}).get("train_events"),
        "validation_events": (report.get("counts") or {}).get("validation_events"),
        "summary": str(path.resolve()),
        "summary_sha256": _sha256(path),
        "selection_split": "wfigs_validation",
        "test_evaluated": False,
    }
    return row, per_event


def freeze_wfigs_source(
    candidates: dict[str, Path],
    *,
    bootstrap_resamples: int = 10_000,
    bootstrap_seed: int = 20260825,
) -> dict[str, Any]:
    if len(candidates) < 2:
        raise ValueError("source selection requires at least two candidates")
    rows: list[dict[str, Any]] = []
    per_event_by_name: dict[str, dict[str, float]] = {}
    for name, path in candidates.items():
        row, per_event = _candidate(name, path)
        rows.append(row)
        per_event_by_name[name] = per_event
    cohorts = [set(values) for values in per_event_by_name.values()]
    if any(cohort != cohorts[0] for cohort in cohorts[1:]):
        raise ValueError("WFIGS adaptation candidates use different VAL events")
    train_counts = {row["train_events"] for row in rows}
    val_counts = {row["validation_events"] for row in rows}
    if len(train_counts) != 1 or len(val_counts) != 1:
        raise ValueError("WFIGS adaptation candidates use different dataset counts")
    rows.sort(key=lambda row: float(row["val_event_macro_iou"]), reverse=True)
    winner = rows[0]
    events = sorted(cohorts[0])
    winner_values = np.asarray(
        [per_event_by_name[winner["name"]][event] for event in events],
        dtype=np.float64,
    )
    rng = np.random.default_rng(bootstrap_seed)
    comparisons = []
    for candidate in rows[1:]:
        candidate_values = np.asarray(
            [per_event_by_name[candidate["name"]][event] for event in events],
            dtype=np.float64,
        )
        delta = winner_values - candidate_values
        draws = rng.integers(0, len(events), size=(bootstrap_resamples, len(events)))
        boot = delta[draws].mean(axis=1)
        comparisons.append(
            {
                "candidate": candidate["name"],
                "winner_minus_candidate_paired_delta": float(delta.mean()),
                "paired_event_bootstrap_95_ci": np.quantile(
                    boot, [0.025, 0.975]
                ).tolist(),
                "winner_wins_event_fraction": float((delta > 0).mean()),
                "events": len(events),
            }
        )
    return {
        "schema": SCHEMA,
        "frozen_at": utc_now(),
        "selection_split": "wfigs_validation",
        "test_used_for_selection": False,
        "prospective_test_evaluated": False,
        "winner": winner,
        "ranking": rows,
        "paired_comparisons": comparisons,
        "bootstrap_resamples": bootstrap_resamples,
        "bootstrap_seed": bootstrap_seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidates: dict[str, Path] = {}
    for value in args.candidate:
        name, separator, raw_path = value.partition("=")
        if not separator or not name or not raw_path:
            raise ValueError("--candidate must use NAME=PATH")
        candidates[name] = Path(raw_path)
    frozen = freeze_wfigs_source(candidates)
    write_json(args.output, frozen)
    print(json.dumps(frozen, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
