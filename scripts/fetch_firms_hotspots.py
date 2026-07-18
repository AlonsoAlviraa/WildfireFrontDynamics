#!/usr/bin/env python3
"""Fetch NASA FIRMS active-fire hotspots (public CSV, no API key for archives).

Sources:
  - Country-year archives: https://firms.modaps.eosdis.nasa.gov/data/country/
  - Europe 24h NRT CSV (no key)

Writes GeoJSON (WGS84) for map overlay and a small summary JSON.
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
sys.path.insert(0, str(ROOT))

from wildfire_front.geo_crs import utm_to_wgs84  # noqa: E402

UA = "WildfireFrontDynamics/1.0 (research emergency support)"


def _download(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8", errors="replace")


def bbox_from_main_front(pack: Path, pad_deg: float = 0.15) -> tuple[float, float, float, float] | None:
    """Return lon_min, lat_min, lon_max, lat_max from main_front (UTM or WGS84)."""
    for name in ("main_front_wgs84.geojson", "main_front.geojson"):
        p = pack / name
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        xs: list[float] = []
        ys: list[float] = []

        def walk(c, _xs=xs, _ys=ys):
            if isinstance(c[0], (int, float)):
                _xs.append(float(c[0]))
                _ys.append(float(c[1]))
            else:
                for x in c:
                    walk(x)

        for f in data.get("features") or []:
            g = f.get("geometry") or {}
            if g.get("coordinates") is not None:
                walk(g["coordinates"])
        if not xs:
            continue
        # if UTM, convert corners
        if abs(xs[0]) > 180 or abs(ys[0]) > 90:
            lons, lats = [], []
            for x, y in zip(xs, ys, strict=False):
                lon, lat = utm_to_wgs84(x, y, zone=30, northern=True)
                lons.append(lon)
                lats.append(lat)
            xs, ys = lons, lats
        return (
            min(xs) - pad_deg,
            min(ys) - pad_deg,
            max(xs) + pad_deg,
            max(ys) + pad_deg,
        )
    return None


def fetch_spain_year(year: int, sensor: str = "viirs-snpp") -> list[dict]:
    if sensor == "modis":
        url = f"https://firms.modaps.eosdis.nasa.gov/data/country/modis-c6.1/{year}/modis_{year}_Spain.csv"
    else:
        url = (
            f"https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/"
            f"{year}/viirs-snpp_{year}_Spain.csv"
        )
    text = _download(url)
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def filter_rows(
    rows: list[dict],
    *,
    date: str,
    bbox: tuple[float, float, float, float],
) -> list[dict]:
    lon0, lat0, lon1, lat1 = bbox
    out = []
    for r in rows:
        try:
            if (r.get("acq_date") or "") != date:
                continue
            lat = float(r["latitude"])
            lon = float(r["longitude"])
        except (KeyError, TypeError, ValueError):
            continue
        if lon0 <= lon <= lon1 and lat0 <= lat <= lat1:
            out.append(r)
    return out


def rows_to_geojson(rows: list[dict], *, fire_id: str, source: str) -> dict:
    feats = []
    for r in rows:
        lon = float(r["longitude"])
        lat = float(r["latitude"])
        props = {
            k: r.get(k)
            for k in (
                "acq_date",
                "acq_time",
                "confidence",
                "bright_ti4",
                "brightness",
                "frp",
                "satellite",
                "instrument",
            )
            if r.get(k) not in (None, "")
        }
        props["source"] = source
        props["fire_id"] = fire_id
        props["not_official_perimeter"] = True
        props["note"] = "NASA FIRMS active-fire hotspot (pixel), not fire perimeter"
        feats.append(
            {
                "type": "Feature",
                "properties": props,
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
            }
        )
    return {
        "type": "FeatureCollection",
        "features": feats,
        "properties": {
            "source": source,
            "n": len(feats),
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "not_official_perimeter": True,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", default="tobarra_20240802")
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default from fire id if tobarra)")
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--sensor", choices=["viirs-snpp", "modis"], default="viirs-snpp")
    ap.add_argument("--root", type=Path, default=ROOT / "outputs" / "observatorio")
    args = ap.parse_args()

    pack = args.root / args.fire
    pack.mkdir(parents=True, exist_ok=True)
    date = args.date
    if date is None:
        # tobarra_20240802 -> 2024-08-02
        if "2024" in args.fire and "0802" in args.fire.replace("-", "") or "20240802" in args.fire:
            date = "2024-08-02"
        else:
            # try digits
            import re

            m = re.search(r"(20\d{2})(\d{2})(\d{2})", args.fire.replace("-", ""))
            if m:
                date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            else:
                print("Need --date YYYY-MM-DD", file=sys.stderr)
                return 2
    year = args.year or int(date[:4])
    bbox = bbox_from_main_front(pack)
    if bbox is None:
        # CLM default box around Albacete if no pack geom
        bbox = (-2.2, 38.3, -1.3, 39.0)
        print("WARN: no main_front; using default CLM bbox", file=sys.stderr)

    print(f"Fetching FIRMS {args.sensor} Spain {year} …")
    rows = fetch_spain_year(year, sensor=args.sensor)
    hit = filter_rows(rows, date=date, bbox=bbox)
    print(f"rows_year={len(rows)} in_bbox_date={len(hit)} date={date} bbox={bbox}")

    gj = rows_to_geojson(hit, fire_id=args.fire, source=f"FIRMS/{args.sensor}/{year}")
    out_gj = pack / "firms_hotspots.geojson"
    out_gj.write_text(json.dumps(gj, indent=2), encoding="utf-8")
    summary = {
        "fire_id": args.fire,
        "date": date,
        "sensor": args.sensor,
        "n_hotspots": len(hit),
        "bbox": bbox,
        "geojson": str(out_gj),
        "note": "Hotspots are ~375m pixels, not perimeter. Use as direction/context only.",
    }
    (pack / "firms_hotspots_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
