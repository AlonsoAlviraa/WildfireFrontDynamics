#!/usr/bin/env python3
"""P1-A/B: materialize MapBiomas + NAFI weak packs (≥3 dated GeoTIFF).

Uses downloaded annual rasters (or downloads them). Windows to event bbox.
On network / format fail writes honest GAP. Never invents transfer IoU.

  python scripts/materialize_latam_au_weak_packs.py
  python scripts/materialize_latam_au_weak_packs.py --skip-stac
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    USER_AGENT,
    WEAK_PACK_SPECS,
    build_pack_meta,
    is_allowed_pack_path,
    pack_dir_for,
    pack_readme,
    quote_http_url,
    sha256_file,
    try_stac_s2_windows,
    utc_now,
    validate_pack_meta,
    window_geotiff_to_bbox,
)


def _download(url: str, dest: Path, *, timeout: int = 300) -> Path:
    import urllib.request

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 200:
        return dest
    encoded = quote_http_url(url)
    req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    print(f"  GET {encoded}", flush=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    return dest


def _first_raster_in_zip(zpath: Path, extract_dir: Path) -> Path | None:
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath, "r") as zf:
        names = [n for n in zf.namelist() if n.lower().endswith((".tif", ".tiff", ".img", ".asc"))]
        if not names:
            return None
        # Prefer a tif covering NT / north AU if named; else first raster.
        names.sort(key=lambda n: (0 if any(k in n.lower() for k in ("nt", "north", "darwin")) else 1, n))
        chosen = names[0]
        dest = extract_dir / Path(chosen).name
        dest.write_bytes(zf.read(chosen))
        return dest


def materialize_mapbiomas(data_root: Path, repo_root: Path, try_stac: bool) -> dict[str, Any]:
    spec = WEAK_PACK_SPECS["BR_PANTANAL_2020_MAPBIOMAS"]
    pack_dir = pack_dir_for(data_root, spec)
    if not is_allowed_pack_path(pack_dir, repo_root=repo_root):
        raise RuntimeError(f"pack path not allowlisted: {pack_dir}")
    raw = pack_dir / "raw_mapbiomas"
    labels = pack_dir / "labels"
    raw.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    bbox = tuple(float(x) for x in spec["bbox_wgs84"])
    geotiffs: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    for prod in spec["products"]:
        year = int(str(prod["product_id"]).split("_")[-1])
        src = _download(prod["url"], raw / f"burned_area_{year}.tif")
        dest = labels / f"{spec['event_id']}_{prod['dated']}.tif"
        rast = window_geotiff_to_bbox(src, dest, bbox)
        rec = {
            "rel": f"labels/{dest.name}",
            "file": dest.name,
            "role": "label_burned_mapbiomas_annual",
            "product_id": prod["product_id"],
            "kind": prod["kind"],
            "delivery_utc": prod["delivery_utc"],
            "source_url": prod["url"],
            "sha256": sha256_file(dest),
            "bytes": dest.stat().st_size,
            "crs": rast["crs"],
            "width": rast["width"],
            "height": rast["height"],
            "positive_pixels": rast["positive_pixels"],
            "note": "National annual burned raster windowed to Pantanal bbox. L1 weak.",
        }
        geotiffs.append(rec)
        label_rows.append({"rel": rec["rel"], "kind": "mapbiomas_annual_burned_window"})
        print(f"  MapBiomas {year} +pix={rast['positive_pixels']} {dest.name}", flush=True)
    extra: dict[str, Any] = {
        "bbox_wgs84": list(bbox),
        "n_geotiff": len(geotiffs),
        "stac_eo": [],
        "geotiff_origin": "mapbiomas_fogo_col5_windowed",
        "sensor": "MapBiomas Fogo Collection 5 annual burned (windowed)",
        "license_id": spec["license_id"],
    }
    if try_stac:
        extra["stac_eo"] = try_stac_s2_windows(pack_dir, spec, list(bbox), "2020-08-01")
        for rec in extra["stac_eo"]:
            if rec.get("status") == "ok":
                print(f"  STAC {rec.get('role')} {rec.get('item_id')} -> {rec.get('file')}", flush=True)
            else:
                print(f"  STAC {rec.get('role') or '?'} {rec.get('status')}: {rec.get('reason') or rec.get('range')}", flush=True)
        for rec in extra["stac_eo"]:
            if rec.get("status") == "ok" and rec.get("rel"):
                geotiffs.append(
                    {
                        "rel": rec["rel"],
                        "file": rec.get("file"),
                        "role": rec.get("role"),
                        "delivery_utc": rec.get("datetime"),
                        "sha256": rec.get("sha256"),
                        "bytes": rec.get("bytes"),
                        "crs": rec.get("crs"),
                        "sensor": rec.get("sensor"),
                    }
                )
    extra["n_geotiff"] = len(geotiffs)
    meta = build_pack_meta(spec, geotiffs=geotiffs, labels=label_rows, extra=extra)
    fails = validate_pack_meta(meta)
    if fails:
        raise RuntimeError(f"pack meta invalid: {fails}")
    (pack_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (pack_dir / "README.md").write_text(pack_readme(spec, meta), encoding="utf-8")
    return {"pack_dir": str(pack_dir), "meta": meta, "n_geotiff": len(geotiffs)}


def materialize_nafi(data_root: Path, repo_root: Path, try_stac: bool) -> dict[str, Any]:
    spec = WEAK_PACK_SPECS["AU_NAFI_NT_SEASON_2023"]
    pack_dir = pack_dir_for(data_root, spec)
    if not is_allowed_pack_path(pack_dir, repo_root=repo_root):
        raise RuntimeError(f"pack path not allowlisted: {pack_dir}")
    raw = pack_dir / "raw_nafi"
    labels = pack_dir / "labels"
    raw.mkdir(parents=True, exist_ok=True)
    labels.mkdir(parents=True, exist_ok=True)
    bbox = tuple(float(x) for x in spec["bbox_wgs84"])
    geotiffs: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    for prod in spec["products"]:
        year = int(str(prod["product_id"]).split("_")[-1])
        zpath = _download(prod["url"], raw / f"nafi_{year}_image.zip")
        extracted = _first_raster_in_zip(zpath, raw / f"extract_{year}")
        if extracted is None:
            raise RuntimeError(f"no raster member in NAFI zip {zpath.name}")
        dest = labels / f"{spec['event_id']}_{prod['dated']}.tif"
        rast = window_geotiff_to_bbox(extracted, dest, bbox)
        rec = {
            "rel": f"labels/{dest.name}",
            "file": dest.name,
            "role": "label_burned_nafi_annual",
            "product_id": prod["product_id"],
            "kind": prod["kind"],
            "delivery_utc": prod["delivery_utc"],
            "source_url": prod["url"],
            "source_zip": zpath.name,
            "source_member": extracted.name,
            "sha256": sha256_file(dest),
            "bytes": dest.stat().st_size,
            "crs": rast["crs"],
            "width": rast["width"],
            "height": rast["height"],
            "positive_pixels": rast["positive_pixels"],
            "note": "NAFI 250m annual scar windowed to Darwin/NT bbox. L1 weak.",
        }
        geotiffs.append(rec)
        label_rows.append({"rel": rec["rel"], "kind": "nafi_annual_scar_window"})
        print(f"  NAFI {year} +pix={rast['positive_pixels']} {dest.name}", flush=True)
    extra: dict[str, Any] = {
        "bbox_wgs84": list(bbox),
        "n_geotiff": len(geotiffs),
        "stac_eo": [],
        "geotiff_origin": "nafi_annual_windowed",
        "sensor": "NAFI 250m fire scars (windowed)",
        "license_id": spec["license_id"],
    }
    if try_stac:
        extra["stac_eo"] = try_stac_s2_windows(pack_dir, spec, list(bbox), "2023-08-01")
        for rec in extra["stac_eo"]:
            if rec.get("status") == "ok":
                print(f"  STAC {rec.get('role')} {rec.get('item_id')} -> {rec.get('file')}", flush=True)
            else:
                print(f"  STAC {rec.get('role') or '?'} {rec.get('status')}: {rec.get('reason') or rec.get('range')}", flush=True)
        for rec in extra["stac_eo"]:
            if rec.get("status") == "ok" and rec.get("rel"):
                geotiffs.append(
                    {
                        "rel": rec["rel"],
                        "file": rec.get("file"),
                        "role": rec.get("role"),
                        "delivery_utc": rec.get("datetime"),
                        "sha256": rec.get("sha256"),
                        "bytes": rec.get("bytes"),
                        "crs": rec.get("crs"),
                        "sensor": rec.get("sensor"),
                    }
                )
    extra["n_geotiff"] = len(geotiffs)
    meta = build_pack_meta(spec, geotiffs=geotiffs, labels=label_rows, extra=extra)
    fails = validate_pack_meta(meta)
    if fails:
        raise RuntimeError(f"pack meta invalid: {fails}")
    (pack_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (pack_dir / "README.md").write_text(pack_readme(spec, meta), encoding="utf-8")
    return {"pack_dir": str(pack_dir), "meta": meta, "n_geotiff": len(geotiffs)}


def main() -> int:
    ap = argparse.ArgumentParser(description="Materialize MapBiomas/NAFI weak packs")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--skip-stac", action="store_true")
    ap.add_argument("--only", choices=sorted(WEAK_PACK_SPECS), action="append", default=None)
    args = ap.parse_args()

    wanted = args.only or list(WEAK_PACK_SPECS)
    reports: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    runners = {
        "BR_PANTANAL_2020_MAPBIOMAS": materialize_mapbiomas,
        "AU_NAFI_NT_SEASON_2023": materialize_nafi,
    }
    for eid in wanted:
        print(f"== {eid} ==", flush=True)
        try:
            reports.append(runners[eid](args.data_root, ROOT, not args.skip_stac))
        except Exception as exc:  # noqa: BLE001
            rec = {"event_id": eid, "status": "gap", "error": f"{type(exc).__name__}:{exc}"}
            gaps.append(rec)
            print(f"  GAP {eid}: {rec['error']}", flush=True)
            gap_dir = pack_dir_for(args.data_root, WEAK_PACK_SPECS[eid])
            gap_dir.mkdir(parents=True, exist_ok=True)
            (gap_dir / "GAP.json").write_text(json.dumps({**rec, "as_of_utc": utc_now()}, indent=2), encoding="utf-8")

    pack_rows: dict[str, dict[str, Any]] = {}
    prev_path = args.data_root / "WEAK_MATERIALIZE_REPORT.json"
    if prev_path.is_file():
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
            for rec in prev.get("packs") or []:
                eid = rec.get("event_id")
                if eid:
                    pack_rows[str(eid)] = rec
        except (OSError, json.JSONDecodeError):
            pass
    for r in reports:
        pack_rows[r["meta"]["event_id"]] = {
            "event_id": r["meta"]["event_id"],
            "pack_dir": r["pack_dir"],
            "n_geotiff": r["n_geotiff"],
            "status": "ok",
        }
    summary = {
        "schema": "wfd_open_if_latam_au_weak_materialize_v1",
        "built_at_utc": utc_now(),
        "packs": list(pack_rows.values()),
        "gaps": gaps,
        "not_claims": ["not transfer IoU", "not ROS", "not ml_strong", "not GO_Q complete"],
    }
    out = args.data_root / "WEAK_MATERIALIZE_REPORT.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if reports else 2


if __name__ == "__main__":
    raise SystemExit(main())
