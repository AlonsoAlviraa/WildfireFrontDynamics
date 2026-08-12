"""Land-cover → fuel model map for Tobarra / IF stacks.

Sources (priority in ``resolve_fuel_map``):
1. Local land-cover GeoTIFF (CLC / WorldCover / Prometheus codes)
2. Cache under ``data/fuel_map/``
3. Opt-in ESA WorldCover 10 m COG window (AWS open data)
4. Synthetic mosaic (explicit allow only)

Honesty: WorldCover→fuel is an **engineering crosswalk**, not UCO40/Vega field inventory.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from .models import (
    crosswalk_tables,
    fuel_from_landcover,
    get_fuel,
)

TOBARRA_BBOX_WGS84 = (-1.72, 38.58, -1.66, 38.63)
DEFAULT_CRS = "EPSG:32630"
DEFAULT_CELL_M = 25.0

# ESA WorldCover v200 2021 3° tiles on open AWS
_WC_BUCKET = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"


class FuelMapFetchError(Exception):
    """Remote land-cover download failure."""


class FuelMapUnavailableError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = list(reasons)
        super().__init__("; ".join(self.reasons))


@dataclass
class FuelMapProduct:
    """Aligned land-cover + fuel class grids."""

    landcover_code: np.ndarray  # float64 HxW codes
    fuel_id_grid: np.ndarray  # object HxW fuel ids
    height_m: np.ndarray  # proxy veg height from fuel model
    scheme: str  # worldcover | clc | prometheus | synthetic
    source: str  # local_geotiff | esa_worldcover | synthetic
    transform: Any
    crs: str
    cell_size_m: float
    bbox_wgs84: list[float]
    fuel_mix: dict[str, float]
    fuel_id_dominant: str
    source_uri: str | None = None
    cache_path: str | None = None
    sha256: str | None = None
    synthetic: bool = False
    notes: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("landcover_code", None)
        d.pop("fuel_id_grid", None)
        d.pop("height_m", None)
        t = self.transform
        if t is not None:
            try:
                d["transform"] = [
                    float(t.a),
                    float(t.b),
                    float(t.c),
                    float(t.d),
                    float(t.e),
                    float(t.f),
                ]
            except Exception:
                d["transform"] = None
        d["shape"] = list(self.landcover_code.shape)
        d["unique_landcover"] = sorted(
            {int(x) for x in np.unique(self.landcover_code) if np.isfinite(x)}
        )
        d["unique_fuels"] = sorted(set(self.fuel_id_grid.ravel().tolist()))
        return d


def _require_rasterio():
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.warp import Resampling, reproject, transform_bounds

    return rasterio, from_bounds, transform_bounds, reproject, Resampling


def _sha256_array(arr: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(np.ascontiguousarray(arr).tobytes())
    return h.hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def worldcover_tile_id(lat: float, lon: float) -> str:
    """ESA WorldCover 3° tile id for a point (e.g. N36W003)."""
    # Tile lower-left is floored to 3° multiples
    lat0 = int(math.floor(lat / 3.0) * 3)
    lon0 = int(math.floor(lon / 3.0) * 3)
    ns = "N" if lat0 >= 0 else "S"
    ew = "E" if lon0 >= 0 else "W"
    return f"{ns}{abs(lat0):02d}{ew}{abs(lon0):03d}"


def worldcover_tiles_for_bbox(bbox_wgs84: Sequence[float]) -> list[str]:
    w, s, e, n = (float(x) for x in bbox_wgs84)
    tiles: set[str] = set()
    # sample corners + center
    for lat in (s, n, 0.5 * (s + n)):
        for lon in (w, e, 0.5 * (w + e)):
            tiles.add(worldcover_tile_id(lat, lon))
    return sorted(tiles)


def worldcover_public_href(tile_id: str) -> str:
    # ESA_WorldCover_10m_2021_v200_N36W003_Map.tif
    return f"{_WC_BUCKET}/ESA_WorldCover_10m_2021_v200_{tile_id}_Map.tif"


def _grid_for_bbox(bbox_wgs84: Sequence[float], *, target_crs: str, cell_size_m: float):
    rasterio, from_bounds, transform_bounds, _, _ = _require_rasterio()
    w, s, e, n = (float(x) for x in bbox_wgs84)
    left, bottom, right, top = transform_bounds("EPSG:4326", target_crs, w, s, e, n, densify_pts=21)
    width = max(2, int(math.ceil((right - left) / cell_size_m)))
    height = max(2, int(math.ceil((top - bottom) / cell_size_m)))
    transform = from_bounds(left, bottom, right, top, width, height)
    return transform, width, height


def codes_to_fuel_layers(
    codes: np.ndarray,
    *,
    scheme: str,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, dict[str, float], str, list[str]]:
    """Map landcover code grid → fuel_id grid + height proxy + mix."""
    rng = np.random.default_rng(seed)
    h, w = codes.shape
    fuel_ids = np.empty((h, w), dtype=object)
    height = np.zeros((h, w), dtype=np.float64)
    for i in range(h):
        for j in range(w):
            c = codes[i, j]
            if not np.isfinite(c):
                fm = get_fuel("UNKNOWN")
            else:
                fm = fuel_from_landcover(c, scheme=scheme)
            fuel_ids[i, j] = fm.id
            height[i, j] = fm.height_m * (0.9 + 0.2 * rng.random()) if fm.fuel_load > 0 else 0.0
    flat = fuel_ids.ravel().tolist()
    mix: dict[str, float] = {}
    for fid in flat:
        mix[fid] = mix.get(fid, 0) + 1
    total = float(len(flat)) or 1.0
    mix = {k: round(v / total, 4) for k, v in sorted(mix.items(), key=lambda x: -x[1])}
    dominant = max(mix, key=mix.get) if mix else "UNKNOWN"  # type: ignore[arg-type]
    return fuel_ids, height, mix, dominant, sorted(set(flat))


def load_landcover_geotiff(
    path: Path | str,
    *,
    bbox_wgs84: Sequence[float] | None = None,
    target_crs: str = DEFAULT_CRS,
    cell_size_m: float = DEFAULT_CELL_M,
    scheme: str = "worldcover",
    reference_shape: tuple[int, int] | None = None,
    reference_transform: Any | None = None,
) -> FuelMapProduct:
    """Load local land-cover raster and reproject to target grid (nearest)."""
    rasterio, _, transform_bounds, reproject, Resampling = _require_rasterio()
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))

    with rasterio.open(p) as src:
        src_crs = str(src.crs) if src.crs else target_crs
        if reference_shape is not None and reference_transform is not None:
            height, width = reference_shape
            transform = reference_transform
            bbox = (
                [float(x) for x in bbox_wgs84]
                if bbox_wgs84 is not None
                else list(TOBARRA_BBOX_WGS84)
            )
        else:
            if bbox_wgs84 is None:
                try:
                    w, s, e, n = transform_bounds(src_crs, "EPSG:4326", *src.bounds, densify_pts=21)
                    bbox = [float(w), float(s), float(e), float(n)]
                except Exception:
                    bbox = list(TOBARRA_BBOX_WGS84)
            else:
                bbox = [float(x) for x in bbox_wgs84]
            transform, width, height = _grid_for_bbox(
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
            resampling=Resampling.nearest,
            src_nodata=src.nodata,
            dst_nodata=np.nan,
        )

    if not np.isfinite(dest).any():
        raise ValueError(f"landcover load produced no valid codes from {p}")

    fuel_ids, height_m, mix, dominant, _ = codes_to_fuel_layers(dest, scheme=scheme)
    return FuelMapProduct(
        landcover_code=dest,
        fuel_id_grid=fuel_ids,
        height_m=height_m,
        scheme=scheme,
        source="local_geotiff",
        transform=transform,
        crs=target_crs,
        cell_size_m=float(cell_size_m),
        bbox_wgs84=list(bbox),
        fuel_mix=mix,
        fuel_id_dominant=dominant,
        source_uri=str(p.resolve()),
        sha256=_sha256_array(dest),
        synthetic=False,
        notes=[f"loaded_local:{p.name}", f"scheme={scheme}"],
    )


def download_worldcover_window(
    bbox_wgs84: Sequence[float],
    cache_path: Path,
    *,
    target_crs: str = DEFAULT_CRS,
    cell_size_m: float = DEFAULT_CELL_M,
    timeout_s: int = 90,
    force: bool = False,
    reference_shape: tuple[int, int] | None = None,
    reference_transform: Any | None = None,
) -> FuelMapProduct:
    """Windowed ESA WorldCover 10 m → metric grid; cache as GeoTIFF."""
    rasterio, _, _, reproject, Resampling = _require_rasterio()
    cache_path = Path(cache_path)
    if cache_path.is_file() and not force:
        prod = load_landcover_geotiff(
            cache_path,
            bbox_wgs84=bbox_wgs84,
            target_crs=target_crs,
            cell_size_m=cell_size_m,
            scheme="worldcover",
            reference_shape=reference_shape,
            reference_transform=reference_transform,
        )
        prod.source = "esa_worldcover"
        prod.cache_path = str(cache_path.resolve())
        prod.notes.append("loaded_from_cache")
        with contextlib.suppress(OSError):
            prod.sha256 = _sha256_file(cache_path)
        return prod

    tiles = worldcover_tiles_for_bbox(bbox_wgs84)
    if reference_shape is not None and reference_transform is not None:
        height, width = reference_shape
        transform = reference_transform
    else:
        transform, width, height = _grid_for_bbox(
            bbox_wgs84, target_crs=target_crs, cell_size_m=cell_size_m
        )

    dest = np.full((height, width), np.nan, dtype=np.float64)
    hrefs: list[str] = []
    env_opts = {
        "GDAL_HTTP_TIMEOUT": str(timeout_s),
        "GDAL_HTTP_CONNECTTIMEOUT": "20",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.TIF,.tiff",
        "CPL_VSIL_CURL_USE_HEAD": "NO",
    }
    try:
        with rasterio.Env(**env_opts):
            for tid in tiles:
                href = worldcover_public_href(tid)
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
                            resampling=Resampling.nearest,
                            src_nodata=src.nodata,
                            dst_nodata=np.nan,
                        )
                except Exception as exc:
                    raise FuelMapFetchError(f"WorldCover tile {tid} failed: {exc}") from exc
    except FuelMapFetchError:
        raise
    except Exception as exc:
        raise FuelMapFetchError(f"WorldCover download failed: {exc}") from exc

    if not np.isfinite(dest).any():
        raise FuelMapFetchError("WorldCover window is all nodata")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        cache_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float64",
        crs=target_crs,
        transform=transform,
        compress="deflate",
    ) as dst:
        dst.write(dest, 1)

    fuel_ids, height_m, mix, dominant, _ = codes_to_fuel_layers(dest, scheme="worldcover")
    sha = _sha256_file(cache_path)
    manifest = {
        "source": "esa_worldcover",
        "scheme": "worldcover",
        "bbox_wgs84": [float(x) for x in bbox_wgs84],
        "tiles": tiles,
        "hrefs": hrefs,
        "crs": target_crs,
        "cell_size_m": cell_size_m,
        "sha256": sha,
        "fetched_at": datetime.now(UTC).isoformat(),
        "crosswalk": "WORLDCOVER_TO_FUEL engineering prior",
    }
    (cache_path.parent / "fuel_map_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return FuelMapProduct(
        landcover_code=dest,
        fuel_id_grid=fuel_ids,
        height_m=height_m,
        scheme="worldcover",
        source="esa_worldcover",
        transform=transform,
        crs=target_crs,
        cell_size_m=float(cell_size_m),
        bbox_wgs84=[float(x) for x in bbox_wgs84],
        fuel_mix=mix,
        fuel_id_dominant=dominant,
        source_uri=";".join(hrefs),
        cache_path=str(cache_path.resolve()),
        sha256=sha,
        synthetic=False,
        notes=[f"tiles={tiles}", "scheme=worldcover", "crosswalk=engineering"],
    )


def synthetic_fuel_map(
    n_rows: int,
    n_cols: int,
    *,
    seed: int = 42,
    transform: Any = None,
    crs: str = DEFAULT_CRS,
    cell_size_m: float = DEFAULT_CELL_M,
    bbox_wgs84: Sequence[float] = TOBARRA_BBOX_WGS84,
) -> FuelMapProduct:
    """Legacy synthetic mosaic (CLC-like codes)."""
    np.random.default_rng(seed)
    y = np.linspace(0, 1, n_rows)
    x = np.linspace(0, 1, n_cols)
    xx, yy = np.meshgrid(x, y)
    codes = np.full((n_rows, n_cols), 323.0)
    codes[yy < 0.25] = 321
    codes[(xx > 0.7) & (yy > 0.5)] = 312
    codes[(xx > 0.4) & (xx < 0.55) & (yy > 0.6)] = 324
    fuel_ids, height, mix, dominant, _ = codes_to_fuel_layers(codes, scheme="clc", seed=seed)
    return FuelMapProduct(
        landcover_code=codes,
        fuel_id_grid=fuel_ids,
        height_m=height,
        scheme="clc",
        source="synthetic",
        transform=transform,
        crs=crs,
        cell_size_m=cell_size_m,
        bbox_wgs84=list(bbox_wgs84),
        fuel_mix=mix,
        fuel_id_dominant=dominant,
        synthetic=True,
        sha256=_sha256_array(codes),
        notes=["synthetic_clc_mosaic"],
    )


def resolve_fuel_map(
    *,
    bbox_wgs84: Sequence[float] = TOBARRA_BBOX_WGS84,
    local_path: Path | str | None = None,
    cache_dir: Path | None = None,
    allow_download: bool = False,
    allow_synthetic: bool = False,
    scheme: str = "worldcover",
    cell_size_m: float = DEFAULT_CELL_M,
    target_crs: str = DEFAULT_CRS,
    reference_shape: tuple[int, int] | None = None,
    reference_transform: Any | None = None,
    synthetic_seed: int = 42,
    force_download: bool = False,
) -> FuelMapProduct:
    """Resolve fuel map: local → cache → opt-in WorldCover → synthetic."""
    reasons: list[str] = []
    bbox = [float(x) for x in bbox_wgs84]

    if local_path is not None:
        lp = Path(local_path)
        if lp.is_file():
            # auto scheme from filename hints
            sch = scheme
            name = lp.name.lower()
            if "worldcover" in name or "esa_wc" in name:
                sch = "worldcover"
            elif "clc" in name or "corine" in name:
                sch = "clc"
            return load_landcover_geotiff(
                lp,
                bbox_wgs84=bbox,
                target_crs=target_crs,
                cell_size_m=cell_size_m,
                scheme=sch,
                reference_shape=reference_shape,
                reference_transform=reference_transform,
            )
        reasons.append(f"local_missing:{lp}")

    if cache_dir is not None:
        cp = Path(cache_dir) / "worldcover_window.tif"
        if cp.is_file():
            prod = load_landcover_geotiff(
                cp,
                bbox_wgs84=bbox,
                target_crs=target_crs,
                cell_size_m=cell_size_m,
                scheme="worldcover",
                reference_shape=reference_shape,
                reference_transform=reference_transform,
            )
            prod.source = "esa_worldcover"
            prod.cache_path = str(cp.resolve())
            prod.notes.append("resolved_from_cache")
            return prod
        reasons.append(f"cache_missing:{cp}")

    if allow_download:
        if cache_dir is None:
            reasons.append("allow_download_but_no_cache_dir")
        else:
            try:
                return download_worldcover_window(
                    bbox,
                    Path(cache_dir) / "worldcover_window.tif",
                    target_crs=target_crs,
                    cell_size_m=cell_size_m,
                    force=force_download,
                    reference_shape=reference_shape,
                    reference_transform=reference_transform,
                )
            except FuelMapFetchError as exc:
                reasons.append(f"download_failed:{exc}")
    else:
        reasons.append("download_disabled_default")

    if allow_synthetic:
        n_rows, n_cols = reference_shape or (40, 40)
        return synthetic_fuel_map(
            n_rows,
            n_cols,
            seed=synthetic_seed,
            transform=reference_transform,
            crs=target_crs,
            cell_size_m=cell_size_m,
            bbox_wgs84=bbox,
        )

    raise FuelMapUnavailableError(reasons)


def write_fuel_map_geotiffs(product: FuelMapProduct, out_dir: Path) -> dict[str, str]:
    """Write landcover codes GeoTIFF + JSON meta (fuel ids in NPZ via stack)."""
    rasterio, _, _, _, _ = _require_rasterio()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}
    tif = out_dir / "landcover_code.tif"
    with rasterio.open(
        tif,
        "w",
        driver="GTiff",
        height=product.landcover_code.shape[0],
        width=product.landcover_code.shape[1],
        count=1,
        dtype="float64",
        crs=product.crs,
        transform=product.transform,
        compress="deflate",
    ) as dst:
        dst.write(np.asarray(product.landcover_code, dtype=np.float64), 1)
    paths["landcover_tif"] = str(tif)
    meta_path = out_dir / "fuel_map_meta.json"
    meta = product.to_meta()
    meta["crosswalk_tables"] = crosswalk_tables()
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    paths["fuel_map_meta"] = str(meta_path)
    return paths
