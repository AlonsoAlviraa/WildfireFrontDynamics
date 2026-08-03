"""Tests for landcover → fuel map (offline)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

try:
    import rasterio
    from rasterio.transform import from_bounds
except ModuleNotFoundError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    from_bounds = None  # type: ignore[assignment]

from wildfire_front.fuel.fuel_map import (
    codes_to_fuel_layers,
    resolve_fuel_map,
    synthetic_fuel_map,
    worldcover_public_href,
    worldcover_tile_id,
    worldcover_tiles_for_bbox,
)
from wildfire_front.fuel.models import fuel_from_landcover, fuel_from_worldcover
from wildfire_front.fuel.stack import build_stack_from_dem

pytestmark = [pytest.mark.skipif(rasterio is None, reason="rasterio not installed")]


class TestCrosswalk:
    def test_worldcover_shrub(self) -> None:
        f = fuel_from_worldcover(20)
        assert f.id == "MED_MAQUIS_LOW"

    def test_worldcover_tree(self) -> None:
        f = fuel_from_worldcover(10)
        assert f.id == "MED_PINE_LITTER"

    def test_worldcover_built(self) -> None:
        assert fuel_from_worldcover(50).id == "UNKNOWN"

    def test_landcover_dispatch(self) -> None:
        assert fuel_from_landcover(323, scheme="clc").id == "MED_MAQUIS_LOW"
        assert fuel_from_landcover(20, scheme="worldcover").id == "MED_MAQUIS_LOW"


class TestTiles:
    def test_tobarra_tile(self) -> None:
        tid = worldcover_tile_id(38.6, -1.7)
        assert tid.startswith("N")
        assert "W" in tid
        tiles = worldcover_tiles_for_bbox((-1.72, 38.58, -1.66, 38.63))
        assert tid in tiles
        href = worldcover_public_href(tid)
        assert "ESA_WorldCover" in href
        assert href.endswith("_Map.tif")


class TestSyntheticAndStack:
    def test_synthetic_map(self) -> None:
        fm = synthetic_fuel_map(16, 16, seed=1)
        assert fm.synthetic is True
        assert fm.fuel_id_dominant
        assert "MED" in fm.fuel_id_dominant or fm.fuel_id_dominant in {
            "GR2",
            "GS2",
            "TL6",
            "TU1",
            "UNKNOWN",
        }

    def test_codes_to_fuel(self) -> None:
        codes = np.array([[10, 20], [30, 50]], dtype=float)
        fuel_ids, height, mix, dom, uniq = codes_to_fuel_layers(codes, scheme="worldcover")
        assert fuel_ids[0, 0] == "MED_PINE_LITTER"
        assert fuel_ids[0, 1] == "MED_MAQUIS_LOW"
        assert fuel_ids[1, 1] == "UNKNOWN"
        assert sum(mix.values()) == pytest.approx(1.0)

    def test_resolve_synthetic(self) -> None:
        fm = resolve_fuel_map(allow_synthetic=True, reference_shape=(12, 12))
        assert fm.synthetic is True

    def test_resolve_fails_without_sources(self, tmp_path: Path) -> None:
        from wildfire_front.fuel.fuel_map import FuelMapUnavailableError

        with pytest.raises(FuelMapUnavailableError):
            resolve_fuel_map(
                local_path=tmp_path / "missing.tif",
                cache_dir=tmp_path / "empty",
                allow_download=False,
                allow_synthetic=False,
            )

    def test_local_worldcover_geotiff(self, tmp_path: Path) -> None:
        from wildfire_front.fuel.dem import TOBARRA_BBOX_WGS84, synthetic_dem_product
        from wildfire_front.fuel.fuel_map import load_landcover_geotiff

        # Write WC-like codes over Tobarra bbox
        h, w = 20, 20
        transform = from_bounds(-1.72, 38.58, -1.66, 38.63, w, h)
        data = np.full((h, w), 20.0)  # shrub
        data[:5, :] = 10.0  # tree
        data[15:, :5] = 50.0  # built
        tif = tmp_path / "esa_worldcover_test.tif"
        with rasterio.open(
            tif,
            "w",
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype="float64",
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data, 1)

        dem = synthetic_dem_product(n=16, seed=2)
        fm = load_landcover_geotiff(
            tif,
            bbox_wgs84=TOBARRA_BBOX_WGS84,
            scheme="worldcover",
            reference_shape=dem.elevation_m.shape,
            reference_transform=dem.transform,
            cell_size_m=dem.cell_size_m,
        )
        assert fm.source == "local_geotiff"
        assert fm.scheme == "worldcover"
        assert not fm.synthetic
        stack = build_stack_from_dem(dem, fuel_map=fm)
        assert stack.fuel_id_dominant
        assert stack.terrain_summary.get("fuel_map_source") == "local_geotiff"
        assert "worldcover" in str(stack.terrain_summary.get("fuel_scheme"))
