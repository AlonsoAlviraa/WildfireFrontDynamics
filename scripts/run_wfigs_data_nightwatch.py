#!/usr/bin/env python3
"""Wait for WFIGS TRAIN tensors, build VAL tensors, then assemble the dataset."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402
from wildfire_front.open_if.regional.wfigs_campaign import WFIGSTensorCampaign  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history-root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument(
        "--train-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_training_campaign_20260819",
    )
    parser.add_argument(
        "--validation-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_validation_campaign_20260819",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_tensor_dataset_20260819",
    )
    parser.add_argument("--poll-seconds", type=int, default=30)
    parser.add_argument("--max-hours", type=float, default=10.0)
    parser.add_argument("--train-events-per-region", type=int, default=8)
    parser.add_argument("--validation-events-per-region", type=int, default=3)
    args = parser.parse_args()
    state_path = args.dataset_root / "NIGHTWATCH_STATE.json"
    deadline = time.monotonic() + args.max_hours * 3600.0
    train_inventory = args.train_root / "INVENTORY.json"
    while not train_inventory.is_file():
        _atomic_write_json(
            state_path,
            {
                "phase": "waiting_for_train_campaign",
                "updated_at": utc_now(),
                "train_state": str(args.train_root / "STATE.json"),
            },
        )
        if time.monotonic() >= deadline:
            raise TimeoutError("WFIGS TRAIN campaign did not finish before deadline")
        time.sleep(max(5, args.poll_seconds))

    _atomic_write_json(
        state_path,
        {"phase": "expanding_train_campaign", "updated_at": utc_now()},
    )
    expanded_train = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=args.train_root,
        split="train",
        events_per_region=args.train_events_per_region,
        size=256,
        resolution_m=60.0,
        min_valid_fraction=0.70,
    ).run()
    _atomic_write_json(
        state_path,
        {
            "phase": "materializing_validation",
            "updated_at": utc_now(),
            "train_counts": expanded_train["counts"],
        },
    )
    validation = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=args.validation_root,
        split="validation",
        events_per_region=args.validation_events_per_region,
        size=256,
        resolution_m=60.0,
        min_valid_fraction=0.70,
    ).run()
    validation_inventory = args.validation_root / "INVENTORY.json"
    _atomic_write_json(
        state_path,
        {
            "phase": "building_train_val_dataset",
            "updated_at": utc_now(),
            "validation_counts": validation["counts"],
        },
    )
    report = WFIGSTensorDatasetBuilder(
        inventory_paths=[train_inventory, validation_inventory],
        output_root=args.dataset_root,
    ).build()
    final = {
        "phase": "complete",
        "updated_at": utc_now(),
        "test_materialized": False,
        "test_evaluated": False,
        "dataset_counts": report["counts"],
    }
    _atomic_write_json(state_path, final)
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
