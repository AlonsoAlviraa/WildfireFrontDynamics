#!/usr/bin/env python3
"""R-A3 — FIRMS direction overlay note for one open pack / firms artifact.

Offline-first: reads existing ``firms_hotspots*.geojson`` or ``outputs/firms/**``
summaries. Does **not** invent Vp. Hotspots are ~375 m pixels, not perimeters.

Writes ``outputs/firms_direction_notes/<id>/firms_direction_note.json`` (+ md).

Usage
-----
::

    python scripts/firms_direction_overlay_note.py --pack outputs/open_if/la_mierla_20260717
    python scripts/firms_direction_overlay_note.py --firms-dir outputs/firms/guadalajara_la_mierla_20260717
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _find_hotspot_geojson(pack: Path | None, firms_dir: Path | None) -> Path | None:
    candidates: list[Path] = []
    if pack is not None:
        candidates.extend(
            [
                pack / "firms_hotspots.geojson",
                pack / "firms_hotspots_7d.geojson",
                pack / "vectors" / "firms_hotspots.geojson",
            ]
        )
    if firms_dir is not None:
        candidates.extend(sorted(firms_dir.glob("*.geojson")))
    for c in candidates:
        if c.is_file():
            return c
    return None


def _bearing_deg(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    """Initial bearing degrees clockwise from north."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    brng = math.degrees(math.atan2(x, y))
    return (brng + 360.0) % 360.0


def _parse_hotspots(fc: dict[str, Any]) -> list[dict[str, Any]]:
    pts: list[dict[str, Any]] = []
    for feat in fc.get("features") or []:
        geom = feat.get("geometry") or {}
        if geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            continue
        props = feat.get("properties") or {}
        pts.append(
            {
                "lon": float(coords[0]),
                "lat": float(coords[1]),
                "acq_date": props.get("acq_date"),
                "acq_time": props.get("acq_time"),
                "brightness": props.get("brightness") or props.get("bright_ti4"),
                "frp": props.get("frp"),
            }
        )
    return pts


def _sort_key(p: dict[str, Any]) -> tuple[str, str]:
    return (str(p.get("acq_date") or ""), str(p.get("acq_time") or ""))


