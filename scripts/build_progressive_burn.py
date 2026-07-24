#!/usr/bin/env python3
"""Build progressive synthetic burn layer for an open_if pack or raw GeoJSON.

Examples:
  python scripts/build_progressive_burn.py --pack outputs/open_if/and_2024040053_20240606
  python scripts/build_progressive_burn.py --geojson path.geojson --out-dir /tmp/psb --source-crs EPSG:3042
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.progressive_burn.geometry import geojson_to_geom  # noqa: E402
from wildfire_front.progressive_burn.metrics import evaluate_invariants  # noqa: E402
from wildfire_front.progressive_burn.pack_attach import (  # noqa: E402
    attach_progressive_burn,
    sequence_to_geojson_fc,
)
from wildfire_front.progressive_burn.pipeline import (  # noqa: E402
    ProgressiveBurnConfig,
    build_stage_sequence,
)
from wildfire_front.progressive_burn.schemas import ATTRIBUTION_REDIAM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Progressive Synthetic Burn builder")
    p.add_argument("--pack", type=Path, help="open_if pack directory")
    p.add_argument("--geojson", type=Path, help="final perimeter GeoJSON")
    p.add_argument("--out-dir", type=Path, help="output dir when using --geojson")
    p.add_argument("--source-crs", default="EPSG:4326")
    p.add_argument("--n-stages", type=int, default=12)
    p.add_argument("--engine", default="area_fraction", choices=["area_fraction", "buffer_rings"])
    p.add_argument("--schedule", default="sqrt")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--total-duration-s", type=float, default=86400.0)
    p.add_argument("--min-component-area-ha", type=float, default=2.0)
    p.add_argument("--no-front-dynamics", action="store_true")
    args = p.parse_args(argv)

    cfg = ProgressiveBurnConfig(
        n_stages=args.n_stages,
        engine=args.engine,
        schedule=args.schedule,
        seed=args.seed,
        total_duration_s=args.total_duration_s,
        min_component_area_ha=args.min_component_area_ha,
        attribution=ATTRIBUTION_REDIAM,
    )

    if args.pack:
        result = attach_progressive_burn(args.pack, cfg, run_fd=not args.no_front_dynamics)
        print(json.dumps(result, indent=2))
        return 0 if result.get("verdict") != "NO_GO" else 2

    if not args.geojson or not args.out_dir:
        p.error("provide --pack OR (--geojson and --out-dir)")

    data = json.loads(args.geojson.read_text(encoding="utf-8"))
    geom = geojson_to_geom(data)
    seq = build_stage_sequence(geom, cfg, source_crs=args.source_crs)
    metrics = evaluate_invariants(seq)
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    (out / "timeline_progressive.geojson").write_text(
        json.dumps(sequence_to_geojson_fc(seq), indent=2), encoding="utf-8"
    )
    (out / "metrics_progressive.json").write_text(
        json.dumps(metrics, indent=2, default=str), encoding="utf-8"
    )
    print(
        json.dumps(
            {"verdict": metrics["verdict"], "n_stages": seq.n_stages, "out": str(out)}, indent=2
        )
    )
    return 0 if metrics["verdict"] != "NO_GO" else 2


if __name__ == "__main__":
    raise SystemExit(main())
