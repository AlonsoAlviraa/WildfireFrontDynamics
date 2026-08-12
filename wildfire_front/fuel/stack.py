"""Fuel–terrain stack artifact builder (Fase 1 mega-plan).

Without local DEM/CLC rasters, builds a **synthetic Tobarra scenario stack**
from literature priors + known ops anchors for pipeline wiring.
When rasters are available, the same schema holds real grids.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any  # noqa: TC003 — used at runtime in annotations

import numpy as np

from .dem import DemProduct
from .fuel_map import FuelMapProduct, synthetic_fuel_map
from .models import FUEL_CATALOG, FuelModel, catalog_as_list, get_fuel
from .terrain import TerrainSample, aspect_array_from_dem, slope_array_from_dem


@dataclass
class FuelTerrainStack:
    """Versioned fuel+terrain product for one fire/scenario."""

    fire_id: str
    protocol: str = "fuel_terrain_stack_v1"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    bbox_wgs84: list[float] | None = None  # [west, south, east, north]
    cell_size_m: float = 25.0
    n_rows: int = 0
    n_cols: int = 0
    fuel_id_dominant: str = "MED_MAQUIS_LOW"
    fuel_mix: dict[str, float] = field(default_factory=dict)
    terrain_summary: dict[str, Any] = field(default_factory=dict)
    layers: dict[str, Any] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    synthetic: bool = False
    notes: list[str] = field(default_factory=list)
    crs: str | None = None
    transform: list[float] | None = None  # affine 6-tuple
    dem_source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # do not dump huge arrays into JSON by default
        layers = {}
        for k, v in self.layers.items():
            if isinstance(v, np.ndarray):
                layers[k] = {
                    "shape": list(v.shape),
                    "dtype": str(v.dtype),
                    "min": float(np.nanmin(v)) if v.size else None,
                    "max": float(np.nanmax(v)) if v.size else None,
                    "mean": float(np.nanmean(v)) if v.size else None,
                }
            else:
                layers[k] = v
        d["layers"] = layers
        return d


def _affine_tuple(transform: Any) -> list[float] | None:
    if transform is None:
        return None
    try:
        return [
            float(transform.a),
            float(transform.b),
            float(transform.c),
            float(transform.d),
            float(transform.e),
            float(transform.f),
        ]
    except Exception:
        return None


def build_stack_from_dem(
    dem: DemProduct,
    *,
    fire_id: str = "tobarra_20240802",
    fuel_mode: str = "auto",
    seed: int = 42,
    fuel_map: FuelMapProduct | None = None,
) -> FuelTerrainStack:
    """Build stack grids from DemProduct.elevation_m + optional real fuel map.

    ``fuel_map``: WorldCover/CLC product aligned to DEM grid preferred.
    ``fuel_mode``: auto | synthetic_mosaic | worldcover | clc (label only when map given).
    """
    elev = np.asarray(dem.elevation_m, dtype=np.float64)
    if elev.ndim != 2:
        raise ValueError("dem elevation must be 2D")
    n_rows, n_cols = elev.shape
    slope = slope_array_from_dem(elev, cell_size_m=dem.cell_size_m)
    aspect = aspect_array_from_dem(elev, cell_size_m=dem.cell_size_m)

    if fuel_map is None:
        fuel_map = synthetic_fuel_map(
            n_rows,
            n_cols,
            seed=seed,
            transform=dem.transform,
            crs=dem.crs,
            cell_size_m=dem.cell_size_m,
            bbox_wgs84=dem.bbox_wgs84,
        )
        fuel_label = "synthetic_mosaic"
    else:
        # ensure shape match (caller should align; re-check)
        if fuel_map.landcover_code.shape != elev.shape:
            raise ValueError(f"fuel_map shape {fuel_map.landcover_code.shape} != dem {elev.shape}")
        fuel_label = fuel_map.source

    codes = np.asarray(fuel_map.landcover_code, dtype=np.float64)
    height = np.asarray(fuel_map.height_m, dtype=np.float64)
    mix = dict(fuel_map.fuel_mix)
    dominant = fuel_map.fuel_id_dominant
    unique = sorted(set(fuel_map.fuel_id_grid.ravel().tolist()))

    notes = list(dem.notes or [])
    notes.extend(list(fuel_map.notes or []))
    notes.append("Does not invent official ha or Vp")
    if fuel_map.synthetic:
        notes.append("Fuel map SYNTHETIC engineering mosaic")
    else:
        notes.append(
            f"Fuel map source={fuel_map.source} scheme={fuel_map.scheme} "
            "(landcover→fuel crosswalk engineering prior, not UCO40 field plot)"
        )
    if dem.synthetic:
        notes.insert(0, "SYNTHETIC DEM elevations")
    else:
        notes.insert(0, f"Real DEM source={dem.source}")

    sources = [
        dem.source,
        fuel_map.source,
        f"fuel_scheme_{fuel_map.scheme}",
        "fuel.models crosswalk engineering priors",
    ]

    stack = FuelTerrainStack(
        fire_id=fire_id,
        bbox_wgs84=list(dem.bbox_wgs84),
        cell_size_m=float(dem.cell_size_m),
        n_rows=n_rows,
        n_cols=n_cols,
        fuel_id_dominant=dominant,
        fuel_mix=mix,
        terrain_summary={
            "slope_deg_mean": round(float(np.nanmean(slope)), 3),
            "slope_deg_p90": round(float(np.nanpercentile(slope, 90)), 3),
            "slope_deg_max": round(float(np.nanmax(slope)), 3),
            "elevation_m_mean": round(float(np.nanmean(elev)), 1),
            "elevation_m_range": [
                round(float(np.nanmin(elev)), 1),
                round(float(np.nanmax(elev)), 1),
            ],
            "height_veg_m_mean": round(float(np.nanmean(height)), 3),
            "dem_source": dem.source,
            "dem_crs": dem.crs,
            "dem_synthetic": bool(dem.synthetic),
            "fuel_map_source": fuel_map.source,
            "fuel_scheme": fuel_map.scheme,
            "fuel_map_synthetic": bool(fuel_map.synthetic),
            "fuel_mode": fuel_mode if fuel_mode != "auto" else fuel_label,
        },
        layers={
            "dem_m": elev,
            "slope_deg": slope,
            "aspect_deg": aspect,
            "clc_code": codes,  # landcover codes (WC or CLC)
            "landcover_code": codes,
            "veg_height_m": height,
            "fuel_id_grid": {
                "shape": [n_rows, n_cols],
                "dominant": dominant,
                "unique": unique,
                "source": fuel_map.source,
                "scheme": fuel_map.scheme,
            },
        },
        sources=sources,
        # True if *any* layer is engineering synthetic (not only both)
        synthetic=bool(dem.synthetic or fuel_map.synthetic),
        notes=notes,
        crs=dem.crs,
        transform=_affine_tuple(dem.transform),
        dem_source=dem.source,
    )
    return stack


def build_synthetic_tobarra_stack(
    *,
    n: int = 40,
    cell_size_m: float = 25.0,
    seed: int = 42,
) -> FuelTerrainStack:
    """Synthetic Tobarra-class landscape for pipeline + unit tests.

    Tobarra (AB) ~39 ha, Mediterranean scrub / grass mosaic, gentle–moderate
    slopes. Bbox is approximate operational AOI (not survey-grade).
    """
    from .dem import synthetic_dem_product

    dem = synthetic_dem_product(n=n, cell_size_m=cell_size_m, seed=seed)
    return build_stack_from_dem(dem, fire_id="tobarra_20240802", seed=seed)


def stack_summary(stack: FuelTerrainStack) -> dict[str, Any]:
    ts = stack.terrain_summary or {}
    return {
        "fire_id": stack.fire_id,
        "protocol": stack.protocol,
        "synthetic": stack.synthetic,
        "dem_synthetic": ts.get("dem_synthetic"),
        "fuel_map_synthetic": ts.get("fuel_map_synthetic"),
        "fuel_id_dominant": stack.fuel_id_dominant,
        "fuel_mix": stack.fuel_mix,
        "terrain_summary": stack.terrain_summary,
        "shape": [stack.n_rows, stack.n_cols],
        "cell_size_m": stack.cell_size_m,
        "bbox_wgs84": stack.bbox_wgs84,
        "n_catalog_fuels": len(list(FUEL_CATALOG)),
    }


def write_stack(
    stack: FuelTerrainStack,
    out_dir: Path,
    *,
    save_npz: bool = True,
    save_geotiff: bool = False,
) -> dict[str, str]:
    """Write stack JSON + optional NPZ grids + optional GeoTIFFs."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    meta_path = out_dir / "fuel_terrain_stack.json"
    meta = stack.to_dict()
    meta["catalog_fuel_ids"] = [m["id"] for m in catalog_as_list()]
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    paths["meta"] = str(meta_path)

    catalog_path = out_dir / "fuel_catalog.json"
    catalog_path.write_text(
        json.dumps(catalog_as_list(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    paths["catalog"] = str(catalog_path)

    if save_npz:
        arrays = {k: v for k, v in stack.layers.items() if isinstance(v, np.ndarray)}
        if arrays:
            npz_path = out_dir / "fuel_terrain_grids.npz"
            np.savez_compressed(npz_path, **arrays)
            paths["grids_npz"] = str(npz_path)

    if save_geotiff and stack.crs and stack.transform:
        try:
            import rasterio
            from affine import Affine
        except ImportError:  # pragma: no cover
            paths["geotiff_skip"] = "rasterio_missing"
        else:
            transform = Affine(*stack.transform)
            for key, fname in (
                ("dem_m", "dem_m.tif"),
                ("slope_deg", "slope_deg.tif"),
                ("aspect_deg", "aspect_deg.tif"),
            ):
                arr = stack.layers.get(key)
                if not isinstance(arr, np.ndarray):
                    continue
                tif = out_dir / fname
                with rasterio.open(
                    tif,
                    "w",
                    driver="GTiff",
                    height=arr.shape[0],
                    width=arr.shape[1],
                    count=1,
                    dtype="float64",
                    crs=stack.crs,
                    transform=transform,
                    compress="deflate",
                ) as dst:
                    dst.write(np.asarray(arr, dtype=np.float64), 1)
                paths[key + "_tif"] = str(tif)

    return paths


def representative_terrain(stack: FuelTerrainStack) -> TerrainSample:
    ts = stack.terrain_summary
    return TerrainSample(
        slope_deg=float(ts.get("slope_deg_mean", 5.0)),
        aspect_deg=None,
        elevation_m=float((ts.get("elevation_m_range") or [None])[0] or 0),
    )


def default_fuel_for_stack(stack: FuelTerrainStack) -> FuelModel:
    return get_fuel(stack.fuel_id_dominant)
