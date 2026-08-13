"""PT-FireSprd L1 progression ingest (open CC-BY; not product ROS).

Parses per-fire shapefile progressions, evaluates GEOTIFF_INPUT_CONTRACT R1
(≥3 dated aligned scenes), and optionally rasterizes a common grid.

Author L2/L3 ros_* fields are inventoried as dataset attributes only.
Timestamps are copied from source ``date_hour``; timezone is unspecified
in the shapefile and is not invented.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

from .external_ros import PACK_CATALOG, extracted_root, sha256_file, utc_now
from .latam_au import dated_geotiff_ok

PT_DATE_RE = re.compile(r"^(20\d{2})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?$")
BAD_DATE_TOKENS = frozenset({"", "na", "n/a", "uncertain", "none", "null"})
INGEST_SCHEMA = "wfd_pt_firesprd_ingest_v1"
DEFAULT_EPSG = 32629  # WGS_1984_UTM_Zone_29N as written in L1 .prj
DEFAULT_GSD_M = 30.0
MAX_RASTER_DIM = 2048
PERIMETER_TYPES = frozenset({"p", "z"})


def parse_date_hour(raw: Any) -> dict[str, Any] | None:
    """Parse source date_hour. Returns None instead of inventing a stamp."""
    text = str(raw or "").strip()
    if text.lower() in BAD_DATE_TOKENS:
        return None
    match = PT_DATE_RE.match(text)
    if not match:
        return None
    year, month, day, hour, minute, second = match.groups()
    second = second or "00"
    naive = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
    stamp = naive.strftime("%Y%m%d_%H%M%S")
    return {
        "raw": text,
        "naive": naive.isoformat(sep="T"),
        "filename_stamp": stamp,
        "tz": "unspecified_in_source",
        "not_verified_utc": True,
    }


def epsg_from_prj(text: str) -> int | None:
    compact = re.sub(r"[\s_]+", "_", text.upper())
    if "UTM" in compact and "ZONE_29N" in compact:
        return 32629
    if "UTM" in compact and "ZONE_29S" in compact:
        return 32729
    if "GCS_WGS_1984" in compact or 'GEOGCS["WGS_84"' in compact:
        return 4326
    return None


def _require_shapefile():
    try:
        import shapefile
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyshp_missing") from exc
    return shapefile


def list_l1_shapefiles(extracted: Path) -> list[Path]:
    root = extracted / "PT-FireSprd_v0.08" / "L1_FireProgressions"
    if not root.is_dir():
        # zip may flatten differently
        hits = sorted(extracted.rglob("progression_*.shp"))
        return hits
    return sorted(root.rglob("progression_*.shp"))


def _valid_geom(geom: Any) -> Any | None:
    if geom is None or geom.is_empty:
        return None
    try:
        if geom.is_valid:
            return geom
    except Exception:
        pass
    for fixer in (
        lambda g: g.buffer(0),
        lambda g: getattr(g, "make_valid", lambda: None)(),
    ):
        try:
            fixed = fixer(geom)
        except Exception:
            continue
        if fixed is not None and not fixed.is_empty:
            return fixed
    return None


def _safe_union(geoms: list[Any]) -> Any | None:
    cleaned = []
    for geom in geoms:
        fixed = _valid_geom(geom)
        if fixed is not None:
            cleaned.append(fixed)
    if not cleaned:
        return None
    try:
        union = unary_union(cleaned)
    except Exception:
        acc = cleaned[0]
        for geom in cleaned[1:]:
            try:
                acc = acc.union(geom)
            except Exception:
                continue
        union = acc
    return _valid_geom(union)


def _shape_to_geom(shp_obj: Any) -> Any | None:
    try:
        geo = shp_obj.__geo_interface__
    except Exception:
        return None
    if not geo or geo.get("type") in {None, "Null", "null"}:
        return None
    try:
        geom = shape(geo)
    except Exception:
        return None
    if geom is None or geom.is_empty:
        return None
    return geom


def load_l1_features(shp_path: Path) -> dict[str, Any]:
    shapefile = _require_shapefile()
    reader = shapefile.Reader(str(shp_path))
    prj_path = shp_path.with_suffix(".prj")
    prj_text = prj_path.read_text(encoding="utf-8", errors="replace") if prj_path.is_file() else ""
    epsg = epsg_from_prj(prj_text) if prj_text else None
    features: list[dict[str, Any]] = []
    # Index access: iterShapeRecords() raises KeyError on several L1 files (pyshp 3.1).
    n_rec = int(getattr(reader, "numRecords", 0) or 0)
    for idx in range(n_rec):
        try:
            sr = reader.shapeRecord(idx)
        except Exception:
            continue
        rec = sr.record.as_dict() if hasattr(sr.record, "as_dict") else {}
        geom = _valid_geom(_shape_to_geom(sr.shape))
        parsed = parse_date_hour(rec.get("date_hour"))
        area_m2 = float(geom.area) if geom is not None and epsg and epsg != 4326 else None
        features.append(
            {
                "id": rec.get("id"),
                "type": str(rec.get("type") or "").strip().lower(),
                "date_hour_raw": rec.get("date_hour"),
                "source": rec.get("source"),
                "parsed": parsed,
                "geom": geom,
                "area_m2": area_m2,
            }
        )
    return {
        "shp": shp_path,
        "n_records": len(features),
        "epsg": epsg,
        "prj": prj_text[:240] if prj_text else None,
        "bbox": list(reader.bbox) if reader.bbox else None,
        "features": features,
    }


def scenes_from_features(
    loaded: dict[str, Any],
    *,
    types: frozenset[str] = PERIMETER_TYPES,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for feat in loaded.get("features") or []:
        parsed = feat.get("parsed")
        if not parsed:
            continue
        geom = feat.get("geom")
        if geom is None or geom.is_empty:
            continue
        ftype = str(feat.get("type") or "")
        if types and ftype not in types:
            continue
        stamp = parsed["filename_stamp"]
        grouped.setdefault(stamp, []).append(geom)
        meta.setdefault(
            stamp,
            {
                "filename_stamp": stamp,
                "date_hour_raw": parsed["raw"],
                "naive": parsed["naive"],
                "tz": parsed["tz"],
                "not_verified_utc": True,
                "types": set(),
                "n_parts": 0,
            },
        )
        meta[stamp]["types"].add(ftype)
        meta[stamp]["n_parts"] += 1
    scenes: list[dict[str, Any]] = []
    epsg = loaded.get("epsg")
    for stamp in sorted(grouped):
        union = _safe_union(grouped[stamp])
        if union is None or union.is_empty:
            continue
        rec = dict(meta[stamp])
        rec["types"] = sorted(rec["types"])
        rec["geom"] = union
        rec["area_m2"] = float(union.area) if epsg and epsg != 4326 else None
        rec["area_ha_from_vector"] = (
            float(union.area) / 10_000.0 if rec["area_m2"] is not None else None
        )
        rec["area_ha_is_vector_proxy"] = True
        rec["not_official_ha"] = True
        scenes.append(rec)
    return scenes


def evaluate_r1_contract(scenes: list[dict[str, Any]], *, epsg: int | None) -> dict[str, Any]:
    stamps = [s.get("filename_stamp") or "" for s in scenes]
    dated_ok = [s for s in scenes if dated_geotiff_ok(str(s.get("filename_stamp") or ""))]
    r1 = len(dated_ok) >= 3
    r2 = any(s.get("geom") is not None for s in scenes)
    r3 = epsg is not None and all(s.get("filename_stamp") for s in dated_ok)
    return {
        "R1_ge3_dated_scenes": r1,
        "R2_usable_geometry": r2,
        "R3_crs_and_dates": bool(r3),
        "R4_license_open": True,
        "n_dated_scenes": len(dated_ok),
        "n_scenes": len(scenes),
        "stamps": stamps,
        "epsg": epsg,
        "meets_geotiff_r1": r1 and r2 and r3,
        "skip_reason": None
        if (r1 and r2 and r3)
        else ("r1_lt_3_dated" if not r1 else ("no_geometry" if not r2 else "missing_crs_or_dates")),
    }


def _rel_or_posix(path: Path) -> str:
    text = str(path).replace("\\", "/")
    marker = "/data/external/"
    if marker in text:
        return "data/external/" + text.split(marker, 1)[1]
    return text


def inventory_one_fire(shp_path: Path) -> dict[str, Any]:
    year = shp_path.parent.parent.name
    fire_id = shp_path.parent.name
    shp_rel = _rel_or_posix(shp_path)
    try:
        loaded = load_l1_features(shp_path)
        scenes = scenes_from_features(loaded)
        contract = evaluate_r1_contract(scenes, epsg=loaded.get("epsg"))
    except Exception as exc:
        return {
            "fire_id": fire_id,
            "year": year,
            "shp": shp_rel,
            "ok": False,
            "reason": f"{type(exc).__name__}:{exc}",
        }
    type_counts: dict[str, int] = {}
    n_unparsed = 0
    for feat in loaded["features"]:
        key = str(feat.get("type") or "?")
        type_counts[key] = type_counts.get(key, 0) + 1
        if feat.get("parsed") is None:
            n_unparsed += 1
    return {
        "fire_id": fire_id,
        "year": year,
        "shp": shp_rel,
        "ok": True,
        "n_records": loaded["n_records"],
        "n_unparsed_date_hour": n_unparsed,
        "type_counts": type_counts,
        "epsg": loaded.get("epsg"),
        "bbox": loaded.get("bbox"),
        "n_dated_scenes": contract["n_dated_scenes"],
        "meets_geotiff_r1": contract["meets_geotiff_r1"],
        "skip_reason": contract["skip_reason"],
        "stamps": contract["stamps"],
    }


def inventory_l1_pack(extracted: Path) -> dict[str, Any]:
    shps = list_l1_shapefiles(extracted)
    fires = [inventory_one_fire(p) for p in shps]
    ok_fires = [f for f in fires if f.get("ok")]
    return {
        "schema": "wfd_pt_firesprd_l1_inventory_v1",
        "as_of_utc": utc_now(),
        "n_shapefiles": len(shps),
        "n_fires_ok": len(ok_fires),
        "n_fires_r1": sum(1 for f in ok_fires if f.get("meets_geotiff_r1")),
        "license_id": PACK_CATALOG["pt_firesprd"]["license_id"],
        "doi": PACK_CATALOG["pt_firesprd"]["resolved_doi"],
        "dataset_l2_l3_ros_fields_are_author_attributes": True,
        "not_product_ros": True,
        "fires": fires,
    }


def select_ingest_fire(fires: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Deterministic pick: R1-capable, prefer 4–12 scenes, then fewest records."""
    candidates = [f for f in fires if f.get("meets_geotiff_r1") and f.get("ok")]
    if not candidates:
        return None

    def _key(row: dict[str, Any]) -> tuple[int, int, int, str]:
        n = int(row.get("n_dated_scenes") or 0)
        in_band = 0 if 4 <= n <= 12 else 1
        return (in_band, abs(n - 8), int(row.get("n_records") or 0), str(row.get("fire_id")))

    return sorted(candidates, key=_key)[0]


