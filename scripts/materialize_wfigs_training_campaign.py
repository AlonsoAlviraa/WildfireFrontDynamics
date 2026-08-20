#!/usr/bin/env python3
"""Run a small region-balanced, resumable WFIGS TRAIN tensor campaign."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.wfigs_campaign import WFIGSTensorCampaign  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history-root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_training_campaign",
    )
    parser.add_argument("--split", default="train", choices=["train", "validation", "test"])
    parser.add_argument("--events-per-region", type=int, default=2)
    parser.add_argument("--event-offset-per-region", type=int, default=0)
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--resolution-m", type=float, default=60.0)
    parser.add_argument("--min-valid-fraction", type=float, default=0.70)
    args = parser.parse_args()
    inventory = WFIGSTensorCampaign(
        history_root=args.history_root,
        output_root=args.output,
        split=args.split,
        events_per_region=args.events_per_region,
        event_offset_per_region=args.event_offset_per_region,
        size=args.size,
        resolution_m=args.resolution_m,
        min_valid_fraction=args.min_valid_fraction,
    ).run()
    print(json.dumps(inventory["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