def build_note(
    *,
    pack: Path | None,
    firms_dir: Path | None,
    geojson_path: Path | None = None,
) -> dict[str, Any]:
    gj_path = geojson_path or _find_hotspot_geojson(pack, firms_dir)
    source_id = (
        pack.name if pack is not None else (firms_dir.name if firms_dir is not None else "unknown")
    )
    if gj_path is None or not gj_path.is_file():
        return {
            "schema": "firms_direction_note_v1",
            "graph_id": "R-A3",
            "built_at_utc": datetime.now(UTC).isoformat(),
            "source_id": source_id,
            "status": "GAP_NO_HOTSPOTS",
            "n_hotspots": 0,
            "direction_bearing_deg": None,
            "direction_label": None,
            "invented_vp": False,
            "note": (
                "No firms_hotspots*.geojson found. Run "
                "`python scripts/overlay_firms_on_open_pack.py --pack <pack>` "
                "when network available, or point --firms-dir at outputs/firms/…"
            ),
            "rails": {
                "not_perimeter": True,
                "not_ops_ros": True,
                "no_invented_vp": True,
            },
        }

    fc = _load(gj_path) or {}
    pts = _parse_hotspots(fc if isinstance(fc, dict) else {})
    summary_sidecar = None
    if firms_dir is not None:
        summary_sidecar = _load(firms_dir / "firms_summary.json")
    if pack is not None:
        summary_sidecar = summary_sidecar or _load(pack / "firms_metrics.json")

    if not pts:
        return {
            "schema": "firms_direction_note_v1",
            "graph_id": "R-A3",
            "built_at_utc": datetime.now(UTC).isoformat(),
            "source_id": source_id,
            "geojson": str(gj_path).replace("\\", "/"),
            "status": "EMPTY_HOTSPOTS",
            "n_hotspots": 0,
            "direction_bearing_deg": None,
            "direction_label": None,
            "invented_vp": False,
            "sidecar_metrics": summary_sidecar,
            "note": (
                "GeoJSON present but zero Point features (common for historical packs "
                "re-queried with 24h Europe CSV). Not a perimeter; no Vp."
            ),
            "rails": {
                "not_perimeter": True,
                "not_ops_ros": True,
                "no_invented_vp": True,
            },
        }

    pts_sorted = sorted(pts, key=_sort_key)
    # Split early/late halves by acquisition time when available; else spatial only
    has_time = any(p.get("acq_date") for p in pts_sorted)
    if has_time and len(pts_sorted) >= 4:
        mid = len(pts_sorted) // 2
        early, late = pts_sorted[:mid], pts_sorted[mid:]
        method = "temporal_half_centroids"
    else:
        # Spatial: SW half vs NE half by lon+lat sum
        ranked = sorted(pts_sorted, key=lambda p: p["lon"] + p["lat"])
        mid = len(ranked) // 2
        early, late = ranked[:mid], ranked[mid:]
        method = "spatial_diagonal_split_no_time"

    def centroid(group: list[dict[str, Any]]) -> tuple[float, float] | None:
        if not group:
            return None
        return (
            sum(p["lon"] for p in group) / len(group),
            sum(p["lat"] for p in group) / len(group),
        )

    c0, c1 = centroid(early), centroid(late)
    bearing = None
    label = None
    if c0 and c1 and (c0 != c1):
        bearing = _bearing_deg(c0[0], c0[1], c1[0], c1[1])
        # 8-wind rose
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        label = dirs[int((bearing + 22.5) // 45) % 8]

    return {
        "schema": "firms_direction_note_v1",
        "graph_id": "R-A3",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "source_id": source_id,
        "geojson": str(gj_path).replace("\\", "/"),
        "status": "OK_DIRECTION_PROXY",
        "n_hotspots": len(pts),
        "method": method,
        "early_centroid": list(c0) if c0 else None,
        "late_centroid": list(c1) if c1 else None,
        "direction_bearing_deg": bearing,
        "direction_label": label,
        "invented_vp": False,
        "sidecar_metrics": summary_sidecar,
        "overlay_path_doc": (
            "1) Ensure open pack has timeline/vectors. "
            "2) `python scripts/overlay_firms_on_open_pack.py --pack outputs/open_if/<id>` "
            "(live CSV) or reuse `outputs/firms/<event>/`. "
            "3) `python scripts/firms_direction_overlay_note.py --pack …` for this note. "
            "Map: load firms_hotspots.geojson under pack vectors + open perimeters."
        ),
        "note": (
            "Direction is a **proxy** from hotspot centroids (early→late or spatial split). "
            "FIRMS pixels are not fire perimeter and **not** LWIR ROS / Vp. "
            "Do not use bearing as tactical head bearing without ops confirmation."
        ),
        "rails": {
            "not_perimeter": True,
            "not_ops_ros": True,
            "no_invented_vp": True,
        },
    }


def render_md(note: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# FIRMS direction overlay — {note.get('source_id')} (R-A3)",
            "",
            f"_UTC: {note.get('built_at_utc')}_",
            "",
            f"- **status:** `{note.get('status')}`",
            f"- **n_hotspots:** {note.get('n_hotspots')}",
            f"- **bearing_deg:** {note.get('direction_bearing_deg')} ({note.get('direction_label')})",
            f"- **method:** {note.get('method')}",
            f"- **invented_vp:** {note.get('invented_vp')}",
            "",
            f"> {note.get('note')}",
            "",
            "## One-pack overlay path",
            "",
            note.get("overlay_path_doc")
            or "See scripts/overlay_firms_on_open_pack.py + this script.",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="R-A3 FIRMS direction overlay note")
    ap.add_argument("--pack", type=Path, default=None)
    ap.add_argument("--firms-dir", type=Path, default=None)
    ap.add_argument("--geojson", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.pack is None and args.firms_dir is None and args.geojson is None:
        # Prefer la_mierla if present, else firms dir
        default_pack = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
        default_firms = ROOT / "outputs" / "firms" / "guadalajara_la_mierla_20260717"
        if default_pack.is_dir():
            args.pack = default_pack
        elif default_firms.is_dir():
            args.firms_dir = default_firms
        else:
            print(
                json.dumps({"ok": False, "error": "provide --pack or --firms-dir"}), file=sys.stderr
            )
            return 2

    note = build_note(pack=args.pack, firms_dir=args.firms_dir, geojson_path=args.geojson)
    sid = note.get("source_id") or "unknown"
    out_dir = args.out_dir or (ROOT / "outputs" / "firms_direction_notes" / sid)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "firms_direction_note.json").write_text(
        json.dumps(note, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "firms_direction_note.md").write_text(render_md(note), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "graph_id": "R-A3",
                "source_id": sid,
                "status": note.get("status"),
                "n_hotspots": note.get("n_hotspots"),
                "direction_bearing_deg": note.get("direction_bearing_deg"),
                "invented_vp": False,
                "out": str(out_dir.relative_to(ROOT)).replace("\\", "/")
                if out_dir.is_relative_to(ROOT)
                else str(out_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
