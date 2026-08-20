#!/usr/bin/env python3
"""Adapt registered RCDA front-ring replications on WFIGS TRAIN/VAL only."""

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

from scripts.run_rcda_kaggle_alt_continuation import write_json  # noqa: E402
from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.open_if.regional.base import utc_now  # noqa: E402

SOURCE_SCHEMA = "wfd_rcda_val_replication_summary_v1"


def validate_replication_source(path: Path) -> tuple[dict[str, Any], tuple[int, ...]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    reports = source.get("reports") or []
    seeds = tuple(int((row.get("config") or {}).get("seed")) for row in reports)
    claims = source.get("claims") or {}
    if not (
        source.get("schema") == SOURCE_SCHEMA
        and source.get("selection_split") == "val"
        and source.get("test_used_for_selection") is False
        and source.get("test_evaluated") is False
        and claims.get("ready_as_test_free_wfigs_adaptation_source") is True
        and len(reports) >= 3
        and len(seeds) == len(set(seeds))
    ):
        raise ValueError("front-ring source is not a replicated, TEST-free VAL summary")
    for report in reports:
        checkpoint = Path(str(report.get("local_checkpoint") or ""))
        if not checkpoint.is_file():
            raise FileNotFoundError(f"replication checkpoint is missing: {checkpoint}")
        if not (
            report.get("threshold_selected_on") == "val"
            and report.get("test_used_for_selection") is False
            and report.get("test_evaluated") is False
        ):
            raise ValueError("replication report crosses the VAL/TEST boundary")
    return source, seeds


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_summary", type=Path)
    parser.add_argument("wfigs_dataset", type=Path)
    parser.add_argument("rcda_normalization", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    source, seeds = validate_replication_source(args.source_summary)
    args.output.mkdir(parents=True, exist_ok=True)
    state_path = args.output / "STATE.json"
    source_hash = hashlib.sha256(args.source_summary.read_bytes()).hexdigest()

    def progress(row: dict[str, Any]) -> None:
        write_json(
            state_path,
            {
                "phase": "adapting_replicated_front_ring_source_on_wfigs_val",
                "updated_at": utc_now(),
                "source_summary_sha256": source_hash,
                "source_seeds": list(seeds),
                "training_progress": row,
                "selection_split": "wfigs_validation",
                "test_evaluated": False,
            },
        )

    report = adapt_frozen_rcda_on_wfigs(
        final_summary_path=args.source_summary,
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
            source_seeds=seeds,
        ),
        progress_callback=progress,
    )
    selected = report["ensemble"]["validation"]["selected"]
    final = {
        "phase": "complete",
        "updated_at": utc_now(),
        "run_name": source.get("run_name"),
        "source_summary_sha256": source_hash,
        "source_seeds": list(seeds),
        "val_ensemble_event_macro_iou": selected["event_macro_iou"],
        "selected_threshold": report["ensemble"]["selected_threshold"],
        "selection_split": "wfigs_validation",
        "test_evaluated": False,
        "summary": str(args.output / "WFIGS_ADAPTATION_VAL_ONLY.json"),
    }
    write_json(state_path, final)
    print(json.dumps(final, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
