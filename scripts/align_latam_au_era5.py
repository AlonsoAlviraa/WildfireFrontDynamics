#!/usr/bin/env python3
"""P1-D: optional ERA5 / archive meteo align for LATAM+AU packs.

Writes CDS-style request templates from pack bbox+dates. Optionally fetches
Open-Meteo ERA5 archive (no CDS key). Labels provenance honestly.
Does **not** invent ROS / Vp / transfer IoU.

  python scripts/align_latam_au_era5.py
  python scripts/align_latam_au_era5.py --skip-fetch
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    ERA5_ALIGN_SCHEMA,
    USER_AGENT,
    build_era5_request_template,
    pack_dir_for,
    utc_now,
    validate_era5_align,
)

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"


def _fetch_open_meteo(lat: float, lon: float, start: str, end: str, timeout: int = 45) -> dict[str, Any]:
    qs = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "start_date": start,
            "end_date": end,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
            "models": "era5",
            "timezone": "UTC",
        }
    )
    url = f"{OPEN_METEO}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def align_one(spec: dict[str, Any], data_root: Path, *, fetch: bool) -> dict[str, Any]:
    pack = pack_dir_for(data_root, spec)
    weather = pack / "weather"
    weather.mkdir(parents=True, exist_ok=True)
    tmpl = build_era5_request_template(spec)
    # Prefer pack bbox from meta if materialized
    meta_p = pack / "meta.json"
    if meta_p.is_file():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if meta.get("bbox_wgs84"):
                tmpl["bbox_wgs84"] = [float(x) for x in meta["bbox_wgs84"]]
                lon0 = (tmpl["bbox_wgs84"][0] + tmpl["bbox_wgs84"][2]) / 2.0
                lat0 = (tmpl["bbox_wgs84"][1] + tmpl["bbox_wgs84"][3]) / 2.0
                tmpl["centroid_lonlat"] = [lon0, lat0]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    (weather / "era5_request_template.json").write_text(json.dumps(tmpl, indent=2), encoding="utf-8")
    fetch_rec: dict[str, Any] = {
        "status": "skipped",
        "source": "open_meteo_era5_archive",
        "not_cds_era5_land_native": True,
        "error": "",
        "n_hourly": 0,
    }
    if fetch:
        lon, lat = tmpl["centroid_lonlat"]
        try:
            payload = _fetch_open_meteo(lat, lon, tmpl["date_start"], tmpl["date_end"])
            hourly = payload.get("hourly") or {}
            n = len(hourly.get("time") or [])
            out_json = weather / "open_meteo_era5_archive.json"
            slim = {
                "schema": "wfd_open_meteo_era5_archive_v1",
                "event_id": spec["event_id"],
                "latitude": payload.get("latitude"),
                "longitude": payload.get("longitude"),
                "elevation_m": payload.get("elevation"),
                "hourly": hourly,
                "not_cds_era5_land_native": True,
                "not_ros": True,
            }
            out_json.write_text(json.dumps(slim), encoding="utf-8")
            fetch_rec.update({"status": "ok", "n_hourly": n, "rel": "weather/open_meteo_era5_archive.json"})
        except Exception as exc:  # noqa: BLE001
            fetch_rec.update({"status": "gap", "error": f"{type(exc).__name__}:{exc}"})
            (weather / "ERA5_GAP.json").write_text(json.dumps(fetch_rec, indent=2), encoding="utf-8")

    doc = {
        "schema": ERA5_ALIGN_SCHEMA,
        "as_of_utc": utc_now(),
        "event_id": spec["event_id"],
        "pack_dir": str(pack.relative_to(ROOT)).replace("\\", "/") if pack.is_relative_to(ROOT) else str(pack),
        "request": tmpl,
        "fetch": fetch_rec,
        "not_ros": True,
        "not_tactical": True,
        "not_claims": [
            "not ROS / Vp",
            "not CDS ERA5-Land native unless nc present",
            "not transfer IoU",
        ],
    }
    fails = validate_era5_align(doc)
    if fails:
        raise RuntimeError(f"era5 align invalid: {fails}")
    (weather / "PROVENANCE.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")
    return {
        "event_id": spec["event_id"],
        "status": fetch_rec["status"] if fetch else "template_only",
        "n_hourly": fetch_rec["n_hourly"],
        "error": fetch_rec.get("error") or "",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Optional ERA5 align for LATAM/AU packs")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--skip-fetch", action="store_true")
    ap.add_argument("--only", action="append", default=None)
    ap.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au" / "inventories" / "era5_align_report.json",
    )
    args = ap.parse_args(argv)

    wanted = args.only or list(ALL_PACK_SPECS)
    rows: list[dict[str, Any]] = []
    for eid in wanted:
        spec = ALL_PACK_SPECS[eid]
        print(f"== {eid} ==", flush=True)
        try:
            rows.append(align_one(spec, args.data_root, fetch=not args.skip_fetch))
            print(f"  {rows[-1]['status']} n_hourly={rows[-1]['n_hourly']}", flush=True)
        except Exception as exc:  # noqa: BLE001
            rows.append({"event_id": eid, "status": "gap", "n_hourly": 0, "error": f"{type(exc).__name__}:{exc}"})
            print(f"  GAP {eid}: {rows[-1]['error']}", flush=True)

    report = {
        "schema": ERA5_ALIGN_SCHEMA,
        "as_of_utc": utc_now(),
        "n": len(rows),
        "n_ok": sum(1 for r in rows if r["status"] in {"ok", "template_only", "skipped"}),
        "packs": rows,
        "not_ros": True,
        "note": "Optional meteo only. Open-Meteo ERA5 archive is not CDS ERA5-Land native.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(args.report), "n_ok": report["n_ok"], "n": report["n"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
