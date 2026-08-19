#!/usr/bin/env python3
"""Resolve pre-t0 Sentinel-2/Landsat candidates and HRRR runs for WFIGS pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.pair_enrichment import WFIGSPairEnricher  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    inventory = WFIGSPairEnricher(
        pairs_path=args.root / "temporal_pairs/PAIRS.json",
        observations_path=args.root / "observations.geojson",
        output_root=args.root / "enrichment",
        workers=args.workers,
    ).build()
    if args.json:
        print(json.dumps(inventory, ensure_ascii=False, indent=2))
    else:
        counts = inventory["counts"]
        print(
            "enrichment: "
            f"pairs={counts['pairs']} "
            f"s2={counts['pairs_sentinel2_pre_t0']} "
            f"landsat={counts['pairs_landsat_pre_t0']} "
            f"hrrr={counts['pairs_hrrr_available_by_t0_and_full_window']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
