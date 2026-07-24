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
    compute_short_horizon_envelope,
    enrich_ops_dict,
    expansion_bearing_deg_from_centroids,
    load_main_front_centroids,
    write_emergency_envelope_file,
    write_envelope_geojson,
)
from wildfire_front.sector_ros_local import (  # noqa: E402
    load_local_speed_rows,
    sector_ros_from_local_samples,
)


def enrich_pack(pack_dir: Path) -> dict:
    ops_path = pack_dir / "operational_metrics.json"
    if not ops_path.is_file():
        return {"fire_id": pack_dir.name, "status": "missing_ops"}
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    bearing = None
    mf = pack_dir / "main_front.geojson"
    cents: list = []
    if mf.is_file():
        cents = load_main_front_centroids(mf)
        bearing = expansion_bearing_deg_from_centroids(cents)
    enriched = enrich_ops_dict(ops, expansion_bearing_deg=bearing)

    # Prefer precise local normal-ray sectors when we have samples
    local_csv = pack_dir / "local_speeds.csv"
    local_rows = load_local_speed_rows(local_csv)
    sector_source = "bulk_quartile"
    if local_rows:
        bulk_primary = enriched.get("speed_median_m_min")
        precise = sector_ros_from_local_samples(
            local_rows,
            expansion_bearing_deg=bearing,
            scale_to_primary_m_min=float(bulk_primary) if bulk_primary is not None else None,
        )

        if precise.get("status") == "estimated" and precise.get("sectors"):
            enriched["sector_ros"] = precise
            enriched["sector_ros_source"] = "local_normal_ray"
            sector_source = "local_normal_ray"
            secs = precise["sectors"]
            # Rebuild envelope with precise head/flank/rear
            primary = enriched.get("speed_median_m_min")
            if primary is None:
                primary = secs.get("primary_m_min")
            env = compute_short_horizon_envelope(
                float(primary) if primary is not None else None,
                expansion_bearing_deg=precise.get("expansion_bearing_deg") or bearing,
                quality_grade=str(enriched.get("quality_grade") or ""),
                head_ros_m_min=secs.get("head_m_min"),
                flank_ros_m_min=secs.get("flank_m_min"),
                rear_ros_m_min=secs.get("rear_m_min"),
            )
            enriched["short_horizon_envelope"] = env
            if precise.get("expansion_bearing_deg") is not None:
                bearing = precise["expansion_bearing_deg"]
    else:
        enriched["sector_ros_source"] = sector_source

    ops_path.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    env = enriched.get("short_horizon_envelope") or {}
    write_emergency_envelope_file(env, pack_dir / "emergency_envelope.json")
    center = cents[-1] if cents else None
    write_envelope_geojson(
        env,
        pack_dir / "emergency_envelope_guidance.geojson",
        center_xy=center,
        fire_id=pack_dir.name,
        expansion_bearing_deg=bearing,
    )
    sector = enriched.get("sector_ros") or {}
    return {
        "fire_id": pack_dir.name,
        "status": "ok",
        "quality_grade": enriched.get("quality_grade"),
        "primary_ros": enriched.get("speed_median_m_min"),
        "sector_status": sector.get("status"),
        "sector_source": sector_source,
        "sector_n_samples": sector.get("n_samples"),
        "envelope_status": env.get("status"),
        "bearing": bearing,
        "gis": str(pack_dir / "emergency_envelope_guidance.geojson"),
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