def aligned_bounds(
    scenes: list[dict[str, Any]], *, pad_m: float
) -> tuple[float, float, float, float]:
    union = unary_union([s["geom"] for s in scenes if s.get("geom") is not None])
    minx, miny, maxx, maxy = union.bounds
    return (minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m)


def rasterize_projected(
    geom: Any,
    dest: Path,
    *,
    epsg: int,
    gsd_m: float,
    ref_bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    import numpy as np
    import rasterio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    dest.parent.mkdir(parents=True, exist_ok=True)
    minx, miny, maxx, maxy = ref_bounds
    width = max(8, int(math.ceil((maxx - minx) / gsd_m)))
    height = max(8, int(math.ceil((maxy - miny) / gsd_m)))
    used_gsd = float(gsd_m)
    if width > MAX_RASTER_DIM or height > MAX_RASTER_DIM:
        scale = max(width / MAX_RASTER_DIM, height / MAX_RASTER_DIM)
        used_gsd = gsd_m * scale
        width = max(8, int(math.ceil((maxx - minx) / used_gsd)))
        height = max(8, int(math.ceil((maxy - miny) / used_gsd)))
    transform_aff = from_origin(minx, maxy, used_gsd, used_gsd)
    burned = rasterize(
        [(geom, 1)],
        out_shape=(height, width),
        transform=transform_aff,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    with rasterio.open(
        dest,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=f"EPSG:{int(epsg)}",
        transform=transform_aff,
        compress="deflate",
        nodata=0,
    ) as ds:
        ds.write(np.asarray(burned, dtype="uint8"), 1)
        ds.update_tags(
            source="PT-FireSprd L1 progression (rasterized vector)",
            license_id="cc-by-4.0",
            timestamp_tz="unspecified_in_source",
            not_official_cadastre="true",
            not_product_ros="true",
        )
    return {
        "path": str(dest),
        "file": dest.name,
        "crs": f"EPSG:{int(epsg)}",
        "gsd_m": float(used_gsd),
        "width": int(width),
        "height": int(height),
        "positive_pixels": int(burned.sum()),
        "sha256": sha256_file(dest),
        "bytes": int(dest.stat().st_size),
        "transform": [
            float(transform_aff.a),
            float(transform_aff.b),
            float(transform_aff.c),
            float(transform_aff.d),
            float(transform_aff.e),
            float(transform_aff.f),
        ],
    }


def scenes_aligned(rasters: list[dict[str, Any]]) -> bool:
    if len(rasters) < 2:
        return len(rasters) >= 1
    key = (rasters[0]["width"], rasters[0]["height"], rasters[0]["crs"], rasters[0]["gsd_m"])
    return all((r["width"], r["height"], r["crs"], r["gsd_m"]) == key for r in rasters)


def write_scene_geojson(scene: dict[str, Any], dest: Path, *, fire_id: str, epsg: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    geom = scene["geom"]
    if epsg != 4326:
        from pyproj import Transformer
        from shapely.ops import transform as shp_transform

        tf = Transformer.from_crs(f"EPSG:{int(epsg)}", "EPSG:4326", always_xy=True)

        def _proj(x: float, y: float, z: float | None = None) -> tuple[float, float]:
            return tf.transform(x, y)

        geom = shp_transform(_proj, geom)
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "fire_id": fire_id,
                    "date_hour_raw": scene.get("date_hour_raw"),
                    "filename_stamp": scene.get("filename_stamp"),
                    "area_ha_from_vector": scene.get("area_ha_from_vector"),
                    "not_official_ha": True,
                    "not_product_ros": True,
                    "crs_source": f"EPSG:{int(epsg)}",
                    "geojson_crs": "EPSG:4326",
                },
                "geometry": mapping(geom),
            }
        ],
    }
    dest.write_text(json.dumps(fc), encoding="utf-8")


