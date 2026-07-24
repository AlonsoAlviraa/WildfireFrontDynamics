#!/usr/bin/env python3
"""Overlay NASA FIRMS hotspots (24h Europe CSV) on an open_if pack bbox.

Not a perimeter — context only. Writes firms_hotspots.geojson + metrics snippet.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRMS_EU_24H = (
    "https://firms.modaps.eosdis.nasa.gov/data/active_fire/"
    "noaa-20-viirs-c2/csv/J1_VIIRS_C2_Europe_24h.csv"
)


def _bbox_from_geojson(path: Path) -> tuple[float, float, float, float] | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    coords: list[tuple[float, float]] = []

    def walk(g):
        if not g:
            return
        t = g.get("type")
        c = g.get("coordinates")
        if t == "Point":
            coords.append((float(c[0]), float(c[1])))
        elif t in ("LineString", "MultiPoint"):
            for p in c:
                coords.append((float(p[0]), float(p[1])))
        elif t in ("Polygon", "MultiLineString"):
            for ring in c:
                for p in ring:
                    coords.append((float(p[0]), float(p[1])))
        elif t == "MultiPolygon":
            for poly in c:
                for ring in poly:
                    for p in ring:
                        coords.append((float(p[0]), float(p[1])))
        elif t == "Feature":
            walk(g.get("geometry"))
        elif t == "FeatureCollection":
            for f in g.get("features") or []:
                walk(f)

    walk(data)
    if not coords:
        return None
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    pad = 0.15  # degrees buffer
    return min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", type=Path, required=True, help="outputs/open_if/emsr578")
    ap.add_argument("--csv-url", default=FIRMS_EU_24H)
    ap.add_argument("--local-csv", type=Path, default=None)
    args = ap.parse_args()
    pack = args.pack
    if not pack.is_dir():
        print(f"missing pack {pack}", file=sys.stderr)
        return 2

    gj = pack / "timeline_perimeters.geojson"
    if not gj.is_file():
        # try any vector
        vecs = list((pack / "vectors").glob("*.geojson")) if (pack / "vectors").is_dir() else []
        if not vecs:
            print("no geojson in pack", file=sys.stderr)
            return 2
        gj = vecs[0]
    bbox = _bbox_from_geojson(gj)
    if not bbox:
        print("empty bbox", file=sys.stderr)
        return 2
    minx, miny, maxx, maxy = bbox

    if args.local_csv and args.local_csv.is_file():
        text = args.local_csv.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            text = (
                urllib.request.urlopen(args.csv_url, timeout=90).read().decode("utf-8", "replace")
            )
        except Exception as exc:
            print(f"FIRMS download failed: {exc}", file=sys.stderr)
            # write empty with note
            out = {
                "type": "FeatureCollection",
                "features": [],
                "properties": {
                    "error": str(exc),
                    "note": "FIRMS hotspots unavailable; not a perimeter",
                },
            }
            (pack / "firms_hotspots.geojson").write_text(
                json.dumps(out, indent=2), encoding="utf-8"
            )
            return 1

    reader = csv.DictReader(io.StringIO(text))
    feats = []
    for row in reader:
        try:
            lon = float(row.get("longitude") or row.get("Longitude") or "")
            lat = float(row.get("latitude") or row.get("Latitude") or "")
        except ValueError:
            continue
        if not (minx <= lon <= maxx and miny <= lat <= maxy):
            continue
        feats.append(
            {
                "type": "Feature",
                "properties": {
                    "brightness": row.get("bright_ti4") or row.get("brightness"),
                    "acq_date": row.get("acq_date"),
                    "acq_time": row.get("acq_time"),
                    "confidence": row.get("confidence"),
                    "satellite": row.get("satellite"),
                    "not_official_perimeter": True,
                    "source": "NASA FIRMS VIIRS 24h Europe",
                },
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )

    fc = {
        "type": "FeatureCollection",
        "features": feats,
        "properties": {
            "bbox": [minx, miny, maxx, maxy],
            "n_hotspots": len(feats),
            "built_at_utc": datetime.now(UTC).isoformat(),
            "note": "Hotspots ~375m pixels, NOT fire perimeter",
        },
    }
    (pack / "firms_hotspots.geojson").write_text(json.dumps(fc, indent=2), encoding="utf-8")
    metrics = {
        "n_hotspots_in_bbox": len(feats),
        "bbox": [minx, miny, maxx, maxy],
        "csv_url": args.csv_url if not args.local_csv else str(args.local_csv),
    }
    (pack / "firms_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return 0


if __name__ == "__main__":
    from datetime import datetime

    raise SystemExit(main())
