"""Tests for DEM resolve/load (offline; no network)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

try:
    import rasterio
    from rasterio.transform import from_origin
except ModuleNotFoundError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    from_origin = None  # type: ignore[assignment]

from wildfire_front.fuel.dem import (
    TOBARRA_BBOX_WGS84,
    DemUnavailableError,
    glo30_public_href,
    glo30_tile_ids_for_bbox,
    load_dem_geotiff,
    resolve_dem,
    synthetic_dem_product,
)
from wildfire_front.fuel.stack import build_stack_from_dem, write_stack

pytestmark = [pytest.mark.skipif(rasterio is None, reason="rasterio not installed")]


def _write_plane_dem(path: Path, h: int = 20, w: int = 20) -> Path:
    """Plane DEM over Tobarra bbox in WGS84 (reprojects cleanly to UTM 30N)."""
    # west, south = -1.72, 38.58; ~0.003 deg/pixel
    from rasterio.transform import from_bounds

    transform = from_bounds(-1.72, 38.58, -1.66, 38.63, w, h)
    xs = np.linspace(0, 1, w)
    dem = np.tile(700.0 + 40.0 * xs, (h, 1))  # slope eastward
    # add mild north-south tilt for non-zero slope
    dem = dem + np.linspace(0, 15.0, h)[:, None]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype="float64",
        crs="EPSG:4326",
        transform=transform,
    ) as dst:
        dst.write(dem, 1)
    return path


class TestGlo30Ids:
    def test_tobarra_tile(self) -> None:
        tiles = glo30_tile_ids_for_bbox(TOBARRA_BBOX_WGS84)
        assert "N38_W002" in tiles
        href = glo30_public_href("N38_W002")
        assert "Copernicus_DSM_COG_10_N38_00_W002_00_DEM" in href
        assert href.startswith("https://")


class TestLocalDem:
    def test_load_local_and_stack(self, tmp_path: Path) -> None:
        tif = _write_plane_dem(tmp_path / "dem.tif")
        dem = load_dem_geotiff(
            tif,
            bbox_wgs84=TOBARRA_BBOX_WGS84,
            cell_size_m=25.0,
        )
        assert dem.synthetic is False
        assert dem.source == "local_geotiff"
        assert dem.elevation_m.ndim == 2
        assert dem.crs == "EPSG:32630"
        stack = build_stack_from_dem(dem)
        # Real DEM + default synthetic fuel mosaic → synthetic stack (OR honesty)
        assert stack.synthetic is True
        assert stack.terrain_summary.get("dem_synthetic") is False
        assert stack.terrain_summary.get("fuel_map_synthetic") is True
        assert stack.dem_source == "local_geotiff"
        assert stack.crs is not None
        assert stack.transform is not None
        assert stack.terrain_summary["slope_deg_mean"] >= 0
        paths = write_stack(stack, tmp_path / "out", save_geotiff=True)
        assert Path(paths["meta"]).is_file()
        assert "dem_m_tif" in paths

    def test_resolve_local(self, tmp_path: Path) -> None:
        tif = _write_plane_dem(tmp_path / "dem.tif")
        dem = resolve_dem(
            local_path=tif,
            allow_download=False,
            allow_synthetic=False,
            bbox_wgs84=TOBARRA_BBOX_WGS84,
        )
        assert dem.source == "local_geotiff"

    def test_resolve_fails_without_sources(self, tmp_path: Path) -> None:
        with pytest.raises(DemUnavailableError) as ei:
            resolve_dem(
                local_path=tmp_path / "missing.tif",
                cache_dir=tmp_path / "empty_cache",
                allow_download=False,
                allow_synthetic=False,
            )
        assert ei.value.reasons

    def test_resolve_synthetic_explicit(self) -> None:
        dem = resolve_dem(allow_synthetic=True, allow_download=False, synthetic_n=12)
        assert dem.synthetic is True
        assert dem.source == "synthetic"

    def test_cache_hit_no_network(self, tmp_path: Path) -> None:
        tif = _write_plane_dem(tmp_path / "glo30_window.tif")
        # rename pattern expected by resolve
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        target = cache_dir / "glo30_window.tif"
        target.write_bytes(tif.read_bytes())
        dem = resolve_dem(
            cache_dir=cache_dir,
            allow_download=False,
            allow_synthetic=False,
            bbox_wgs84=TOBARRA_BBOX_WGS84,
        )
        assert dem.source == "copernicus_glo30"
        assert "cache" in " ".join(dem.notes).lower() or dem.cache_path


class TestSyntheticProduct:
    def test_synthetic_dem_product(self) -> None:
        dem = synthetic_dem_product(n=16, seed=1)
        assert dem.elevation_m.shape == (16, 16)
        assert dem.synthetic is True