def materialize_geotiff_scenes(
    shp_path: Path,
    out_dir: Path,
    *,
    max_scenes: int = 8,
    gsd_m: float = DEFAULT_GSD_M,
) -> dict[str, Any]:
    loaded = load_l1_features(shp_path)
    scenes = scenes_from_features(loaded)
    contract = evaluate_r1_contract(scenes, epsg=loaded.get("epsg"))
    fire_id = shp_path.parent.name
    if not contract["meets_geotiff_r1"]:
        return {
            "schema": INGEST_SCHEMA,
            "ok": False,
            "fire_id": fire_id,
            "reason": contract["skip_reason"],
            "contract": contract,
        }
    epsg = int(loaded["epsg"] or DEFAULT_EPSG)
    if len(scenes) > max_scenes:
        # keep temporal ends + evenly spaced middles
        idxs = sorted(
            {
                0,
                len(scenes) - 1,
                *[round(i * (len(scenes) - 1) / (max_scenes - 1)) for i in range(max_scenes)],
            }
        )[:max_scenes]
        scenes = [scenes[i] for i in idxs]
    bounds = aligned_bounds(scenes, pad_m=300.0)
    images = out_dir / "images"
    masks = out_dir / "masks"
    labels = out_dir / "labels"
    geotiffs: list[dict[str, Any]] = []
    for scene in scenes:
        fname = f"{fire_id}_{scene['filename_stamp']}.tif"
        img_path = images / fname
        rast = rasterize_projected(
            scene["geom"], img_path, epsg=epsg, gsd_m=gsd_m, ref_bounds=bounds
        )
        mask_path = masks / fname
        mask_path.parent.mkdir(parents=True, exist_ok=True)
        mask_path.write_bytes(img_path.read_bytes())
        write_scene_geojson(
            scene, labels / fname.replace(".tif", ".geojson"), fire_id=fire_id, epsg=epsg
        )
        geotiffs.append(
            {
                **{k: v for k, v in rast.items() if k != "path"},
                "rel_image": f"images/{fname}",
                "rel_mask": f"masks/{fname}",
                "role": "label_burned_pt_firesprd_rasterized",
                "date_hour_raw": scene.get("date_hour_raw"),
                "filename_stamp": scene.get("filename_stamp"),
                "area_ha_from_vector": scene.get("area_ha_from_vector"),
                "positive_pixels": rast["positive_pixels"],
            }
        )
    aligned = scenes_aligned(geotiffs)
    meta = {
        "schema": INGEST_SCHEMA,
        "fire_id": fire_id,
        "source_shp": str(shp_path).replace("\\", "/"),
        "license_id": "cc-by-4.0",
        "doi": PACK_CATALOG["pt_firesprd"]["resolved_doi"],
        "crs": f"EPSG:{epsg}",
        "gsd_m": geotiffs[0]["gsd_m"] if geotiffs else gsd_m,
        "n_scenes": len(geotiffs),
        "aligned": aligned,
        "timestamp_tz": "unspecified_in_source",
        "not_verified_utc": True,
        "not_official_ha": True,
        "not_product_ros": True,
        "not_lwir": True,
        "not_grade_a": True,
        "not_tactical_dispatch": True,
        "class": "ml_weak",
        "geotiffs": geotiffs,
        "contract": {**contract, "n_rasterized": len(geotiffs), "aligned": aligned},
        "built_at_utc": utc_now(),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"ok": True, "fire_id": fire_id, "out_dir": str(out_dir), "meta": meta}


