#!/usr/bin/env python3
"""F2 / P1-A: materialize CEMS EMSR packs (≥3 dated GeoTIFF).

P0: EMSR500 Perth + EMSR647 Nacimiento.
P1-A: EMSR408 NSW Bendemeer + EMSR715 Valparaíso.

Downloads public CEMS vector zips / Rapid Mapping JSON, rasterizes
observedEvent polygons to GeoTIFF. Optionally windowed Sentinel-2 via STAC
(distinct calendar dates). Does not commit rasters. Does not flip GO_Q / FREEZE / fusion.

  python scripts/materialize_latam_au_emsr_packs.py
  python scripts/materialize_latam_au_emsr_packs.py --only AU_EMSR408_NSW --only CL_EMSR715_VALPARAISO
  python scripts/materialize_latam_au_emsr_packs.py --skip-stac
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    USER_AGENT,
    aligned_bounds_m,
    build_pack_meta,
    is_allowed_pack_path,
    load_observed_from_path,
    pack_dir_for,
    pack_readme,
    rasterize_geom_to_geotiff,
    sha256_file,
    try_stac_s2_windows,
    utc_now,
    validate_pack_meta,
)


def _download(url: str, dest: Path, *, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 200:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    print(f"  GET {url}", flush=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    return dest


def materialize_one(
    spec: dict[str, Any],
    *,
    data_root: Path,
    repo_root: Path,
    try_stac: bool,
) -> dict[str, Any]:
    pack_dir = pack_dir_for(data_root, spec)
    if not is_allowed_pack_path(pack_dir, repo_root=repo_root):
        raise RuntimeError(f"pack path not allowlisted: {pack_dir}")
    raw_dir = pack_dir / "raw_cems"
    labels_dir = pack_dir / "labels"
    eo_dir = pack_dir / "eo"
    for d in (raw_dir, labels_dir, eo_dir):
        d.mkdir(parents=True, exist_ok=True)

    loaded: list[dict[str, Any]] = []
    for prod in spec["products"]:
        url = str(prod["url"])
        fname = url.rsplit("/", 1)[-1]
        src_path = _download(url, raw_dir / fname)
        obs = load_observed_from_path(src_path)
        if obs is None and prod.get("zip_url"):
            zname = str(prod["zip_url"]).rsplit("/", 1)[-1]
            zpath = _download(str(prod["zip_url"]), raw_dir / zname)
            obs = load_observed_from_path(zpath)
            src_path = zpath
        if obs is None:
            raise RuntimeError(f"no observedEvent in {fname}")
        loaded.append({**prod, "zip": src_path, "obs": obs})
        print(f"  {prod['product_id']} area_ha={obs['area_ha']:.2f} {obs['member']}", flush=True)

    geoms = [row["obs"]["geometry"] for row in loaded]
    bounds_m = aligned_bounds_m(geoms, epsg=int(spec["crs_epsg"]))
    geotiffs: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []

    for row in loaded:
        tif_name = f"{spec['event_id']}_{row['dated']}.tif"
        dest = labels_dir / tif_name
        rast = rasterize_geom_to_geotiff(
            row["obs"]["geometry"],
            dest,
            epsg=int(spec["crs_epsg"]),
            gsd_m=float(spec["gsd_m"]),
            ref_bounds_m=bounds_m,
        )
        rec = {
            "rel": f"labels/{tif_name}",
            "file": tif_name,
            "role": "label_burned_cems_rasterized",
            "product_id": row["product_id"],
            "kind": row["kind"],
            "delivery_utc": row["delivery_utc"],
            "source_url": row["url"],
            "source_zip": Path(row["zip"]).name,
            "source_member": row["obs"]["member"],
            "area_ha": row["obs"]["area_ha"],
            "sha256": sha256_file(dest),
            "bytes": dest.stat().st_size,
            "crs": rast["crs"],
            "gsd_m": rast["gsd_m"],
            "width": rast["width"],
            "height": rast["height"],
            "positive_pixels": rast["positive_pixels"],
        }
        geotiffs.append(rec)
        labels.append(
            {
                "rel": rec["rel"],
                "kind": "cems_observed_event_raster",
                "vector_member": row["obs"]["member"],
            }
        )
        gj_name = f"{spec['event_id']}_{row['dated']}.geojson"
        from wildfire_front.open_if.latam_au import write_label_geojson

        write_label_geojson(
            row["obs"]["geometry"],
            pack_dir / "labels" / gj_name,
            {
                "event_id": spec["event_id"],
                "product_id": row["product_id"],
                "area_ha": row["obs"]["area_ha"],
                "source": "Copernicus EMS Rapid Mapping",
                "not_national_cadastre": True,
            },
        )
        labels.append({"rel": f"labels/{gj_name}", "kind": "cems_observed_event_geojson"})

    extra: dict[str, Any] = {
        "bbox_wgs84": list(unary_bounds(geoms)),
        "n_geotiff": len(geotiffs),
        "stac_eo": [],
        "geotiff_origin": "rasterized_cems_vector",
    }
    if try_stac:
        event_date = spec["products"][0]["delivery_utc"][:10]
        extra["stac_eo"] = try_stac_s2_windows(
            pack_dir, spec, tuple(extra["bbox_wgs84"]), event_date, max_cloud=60.0
        )
        for rec in extra["stac_eo"]:
            if rec.get("status") == "ok":
                print(f"  STAC {rec.get('role')} {rec.get('item_id')} -> {rec.get('file')}", flush=True)
            else:
                print(f"  STAC {rec.get('role') or '?'} {rec.get('status')}: {rec.get('reason') or rec.get('range')}", flush=True)
        if any(r.get("status") == "ok" for r in extra["stac_eo"]):
            extra["geotiff_origin"] = "rasterized_cems_vector+stac_s2_nbr"
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
    meta = build_pack_meta(spec, geotiffs=geotiffs, labels=labels, extra=extra)
    fails = validate_pack_meta(meta)
    if fails:
        raise RuntimeError(f"pack meta invalid: {fails}")
    (pack_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (pack_dir / "README.md").write_text(pack_readme(spec, meta), encoding="utf-8")
    return {"pack_dir": str(pack_dir), "meta": meta, "n_geotiff": len(geotiffs)}


def unary_bounds(geoms: list[Any]) -> tuple[float, float, float, float]:
    from shapely.ops import unary_union

    b = unary_union(geoms).bounds
    return float(b[0]), float(b[1]), float(b[2]), float(b[3])


def main() -> int:
    ap = argparse.ArgumentParser(description="Materialize LATAM/AU EMSR GeoTIFF packs")
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument("--skip-stac", action="store_true")
    ap.add_argument(
        "--only",
        choices=sorted(EMSR_PACK_SPECS),
        action="append",
        default=None,
    )
    args = ap.parse_args()

    wanted = args.only or list(EMSR_PACK_SPECS)
    reports: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for eid in wanted:
        spec = EMSR_PACK_SPECS[eid]
        print(f"== {eid} ==", flush=True)
        try:
            reports.append(
                materialize_one(
                    spec,
                    data_root=args.data_root,
                    repo_root=ROOT,
                    try_stac=not args.skip_stac,
                )
            )
        except Exception as exc:  # noqa: BLE001 — record honest GAP, do not invent pack
            rec = {
                "event_id": eid,
                "status": "gap",
                "error": f"{type(exc).__name__}:{exc}",
            }
            gaps.append(rec)
            print(f"  GAP {eid}: {rec['error']}", flush=True)
    summary = {
        "schema": "wfd_open_if_latam_au_materialize_v1",
        "built_at_utc": utc_now(),
        "packs": [
            {
                "event_id": r["meta"]["event_id"],
                "pack_dir": r["pack_dir"],
                "n_geotiff": r["n_geotiff"],
                "stac_ok": sum(1 for x in (r["meta"].get("stac_eo") or []) if x.get("status") == "ok"),
                "status": "ok",
            }
            for r in reports
        ],
        "gaps": gaps,
    }
    out = args.data_root / "MATERIALIZE_REPORT.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
