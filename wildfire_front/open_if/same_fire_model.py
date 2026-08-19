"""Frozen complete-proxy UNet IoU on same-fire rasters.

Vector CEMS/INFOCAM outlines are burned onto a shared grid; Caldor uses the
on-disk cumulative masks plus physical HRRR/3DEP/LANDFIRE fields mapped
through ``build_legacy17_channels``. Decode knobs stay frozen (8-ring, k=1,
growth thr 0.90, keep-t0). This is not sealed transfer and not GO_Q.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import shape
from shapely.ops import transform, unary_union

from scripts.run_latam_au_complete_model_iou import (
    N_CH,
    OOD_GROWTH_THRESHOLD,
    PATCH,
    binary_iou,
    build_seq_tile,
    crop,
    decode_complete_proxy_pred,
    fire_growth_ring,
    oracle_frozen_decode_mask,
    stratified_tiles,
)
from wildfire_front.ml.feature_schema import build_legacy17_channels
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, model_forward, prepare_input
from wildfire_front.open_if.latam_au import (
    USER_AGENT,
    classify_temporal_pair,
    load_observed_from_path,
    parse_iso_utc,
)

OPEN_METEO = "https://archive-api.open-meteo.com/v1/archive"
OPENTOPO = "https://api.opentopodata.org/v1/srtm90m"
MAX_GEOJSON_BYTES = 80_000_000
MAX_OBSERVED_JSON_BYTES = 20_000_000
DEFAULT_GSD_M = 100.0
MAX_RASTER_DIM = 1024
SAME_FIRE_SCRATCH = Path("outputs") / "ml_eval" / "mega_goal_model" / "same_fire_scratch" / "weights_pretrained_best.pt"
CLIMATOLOGY = {
    "temperature_c": 26.0,
    "humidity_pct": 30.0,
    "wind_speed_ms": 3.5,
    "wind_dir_deg": 270.0,
    "precip_mm": 0.0,
    "elevation_m": 450.0,
    "veg": 0.35,
}


def default_same_fire_weights(root: Path) -> Path:
    scratch = root / SAME_FIRE_SCRATCH
    lab = root / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen" / "weights_pretrained_best.pt"
    product = root / "models" / "clm_ensemble" / "weights_multi_if.pt"
    if scratch.is_file():
        return scratch
    if lab.is_file():
        return lab
    return product


def load_frozen_unet(weights: Path, device: Any | None = None):
    import torch

    dev = device or torch.device("cpu")
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=N_CH + 1)
    state = torch.load(Path(weights), map_location=dev, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(dev)
    model.eval()
    return model, dev


def utm_epsg(lon: float, lat: float) -> int:
    zone = int((float(lon) + 180.0) // 6) + 1
    return (32600 if lat >= 0 else 32700) + zone


def constant_cov(h: int, w: int, values: dict[str, float] | None = None) -> dict[str, np.ndarray]:
    src = dict(CLIMATOLOGY)
    if values:
        src.update({k: float(v) for k, v in values.items() if v is not None})
    shape = (int(h), int(w))

    def _full(key: str, fallback: float) -> np.ndarray:
        return np.full(shape, float(src.get(key, fallback)), dtype=np.float32)

    return {
        "elevation": _full("elevation_m", 450.0),
        "temperature": _full("temperature_c", 26.0),
        "humidity": _full("humidity_pct", 30.0),
        "wind_speed": _full("wind_speed_ms", 3.5),
        "wind_dir": _full("wind_dir_deg", 270.0),
        "precip": _full("precip_mm", 0.0),
        "veg": _full("veg", 0.35),
    }


def fetch_open_meteo_point(lat: float, lon: float, when: datetime | None, *, timeout: int = 20) -> dict[str, Any]:
    if when is None:
        return {"ok": False, "error": "no_timestamp"}
    day = when.strftime("%Y-%m-%d")
    qs = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.5f}",
            "longitude": f"{lon:.5f}",
            "start_date": day,
            "end_date": day,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation",
            "models": "era5",
            "timezone": "UTC",
        }
    )
    url = f"{OPEN_METEO}?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    hourly = payload.get("hourly") or {}
    times = list(hourly.get("time") or [])
    if not times:
        return {"ok": False, "error": "empty_hourly", "source": "open_meteo_era5_archive"}
    parsed = [parse_iso_utc(str(t) + "Z" if "Z" not in str(t) else str(t)) for t in times]
    best_i = 0
    best_abs = None
    for i, dt in enumerate(parsed):
        if dt is None:
            continue
        delta = abs((dt - when).total_seconds())
        if best_abs is None or delta < best_abs:
            best_abs = delta
            best_i = i

    def _at(key: str) -> float | None:
        vals = list(hourly.get(key) or [])
        if best_i >= len(vals) or vals[best_i] is None:
            return None
        try:
            return float(vals[best_i])
        except (TypeError, ValueError):
            return None

    wind_kmh = _at("wind_speed_10m")
    return {
        "ok": True,
        "source": "open_meteo_era5_archive",
        "sample_at": times[best_i],
        "temperature_c": _at("temperature_2m"),
        "humidity_pct": _at("relative_humidity_2m"),
        "wind_speed_ms": (wind_kmh / 3.6) if wind_kmh is not None else None,
        "wind_dir_deg": _at("wind_direction_10m"),
        "precip_mm": _at("precipitation"),
        "elevation_m": payload.get("elevation"),
    }


def point_cov_for_recs(
    recs: list[dict[str, Any]],
    shape_hw: tuple[int, int],
    *,
    meteo_mode: str,
    cache: dict[str, Any] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    h, w = shape_hw
    cache = cache if cache is not None else {}
    lon = lat = None
    when = None
    for rec in recs:
        geom = rec.get("geom")
        if geom is not None and not geom.is_empty:
            c = geom.centroid
            lon, lat = float(c.x), float(c.y)
            break
    for rec in recs:
        if rec.get("dt") is not None:
            when = rec["dt"]
            break
    values = dict(CLIMATOLOGY)
    prov: dict[str, Any] = {"meteo_mode": meteo_mode, "fallback": "climatology_point"}
    if meteo_mode == "fetch" and lat is not None and lon is not None and when is not None:
        key = f"{lat:.3f},{lon:.3f},{when.strftime('%Y-%m-%d-%H')}"
        hit = cache.get(key)
        if hit is None:
            try:
                hit = fetch_open_meteo_point(lat, lon, when)
            except Exception as exc:  # noqa: BLE001
                hit = {"ok": False, "error": f"{type(exc).__name__}:{exc}"}
            cache[key] = hit
        prov["fetch"] = {k: hit.get(k) for k in ("ok", "error", "source", "sample_at")}
        if hit.get("ok"):
            for src, dst in (
                ("temperature_c", "temperature_c"),
                ("humidity_pct", "humidity_pct"),
                ("wind_speed_ms", "wind_speed_ms"),
                ("wind_dir_deg", "wind_dir_deg"),
                ("precip_mm", "precip_mm"),
                ("elevation_m", "elevation_m"),
            ):
                if hit.get(src) is not None:
                    values[dst] = float(hit[src])
            prov["fallback"] = None
            prov["meteo_mode"] = "open_meteo_point"
    if meteo_mode == "fetch" and lat is not None and lon is not None:
        dem_key = f"dem:{lat:.3f},{lon:.3f},{h}x{w}"
        dem = cache.get(dem_key)
        if dem is None:
            try:
                dem = fetch_srtm_elevation(lat, lon, (h, w))
            except Exception as exc:  # noqa: BLE001
                dem = None
                prov["dem_error"] = f"{type(exc).__name__}:{exc}"
            cache[dem_key] = dem
        if dem is not None and dem.shape == (h, w):
            cov = constant_cov(h, w, values)
            cov["elevation"] = dem
            prov["dem"] = "opentopodata_srtm90m"
            return cov, prov
    return constant_cov(h, w, values), prov


def fetch_srtm_elevation(lat: float, lon: float, shape_hw: tuple[int, int]) -> np.ndarray:
    """Coarse SRTM90 via OpenTopo around a point, bilinear to the label grid."""
    n_y, n_x = 8, 8
    dlat = 0.08
    dlon = 0.08
    lats = np.linspace(lat + dlat, lat - dlat, n_y)
    lons = np.linspace(lon - dlon, lon + dlon, n_x)
    locs = "|".join(f"{float(y):.5f},{float(x):.5f}" for y in lats for x in lons)
    url = f"{OPENTOPO}?{urllib.parse.urlencode({'locations': locs})}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        payload = json.loads(resp.read().decode("utf-8"))
    vals = []
    for row in payload.get("results") or []:
        elev = row.get("elevation")
        vals.append(float(elev) if elev is not None else np.nan)
    grid = np.asarray(vals, dtype=np.float32).reshape(n_y, n_x)
    if not np.isfinite(grid).any():
        raise RuntimeError("empty SRTM grid")
    med = float(np.nanmedian(grid))
    grid = np.where(np.isfinite(grid), grid, med).astype(np.float32)
    h, w = shape_hw
    yy = np.linspace(0, n_y - 1, h)
    xx = np.linspace(0, n_x - 1, w)
    yi = np.clip(np.floor(yy).astype(int), 0, n_y - 2)
    xi = np.clip(np.floor(xx).astype(int), 0, n_x - 2)
    ty = (yy - yi)[:, None]
    tx = (xx - xi)[None, :]
    g00 = grid[yi[:, None], xi[None, :]]
    g10 = grid[yi[:, None] + 1, xi[None, :]]
    g01 = grid[yi[:, None], xi[None, :] + 1]
    g11 = grid[yi[:, None] + 1, xi[None, :] + 1]
    return ((1 - ty) * (1 - tx) * g00 + ty * (1 - tx) * g10 + (1 - ty) * tx * g01 + ty * tx * g11).astype(
        np.float32
    )


def _grid_from_bounds(
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    *,
    gsd_m: float,
    max_dim: int,
    min_dim: int = PATCH,
) -> tuple[Any, int, int, float]:
    from rasterio.transform import from_origin

    span_x = max(gsd_m, maxx - minx)
    span_y = max(gsd_m, maxy - miny)
    # Small incidents (Tobarra-scale) must still produce a 64px tile.
    if min(span_x, span_y) / gsd_m < float(min_dim):
        gsd_m = max(5.0, min(span_x, span_y) / float(min_dim))
    width = max(8, int(np.ceil((maxx - minx) / gsd_m)))
    height = max(8, int(np.ceil((maxy - miny) / gsd_m)))
    if width > max_dim or height > max_dim:
        scale = max(width / max_dim, height / max_dim)
        gsd_m = gsd_m * scale
        width = max(8, int(np.ceil((maxx - minx) / gsd_m)))
        height = max(8, int(np.ceil((maxy - miny) / gsd_m)))
    return from_origin(minx, maxy, gsd_m, gsd_m), int(height), int(width), float(gsd_m)


def _project_wgs84(geom: Any, epsg: int) -> Any:
    from pyproj import Transformer

    to_m = Transformer.from_crs("EPSG:4326", f"EPSG:{int(epsg)}", always_xy=True)

    def _xy(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return to_m.transform(x, y)

    return transform(_xy, geom)


def _bounds_from_geoms(geoms: list[Any], *, pad_m: float) -> tuple[float, float, float, float] | None:
    valid = [g for g in geoms if g is not None and not getattr(g, "is_empty", True)]
    if not valid:
        return None
    union = unary_union(valid)
    minx, miny, maxx, maxy = union.bounds
    return (minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m)


def _rasterize_projected(geom_m: Any, transform_aff: Any, height: int, width: int) -> np.ndarray:
    from rasterio.features import rasterize

    if geom_m is None or getattr(geom_m, "is_empty", True):
        return np.zeros((height, width), dtype=np.uint8)
    return rasterize(
        [(geom_m, 1)],
        out_shape=(height, width),
        transform=transform_aff,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )


def _take_json_objects(buf: str) -> tuple[list[str], str]:
    """Split complete top-level `{...}` objects from a JSON array fragment."""
    objects: list[str] = []
    in_str = False
    escape = False
    depth = 0
    start = -1
    consumed = 0
    for i, ch in enumerate(buf):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                objects.append(buf[start : i + 1])
                consumed = i + 1
                start = -1
    return objects, buf[consumed:]


def iter_geojson_geoms_streaming(path: Path):
    """Stream Feature geometries without json.loads of the whole file."""
    if not path.is_file():
        return
    marker = '"features"'
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        buf = ""
        found = False
        while True:
            chunk = handle.read(1_048_576)
            if not chunk:
                if found and buf:
                    objs, _rest = _take_json_objects(buf)
                    for raw in objs:
                        try:
                            feat = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        geom = feat.get("geometry") if isinstance(feat, dict) else None
                        if not geom:
                            continue
                        try:
                            g = shape(geom)
                            if g.is_empty:
                                continue
                            yield g.simplify(0.0008, preserve_topology=True)
                        except (ValueError, TypeError):
                            continue
                break
            buf += chunk
            if not found:
                idx = buf.find(marker)
                if idx < 0:
                    if len(buf) > 64:
                        buf = buf[-64:]
                    continue
                bracket = buf.find("[", idx)
                if bracket < 0:
                    buf = buf[idx:]
                    continue
                buf = buf[bracket + 1 :]
                found = True
            objs, buf = _take_json_objects(buf)
            for raw in objs:
                try:
                    feat = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                geom = feat.get("geometry") if isinstance(feat, dict) else None
                if not geom:
                    continue
                try:
                    g = shape(geom)
                    if g.is_empty:
                        continue
                    yield g.simplify(0.0008, preserve_topology=True)
                except (ValueError, TypeError):
                    continue


def _iter_file_geoms(path: Path, *, max_bytes: int = MAX_GEOJSON_BYTES):
    if not path.is_file():
        return
    if path.stat().st_size > min(max_bytes, 15_000_000):
        yield from iter_geojson_geoms_streaming(path)
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        yield from iter_geojson_geoms_streaming(path)
        return
    feats = doc.get("features") if isinstance(doc, dict) and doc.get("type") == "FeatureCollection" else None
    if feats is None and isinstance(doc, dict) and doc.get("type") == "Feature":
        feats = [doc]
    for feat in feats or []:
        geom = feat.get("geometry") if isinstance(feat, dict) else None
        if not geom:
            continue
        try:
            g = shape(geom)
        except (ValueError, TypeError):
            continue
        if g.is_empty:
            continue
        yield g.simplify(0.0008, preserve_topology=True)


def _rasterize_observed_or_stream(
    path: Path,
    transform_aff: Any,
    height: int,
    width: int,
    epsg: int,
) -> np.ndarray | None:
    """Prefer CEMS observedEvent member; fall back to streamed features."""
    name = path.name.lower()
    observed = path.is_file() and ("observedevent" in name or path.suffix.lower() == ".json")
    if observed and path.stat().st_size > MAX_OBSERVED_JSON_BYTES:
        return None
    if observed:
        try:
            obs = load_observed_from_path(path)
        except (OSError, MemoryError, ValueError):
            obs = None
        geom = obs.get("geometry") if obs else None
        if geom is not None and not getattr(geom, "is_empty", True):
            with suppress(Exception):
                geom = geom.simplify(0.0008, preserve_topology=True)
            try:
                geom_m = _project_wgs84(geom, epsg)
            except Exception:  # noqa: BLE001
                geom_m = None
            if geom_m is not None and not getattr(geom_m, "is_empty", True):
                with suppress(Exception):
                    geom_m = geom_m.simplify(8.0, preserve_topology=True)
                return _rasterize_projected(geom_m, transform_aff, height, width).astype(np.float32)
        return None
    return _rasterize_geojson_path(path, transform_aff, height, width, epsg)


def _rasterize_geojson_path(
    path: Path,
    transform_aff: Any,
    height: int,
    width: int,
    epsg: int,
) -> np.ndarray | None:
    from rasterio.features import rasterize

    if not path.is_file():
        return None
    out = np.zeros((height, width), dtype=np.uint8)
    batch: list[tuple[Any, int]] = []
    n_ok = 0
    max_features = 8000
    for geom in _iter_file_geoms(path):
        try:
            geom_m = _project_wgs84(geom, epsg)
        except Exception:  # noqa: BLE001
            continue
        if geom_m is None or getattr(geom_m, "is_empty", True):
            continue
        with suppress(Exception):
            geom_m = geom_m.simplify(2.0, preserve_topology=True)
        batch.append((geom_m, 1))
        n_ok += 1
        if n_ok >= max_features:
            break
        if len(batch) >= 256:
            out |= rasterize(
                batch,
                out_shape=(height, width),
                transform=transform_aff,
                fill=0,
                dtype="uint8",
                all_touched=True,
            )
            batch = []
    if batch:
        out |= rasterize(
            batch,
            out_shape=(height, width),
            transform=transform_aff,
            fill=0,
            dtype="uint8",
            all_touched=True,
        )
    if n_ok == 0:
        return None
    return out.astype(np.float32)


def rasterize_records(
    recs: list[dict[str, Any]],
    *,
    gsd_m: float = DEFAULT_GSD_M,
    max_dim: int = MAX_RASTER_DIM,
    pad_m: float = 400.0,
    ref_geom: Any | None = None,
    skip_bytes: int | None = None,
) -> tuple[list[np.ndarray | None], dict[str, Any]]:
    """Burn each record onto one shared projected grid. Huge GeoJSON is skipped."""
    sample_lonlat = None
    if ref_geom is not None and not getattr(ref_geom, "is_empty", True):
        c = ref_geom.centroid
        sample_lonlat = (float(c.x), float(c.y))
    for rec in recs:
        if sample_lonlat is not None:
            break
        geom = rec.get("geom")
        if geom is not None and not getattr(geom, "is_empty", True):
            c = geom.centroid
            sample_lonlat = (float(c.x), float(c.y))
            break
        path = rec.get("path")
        if not path:
            continue
        for feat in _iter_file_geoms(Path(path)):
            if feat is None or feat.is_empty:
                continue
            c = feat.centroid
            sample_lonlat = (float(c.x), float(c.y))
            break
    if sample_lonlat is None:
        return [None for _ in recs], {"ok": False, "error": "no_geometry_to_rasterize"}
    lon, lat = sample_lonlat
    epsg = utm_epsg(lon, lat)
    geoms_m = []
    for rec in recs:
        geom = rec.get("geom")
        if geom is None or getattr(geom, "is_empty", True):
            geoms_m.append(None)
            continue
        try:
            geoms_m.append(_project_wgs84(geom, epsg))
        except Exception:  # noqa: BLE001
            geoms_m.append(None)
    ref_m = None
    if ref_geom is not None and not getattr(ref_geom, "is_empty", True):
        try:
            ref_m = _project_wgs84(ref_geom, epsg)
        except Exception:  # noqa: BLE001
            ref_m = None
    bounds = _bounds_from_bounds_or_geoms(geoms_m, ref_m, pad_m=pad_m)
    if bounds is None:
        return [None for _ in recs], {"ok": False, "error": "empty_projected_bounds", "epsg": epsg}
    transform_aff, height, width, used_gsd = _grid_from_bounds(*bounds, gsd_m=gsd_m, max_dim=max_dim)
    masks: list[np.ndarray | None] = []
    for rec, geom_m in zip(recs, geoms_m, strict=True):
        if geom_m is not None:
            masks.append(_rasterize_projected(geom_m, transform_aff, height, width).astype(np.float32))
            rec["raster_skip"] = None
            continue
        path = rec.get("path")
        if path and skip_bytes is not None and Path(path).is_file() and Path(path).stat().st_size > skip_bytes:
            rec["raster_skip"] = "geojson_too_large"
            masks.append(None)
            continue
        if path:
            src = Path(path)
            if (
                src.is_file()
                and src.stat().st_size > MAX_OBSERVED_JSON_BYTES
                and ("observedevent" in src.name.lower() or src.suffix.lower() == ".json")
            ):
                rec["raster_skip"] = "observed_json_too_large"
                masks.append(None)
                continue
            burned = _rasterize_observed_or_stream(src, transform_aff, height, width, epsg)
            if burned is not None:
                rec["raster_skip"] = None
                masks.append(burned)
                continue
        rec["raster_skip"] = "no_geometry"
        masks.append(None)
    n_ok = sum(1 for m in masks if m is not None)
    return masks, {
        "ok": n_ok >= 1,
        "epsg": epsg,
        "gsd_m": used_gsd,
        "height": height,
        "width": width,
        "n_masks": n_ok,
        "schema_mode": "rasterized_vector_legacy17",
    }


def _bounds_from_bounds_or_geoms(
    geoms_m: list[Any | None],
    ref_m: Any | None,
    *,
    pad_m: float,
) -> tuple[float, float, float, float] | None:
    pool = [g for g in geoms_m if g is not None]
    if ref_m is not None:
        pool.append(ref_m)
    return _bounds_from_geoms(pool, pad_m=pad_m)


def oracle_pair_iou(prev_m: np.ndarray, next_m: np.ndarray) -> dict[str, float]:
    prev_b = prev_m >= 0.5
    next_b = next_m >= 0.5
    copy = binary_iou(prev_b, next_b)
    pred = oracle_frozen_decode_mask(prev_m, next_m)
    oracle = binary_iou(pred, next_b)
    ring = fire_growth_ring(prev_m.astype(np.float32))
    return {
        "copy_mask_iou": float(copy),
        "oracle_frozen_iou": float(oracle),
        "oracle_delta_vs_copy": float(oracle - copy),
        "true_ring_pixels": int(np.logical_and(ring, next_b & ~prev_b).sum()),
        "growth_pixels": int((next_b & ~prev_b).sum()),
    }


def _iter_score_tiles(mask: np.ndarray, max_n: int) -> list[tuple[int, int, np.ndarray, str]]:
    h, w = mask.shape
    if min(h, w) < 160:
        step = max(8, PATCH // 4)
        out: list[tuple[int, int, np.ndarray, str]] = []
        for y in range(0, max(1, h - PATCH + 1), step):
            for x in range(0, max(1, w - PATCH + 1), step):
                if y + PATCH > h or x + PATCH > w:
                    continue
                tile = mask[y : y + PATCH, x : x + PATCH]
                if float(tile.mean()) < 0.02:
                    continue
                out.append((y, x, tile.astype(np.float32), "dense"))
                if len(out) >= max_n:
                    return out
        if out:
            return out
    return list(stratified_tiles(mask.astype(np.float32), max_n=max_n))


def collect_pair_tiles(
    prev_m: np.ndarray,
    next_m: np.ndarray,
    cov: dict[str, np.ndarray],
    *,
    max_patches: int,
    caldor: bool = False,
) -> list[dict[str, Any]]:
    if prev_m.shape != next_m.shape:
        return []
    work_prev, work_next, work_cov = prev_m, next_m, cov
    if work_prev.shape[0] < PATCH or work_prev.shape[1] < PATCH:
        work_prev = _pad_to_patch(work_prev)
        work_next = _pad_to_patch(work_next)
        work_cov = {
            k: _pad_to_patch(v) if isinstance(v, np.ndarray) and v.ndim == 2 else v for k, v in cov.items()
        }
    tiles: list[dict[str, Any]] = []
    for y, x, prev_t, kind in _iter_score_tiles(work_prev.astype(np.float32), max_patches):
        tgt = crop(work_next.astype(np.float32), y, x)
        seq = build_caldor_seq_tile(work_cov, y, x) if caldor else build_seq_tile(work_cov, y, x)
        if tgt is None or seq is None:
            continue
        tiles.append(
            {
                "y": int(y),
                "x": int(x),
                "kind": kind,
                "prev": prev_t.astype(np.float32),
                "target": tgt.astype(np.float32),
                "seq": seq.astype(np.float32),
            }
        )
    return tiles


def _pad_to_patch(arr: np.ndarray, size: int = PATCH) -> np.ndarray:
    arr = np.asarray(arr, dtype=np.float32)
    h, w = arr.shape[-2], arr.shape[-1]
    if h >= size and w >= size:
        return arr
    out = np.zeros((size, size), dtype=np.float32)
    out[:h, :w] = arr
    return out


def apply_decode(
    probability: np.ndarray,
    prev: np.ndarray,
    *,
    architecture: str = "residual",
    decode: str = "frozen_ring",
    growth_threshold: float = OOD_GROWTH_THRESHOLD,
) -> np.ndarray:
    prev_b = prev >= 0.5
    if decode == "frozen_ring":
        return decode_complete_proxy_pred(
            probability,
            prev,
            architecture="residual" if architecture == "residual" else architecture,
            target_mode="delta" if architecture == "residual" else "absolute",
            threshold=0.5,
            growth_threshold=growth_threshold,
            require_growth_ring=architecture == "residual",
        )
    if decode == "keep_t0_thr":
        return prev_b | (probability >= float(growth_threshold))
    if decode == "keep_t0_no_ring":
        return prev_b | ((~prev_b) & (probability >= float(growth_threshold)))
    return probability >= 0.5


def score_raster_pair(
    prev_m: np.ndarray,
    next_m: np.ndarray,
    cov: dict[str, np.ndarray],
    model,
    device,
    *,
    max_patches: int = 32,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    """Run frozen residual decode on stratified 64px tiles. Target-blind."""
    import torch

    if prev_m.shape != next_m.shape:
        return {"ok": False, "error": "label_shape_mismatch", "model_iou": None, "n_tiles": 0}
    if prev_m.shape[0] < PATCH or prev_m.shape[1] < PATCH:
        prev_m = _pad_to_patch(prev_m)
        next_m = _pad_to_patch(next_m)
        cov = {k: _pad_to_patch(v) if isinstance(v, np.ndarray) and v.ndim == 2 else v for k, v in cov.items()}
    ious: list[float] = []
    copy_ious: list[float] = []
    oracle_ious: list[float] = []
    for y, x, prev_t, _kind in _iter_score_tiles(prev_m.astype(np.float32), max_patches):
        tgt = crop(next_m.astype(np.float32), y, x)
        if tgt is None and next_m.shape[0] <= PATCH and next_m.shape[1] <= PATCH:
            tgt = _pad_to_patch(next_m)
            prev_t = _pad_to_patch(prev_t if prev_t.shape[0] == PATCH else prev_m)
            y, x = 0, 0
        seq = build_seq_tile(cov, y, x)
        if tgt is None or seq is None:
            continue
        seq_t = torch.from_numpy(seq)
        cur_t = torch.from_numpy(prev_t[np.newaxis, ...].astype(np.float32))
        x_in = prepare_input(seq_t, cur_t).to(device)
        with torch.no_grad():
            logits = model_forward(model, x_in, cur_t.to(device), architecture)
            probability = torch.sigmoid(logits)[0, 0].cpu().numpy()
        pred = apply_decode(
            probability,
            prev_t,
            architecture=architecture,
            decode=decode,
        )
        ious.append(binary_iou(pred, tgt > 0.5))
        copy_ious.append(binary_iou(prev_t >= 0.5, tgt > 0.5))
        oracle_ious.append(binary_iou(oracle_frozen_decode_mask(prev_t, tgt), tgt > 0.5))
    if not ious:
        return {"ok": False, "error": "no_valid_tiles", "model_iou": None, "n_tiles": 0}
    model_iou = float(np.mean(ious))
    copy_iou = float(np.mean(copy_ious))
    oracle_iou = float(np.mean(oracle_ious))
    return {
        "ok": True,
        "model_iou": model_iou,
        "copy_mask_iou": copy_iou,
        "delta_vs_copy": float(model_iou - copy_iou),
        "oracle_frozen_iou": oracle_iou,
        "oracle_delta_vs_copy": float(oracle_iou - copy_iou),
        "n_tiles": len(ious),
        "growth_threshold": OOD_GROWTH_THRESHOLD,
        "decode": decode,
        "architecture": architecture,
    }


def score_pairs_with_masks(
    pairs: list[dict[str, Any]],
    recs: list[dict[str, Any]],
    masks: list[np.ndarray | None],
    cov: dict[str, np.ndarray],
    model,
    device,
    *,
    max_patches: int,
    max_pairs: int | None,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> list[dict[str, Any]]:
    scored = 0
    by_name = {r.get("name"): i for i, r in enumerate(recs)}
    for pair in pairs:
        i0 = by_name.get(pair.get("from"))
        i1 = by_name.get(pair.get("to"))
        if i0 is None or i1 is None:
            continue
        prev_m, next_m = masks[i0], masks[i1]
        if prev_m is None or next_m is None:
            pair["raster_skip"] = recs[i0].get("raster_skip") or recs[i1].get("raster_skip") or "missing_mask"
            continue
        raster_copy = binary_iou(prev_m > 0, next_m > 0)
        pair["raster_copy_iou"] = raster_copy
        if pair.get("copy_mask_iou") is None:
            pair["copy_mask_iou"] = raster_copy
            pair["label_mask_iou"] = raster_copy
            pair["pair_class"] = classify_temporal_pair(
                delta_hours=pair.get("delta_hours"),
                label_mask_iou=raster_copy,
                prev_kind=pair.get("from_kind"),
                next_kind=pair.get("to_kind"),
            )
        if pair.get("pair_class") == "incompatible_product_kind":
            continue
        if max_pairs is not None and scored >= int(max_pairs):
            pair["raster_skip"] = "max_pairs"
            continue
        result = score_raster_pair(
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
        pair["schema_mode"] = "rasterized_vector_legacy17"
        if result.get("copy_mask_iou") is not None:
            pair["tile_copy_mask_iou"] = result["copy_mask_iou"]
        pair["oracle_frozen_iou"] = result.get("oracle_frozen_iou")
        pair["oracle_delta_vs_copy"] = result.get("oracle_delta_vs_copy")
        full_oracle = oracle_pair_iou(prev_m, next_m)
        pair["full_oracle_frozen_iou"] = full_oracle["oracle_frozen_iou"]
        pair["full_oracle_delta_vs_copy"] = full_oracle["oracle_delta_vs_copy"]
    return pairs


def summarize_model_scores(pairs: list[dict[str, Any]]) -> dict[str, Any]:
    used = [
        p
        for p in pairs
        if p.get("pair_class") == "usable" and p.get("complete_proxy_model_iou") is not None
    ]
    scored = [p for p in pairs if p.get("model_iou") is not None]
    used_model = [float(p["complete_proxy_model_iou"]) for p in used]
    used_copy = [float(p["copy_mask_iou"]) for p in used if p.get("copy_mask_iou") is not None]
    used_delta = [float(p["delta_vs_copy"]) for p in used if p.get("delta_vs_copy") is not None]
    scored_model = [float(p["model_iou"]) for p in scored]
    used_oracle = [float(p["oracle_frozen_iou"]) for p in used if p.get("oracle_frozen_iou") is not None]
    model_iou = float(sum(used_model) / len(used_model)) if used_model else None
    scored_model_iou = float(sum(scored_model) / len(scored_model)) if scored_model else None
    copy_iou = float(sum(used_copy) / len(used_copy)) if used_copy else None
    oracle_iou = float(sum(used_oracle) / len(used_oracle)) if used_oracle else None
    return {
        "n_pairs_used": len(used),
        "n_pairs_scored": len(scored),
        "model_iou": model_iou,
        "complete_proxy_model_iou": model_iou,
        "scored_model_iou": scored_model_iou,
        "copy_baseline_iou": copy_iou,
        "usable_copy_mean": copy_iou,
        "oracle_frozen_iou": oracle_iou,
        "oracle_delta_vs_copy": (
            float(oracle_iou - copy_iou) if oracle_iou is not None and copy_iou is not None else None
        ),
        "delta_vs_copy": (
            float(sum(used_delta) / len(used_delta)) if used_delta else None
        ),
        "schema_compatible": scored_model_iou is not None,
        "skip_class": (
            None
            if scored_model_iou is not None
            else (
                "incompatible_product_kind"
                if pairs and all(p.get("pair_class") == "incompatible_product_kind" for p in pairs)
                else "vector_only_no_legacy17"
            )
        ),
        "metric_kind": "complete_proxy_frozen_decode" if scored else "label_vs_label_copy",
    }


def caldor_stamp(utc: str | None) -> str | None:
    dt = parse_iso_utc(str(utc or ""))
    if dt is None:
        return None
    return dt.strftime("%Y%m%dT%H%M%SZ")


def load_tif(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1), dtype=np.float32)


def caldor_cov_at(caldor_root: Path, utc: str) -> dict[str, Any] | None:
    stamp = caldor_stamp(utc)
    if stamp is None:
        return None
    dyn = caldor_root / "covariates" / "dynamic" / stamp
    static = caldor_root / "covariates" / "static"
    needed = {
        "elevation": static / "dem_m.tif",
        "veg": static / "canopy_presence.tif",
        "max_temp": dyn / "max_temperature_c.tif",
        "min_temp": dyn / "min_temperature_c.tif",
        "humidity": dyn / "relative_humidity_pct.tif",
        "wind_speed": dyn / "wind_speed_ms.tif",
        "wind_dir": dyn / "wind_direction_deg.tif",
        "precip": dyn / "precipitation_mm_24h.tif",
        "erc": dyn / "erc_g.tif",
    }
    if not all(p.is_file() for p in needed.values()):
        dyn_root = caldor_root / "covariates" / "dynamic"
        available = sorted(p.name for p in dyn_root.iterdir() if p.is_dir()) if dyn_root.is_dir() else []
        earlier = [name for name in available if name <= stamp]
        if not earlier:
            return None
        fallback = earlier[-1]
        dyn = caldor_root / "covariates" / "dynamic" / fallback
        needed = {
            "elevation": static / "dem_m.tif",
            "veg": static / "canopy_presence.tif",
            "max_temp": dyn / "max_temperature_c.tif",
            "min_temp": dyn / "min_temperature_c.tif",
            "humidity": dyn / "relative_humidity_pct.tif",
            "wind_speed": dyn / "wind_speed_ms.tif",
            "wind_dir": dyn / "wind_direction_deg.tif",
            "precip": dyn / "precipitation_mm_24h.tif",
            "erc": dyn / "erc_g.tif",
        }
        if not all(p.is_file() for p in needed.values()):
            return None
        stamp = fallback
    arrays = {key: load_tif(path) for key, path in needed.items()}
    shapes = {arr.shape for arr in arrays.values()}
    if len(shapes) != 1:
        return None
    temperature = 0.5 * (arrays["max_temp"] + arrays["min_temp"])
    return {
        "elevation": arrays["elevation"],
        "temperature": temperature.astype(np.float32),
        "humidity": arrays["humidity"],
        "wind_speed": arrays["wind_speed"],
        "wind_dir": arrays["wind_dir"],
        "precip": arrays["precip"],
        "veg": arrays["veg"],
        "max_temp": arrays["max_temp"],
        "min_temp": arrays["min_temp"],
        "erc": arrays["erc"],
        "stamp": stamp,
        "schema_mode": "caldor_physical_to_legacy17",
    }


def build_caldor_seq_tile(cov: dict[str, np.ndarray], y: int, x: int) -> np.ndarray | None:
    keys = (
        "elevation",
        "wind_dir",
        "wind_speed",
        "max_temp",
        "min_temp",
        "humidity",
        "precip",
        "veg",
        "erc",
    )
    parts: dict[str, np.ndarray] = {}
    for key in keys:
        piece = crop(cov[key], y, x)
        if piece is None:
            return None
        parts[key] = piece
    ch = build_legacy17_channels(
        elevation=parts["elevation"],
        wind_dir=parts["wind_dir"],
        wind_speed=parts["wind_speed"],
        max_temp=parts["max_temp"],
        min_temp=parts["min_temp"],
        humidity=parts["humidity"],
        precip=parts["precip"],
        veg=parts["veg"],
        erc=parts["erc"],
    )
    return ch[np.newaxis, np.newaxis, ...].astype(np.float32)


def score_caldor_pair(
    prev_m: np.ndarray,
    next_m: np.ndarray,
    cov: dict[str, np.ndarray],
    model,
    device,
    *,
    max_patches: int,
    architecture: str = "residual",
    decode: str = "frozen_ring",
) -> dict[str, Any]:
    import torch

    if prev_m.shape != next_m.shape:
        return {"ok": False, "error": "label_shape_mismatch", "model_iou": None, "n_tiles": 0}
    ious: list[float] = []
    copy_ious: list[float] = []
    oracle_ious: list[float] = []
    for y, x, prev_t, _kind in _iter_score_tiles(prev_m.astype(np.float32), max_patches):
        tgt = crop(next_m.astype(np.float32), y, x)
        seq = build_caldor_seq_tile(cov, y, x)
        if tgt is None or seq is None:
            continue
        seq_t = torch.from_numpy(seq)
        cur_t = torch.from_numpy(prev_t[np.newaxis, ...].astype(np.float32))
        x_in = prepare_input(seq_t, cur_t).to(device)
        with torch.no_grad():
            logits = model_forward(model, x_in, cur_t.to(device), architecture)
            probability = torch.sigmoid(logits)[0, 0].cpu().numpy()
        pred = apply_decode(
            probability,
            prev_t,
            architecture=architecture,
            decode=decode,
        )
        ious.append(binary_iou(pred, tgt > 0.5))
        copy_ious.append(binary_iou(prev_t >= 0.5, tgt > 0.5))
        oracle_ious.append(binary_iou(oracle_frozen_decode_mask(prev_t, tgt), tgt > 0.5))
    if not ious:
        return {"ok": False, "error": "no_valid_tiles", "model_iou": None, "n_tiles": 0}
    model_iou = float(np.mean(ious))
    copy_iou = float(np.mean(copy_ious))
    oracle_iou = float(np.mean(oracle_ious))
    return {
        "ok": True,
        "model_iou": model_iou,
        "copy_mask_iou": copy_iou,
        "delta_vs_copy": float(model_iou - copy_iou),
        "oracle_frozen_iou": oracle_iou,
        "oracle_delta_vs_copy": float(oracle_iou - copy_iou),
        "n_tiles": len(ious),
        "schema_mode": "caldor_physical_to_legacy17",
    }


def aoi_ref_geom(pack: Path, aoi: str) -> Any | None:
    path = pack / "aois.geojson"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    token = str(aoi).upper()
    for feat in doc.get("features") or []:
        name = str((feat.get("properties") or {}).get("name") or "")
        if token in name.upper():
            geom = feat.get("geometry")
            if geom:
                try:
                    return shape(geom)
                except (ValueError, TypeError):
                    return None
    return None
