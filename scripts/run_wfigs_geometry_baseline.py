#!/usr/bin/env python3
"""Run event-disjoint copy/dilation geometry baselines on approved WFIGS pairs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.geometry_baseline import (  # noqa: E402
    WFIGSGeometryBaseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = WFIGSGeometryBaseline(
        pairs_path=args.root / "temporal_pairs/PAIRS.json",
        observations_path=args.root / "observations.geojson",
        output_path=args.root / "ml/GEOMETRY_BASELINE.json",
    ).build()
    if args.json:
        print(json.dumps(report["sealed_test"], ensure_ascii=False, indent=2))
    else:
        full = report["selection"]["full_iou"]["selected_radius_m"]
        growth = report["selection"]["growth_transition_iou"]["selected_radius_m"]
        print(
            f"geometry baseline: usable={report['counts']['pairs_usable']} "
            f"full_radius_m={full} growth_radius_m={growth}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
