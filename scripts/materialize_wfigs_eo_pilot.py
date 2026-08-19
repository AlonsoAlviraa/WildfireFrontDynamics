#!/usr/bin/env python3
"""Materialize a bounded Sentinel/WFIGS pilot without touching the sealed TEST."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.wfigs_materialize import WFIGSEOMaterializer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    base = ROOT / "data/open_if/wfigs_history_2020_2026"
    parser.add_argument("--pairs", type=Path, default=base / "temporal_pairs/PAIRS.json")
    parser.add_argument("--enrichment", type=Path, default=base / "enrichment/PAIR_ENRICHMENT.json")
    parser.add_argument("--observations", type=Path, default=base / "observations.geojson")
    parser.add_argument("--output", type=Path, default=base / "materialized_eo_pilot")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--splits", nargs="+", default=["train"])
    parser.add_argument("--pair-ids", nargs="*", default=[])
    parser.add_argument("--size", type=int, default=256)
    parser.add_argument("--resolution-m", type=float, default=60.0)
    parser.add_argument("--min-valid-fraction", type=float, default=0.70)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    inventory = WFIGSEOMaterializer(
        pairs_path=args.pairs,
        enrichment_path=args.enrichment,
        observations_path=args.observations,
        output_root=args.output,
        limit=args.limit,
        splits=tuple(args.splits),
        pair_ids=tuple(args.pair_ids),
        size=args.size,
        resolution_m=args.resolution_m,
        min_valid_fraction=args.min_valid_fraction,
        overwrite=args.overwrite,
    ).build()
    print(json.dumps(inventory["counts"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
