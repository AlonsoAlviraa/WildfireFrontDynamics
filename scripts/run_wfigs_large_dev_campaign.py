#!/usr/bin/env python3
"""Materialize a larger WFIGS TRAIN/DEV tensor cohort without TEST."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_tensor_dataset import WFIGSTensorDatasetBuilder  # noqa: E402
from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402
from wildfire_front.open_if.regional.wfigs_campaign import WFIGSTensorCampaign  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--events-per-region", type=int, default=50)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--resolution-m", type=float, default=60.0)
    parser.add_argument("--min-valid-fraction", type=float, default=0.70)
    args = parser.parse_args()
    if args.events_per_region <= 0:
        raise ValueError("events-per-region must be positive")
    args.output_root.mkdir(parents=True, exist_ok=True)
    train_root = args.output_root / "train_campaign"
    validation_root = args.output_root / "validation_campaign"
    train = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=train_root,
        split="train",
        events_per_region=args.events_per_region,
        size=args.size,
        resolution_m=args.resolution_m,
        min_valid_fraction=args.min_valid_fraction,
    ).run()
    validation = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=validation_root,
        split="validation",
        events_per_region=args.events_per_region,
        size=args.size,
        resolution_m=args.resolution_m,
        min_valid_fraction=args.min_valid_fraction,
    ).run()
    dataset_root = args.output_root / "dataset"
    report = WFIGSTensorDatasetBuilder(
        inventory_paths=[train_root / "INVENTORY.json", validation_root / "INVENTORY.json"],
        output_root=dataset_root,
    ).build()
    if (dataset_root / "test.json").exists():
        raise RuntimeError("large DEV campaign unexpectedly materialized TEST")
    final = {
        "schema": "wfd_wfigs_large_dev_campaign_v1",
        "generated_at": utc_now(),
        "configuration": {
            "events_per_region": args.events_per_region,
            "size": args.size,
            "resolution_m": args.resolution_m,
            "min_valid_fraction": args.min_valid_fraction,
            "test_materialized": False,
        },
        "train_campaign_counts": train["counts"],
        "validation_campaign_counts": validation["counts"],
        "dataset_counts": report["counts"],
        "rights": report["rights"],
        "claims": {
            "internal_noncommercial_training_only": True,
            "test_used_for_selection": False,
            "raw_or_derived_publication_allowed": False,
        },
    }
    _atomic_write_json(args.output_root / "LARGE_DEV_CAMPAIGN_REPORT.json", final)
    print(json.dumps(final, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