def run_geotiff_ingest(out_dir: Path, *, fire_id: str) -> dict[str, Any]:
    from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence

    images = out_dir / "images"
    masks = out_dir / "masks"
    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=fire_id,
        sensor_id="pt_firesprd_l1_vector_raster",
        estimated_error_m=30.0,
    )
    records = [
        {
            "source_path": rec.source_path,
            "status": rec.status,
            "reason": rec.reason,
            "observed_at": rec.observed_at,
            "crs": rec.crs,
            "component_count": rec.component_count,
        }
        for rec in result.records
    ]
    n_accepted = sum(1 for rec in result.records if rec.status == "accepted")
    return {
        "ok": n_accepted >= 3 and len(result.observations) >= 3,
        "n_records": len(result.records),
        "n_accepted": n_accepted,
        "n_observations": len(result.observations),
        "records": records,
        "note": (
            "ingest treats filename stamps as UTC by GEOTIFF_INPUT_CONTRACT; "
            "source date_hour TZ is unspecified and was not invented."
        ),
    }


def write_decide_open_pack(
    ingest_dir: Path,
    out_pack: Path,
    *,
    fire_id: str,
) -> dict[str, Any]:
    """Bridge rasterized PT-FireSprd scenes to decide's scorecard_pista_b loader.

    The product source id stays ``open_cems_perimeter`` (existing adapter name).
    This pack is PT-FireSprd L1 proxy, not CEMS / ES cadastre.
    """
    meta_path = ingest_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    geotiffs = meta.get("geotiffs") or []
    areas = [
        float(g["area_ha_from_vector"])
        for g in geotiffs
        if g.get("area_ha_from_vector") is not None
    ]
    max_area = max(areas) if areas else 0.0
    out_pack.mkdir(parents=True, exist_ok=True)
    vec_dir = out_pack / "vectors"
    vec_dir.mkdir(exist_ok=True)
    features: list[dict[str, Any]] = []
    for i, rec in enumerate(geotiffs):
        src = (
            ingest_dir
            / "labels"
            / Path(str(rec.get("rel_image") or "")).name.replace(".tif", ".geojson")
        )
        if not src.is_file():
            continue
        dest = vec_dir / f"{fire_id}_{rec.get('filename_stamp')}.geojson"
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        fc = json.loads(dest.read_text(encoding="utf-8"))
        for feat in fc.get("features") or []:
            if isinstance(feat, dict):
                feat.setdefault("properties", {})
                if isinstance(feat["properties"], dict):
                    feat["properties"]["timeline_index"] = i
                features.append(feat)
    (out_pack / "timeline_perimeters.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2),
        encoding="utf-8",
    )
    score = {
        "track": "Pista_B",
        "activation": f"PT_FIRESPRD_{fire_id}",
        "pack_id": fire_id,
        "event_id": fire_id,
        "region": "pt",
        "country": "PT",
        "max_area_ha": max_area,
        "n_timeline_steps": len(geotiffs),
        "n_ros_proxy_steps": max(0, len(geotiffs) - 1),
        "O2_cems_delineation": "NO_GO_NOT_CEMS",
        "O2_national_official": "NO_GO_PT_FIRESPRD_PROXY",
        "lwir_heligraphics": False,
        "status": "GO_OPEN_DATA_PACK",
        "decision_open": "HOLD",
        "decision_open_note": (
            "PT-FireSprd L1 vector progressions rasterized for lab decide path. "
            "Not CEMS, not official cadastre, not ops ROS, not tactical dispatch. "
            "decide source id open_cems_perimeter is the existing adapter name."
        ),
        "not_tactical_dispatch": True,
        "not_ops_ros": True,
        "ros_is_proxy_only": True,
        "vp_invented": False,
        "firms_hull_is_official_burned_area": False,
        "not_national_cadastre": True,
        "not_o2_es": True,
        "source": "pt_firesprd_l1",
        "license_id": "cc-by-4.0",
        "bridge": "pt_firesprd_to_open_if_v1",
    }
    (out_pack / "scorecard_pista_b.json").write_text(json.dumps(score, indent=2), encoding="utf-8")
    (out_pack / "source_meta.json").write_text(
        json.dumps(
            {
                "schema": "wfd_pt_firesprd_bridge_source_v1",
                "source_pack": str(ingest_dir).replace("\\", "/"),
                "event_id": fire_id,
                "built_at_utc": utc_now(),
                "not_cems": True,
                "not_product_ros": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"ok": True, "out_pack": str(out_pack).replace("\\", "/"), "scorecard": score}


def default_extracted(repo_root: Path) -> Path:
    return extracted_root(repo_root, "pt_firesprd")
