#!/usr/bin/env python3
"""Post-process observatorio packs: sector ROS + 15/30/60 envelope (emergency)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.emergency_products import (  # noqa: E402
    enrich_ops_dict,
    expansion_bearing_deg_from_centroids,
    load_main_front_centroids,
    write_emergency_envelope_file,
)


def enrich_pack(pack_dir: Path) -> dict:
    ops_path = pack_dir / "operational_metrics.json"
    if not ops_path.is_file():
        return {"fire_id": pack_dir.name, "status": "missing_ops"}
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    bearing = None
    mf = pack_dir / "main_front.geojson"
    if mf.is_file():
        cents = load_main_front_centroids(mf)
        bearing = expansion_bearing_deg_from_centroids(cents)
    enriched = enrich_ops_dict(ops, expansion_bearing_deg=bearing)
    ops_path.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    env = enriched.get("short_horizon_envelope") or {}
    write_emergency_envelope_file(env, pack_dir / "emergency_envelope.json")
    sector = enriched.get("sector_ros") or {}
    return {
        "fire_id": pack_dir.name,
        "status": "ok",
        "quality_grade": enriched.get("quality_grade"),
        "primary_ros": enriched.get("speed_median_m_min"),
        "sector_status": sector.get("status"),
        "envelope_status": env.get("status"),
        "bearing": bearing,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--packs",
        default="tobarra_20240802,cardoso_2025,hellin_2024,brazatortas_2025",
        help="Comma-separated pack folder names under outputs/observatorio",
    )
    ap.add_argument(
        "--root",
        type=Path,
        default=ROOT / "outputs" / "observatorio",
    )
    args = ap.parse_args()
    rows = []
    for name in [x.strip() for x in args.packs.split(",") if x.strip()]:
        pack = args.root / name
        if not pack.is_dir():
            rows.append({"fire_id": name, "status": "missing_pack"})
            continue
        rows.append(enrich_pack(pack))
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
