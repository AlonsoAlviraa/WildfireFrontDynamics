#!/usr/bin/env python3
"""Export main_front.geojson + ros_timeline + brief for existing packs (O4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.geometry_speed import signed_area  # noqa: E402
from wildfire_front.models import FrontObservation  # noqa: E402
from wildfire_front.observatory_export import export_operator_bundle  # noqa: E402


def _load_obs_from_geojson(path: Path, event_id: str) -> list[FrontObservation]:
    """Best-effort reconstruct observations from fronts.geojson for export."""
    data = json.loads(path.read_text(encoding="utf-8"))
    by_time: dict[str, list] = {}
    meta: dict[str, dict] = {}
    for feat in data.get("features") or []:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        t = props.get("observed_at") or props.get("time") or str(props.get("time_s"))
        coords = geom.get("coordinates")
        if not coords:
            continue
        # Polygon or LineString
        if geom.get("type") == "Polygon":
            ring = coords[0]
        elif geom.get("type") == "LineString":
            ring = coords
        else:
            continue
        component = tuple((float(x), float(y)) for x, y in ring)
        by_time.setdefault(t, []).append(component)
        meta[t] = props

    obs_list: list[FrontObservation] = []
    for i, (t, comps) in enumerate(sorted(by_time.items())):
        props = meta.get(t) or {}
        # keep largest only as multi
        comps_sorted = sorted(comps, key=lambda c: abs(signed_area(c)), reverse=True)
        time_s = float(props.get("time_s") or i * 60.0)
        obs_list.append(
            FrontObservation(
                observation_id=str(props.get("observation_id") or f"obs_{i}"),
                event_id=event_id,
                sensor_id=str(props.get("sensor_id") or "lwir"),
                time_s=time_s,
                observed_at=str(t),
                components=tuple(comps_sorted[:3]),
                estimated_error_m=float(props.get("estimated_error_m") or 2.0),
                crs=props.get("crs") or "EPSG:32630",
                coordinate_system="projected_metric",
                resolution_m=float(props.get("resolution_m") or 0.5),
                method="from_geojson_export",
            )
        )
    return obs_list


def process_pack(pack_dir: Path) -> dict:
    event_id = pack_dir.name
    ops_path = pack_dir / "operational_metrics.json"
    fronts = pack_dir / "fronts.geojson"
    if not ops_path.is_file():
        return {"fire_id": event_id, "status": "skip", "reason": "no operational_metrics"}
    ops = json.loads(ops_path.read_text(encoding="utf-8"))
    observations: list[FrontObservation] = []
    if fronts.is_file():
        try:
            observations = _load_obs_from_geojson(fronts, event_id)
        except Exception as exc:  # noqa: BLE001
            return {"fire_id": event_id, "status": "fail", "error": str(exc)}
    if not observations:
        # still write timeline + brief
        from wildfire_front.observatory_export import (
            write_operator_brief_md,
            write_ros_timeline_csv,
        )

        structural = ops.get("structural") or {}
        write_ros_timeline_csv(structural, pack_dir / "ros_timeline.csv")
        write_operator_brief_md(
            event_id, ops, structural, pack_dir / "brief_operativo.md"
        )
        return {
            "fire_id": event_id,
            "status": "partial",
            "files": ["ros_timeline.csv", "brief_operativo.md"],
        }

    paths = export_operator_bundle(
        observations, ops, pack_dir, event_id=event_id
    )
    return {"fire_id": event_id, "status": "ok", "files": paths}


def main() -> int:
    root = ROOT / "outputs" / "observatorio"
    if len(sys.argv) > 1:
        root = Path(sys.argv[1])
    results = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if not (d / "operational_metrics.json").is_file():
            continue
        print("Exporting", d.name, flush=True)
        results.append(process_pack(d))
        print(" ", results[-1].get("status"), results[-1].get("files") or results[-1])
    out = root / "operator_export_report.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
