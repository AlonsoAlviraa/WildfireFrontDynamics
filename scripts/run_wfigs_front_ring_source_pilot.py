#!/usr/bin/env python3
"""Adapt one RCDA front-ring seed on WFIGS TRAIN/VAL without loading TEST."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import (  # noqa: E402
    validate_single_run_val_summary,
    write_json,
)
from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.open_if.regional.base import utc_now  # noqa: E402

RUN_NAME = "resunet_multitask_front_ring_v1"


def localized_source_summary(summary_path: Path, *, run_name: str) -> dict[str, Any]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    validate_single_run_val_summary(summary, run_name)
    reports = [
        row
        for row in summary.get("reports") or []
        if str((row.get("config") or {}).get("run_name")) == run_name
    ]
    if len(reports) != 1:
        raise ValueError("front-ring pilot requires exactly one source report")
    source = dict(reports[0])
    checkpoint = Path(str(source.get("checkpoint") or ""))
    if not checkpoint.is_file():
        checkpoint = summary_path.parent / checkpoint.name
    if not checkpoint.is_file():
        raise FileNotFoundError("front-ring pilot checkpoint is missing")
    source["local_checkpoint"] = str(checkpoint.resolve())
    source["test_used_for_selection"] = False
    source["test_evaluated"] = False
    return {
        "schema": "wfd_rcda_val_adaptation_source_v1",
        "generated_at": utc_now(),
        "run_name": run_name,
        "selection_split": "val",
        "test_used_for_selection": False,
        "test_evaluated": False,
        "reports": [source],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_summary", type=Path)
    parser.add_argument("wfigs_dataset", type=Path)
    parser.add_argument("rcda_normalization", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--run-name", default=RUN_NAME)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = localized_source_summary(args.source_summary, run_name=args.run_name)
    source_path = args.output / "VAL_SOURCE_SUMMARY.json"
    write_json(source_path, source)
    seed = int(source["reports"][0]["config"]["seed"])
    state_path = args.output / "STATE.json"

    def progress(row: dict[str, Any]) -> None:
        write_json(
            state_path,
            {
                "phase": "adapting_front_ring_source_on_wfigs_val",
                "updated_at": utc_now(),
                "training_progress": row,
                "selection_split": "wfigs_validation",
                "test_evaluated": False,
            },
        )

    report = adapt_frozen_rcda_on_wfigs(
        final_summary_path=source_path,
        wfigs_dataset_root=args.wfigs_dataset,
        rcda_normalization_path=args.rcda_normalization,
        output_root=args.output,
        adaptation=WFIGSAdaptConfig(
            epochs=12,
            batch_size=4,
            lr=1e-4,
            patience=4,
            trainable_scope="decoder",
            front_ring_bce_weight=0.15,
            front_ring_radius_px=16.0,
            source_seeds=(seed,),
        ),
        progress_callback=progress,
    )
    selected = report["reports"][0]["validation"]["selected"]
    final = {
        "phase": "complete",
        "updated_at": utc_now(),
        "run_name": args.run_name,
        "seed": seed,
        "val_event_macro_iou": selected["event_macro_iou"],
        "selected_threshold": report["reports"][0]["selected_threshold"],
        "selection_split": "wfigs_validation",
        "test_evaluated": False,
        "summary": str(args.output / "WFIGS_ADAPTATION_VAL_ONLY.json"),
    }
    write_json(state_path, final)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
