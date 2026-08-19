#!/usr/bin/env python3
"""Honest same-fire multi-geometry eval on on-disk dated outlines.

One fire + one AOI. Vector copy IoU via shapely; model IoU is frozen complete-proxy
UNet on rasterized labels (CEMS/Tobarra) or Caldor physical→legacy17. Not official
LATAM complete-proxy and not sealed transfer.

  python scripts/run_same_fire_multi_geometry.py
  python scripts/run_same_fire_multi_geometry.py --fire EMSR578_AOI01
  python scripts/run_same_fire_multi_geometry.py --fire US_FIREBENCH_CALDOR_2021 --require-model-iou

Exit:
  0 — wrote additional artifacts
  1 — --require-model-iou but weights file missing
  2 — --require-model-iou but a selected fire still has no UNet score
  3 — missing / unknown / official-LATAM fire id
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from shapely.geometry import shape  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from scripts.run_latam_au_more_data_iou import (  # noqa: E402
    OFFICIAL_JSON,
    OFFICIAL_LATAM_COMPLETE_PROXY_IDS,
    rel_to_root,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    classify_temporal_pair,
    hours_between,
    mean_usable_pair_ious,
    parse_iso_utc,
)
from wildfire_front.open_if.same_fire_model import (  # noqa: E402
    aoi_ref_geom,
    binary_iou,
    caldor_cov_at,
    default_same_fire_weights,
    load_frozen_unet,
    load_tif,
    oracle_pair_iou,
    point_cov_for_recs,
    rasterize_records,
    score_caldor_pair,
    score_pairs_with_masks,
    summarize_model_scores,
)

SCHEMA = "wfd_same_fire_multi_geometry_v1"
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire"
PRODUCT_WEIGHTS = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"

EXIT_OK = 0
EXIT_MISSING_WEIGHTS = 1
EXIT_INCOMPATIBLE_SCHEMA = 2
EXIT_MISSING_DATA = 3

CEST = timezone(timedelta(hours=2))

DEFAULT_FIRE_IDS = (
    "EMSR578_AOI01",
    "EMSR632_AOI01",
    "EMSR898_AOI01",
    "TOBARRA_20240802",
    "US_FIREBENCH_CALDOR_2021",
)

ISOLATION_FIRE_IDS = (
    "EMSR578_AOI02",
    "EMSR898_AOI02",
)

NOT_CLAIMS = (
    "additional same-fire multi-geometry eval — not official LATAM complete-proxy",
    "not sealed transfer IoU",
    "not GO_Q complete",
    "not clm_ensemble_v34",
    "not catalog 0.8963",
    "not U1 TEST CLM (0.857)",
    "lab_ok_conaf remains false",
    "FEP/GRA pairs never enter a usable-growth mean",
    "distinct CEMS AOIs of the same EMSR are not chained",
    "families are not averaged together",
    "same-fire model IoU is frozen complete-proxy decode on rasterized labels + legacy17 fill — not sealed transfer",
    "Caldor uses physical HRRR/3DEP/LANDFIRE mapped through build_legacy17_channels; 21ch tensors are not fed raw",
    "full-product GeoJSON >2MB is not shapely-unioned; 898 rasters from raw observedEvent JSON",
)

KIND_FROM_TOKEN = (
    ("DEL_MONIT", "delineation_monitoring"),
    ("FEP_", "first_estimate"),
    ("GRA_", "grading"),
    ("DEL_PRODUCT", "delineation"),
    ("DEL_", "delineation"),
)


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fire", action="append", dest="fire_ids", default=None)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--weights", type=Path, default=None)
    ap.add_argument(
        "--require-model-iou",
        action="store_true",
        help="Fail if a selected fire cannot run the frozen UNet.",
    )
    ap.add_argument(
        "--include-isolation-aois",
        action="store_true",
        help="Also emit sibling AOI rows (not merged into AOI01 usable means).",
    )
    ap.add_argument("--max-patches", type=int, default=32)
    ap.add_argument("--max-pairs", type=int, default=None)
    ap.add_argument(
        "--meteo-mode",
        choices=("fetch", "constant"),
        default="fetch",
        help="Point meteo for rasterized CEMS/Tobarra (Caldor always uses on-disk HRRR).",
    )
    return ap


def parse_aoi_token(name: str) -> str | None:
    hit = re.search(r"AOI(\d+)", str(name), flags=re.I)
    if not hit:
        return None
    return f"AOI{int(hit.group(1)):02d}"


def parse_product_kind(name: str) -> str | None:
    upper = str(name).upper()
    for token, kind in KIND_FROM_TOKEN:
        if token in upper:
            return kind
    return None


def parse_monit_number(name: str) -> int:
    hit = re.search(r"MONIT(\d+)", str(name), flags=re.I)
    return int(hit.group(1)) if hit else 0


def kind_sort_key(kind: str | None, name: str) -> tuple[int, int]:
    k = str(kind or "")
    if k == "first_estimate":
        return (0, 0)
    if k == "delineation":
        return (10, 0)
    if k == "delineation_monitoring":
        return (20, parse_monit_number(name))
    if k == "grading":
        return (90, 0)
    return (50, 0)


def geom_from_geojson(doc: dict[str, Any]) -> Any | None:
    feats = doc.get("features") if doc.get("type") == "FeatureCollection" else None
    if feats is None and doc.get("type") == "Feature":
        feats = [doc]
    geoms = []
    for feat in feats or []:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            geoms.append(shape(geom))
        except (ValueError, TypeError):
            continue
    if not geoms:
        return None
    merged = unary_union(geoms)
    if merged.is_empty:
        return None
    if merged.geom_type != "Point":
        merged = merged.simplify(0.0005, preserve_topology=True)
    return merged


def load_geojson(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def vector_copy_iou(prev: Any, nxt: Any) -> float | None:
    if prev is None or nxt is None:
        return None
    inter = prev.intersection(nxt).area
    union = prev.union(nxt).area
    if union <= 0:
        return 1.0
    return float(inter / union)


def pair_row(
    prev: dict[str, Any],
    nxt: dict[str, Any],
    *,
    copy_iou: float | None,
) -> dict[str, Any]:
    delta = None
    if prev.get("dt") is not None and nxt.get("dt") is not None:
        delta = hours_between(prev["dt"], nxt["dt"])
    elif prev.get("dt") is None or nxt.get("dt") is None:
        # Do not invent Δt. Kind incompatibility still classifies.
        delta = None
    pair_class = classify_temporal_pair(
        delta_hours=delta,
        label_mask_iou=copy_iou,
        prev_kind=prev.get("kind"),
        next_kind=nxt.get("kind"),
    )
    return {
        "from": prev.get("name"),
        "to": nxt.get("name"),
        "from_kind": prev.get("kind"),
        "to_kind": nxt.get("kind"),
        "from_utc": prev.get("utc"),
        "to_utc": nxt.get("utc"),
        "delta_hours": delta,
        "time_source": prev.get("time_source"),
        "label_mask_iou": copy_iou,
        "copy_mask_iou": copy_iou,
        "pair_class": pair_class,
        "complete_proxy_model_iou": None,
        "model_iou": None,
        "metric_kind": "label_vs_label_copy" if copy_iou is not None else None,
    }


def usable_copy_mean(pairs: list[dict[str, Any]]) -> float | None:
    return mean_usable_pair_ious(pairs, key="copy_mask_iou")


def empty_fire_row(
    fire_id: str,
    *,
    family: str,
    skip_class: str | None,
    **extra: Any,
) -> dict[str, Any]:
    row = {
        "fire_id": fire_id,
        "family": family,
        "skip_class": skip_class,
        "n_geometries": 0,
        "n_pairs": 0,
        "n_pairs_used": 0,
        "pairs": [],
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": None,
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "sold_as_catalog_08963": False,
        "metric_kind": "label_vs_label_copy",
    }
    row.update(extra)
    return row


def cems_pack_dir(activation: str) -> Path:
    return ROOT / "outputs" / "open_if" / activation.lower()


def _delivery_times_from_scorecard(pack: Path) -> dict[str, datetime]:
    score = pack / "scorecard_pista_b.json"
    if not score.is_file():
        return {}
    try:
        doc = json.loads(score.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, datetime] = {}
    for prod in doc.get("products") or []:
        path = str(prod.get("downloadPath") or "")
        dt = parse_iso_utc(str(prod.get("deliveryTime") or ""))
        if not path or dt is None:
            continue
        aoi = parse_aoi_token(path)
        kind = parse_product_kind(path)
        if aoi and kind:
            out[f"{aoi}:{kind}:{parse_monit_number(path)}"] = dt
    return out


def _iso_datestamps_from_raw_xml(pack: Path) -> dict[str, datetime]:
    """CEMS ISO metadata dateStamp (noon UTC). Not image acquisition time."""
    raw = pack / "raw_cems"
    if not raw.is_dir():
        return {}
    out: dict[str, datetime] = {}
    for xml in raw.rglob("*observedEventA*.xml"):
        aoi = parse_aoi_token(xml.name)
        kind = parse_product_kind(xml.name)
        if not aoi or not kind:
            continue
        try:
            text = xml.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        hit = re.search(r"<gco:Date>(\d{4}-\d{2}-\d{2})</gco:Date>", text)
        if not hit:
            continue
        dt = parse_iso_utc(f"{hit.group(1)}T12:00:00Z")
        if dt is None:
            continue
        out[f"{aoi}:{kind}:{parse_monit_number(xml.name)}"] = dt
    return out


def matching_raw_observed(raw_dir: Path, aoi: str, kind: str | None, monit: int) -> Path | None:
    """Smaller CEMS observedEvent JSON for a product (not the full-layer GeoJSON)."""
    if not raw_dir.is_dir():
        return None
    hits: list[Path] = []
    for path in raw_dir.glob("*observedEventA*.json"):
        if parse_aoi_token(path.name) != aoi:
            continue
        if parse_product_kind(path.name) != kind:
            continue
        if parse_monit_number(path.name) != monit:
            continue
        hits.append(path)
    if not hits:
        return None
    return min(hits, key=lambda p: p.stat().st_size)


def load_cems_geometries(pack: Path, aoi: str) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []
    deliveries = _delivery_times_from_scorecard(pack)
    iso_dates = _iso_datestamps_from_raw_xml(pack)

    def _time_for(aoi_token: str, kind: str | None, name: str) -> tuple[datetime | None, str | None]:
        key = f"{aoi_token}:{kind}:{parse_monit_number(name)}"
        if key in deliveries:
            return deliveries[key], "scorecard_deliveryTime"
        if key in iso_dates:
            return iso_dates[key], "cems_iso_datestamp_noon_utc"
        return None, None

    timeline = pack / "timeline_perimeters.geojson"
    if timeline.is_file() and aoi == "AOI01":
        doc = load_geojson(timeline)
        by_name: dict[str, list] = {}
        for feat in doc.get("features") or []:
            props = feat.get("properties") or {}
            src = str(props.get("source_file") or props.get("member") or "")
            feat_aoi = parse_aoi_token(src)
            if feat_aoi != aoi:
                continue
            name = Path(src).name
            by_name.setdefault(name, []).append(feat)
        for name, feats in by_name.items():
            geom = geom_from_geojson({"type": "FeatureCollection", "features": feats})
            kind = parse_product_kind(name) or (feats[0].get("properties") or {}).get("kind")
            dt, time_source = _time_for(aoi, kind, name)
            recs.append(
                {
                    "name": name,
                    "kind": kind,
                    "aoi": aoi,
                    "geom": geom,
                    "path": str(pack / "vectors" / name) if (pack / "vectors" / name).is_file() else None,
                    "dt": dt,
                    "utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
                    "time_source": time_source,
                    "area_ha": (feats[0].get("properties") or {}).get("area_ha"),
                }
            )
    else:
        vector_dir = pack / "vectors"
        raw_dir = pack / "raw_cems"
        paths = []
        if vector_dir.is_dir():
            paths.extend(sorted(vector_dir.glob("*.geojson")))
        # Raw GRA/FEP dumps can be thousands of slivers; only use them when
        # the pack has no pre-merged vector GeoJSON for this AOI.
        if not paths and raw_dir.is_dir():
            paths.extend(sorted(raw_dir.glob("*observedEventA*.json")))
        elif raw_dir.is_dir():
            have = {f"{parse_product_kind(p.name)}:{parse_monit_number(p.name)}" for p in paths}
            for path in sorted(raw_dir.glob("*observedEventA*.json")):
                token = parse_aoi_token(path.name)
                if token != aoi:
                    continue
                key = f"{parse_product_kind(path.name)}:{parse_monit_number(path.name)}"
                if key in have:
                    continue
                # Kind-only (no geom): still classifies FEP/GRA without a heavy union.
                kind = parse_product_kind(path.name)
                dt, time_source = _time_for(aoi, kind, path.name)
                recs.append(
                    {
                        "name": path.name,
                        "kind": kind,
                        "aoi": aoi,
                        "geom": None,
                        "path": str(path),
                        "dt": dt,
                        "utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
                        "time_source": time_source,
                        "area_ha": None,
                    }
                )
                have.add(key)
        seen: set[str] = set()
        for path in paths:
            token = parse_aoi_token(path.name)
            if token != aoi:
                continue
            kind = parse_product_kind(path.name)
            dedupe = f"{kind}:{parse_monit_number(path.name)}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            try:
                # Full-product GeoJSON (898) is too large to union. Rasterize the
                # raw observedEvent member instead.
                if path.stat().st_size > 2_000_000:
                    geom = None
                    doc = {"features": [{"properties": {}}]}
                    raw_hit = matching_raw_observed(
                        raw_dir, aoi, kind, parse_monit_number(path.name)
                    )
                    raster_path = raw_hit if raw_hit is not None else path
                else:
                    doc = load_geojson(path)
                    geom = geom_from_geojson(doc)
                    raster_path = path
            except (OSError, json.JSONDecodeError):
                continue
            props = {}
            if doc.get("features"):
                props = doc["features"][0].get("properties") or {}
            dt, time_source = _time_for(aoi, kind, path.name)
            recs.append(
                {
                    "name": path.name,
                    "kind": kind or props.get("kind"),
                    "aoi": aoi,
                    "geom": geom,
                    "path": str(raster_path),
                    "dt": dt,
                    "utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
                    "time_source": time_source,
                    "area_ha": props.get("area_ha"),
                }
            )
    recs.sort(
        key=lambda r: (
            r["dt"] or datetime.min.replace(tzinfo=UTC),
            kind_sort_key(r.get("kind"), str(r.get("name") or "")),
        )
    )
    return recs


def attach_vector_model_iou(
    row: dict[str, Any],
    recs: list[dict[str, Any]],
    *,
    model,
    device,
    max_patches: int,
    max_pairs: int | None,
    meteo_mode: str,
    meteo_cache: dict[str, Any],
    ref_geom: Any | None = None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    if model is None or device is None or len(recs) < 2:
        return row
    masks, raster_meta = rasterize_records(recs, ref_geom=ref_geom, skip_bytes=None)
    row["raster"] = raster_meta
    if not raster_meta.get("ok"):
        row["skip_class"] = raster_meta.get("error") or "rasterize_failed"
        return row
    cov, prov = point_cov_for_recs(
        recs,
        (int(raster_meta["height"]), int(raster_meta["width"])),
        meteo_mode=meteo_mode,
        cache=meteo_cache,
    )
    row["covariate_provenance"] = prov
    score_pairs_with_masks(
        row.get("pairs") or [],
        recs,
        masks,
        cov,
        model,
        device,
        max_patches=max_patches,
        max_pairs=max_pairs,
        architecture=architecture,
        decode=decode,
    )
    row.update(summarize_model_scores(row.get("pairs") or []))
    row["schema_mode"] = "rasterized_vector_legacy17"
    row["sold_as_clm_ensemble_v34"] = False
    row["sold_as_go_q"] = False
    return row


def has_model_score(fire: dict[str, Any]) -> bool:
    return fire.get("model_iou") is not None or fire.get("scored_model_iou") is not None


def eval_cems_fire(
    fire_id: str,
    *,
    model=None,
    device=None,
    max_patches: int = 32,
    max_pairs: int | None = None,
    meteo_mode: str = "fetch",
    meteo_cache: dict[str, Any] | None = None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    if "_" not in fire_id:
        return empty_fire_row(fire_id, family="cems_vector", skip_class="missing_on_disk")
    activation, aoi = fire_id.split("_", 1)
    pack = cems_pack_dir(activation)
    if not pack.is_dir():
        return empty_fire_row(
            fire_id,
            family="cems_vector",
            skip_class="missing_on_disk",
            path=rel_to_root(pack),
        )
    recs = load_cems_geometries(pack, aoi)
    if len(recs) < 1:
        return empty_fire_row(
            fire_id,
            family="cems_vector",
            skip_class="need_ge2_labels" if not recs else "need_ge2_labels",
            activation=activation,
            aoi=aoi,
            path=rel_to_root(pack),
        )
    pairs: list[dict[str, Any]] = []
    for prev, nxt in zip(recs, recs[1:]):
        pairs.append(pair_row(prev, nxt, copy_iou=vector_copy_iou(prev.get("geom"), nxt.get("geom"))))
    used = [p for p in pairs if p.get("pair_class") == "usable"]
    row = {
        "fire_id": fire_id,
        "activation": activation,
        "aoi": aoi,
        "family": "cems_vector",
        "skip_class": "vector_only_no_legacy17",
        "schema_compatible": False,
        "n_geometries": len(recs),
        "n_pairs": len(pairs),
        "n_pairs_used": 0,
        "pairs": pairs,
        "geometries": [
            {
                "name": r["name"],
                "kind": r.get("kind"),
                "utc": r.get("utc"),
                "area_ha": r.get("area_ha"),
            }
            for r in recs
        ],
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": usable_copy_mean(pairs),
        "usable_copy_mean": usable_copy_mean(pairs),
        "n_usable_pairs": len(used),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "sold_as_catalog_08963": False,
        "metric_kind": "label_vs_label_copy",
        "path": rel_to_root(pack),
    }
    return attach_vector_model_iou(
        row,
        recs,
        model=model,
        device=device,
        max_patches=max_patches,
        max_pairs=max_pairs,
        meteo_mode=meteo_mode,
        meteo_cache=meteo_cache if meteo_cache is not None else {},
        ref_geom=aoi_ref_geom(pack, aoi),
        architecture=architecture,
        decode=decode,
    )


def eval_tobarra(
    drop: Path,
    *,
    model=None,
    device=None,
    max_patches: int = 32,
    max_pairs: int | None = None,
    meteo_mode: str = "fetch",
    meteo_cache: dict[str, Any] | None = None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    g0 = drop / "2024020124_TOBARRA_20240802_1830.geojson"
    g1 = drop / "2024020124_TOBARRA_20240802_2143.geojson"
    if not g0.is_file() or not g1.is_file():
        return empty_fire_row(
            "TOBARRA_20240802",
            family="infocam_kmz",
            skip_class="missing_on_disk",
            path=rel_to_root(drop),
        )
    recs = []
    for path in (g0, g1):
        doc = load_geojson(path)
        props = (doc.get("features") or [{}])[0].get("properties") or {}
        local = props.get("time_local_inferred")
        dt = None
        if local:
            raw = parse_iso_utc(str(local))
            if raw is not None:
                # Filename clock is local CEST, stored naive; treat as UTC+2.
                naive = raw.replace(tzinfo=None)
                dt = naive.replace(tzinfo=CEST).astimezone(UTC)
        recs.append(
            {
                "name": path.name,
                "kind": "delineation_monitoring",
                "geom": geom_from_geojson(doc),
                "path": str(path),
                "dt": dt,
                "utc": dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None,
                "time_source": "filename_YYYYMMDD_HHMM_local_CEST",
                "area_ha": props.get("sup_ha") or props.get("area_ha_geom_utm30n"),
            }
        )
    pairs = [
        pair_row(recs[0], recs[1], copy_iou=vector_copy_iou(recs[0]["geom"], recs[1]["geom"]))
    ]
    row = {
        "fire_id": "TOBARRA_20240802",
        "family": "infocam_kmz",
        "skip_class": "vector_only_no_legacy17",
        "schema_compatible": False,
        "n_geometries": 2,
        "n_pairs": 1,
        "n_pairs_used": 0,
        "pairs": pairs,
        "geometries": [
            {"name": r["name"], "kind": r["kind"], "utc": r.get("utc"), "area_ha": r.get("area_ha")}
            for r in recs
        ],
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": usable_copy_mean(pairs),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "not_national_cadastre": True,
        "metric_kind": "label_vs_label_copy",
        "path": rel_to_root(drop),
    }
    return attach_vector_model_iou(
        row,
        recs,
        model=model,
        device=device,
        max_patches=max_patches,
        max_pairs=max_pairs,
        meteo_mode=meteo_mode,
        meteo_cache=meteo_cache if meteo_cache is not None else {},
        architecture=architecture,
        decode=decode,
    )


def eval_caldor_vectors(
    caldor_root: Path,
    *,
    model=None,
    device=None,
    max_patches: int = 32,
    max_pairs: int | None = None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    """Caldor cumulative masks + physical→legacy17 frozen decode. Not catalog 0.8963."""
    meta_p = caldor_root / "meta.json"
    if not meta_p.is_file():
        return empty_fire_row(
            "US_FIREBENCH_CALDOR_2021",
            family="firebench_caldor",
            skip_class="missing_on_disk",
            path=rel_to_root(caldor_root),
        )
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    recs: list[dict[str, Any]] = []
    for item in meta.get("observations") or []:
        rel = item.get("cumulative_mask") or item.get("raw_mask")
        mask_path = caldor_root / rel if rel else None
        dt = parse_iso_utc(str(item.get("timestamp_utc") or ""))
        recs.append(
            {
                "name": Path(str(rel or item.get("timestamp_utc") or "obs")).name,
                "kind": "delineation_monitoring",
                "geom": None,
                "mask_path": str(mask_path) if mask_path and mask_path.is_file() else None,
                "dt": dt,
                "utc": item.get("timestamp_utc"),
                "time_source": "meta.timestamp_utc",
                "area_ha": item.get("cumulative_area_ha") or item.get("raw_area_ha"),
            }
        )
    recs.sort(key=lambda r: r["dt"] or datetime.min.replace(tzinfo=UTC))
    pairs = [pair_row(a, b, copy_iou=None) for a, b in zip(recs, recs[1:])]
    tensors_manifest = caldor_root / "tensors" / "clean17_physical_v1" / "manifest.json"
    tensor_legacy_ok = False
    if tensors_manifest.is_file():
        tdoc = json.loads(tensors_manifest.read_text(encoding="utf-8"))
        tensor_legacy_ok = bool(tdoc.get("legacy17_checkpoint_compatible"))
    scored = 0
    if model is not None and device is not None:
        mask_cache: dict[str, np.ndarray] = {}
        for pair, prev, nxt in zip(pairs, recs[:-1], recs[1:], strict=True):
            prev_path = prev.get("mask_path")
            next_path = nxt.get("mask_path")
            if not prev_path or not next_path:
                pair["raster_skip"] = "missing_mask"
                continue
            if prev_path not in mask_cache:
                mask_cache[prev_path] = (load_tif(Path(prev_path)) > 0).astype(np.float32)
            if next_path not in mask_cache:
                mask_cache[next_path] = (load_tif(Path(next_path)) > 0).astype(np.float32)
            prev_m = mask_cache[prev_path]
            next_m = mask_cache[next_path]
            raster_copy = binary_iou(prev_m > 0, next_m > 0)
            pair["copy_mask_iou"] = raster_copy
            pair["label_mask_iou"] = raster_copy
            pair["raster_copy_iou"] = raster_copy
            pair["pair_class"] = classify_temporal_pair(
                delta_hours=pair.get("delta_hours"),
                label_mask_iou=raster_copy,
                prev_kind=prev.get("kind"),
                next_kind=nxt.get("kind"),
            )
            if pair.get("pair_class") == "incompatible_product_kind":
                continue
            if max_pairs is not None and scored >= int(max_pairs):
                pair["raster_skip"] = "max_pairs"
                continue
            cov = caldor_cov_at(caldor_root, str(prev.get("utc") or ""))
            if cov is None:
                pair["raster_skip"] = "missing_physical_covariates"
                continue
            result = score_caldor_pair(
                prev_m,
                next_m,
                cov,
                model,
                device,
                max_patches=max_patches,
                architecture=architecture,
                decode=decode,
            )
            scored += 1
            pair["complete_proxy_model_iou"] = result.get("model_iou")
            pair["model_iou"] = result.get("model_iou")
            pair["n_tiles"] = result.get("n_tiles")
            pair["delta_vs_copy"] = result.get("delta_vs_copy")
            pair["metric_kind"] = "complete_proxy_frozen_decode"
            pair["schema_mode"] = "caldor_physical_to_legacy17"
            pair["tile_copy_mask_iou"] = result.get("copy_mask_iou")
            pair["oracle_frozen_iou"] = result.get("oracle_frozen_iou")
            pair["oracle_delta_vs_copy"] = result.get("oracle_delta_vs_copy")
            full_oracle = oracle_pair_iou(prev_m, next_m)
            pair["full_oracle_frozen_iou"] = full_oracle["oracle_frozen_iou"]
            pair["full_oracle_delta_vs_copy"] = full_oracle["oracle_delta_vs_copy"]
    summary = summarize_model_scores(pairs)
    skip = summary.get("skip_class")
    if summary.get("scored_model_iou") is None and skip is None:
        skip = "incompatible_schema"
    row = {
        "fire_id": "US_FIREBENCH_CALDOR_2021",
        "family": "firebench_caldor",
        "skip_class": skip,
        "schema_compatible": bool(summary.get("schema_compatible")),
        "legacy17_checkpoint_compatible": False,
        "legacy17_via_build_legacy17_channels": True,
        "tensor_legacy17_checkpoint_compatible": tensor_legacy_ok,
        "n_geometries": len(recs),
        "n_observations": int(meta.get("n_observations") or len(recs)),
        "n_pairs": len(pairs),
        "n_pairs_used": 0,
        "n_pairs_12_to_36h": int(meta.get("n_pairs_12_to_36h") or 0),
        "pairs": pairs,
        "model_iou": None,
        "complete_proxy_model_iou": None,
        "copy_baseline_iou": usable_copy_mean(pairs),
        "sold_as_clm_ensemble_v34": False,
        "sold_as_go_q": False,
        "sold_as_catalog_08963": False,
        "caldor_copy_is_not_catalog_08963": True,
        "catalog_holdout_iou_08963_used": False,
        "metric_kind": "label_vs_label_copy",
        "schema_mode": "caldor_physical_to_legacy17",
        "path": rel_to_root(caldor_root),
        "not_claims": [
            "not clm_ensemble_v34",
            "not GO_Q",
            "Caldor 21ch tensors are not the UNet input",
            "Caldor label-copy is not catalog 0.8963",
        ],
    }
    row.update(summary)
    if row.get("copy_baseline_iou") is None:
        row["copy_baseline_iou"] = usable_copy_mean(pairs)
    return row


def family_usable_copy_mean(fires: list[dict[str, Any]], family: str) -> float | None:
    vals: list[float] = []
    for fire in fires:
        if fire.get("family") != family:
            continue
        if fire.get("fire_id") in ISOLATION_FIRE_IDS:
            continue
        for pair in fire.get("pairs") or []:
            if pair.get("pair_class") != "usable":
                continue
            iou = pair.get("copy_mask_iou")
            if iou is None:
                continue
            vals.append(float(iou))
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def mixed_family_mean(_fires: list[dict[str, Any]]) -> None:
    return None


def evaluate_fire(
    fire_id: str,
    *,
    caldor_root: Path,
    tobarra_root: Path,
    model=None,
    device=None,
    max_patches: int = 32,
    max_pairs: int | None = None,
    meteo_mode: str = "fetch",
    meteo_cache: dict[str, Any] | None = None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    kwargs = {
        "model": model,
        "device": device,
        "max_patches": max_patches,
        "max_pairs": max_pairs,
        "meteo_mode": meteo_mode,
        "meteo_cache": meteo_cache if meteo_cache is not None else {},
        "architecture": architecture,
        "decode": decode,
    }
    if fire_id in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
        return empty_fire_row(fire_id, family="official_latam_excluded", skip_class="official_latam_excluded")
    if fire_id == "US_FIREBENCH_CALDOR_2021":
        return eval_caldor_vectors(
            caldor_root,
            model=model,
            device=device,
            max_patches=max_patches,
            max_pairs=max_pairs,
            architecture=architecture,
            decode=decode,
        )
    if fire_id == "TOBARRA_20240802":
        return eval_tobarra(tobarra_root, **kwargs)
    if fire_id.startswith("EMSR"):
        return eval_cems_fire(fire_id, **kwargs)
    return empty_fire_row(fire_id, family="unknown", skip_class="missing_on_disk")


def write_scorecard(doc: dict[str, Any], path: Path) -> None:
    lines = [
        "# SCORECARD — same-fire multi-geometry (additional)",
        "",
        "Additional to the official LATAM 4-pair complete-proxy JSON. Not a replacement.",
        "",
        f"- as_of_utc: `{doc.get('as_of_utc')}`",
        f"- product_id: `{doc.get('product_id')}`",
        f"- GO_Q: `{doc.get('go_q')}`",
        f"- lab_ok_conaf: `{doc.get('lab_ok_conaf')}`",
        f"- sold_as_clm_ensemble_v34: `{doc.get('sold_as_clm_ensemble_v34')}`",
        "- model IoU is frozen complete-proxy decode (8-ring k=1 @ 0.90, keep-t0).",
        "- CEMS/Tobarra: rasterized outlines + point meteo/legacy17. Caldor: physical→legacy17.",
        "- Families are not averaged. Isolation AOIs are listed, not chained into AOI01.",
        "",
        "| fire | family | n geom | n pairs | usable copy | model IoU | Δ vs copy | oracle | skip |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for fire in doc.get("fires") or []:
        lines.append(
            "| {id} | {fam} | {ng} | {np} | {copy} | {model} | {delta} | {oracle} | {skip} |".format(
                id=fire.get("fire_id"),
                fam=fire.get("family"),
                ng=fire.get("n_geometries") if fire.get("n_geometries") is not None else "",
                np=fire.get("n_pairs") if fire.get("n_pairs") is not None else "",
                copy="" if fire.get("copy_baseline_iou") is None else f"{fire['copy_baseline_iou']:.6f}",
                model=(
                    ""
                    if fire.get("model_iou") is None and fire.get("scored_model_iou") is None
                    else f"{(fire.get('model_iou') if fire.get('model_iou') is not None else fire.get('scored_model_iou')):.6f}"
                ),
                delta="" if fire.get("delta_vs_copy") is None else f"{fire['delta_vs_copy']:+.6f}",
                oracle="" if fire.get("oracle_frozen_iou") is None else f"{fire['oracle_frozen_iou']:.6f}",
                skip=fire.get("skip_class") or "",
            )
        )
    lines.extend(["", "## not_claims", ""])
    for claim in doc.get("not_claims") or NOT_CLAIMS:
        lines.append(f"- {claim}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    requested = list(args.fire_ids) if args.fire_ids else list(DEFAULT_FIRE_IDS)
    isolation = list(ISOLATION_FIRE_IDS) if (args.include_isolation_aois or not args.fire_ids) else []

    for fire_id in requested:
        if fire_id in OFFICIAL_LATAM_COMPLETE_PROXY_IDS:
            print(f"error: official LATAM pack excluded from same-fire eval: {fire_id}", file=sys.stderr)
            return EXIT_MISSING_DATA
        if fire_id not in DEFAULT_FIRE_IDS and fire_id not in ISOLATION_FIRE_IDS:
            print(f"error: unknown fire {fire_id}", file=sys.stderr)
            return EXIT_MISSING_DATA

    caldor_root = ROOT / "data" / "open_if" / "external_bridge" / "US_FIREBENCH_CALDOR_2021"
    tobarra_root = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
    weights = Path(args.weights) if args.weights is not None else default_same_fire_weights(ROOT)

    if args.require_model_iou and not weights.is_file():
        print(
            f"error: missing weights {weights} — refusing invented same-fire model IoU",
            file=sys.stderr,
        )
        return EXIT_MISSING_WEIGHTS

    model = None
    device = None
    if weights.is_file():
        print(f"loading frozen UNet {rel_to_root(weights)}", flush=True)
        model, device = load_frozen_unet(weights)
    elif args.require_model_iou:
        print(
            f"error: missing weights {weights} — refusing invented same-fire model IoU",
            file=sys.stderr,
        )
        return EXIT_MISSING_WEIGHTS

    meteo_cache: dict[str, Any] = {}
    fires: list[dict[str, Any]] = []
    for fire_id in requested + [i for i in isolation if i not in requested]:
        print(f"evaluating {fire_id} ...", flush=True)
        row = evaluate_fire(
            fire_id,
            caldor_root=caldor_root,
            tobarra_root=tobarra_root,
            model=model,
            device=device,
            max_patches=int(args.max_patches),
            max_pairs=args.max_pairs,
            meteo_mode=str(args.meteo_mode),
            meteo_cache=meteo_cache,
        )
        print(
            f"  done {fire_id} n_geom={row.get('n_geometries')} n_pairs={row.get('n_pairs')} "
            f"model_iou={row.get('model_iou')} scored={row.get('scored_model_iou')}",
            flush=True,
        )
        if row.get("skip_class") == "missing_on_disk" and fire_id in requested:
            print(f"error: missing data for fire {fire_id}", file=sys.stderr)
            return EXIT_MISSING_DATA
        fires.append(row)

    if args.require_model_iou:
        incompatible = [
            f
            for f in fires
            if f.get("fire_id") in requested and not has_model_score(f)
        ]
        if incompatible:
            ids = ", ".join(f["fire_id"] for f in incompatible)
            print(
                f"error: incompatible schema for model IoU ({ids}); "
                "refusing invented UNet score",
                file=sys.stderr,
            )
            return EXIT_INCOMPATIBLE_SCHEMA

    aoi01 = [f for f in fires if f.get("fire_id") == "EMSR578_AOI01"]
    aoi02_pairs = []
    for f in fires:
        if f.get("fire_id") == "EMSR578_AOI02":
            aoi02_pairs = list(f.get("pairs") or [])
    if aoi01 and aoi02_pairs:
        names01 = {(p.get("from"), p.get("to")) for p in (aoi01[0].get("pairs") or [])}
        for p in aoi02_pairs:
            if (p.get("from"), p.get("to")) in names01:
                print("error: AOI02 pair leaked into AOI01", file=sys.stderr)
                return EXIT_MISSING_DATA

    doc = {
        "schema": SCHEMA,
        "as_of_utc": utc_now(),
        "product_id": "same_fire_multi_geometry_additional",
        "go_q": "partial",
        "lab_ok_conaf": False,
        "sold_as_clm_ensemble_v34": False,
        "official_json_untouched": rel_to_root(OFFICIAL_JSON),
        "weights": rel_to_root(weights) if weights.is_file() else None,
        "decode": {
            "architecture": "residual",
            "target_mode": "delta",
            "growth_threshold": 0.90,
            "growth_ring_connectivity": 8,
            "growth_ring_min_neighbors": 1,
            "keep_t0": True,
        },
        "n_fires": len(fires),
        "fires": fires,
        "family_usable_copy_mean": {
            "cems_vector": family_usable_copy_mean(fires, "cems_vector"),
            "infocam_kmz": family_usable_copy_mean(fires, "infocam_kmz"),
            "firebench_caldor": family_usable_copy_mean(fires, "firebench_caldor"),
        },
        "mixed_family_mean": mixed_family_mean(fires),
        "not_claims": list(NOT_CLAIMS),
        "pair_protocol": {
            "min_delta_hours": 12.0,
            "static_label_copy_iou_gt": 0.98,
            "growth_kinds": ["delineation", "delineation_monitoring"],
            "excluded": ["too_short_delta", "static_label_copy", "incompatible_product_kind"],
            "aoi_isolation": True,
        },
    }

    out = Path(args.out_root)
    if out.resolve() == OFFICIAL_JSON.resolve() or out.resolve() == OFFICIAL_JSON.parent.resolve():
        print("error: refusing to write over official complete-proxy JSON", file=sys.stderr)
        return EXIT_MISSING_DATA
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "same_fire_eval.json"
    json_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    write_scorecard(doc, out / "SCORECARD.md")
    print(f"wrote {rel_to_root(json_path)} n_fires={len(fires)}")
    for fire in fires:
        print(
            f"{fire.get('fire_id')}: n_geom={fire.get('n_geometries')} "
            f"n_pairs={fire.get('n_pairs')} copy={fire.get('copy_baseline_iou')} "
            f"model_iou={fire.get('model_iou')} skip={fire.get('skip_class')}"
        )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
