#!/usr/bin/env python3
"""Harvest WFIGS daily perimeters by incident year/GACC and build temporal pairs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.temporal_pairs import (  # noqa: E402
    RegionalTemporalPairBuilder,
)
from wildfire_front.open_if.regional.wfigs_history import (  # noqa: E402
    GACC_REGIONS,
    WFIGSHistoricalHarvester,
)


def _years(value: str) -> list[int]:
    output: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            first, last = token.split("-", 1)
            output.update(range(int(first), int(last) + 1))
        else:
            output.add(int(token))
    if not output:
        raise argparse.ArgumentTypeError("years cannot be empty")
    return sorted(output)


def _regions(value: str) -> list[str]:
    regions = [item.strip() for item in value.split(",") if item.strip()]
    if regions == ["all"]:
        return list(GACC_REGIONS)
    unknown = sorted(set(regions) - set(GACC_REGIONS))
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown regions: {', '.join(unknown)}")
    return regions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=_years, default=_years("2020-2026"))
    parser.add_argument("--regions", type=_regions, default=list(GACC_REGIONS))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "wfigs_history_2020_2026",
    )
    parser.add_argument("--pairs-output", type=Path)
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--page-size", type=int, default=250)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--harvest-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    harvester = WFIGSHistoricalHarvester(
        output_root=args.output_root,
        timeout=args.timeout,
        max_bytes=args.max_bytes,
        page_size=args.page_size,
        as_of=args.as_of,
    )
    report = harvester.harvest(
        years=args.years,
        regions=args.regions,
        resume=not args.no_resume,
        continue_on_error=not args.fail_fast,
        workers=args.workers,
    )
    result: dict[str, object] = {"harvest": report}
    if not args.harvest_only:
        pairs_output = args.pairs_output or (args.output_root / "temporal_pairs")
        inventory = RegionalTemporalPairBuilder(
            observations_path=Path(report["observations"]["file"]),
            output_root=pairs_output,
        ).build()
        result["inventory"] = inventory
        result["pairs_output"] = str(pairs_output)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        counts = report["counts"]
        print(
            "harvest: "
            f"partitions={counts['partitions_complete']}/{counts['partitions_requested']} "
            f"observations={counts['observations']} events={counts['events']} "
            f"failures={counts['partitions_failed']}"
        )
        if "inventory" in result:
            inventory_obj = result["inventory"]
            if not isinstance(inventory_obj, dict):
                raise TypeError("inventory result must be a dictionary")
            print(
                "pairs: "
                f"events_2plus={inventory_obj['n_eventos_con_2_mas_perimetros']} "
                f"approved={inventory_obj['n_pares_aprobados']} "
                f"rejected={inventory_obj['n_pares_rechazados']}"
            )
            print(f"inventory: {Path(str(result['pairs_output'])) / 'INVENTORY.json'}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
