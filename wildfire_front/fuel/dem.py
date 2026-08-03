"""Real DEM load/cache/download for fuel–terrain stacks.

Fallback chain (``resolve_dem``):
  local GeoTIFF → cache → optional GLO-30 HTTPS (opt-in) → optional synthetic

Network is **never** used unless ``allow_download=True``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import numpy as np

TOBARRA_BBOX_WGS84: tuple[float, float, float, float] = (-1.72, 38.58, -1.66, 38.63)
DEFAULT_CELL_M = 25.0
DEFAULT_CRS = "EPSG:32630"  # UTM 30N (ops_perimeter METRIC_CRS)

# AWS Open Data Copernicus DEM 30 m (GLO-30 COG)
_GLO30_BUCKET = "https://copernicus-dem-30m.s3.amazonaws.com"


class DemFetchError(Exception):
    """Network / remote DEM failure."""


class DemUnavailableError(Exception):
    """No local/cache/download/synthetic path succeeded."""

    def __init__(self, reasons: list[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass
class DemProduct:
    elevation_m: np.ndarray
    transform: Any  # affine.Affine
    crs: str
    cell_size_m: float
    bbox_wgs84: list[float]
    source: str  # local_geotiff | copernicus_glo30 | synthetic
    source_uri: str | None = None
    synthetic: bool = False
    nodata: float | None = None
    cache_path: str | None = None
    sha256: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("elevation_m", None)
        t = self.transform
        if t is not None:
            d["transform"] = [float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f)]
        d["shape"] = list(self.elevation_m.shape)
        d["elevation_m_stats"] = {
            "min": float(np.nanmin(self.elevation_m)),
            "max": float(np.nanmax(self.elevation_m)),
            "mean": float(np.nanmean(self.elevation_m)),
        }
        return d


def _require_rasterio():
    try:
        import affine  # noqa: F401
        import rasterio
        from rasterio.transform import from_bounds
        from rasterio.warp import Resampling, reproject, transform_bounds
    except ImportError as exc:  # pragma: no cover
        raise ImportError("rasterio (+ affine) required for DEM I/O") from exc
    return rasterio, from_bounds, transform_bounds, reproject, Resampling


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_array(arr: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def glo30_tile_ids_for_bbox(bbox_wgs84: Sequence[float]) -> list[str]:
    """1° GLO-30 tile keys covering bbox (west,south,east,north)."""
    w, s, e, n = (float(x) for x in bbox_wgs84)
    if e < w or n < s:
        raise ValueError(f"invalid bbox {bbox_wgs84}")
    lat0 = int(math.floor(s))
    lat1 = int(math.floor(n - 1e-12))
    lon0 = int(math.floor(w))
    lon1 = int(math.floor(e - 1e-12))
    tiles: list[str] = []
    for lat in range(lat0, lat1 + 1):
        for lon in range(lon0, lon1 + 1):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            tiles.append(f"{ns}{abs(lat):02d}_{ew}{abs(lon):03d}")
    return tiles


def glo30_public_href(tile_id: str) -> str:
    """HTTPS object URL for AWS Open Data GLO-30 COG.

    tile_id format: N38_W002
    """
    # Copernicus_DSM_COG_10_N38_00_W002_00_DEM/...
    parts = tile_id.replace("-", "_").split("_")
    if len(parts) != 2:
        raise ValueError(f"bad tile_id {tile_id}")
    ns_lat, ew_lon = parts[0], parts[1]
    base = (
        f"Copernicus_DSM_COG_10_{ns_lat}_00_{ew_lon}_00_DEM/"
        f"Copernicus_DSM_COG_10_{ns_lat}_00_{ew_lon}_00_DEM.tif"
    )
    return f"{_GLO30_BUCKET}/{base}"


def _grid_for_bbox(
    bbox_wgs84: Sequence[float],
    *,
    target_crs: str,
    cell_size_m: float,
):
    rasterio, from_bounds, transform_bounds, _, _ = _require_rasterio()
    w, s, e, n = (float(x) for x in bbox_wgs84)
    left, bottom, right, top = transform_bounds("EPSG:4326", target_crs, w, s, e, n, densify_pts=21)
    width = max(2, int(math.ceil((right - left) / cell_size_m)))
    height = max(2, int(math.ceil((top - bottom) / cell_size_m)))
    transform = from_bounds(left, bottom, right, top, width, height)
    return transform, width, height, (left, bottom, right, top)


def load_dem_geotiff(
    path: Path | str,
    *,
    bbox_wgs84: Sequence[float] | None = None,
    target_crs: str = DEFAULT_CRS,
    cell_size_m: float = DEFAULT_CELL_M,
) -> DemProduct:
    """Load local DEM; optional clip+reproject to metric grid."""
    rasterio, _, transform_bounds, reproject, Resampling = _require_rasterio()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))

    with rasterio.open(p) as src:
        src_crs = str(src.crs) if src.crs else target_crs
        if bbox_wgs84 is None:
            # reproject full dataset to target grid at cell_size
            bounds = src.bounds
            # approximate bbox in WGS84 for metadata
            try:
                w, s, e, n = transform_bounds(src_crs, "EPSG:4326", *bounds, densify_pts=21)
                bbox = [float(w), float(s), float(e), float(n)]
            except Exception:
                bbox = list(TOBARRA_BBOX_WGS84)
            transform, width, height, _ = _grid_for_bbox(
                bbox, target_crs=target_crs, cell_size_m=cell_size_m
            )
        else:
            bbox = [float(x) for x in bbox_wgs84]
            transform, width, height, _ = _grid_for_bbox(
                bbox, target_crs=target_crs, cell_size_m=cell_size_m
            )

        dest = np.full((height, width), np.nan, dtype=np.float64)
        reproject(
            source=rasterio.band(src, 1),
            destination=dest,
            src_transform=src.transform,
            src_crs=src.crs or target_crs,
            dst_transform=transform,
            dst_crs=target_crs,
            resampling=Resampling.bilinear,
            src_nodata=src.nodata,
            dst_nodata=np.nan,
        )

        # If requested bbox does not intersect source, fall back to full source extent
        if not np.isfinite(dest).any():
            try:
                w, s, e, n = transform_bounds(
                    src_crs, "EPSG:4326", *src.bounds, densify_pts=21
                )
                bbox = [float(w), float(s), float(e), float(n)]
            except Exception:
                bbox = list(TOBARRA_BBOX_WGS84)
            transform, width, height, _ = _grid_for_bbox(
                bbox, target_crs=target_crs, cell_size_m=cell_size_m
            )
            dest = np.full((height, width), np.nan, dtype=np.float64)
            reproject(
                source=rasterio.band(src, 1),
                destination=dest,
                src_transform=src.transform,
                src_crs=src.crs or target_crs,
                dst_transform=transform,
                dst_crs=target_crs,
                resampling=Resampling.bilinear,
                src_nodata=src.nodata,
                dst_nodata=np.nan,
            )
            notes_fallback = ["fallback_source_extent_no_bbox_overlap"]
        else:
            notes_fallback = []

    # fill tiny holes
    nan_frac = float(np.mean(~np.isfinite(dest))) if dest.size else 1.0
    notes = [f"loaded_local:{p.name}", f"nan_frac={nan_frac:.4f}"] + notes_fallback
    if 0 < nan_frac < 0.01:
        mask = ~np.isfinite(dest)
        if mask.any() and (~mask).any():
            fill = float(np.nanmean(dest))
            dest = np.where(mask, fill, dest)
            notes.append("filled_nan_with_global_mean")
    if not np.isfinite(dest).any():
        raise ValueError(f"DEM load produced no valid elevations from {p}")

    sha = _sha256_array(dest)
    return DemProduct(
        elevation_m=dest,
        transform=transform,
        crs=target_crs,
        cell_size_m=float(cell_size_m),
        bbox_wgs84=list(bbox),
        source="local_geotiff",
        source_uri=str(p.resolve()),
        synthetic=False,
        nodata=None,
        cache_path=None,
        sha256=sha,
        notes=notes,
    )


def write_dem_geotiff(product: DemProduct, path: Path | str) -> Path:
    rasterio, _, _, _, _ = _require_rasterio()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    elev = np.asarray(product.elevation_m, dtype=np.float64)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=elev.shape[0],
        width=elev.shape[1],
        count=1,
        dtype="float64",
        crs=product.crs,
        transform=product.transform,
        compress="deflate",
    ) as dst:
        dst.write(elev, 1)
    return path


def download_glo30_window(
    bbox_wgs84: Sequence[float],
    cache_path: Path,
    *,
    cell_size_m: float = DEFAULT_CELL_M,
    target_crs: str = DEFAULT_CRS,
    timeout_s: int = 60,
    force: bool = False,
) -> DemProduct:
    """Windowed GLO-30 via rasterio HTTPS; cache to GeoTIFF."""
    rasterio, _, _, reproject, Resampling = _require_rasterio()
    cache_path = Path(cache_path)
    if cache_path.is_file() and not force:
        prod = load_dem_geotiff(
            cache_path, bbox_wgs84=bbox_wgs84, target_crs=target_crs, cell_size_m=cell_size_m
        )
        prod.source = "copernicus_glo30"
        prod.cache_path = str(cache_path.resolve())
        prod.notes.append("loaded_from_cache")
        prod.sha256 = _sha256_file(cache_path)
        return prod

    tiles = glo30_tile_ids_for_bbox(bbox_wgs84)
    transform, width, height, _ = _grid_for_bbox(
        bbox_wgs84, target_crs=target_crs, cell_size_m=cell_size_m
    )
    dest = np.full((height, width), np.nan, dtype=np.float64)
    hrefs: list[str] = []
    env_opts = {
        "GDAL_HTTP_TIMEOUT": str(timeout_s),
        "GDAL_HTTP_CONNECTTIMEOUT": "15",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
    }

    try:
        with rasterio.Env(**env_opts):
            for tid in tiles:
                href = glo30_public_href(tid)
                hrefs.append(href)
                try:
                    with rasterio.open(href) as src:
                        reproject(
                            source=rasterio.band(src, 1),
                            destination=dest,
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=target_crs,
                            resampling=Resampling.bilinear,
                            src_nodata=src.nodata,
                            dst_nodata=np.nan,
                        )
                except Exception as exc:
                    raise DemFetchError(f"GLO-30 tile {tid} failed: {exc}") from exc
    except DemFetchError:
        raise
    except Exception as exc:
        raise DemFetchError(f"GLO-30 download failed: {exc}") from exc

    if not np.isfinite(dest).any():
        raise DemFetchError("GLO-30 window is all nodata")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    product = DemProduct(
        elevation_m=dest,
        transform=transform,
        crs=target_crs,
        cell_size_m=float(cell_size_m),
        bbox_wgs84=[float(x) for x in bbox_wgs84],
        source="copernicus_glo30",
        source_uri=";".join(hrefs),
        synthetic=False,
        cache_path=str(cache_path.resolve()),
        notes=[f"tiles={tiles}", f"hrefs={len(hrefs)}"],
    )
    write_dem_geotiff(product, cache_path)
    product.sha256 = _sha256_file(cache_path)
    manifest = {
        "source": "copernicus_glo30",
        "bbox_wgs84": product.bbox_wgs84,
        "crs": product.crs,
        "cell_size_m": product.cell_size_m,
        "tiles": tiles,
        "hrefs": hrefs,
        "sha256": product.sha256,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "cache_path": str(cache_path.resolve()),
    }
    (cache_path.parent / "dem_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return product


def synthetic_dem_product(
    *,
    n: int = 40,
    cell_size_m: float = DEFAULT_CELL_M,
    seed: int = 42,
    bbox_wgs84: Sequence[float] = TOBARRA_BBOX_WGS84,
    target_crs: str = DEFAULT_CRS,
) -> DemProduct:
    """Rolling synthetic DEM matching historical stack geometry style."""
    from affine import Affine

    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, n)
    x = np.linspace(0, 1, n)
    xx, yy = np.meshgrid(x, y)
    dem = 700.0 + 25.0 * np.sin(2.5 * np.pi * xx) + 18.0 * np.cos(2.0 * np.pi * yy)
    dem = dem + rng.normal(0, 1.5, size=dem.shape)

    # place grid in metric CRS covering bbox
    try:
        transform, _, _, _ = _grid_for_bbox(bbox_wgs84, target_crs=target_crs, cell_size_m=cell_size_m)
        # override shape: rebuild transform for n x n
        rasterio, from_bounds, transform_bounds, _, _ = _require_rasterio()
        w, s, e, n_b = (float(x) for x in bbox_wgs84)
        left, bottom, right, top = transform_bounds(
            "EPSG:4326", target_crs, w, s, e, n_b, densify_pts=21
        )
        transform = from_bounds(left, bottom, right, top, n, n)
        # rescale cell to match actual
        cell_x = (right - left) / n
        cell_y = (top - bottom) / n
        cell_size_m = float((abs(cell_x) + abs(cell_y)) / 2.0)
    except Exception:
        transform = Affine(cell_size_m, 0, 0, 0, -cell_size_m, n * cell_size_m)

    return DemProduct(
        elevation_m=dem.astype(np.float64),
        transform=transform,
        crs=target_crs,
        cell_size_m=float(cell_size_m),
        bbox_wgs84=[float(x) for x in bbox_wgs84],
        source="synthetic",
        source_uri=None,
        synthetic=True,
        sha256=_sha256_array(dem),
        notes=["synthetic_dem_explicit_allow"],
    )


def resolve_dem(
    *,
    bbox_wgs84: Sequence[float] = TOBARRA_BBOX_WGS84,
    local_path: Path | str | None = None,
    cache_dir: Path | None = None,
    allow_download: bool = False,
    dem_fallback: str | None = None,  # reserved: "pc"
    allow_synthetic: bool = False,
    cell_size_m: float = DEFAULT_CELL_M,
    synthetic_n: int = 40,
    synthetic_seed: int = 42,
    force_download: bool = False,
) -> DemProduct:
    """Resolve DEM via fallback chain. Download only if allow_download."""
    reasons: list[str] = []
    bbox = [float(x) for x in bbox_wgs84]

    if local_path is not None:
        lp = Path(local_path)
        if lp.is_file():
            return load_dem_geotiff(lp, bbox_wgs84=bbox, cell_size_m=cell_size_m)
        reasons.append(f"local_missing:{lp}")

    if cache_dir is not None:
        cp = Path(cache_dir) / "glo30_window.tif"
        if cp.is_file():
            prod = load_dem_geotiff(cp, bbox_wgs84=bbox, cell_size_m=cell_size_m)
            prod.source = "copernicus_glo30"
            prod.cache_path = str(cp.resolve())
            prod.notes.append("resolved_from_cache")
            try:
                prod.sha256 = _sha256_file(cp)
            except OSError:
                pass
            return prod
        reasons.append(f"cache_missing:{cp}")

    if allow_download:
        if cache_dir is None:
            reasons.append("allow_download_but_no_cache_dir")
        else:
            try:
                return download_glo30_window(
                    bbox,
                    Path(cache_dir) / "glo30_window.tif",
                    cell_size_m=cell_size_m,
                    force=force_download,
                )
            except DemFetchError as exc:
                reasons.append(f"download_failed:{exc}")
                if dem_fallback == "pc":
                    reasons.append("dem_fallback_pc_not_implemented")
    else:
        reasons.append("download_disabled_default")

    if allow_synthetic:
        return synthetic_dem_product(
            n=synthetic_n,
            cell_size_m=cell_size_m,
            seed=synthetic_seed,
            bbox_wgs84=bbox,
        )

    raise DemUnavailableError(reasons)
