"""STAC search + windowed Sentinel-2 L2A COG reads for dNBR."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

# Element84 Earth Search (public, no key for search)
EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-l2a"

# Preferred asset keys for NBR (nir + swir22≈B12)
NIR_KEYS = ("nir", "B08", "rededge3")  # prefer nir
SWIR_KEYS = ("swir22", "B12", "swir16", "B11")


def bbox_from_geojson(path: Path | str) -> tuple[float, float, float, float]:
    """Return (minx, miny, maxx, maxy) WGS84 from FeatureCollection."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return bbox_from_featurecollection(data)


def bbox_from_featurecollection(fc: Mapping[str, Any]) -> tuple[float, float, float, float]:
    from shapely.geometry import shape
    from shapely.ops import unary_union

    geoms = []
    for ft in fc.get("features") or []:
        g = ft.get("geometry")
        if g:
            geoms.append(shape(g))
    if not geoms:
        raise ValueError("no geometries in FeatureCollection")
    b = unary_union(geoms).bounds
    return float(b[0]), float(b[1]), float(b[2]), float(b[3])


def stac_search(
    bbox: Sequence[float],
    datetime_range: str,
    *,
    max_cloud: float = 40.0,
    limit: int = 8,
    stac_url: str = EARTH_SEARCH,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    """POST /search for sentinel-2-l2a items sorted by cloud cover."""
    body = {
        "collections": [COLLECTION],
        "bbox": [float(x) for x in bbox],
        "datetime": datetime_range,
        "limit": int(limit),
        "query": {"eo:cloud_cover": {"lt": float(max_cloud)}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    req = urllib.request.Request(
        f"{stac_url.rstrip('/')}/search",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/geo+json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    feats = payload.get("features") or []
    return list(feats)


def pick_asset_href(item: Mapping[str, Any], keys: Sequence[str]) -> str | None:
    assets = item.get("assets") or {}
    for k in keys:
        if k in assets and isinstance(assets[k], dict):
            href = assets[k].get("href")
            if href:
                return str(href)
    # case-insensitive fallback
    lower = {str(k).lower(): v for k, v in assets.items()}
    for k in keys:
        v = lower.get(k.lower())
        if isinstance(v, dict) and v.get("href"):
            return str(v["href"])
    return None


def item_summary(item: Mapping[str, Any]) -> dict[str, Any]:
    props = item.get("properties") or {}
    return {
        "id": item.get("id"),
        "datetime": props.get("datetime"),
        "eo:cloud_cover": props.get("eo:cloud_cover"),
        "platform": props.get("platform"),
        "nir_href": pick_asset_href(item, NIR_KEYS),
        "swir_href": pick_asset_href(item, SWIR_KEYS),
        "bbox": item.get("bbox"),
    }


def read_cog_window(
    href: str,
    bbox: Sequence[float],
    *,
    max_size: int = 256,
    scale: float = 1e-4,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Windowed read of a COG (HTTP) clipped to bbox, downsampled to max_size."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    from .dnbr import scale_s2_reflectance

    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF,.tiff"):
        with rasterio.open(href) as ds:
            left, bottom, right, top = transform_bounds(
                "EPSG:4326", ds.crs, bbox[0], bbox[1], bbox[2], bbox[3], densify_pts=21
            )
            window = from_bounds(left, bottom, right, top, transform=ds.transform)
            # cap resolution
            win_h = max(1, int(round(window.height)))
            win_w = max(1, int(round(window.width)))
            out_h = min(max_size, win_h)
            out_w = min(max_size, win_w)
            data = ds.read(
                1,
                window=window,
                out_shape=(out_h, out_w),
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0,
            )
            meta = {
                "crs": str(ds.crs),
                "src_shape": [ds.height, ds.width],
                "window_shape": [out_h, out_w],
                "dtype": str(ds.dtypes[0]),
            }
    arr = scale_s2_reflectance(data, scale=scale)
    return arr, meta


def load_nbr_for_item(
    item: Mapping[str, Any],
    bbox: Sequence[float],
    *,
    max_size: int = 256,
) -> tuple[np.ndarray, dict[str, Any]]:
    nir_h = pick_asset_href(item, NIR_KEYS)
    swir_h = pick_asset_href(item, SWIR_KEYS)
    if not nir_h or not swir_h:
        raise RuntimeError(f"item {item.get('id')} missing NIR/SWIR assets")
    from .dnbr import compute_nbr

    nir, m_nir = read_cog_window(nir_h, bbox, max_size=max_size)
    swir, m_swir = read_cog_window(swir_h, bbox, max_size=max_size)
    # align shapes if needed
    h = min(nir.shape[0], swir.shape[0])
    w = min(nir.shape[1], swir.shape[1])
    nbr = compute_nbr(nir[:h, :w], swir[:h, :w])
    return nbr, {
        "nir": m_nir,
        "swir": m_swir,
        "nir_href": nir_h,
        "swir_href": swir_h,
        "item_id": item.get("id"),
    }


def default_date_windows(
    *,
    event_date: str | None = None,
    pre_days: int = 45,
    post_start_days: int = 5,
    post_end_days: int = 60,
) -> tuple[str, str]:
    """Return (pre_range, post_range) ISO datetime STAC strings.

    event_date: YYYY-MM-DD mid-fire estimate.
    """
    if event_date:
        mid = datetime.strptime(event_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        mid = datetime.now(timezone.utc) - timedelta(days=180)
    # End pre-window well before fire peak so STAC does not pick an "active fire" scene as pre
    pre_end = mid - timedelta(days=7)
    pre_start = mid - timedelta(days=pre_days)
    post_start = mid + timedelta(days=post_start_days)
    post_end = mid + timedelta(days=post_end_days)

    def rng(a: datetime, b: datetime) -> str:
        return f"{a.strftime('%Y-%m-%dT00:00:00Z')}/{b.strftime('%Y-%m-%dT23:59:59Z')}"

    return rng(pre_start, pre_end), rng(post_start, post_end)


# Known CEMS activations → approximate event date (for auto windows)
KNOWN_EVENT_DATES: dict[str, str] = {
    "EMSR578": "2022-07-15",  # Catalonia / Pont de Suert area
    "EMSR581": "2022-07-18",
    "EMSR583": "2022-07-20",
    "EMSR632": "2023-08-15",
    "EMSR629": "2023-07-20",
}
