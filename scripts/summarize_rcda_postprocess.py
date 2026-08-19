#!/usr/bin/env python3
"""Build a paired VAL-only scorecard for a frozen spatial decoder."""

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

from scripts.analyze_rcda_paper_tuning import validate_tuning_report  # noqa: E402
from scripts.summarize_rcda_validation import _bootstrap_mean_ci  # noqa: E402


def build_postprocess_scorecard(
    tuning_summary_path: Path,
    postprocess_path: Path,
    output_path: Path,
    *,
    run_name: str,
    n_resamples: int = 10_000,
    seed: int = 20260819,
) -> dict[str, Any]:
    tuning = json.loads(Path(tuning_summary_path).read_text(encoding="utf-8"))
    postprocess = json.loads(Path(postprocess_path).read_text(encoding="utf-8"))
    if not (
        tuning.get("selection_split") == "val"
        and tuning.get("test_evaluated") is False
        and postprocess.get("selection_split") == "val"
        and postprocess.get("test_evaluated") is False
        and postprocess.get("test_used_for_selection") is False
    ):
        raise ValueError("paired postprocess scorecard requires VAL-only artifacts")
    matches = [
        report
        for report in tuning.get("reports") or []
        if report.get("config", {}).get("run_name") == run_name
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one tuning report for {run_name!r}")
    raw_report = matches[0]
    validate_tuning_report(raw_report)
    raw_events = raw_report["val"]["selected"]["per_event"]
    decoded_events = (postprocess.get("best") or {}).get("per_event") or {}
    if not raw_events or set(raw_events) != set(decoded_events):
        raise ValueError("raw and postprocessed event sets differ")
    events = sorted(raw_events)
    raw_iou = np.asarray([float(raw_events[event]["iou"]) for event in events])
    decoded_iou = np.asarray(
        [float(decoded_events[event]["iou"]) for event in events]
    )
    delta = decoded_iou - raw_iou
    rng = np.random.default_rng(seed)
    best = postprocess["best"]
    result = {
        "schema": "wfd_rcda_val_postprocess_scorecard_v1",
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "run_name": run_name,
        "events": len(events),
        "bootstrap_resamples": n_resamples,
        "bootstrap_seed": seed,
        "raw_event_macro_iou": float(raw_iou.mean()),
        "raw_event_bootstrap_95_ci": _bootstrap_mean_ci(
            raw_iou, n_resamples=n_resamples, rng=rng
        ),
        "decoded_event_macro_iou": float(decoded_iou.mean()),
        "decoded_event_bootstrap_95_ci": _bootstrap_mean_ci(
            decoded_iou, n_resamples=n_resamples, rng=rng
        ),
        "paired_delta": float(delta.mean()),
        "paired_delta_event_bootstrap_95_ci": _bootstrap_mean_ci(
            delta, n_resamples=n_resamples, rng=rng
        ),
        "decoded_wins_event_fraction": float((delta > 0).mean()),
        "decoded_ties_event_fraction": float((delta == 0).mean()),
        "decoder": {
            "threshold": best.get("threshold"),
            "dilation_radius_px": best.get("dilation_radius_px"),
            "require_t0_connection": best.get("require_t0_connection"),
        },
        "checkpoint_sha256": postprocess.get("checkpoint_sha256"),
        "sources": [str(tuning_summary_path), str(postprocess_path)],
        "interpretation": (
            "Descriptive paired uncertainty after decoder selection on VAL; "
            "not confirmatory TEST evidence."
        ),
    }
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tuning-summary", type=Path, required=True)
    parser.add_argument("--postprocess", type=Path, required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resamples", type=int, default=10_000)
    args = parser.parse_args()
    result = build_postprocess_scorecard(
        args.tuning_summary,
        args.postprocess,
        args.output,
        run_name=args.run_name,
        n_resamples=args.resamples,
    )
    print(
        json.dumps(
            {
                "events": result["events"],
                "paired_delta": result["paired_delta"],
                "paired_delta_event_bootstrap_95_ci": result[
                    "paired_delta_event_bootstrap_95_ci"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
