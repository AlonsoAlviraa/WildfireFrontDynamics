#!/usr/bin/env python3
"""E2-P2: re-emit training NPZ patches under schema ``spatial_v1``.

Honest spatial channel path from DEM / weather / fuel rasters — **not** the
E2-P1 clean12_subset projector on sealed legacy17 tensors.

When source rasters are missing the script **dry-runs with GAP stamps** and
does not invent constant weather/fuel grids sold as spatial variance.

Usage::

    $env:PYTHONPATH = "."
    python scripts/reemit_spatial_v1_patches.py --dry-run
    python scripts/reemit_spatial_v1_patches.py \\
        --images-dir path/to/lwir --masks-dir path/to/masks \\
        --dem-path path/to/dem.tif --output-dir artifacts/clm_ndws_patches/spatial_v1/demo \\
        --source-id LA_ESTRELLA_ACOM1

LOFO residual-small smoke (no KEEP)::

    python scripts/run_clm_lofo_all_folds.py --smoke \\
        --feature-schema spatial_v1 --schema-path-id E2-P2 --in-channels 15
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.feature_schema import (  # noqa: E402
    SPATIAL_V1_HONESTY,
    SPATIAL_V1_N_CHANNELS,
    SPATIAL_V1_NAMES,
    SPATIAL_V1_SCHEMA_PATH_ID,
    build_spatial_v1_channels,
    spatial_v1_schema_map,
)

DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "spatial_v1"


def _try_read_geotiff(path: Path | None, shape: tuple[int, int]) -> np.ndarray | None:
    if path is None or not path.is_file():
        return None
    try:
        import rasterio
    except ImportError:
        return None
    try:
        with rasterio.open(path) as src:
            band = src.read(1, out_shape=shape).astype(np.float32)
        return np.asarray(band, dtype=np.float32)
    except Exception:  # noqa: BLE001
        return None


def _broadcast_scalar(val: float, shape: tuple[int, int]) -> np.ndarray:
    return np.full(shape, float(val), dtype=np.float32)


# ESA WorldCover (and similar class maps) → continuous vegetation density in [0, 1]
# for spatial_v1 vegetation channel (normalized with NDVI-like stats (0, 1)).
_WORLDCOVER_VEG01: dict[int, float] = {
    10: 0.90,  # Tree cover
    20: 0.70,  # Shrubland
    30: 0.50,  # Grassland
    40: 0.35,  # Cropland
    50: 0.05,  # Built-up
    60: 0.10,  # Bare / sparse
    70: 0.00,  # Snow/ice
    80: 0.00,  # Water
    90: 0.55,  # Herbaceous wetland
    95: 0.80,  # Mangroves
    100: 0.40,  # Moss/lichen
}


def _landcover_codes_to_veg01(codes: np.ndarray) -> np.ndarray:
    """Map discrete landcover class codes to vegetation density in [0, 1]."""
    arr = np.asarray(codes, dtype=np.float32)
    out = np.full(arr.shape, 0.15, dtype=np.float32)  # unknown default
    # Integer codes only (WorldCover / CLC-style)
    flat = np.round(arr).astype(np.int32)
    for code, dens in _WORLDCOVER_VEG01.items():
        out[flat == code] = dens
    # If values already look continuous after partial map, keep finite
    out = np.where(np.isfinite(out), out, 0.15).astype(np.float32)
    return np.clip(out, 0.0, 1.0)


def inventory_sources(
    *,
    dem_path: Path | None,
    weather_dir: Path | None,
    fuel_path: Path | None,
    ndvi_path: Path | None,
    images_dir: Path | None,
    masks_dir: Path | None,
) -> dict[str, Any]:
    """Honest presence/absence of spatial sources (no downloads)."""
    weather_rasters: list[str] = []
    if weather_dir is not None and weather_dir.is_dir():
        for name in (
            "tmin.tif",
            "tmax.tif",
            "temp.tif",
            "humidity.tif",
            "wind_speed.tif",
            "wind_dir.tif",
            "precip.tif",
            "rh.tif",
        ):
            if (weather_dir / name).is_file():
                weather_rasters.append(name)

    return {
        "dem_present": bool(dem_path and dem_path.is_file()),
        "dem_path": str(dem_path.as_posix()) if dem_path else None,
        "weather_dir": str(weather_dir.as_posix()) if weather_dir else None,
        "weather_rasters": weather_rasters,
        "weather_spatial_available": len(weather_rasters) > 0,
        "fuel_present": bool(fuel_path and fuel_path.is_file()),
        "fuel_path": str(fuel_path.as_posix()) if fuel_path else None,
        "ndvi_present": bool(ndvi_path and ndvi_path.is_file()),
        "ndvi_path": str(ndvi_path.as_posix()) if ndvi_path else None,
        "images_dir": str(images_dir.as_posix()) if images_dir else None,
        "images_present": bool(images_dir and images_dir.is_dir()),
        "masks_dir": str(masks_dir.as_posix()) if masks_dir else None,
        "masks_present": bool(masks_dir and masks_dir.is_dir()),
    }


def gaps_from_inventory(inv: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if not inv.get("dem_present"):
        gaps.append("dem_missing")
    if not inv.get("weather_spatial_available"):
        gaps.append("weather_rasters_missing")
    if not inv.get("fuel_present") and not inv.get("ndvi_present"):
        gaps.append("fuel_or_ndvi_missing")
    if not inv.get("images_present"):
        gaps.append("images_dir_missing")
    if not inv.get("masks_present"):
        gaps.append("masks_dir_missing")
    return gaps


def build_fields_from_sources(
    shape: tuple[int, int],
    *,
    dem_path: Path | None,
    weather_dir: Path | None,
    fuel_path: Path | None,
    ndvi_path: Path | None,
    weather_scalars: dict[str, float] | None = None,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Assemble channel fields; mark spatial flags honestly.

    Does **not** invent DEM. If DEM missing, returns empty fields + GAP.
    Weather without rasters: optional scalar broadcast with weather_is_spatial=False.
    """
    h, w = shape
    scalars = weather_scalars or {}
    dem = _try_read_geotiff(dem_path, shape)
    dem_is_spatial = dem is not None and float(np.nanstd(dem)) >= 1e-6
    if dem is None:
        return {}, {
            "ok": False,
            "gaps": ["dem_missing"],
            "dem_is_spatial": False,
            "weather_is_spatial": False,
            "fuel_is_spatial": False,
            "note": "Refuse synthetic flat DEM as spatial_v1 terrain source",
        }

    # Weather rasters — per-field spatial flags (BUG-2: never claim bulk spatial
    # when only a subset of rasters exists while scalars fill the rest).
    tmin_r = _try_read_geotiff(weather_dir / "tmin.tif" if weather_dir else None, shape)
    tmax_r = _try_read_geotiff(weather_dir / "tmax.tif" if weather_dir else None, shape)
    temp_r = _try_read_geotiff(weather_dir / "temp.tif" if weather_dir else None, shape)
    hum_r = _try_read_geotiff(
        (weather_dir / "humidity.tif")
        if weather_dir and (weather_dir / "humidity.tif").is_file()
        else (weather_dir / "rh.tif" if weather_dir else None),
        shape,
    )
    ws_r = _try_read_geotiff(weather_dir / "wind_speed.tif" if weather_dir else None, shape)
    wd_r = _try_read_geotiff(weather_dir / "wind_dir.tif" if weather_dir else None, shape)
    pr_r = _try_read_geotiff(weather_dir / "precip.tif" if weather_dir else None, shape)

    def _is_spatial_arr(arr: np.ndarray | None) -> bool:
        """True only when geotiff has non-trivial spatial variance (not constant fill)."""
        if arr is None:
            return False
        try:
            return float(np.nanstd(arr)) >= 1e-6
        except Exception:  # noqa: BLE001
            return False

    def _wx(arr: np.ndarray | None, key: str, default: float) -> tuple[np.ndarray, bool]:
        # Constant geotiffs keep their values but must not stamp field_spatial=True
        # (mirrors fuel/DEM honesty; inventory treats constant-only as non-spatial).
        if arr is not None:
            return arr, _is_spatial_arr(arr)
        return _broadcast_scalar(float(scalars.get(key, default)), shape), False

    field_spatial: dict[str, bool] = {}
    if temp_r is not None and tmin_r is None and tmax_r is None:
        tmin = (temp_r - 5.0).astype(np.float32)
        tmax = (temp_r + 5.0).astype(np.float32)
        temp_spatial = _is_spatial_arr(temp_r)
        field_spatial["tmin"] = temp_spatial
        field_spatial["tmax"] = temp_spatial
    else:
        tmin, field_spatial["tmin"] = _wx(tmin_r, "tmin", float(scalars.get("temp", 25.0)) - 5.0)
        tmax, field_spatial["tmax"] = _wx(tmax_r, "tmax", float(scalars.get("temp", 25.0)) + 5.0)

    humidity, field_spatial["humidity"] = _wx(hum_r, "humidity", 40.0)
    wind_speed, field_spatial["wind_speed"] = _wx(ws_r, "wind_speed", 5.0)
    wind_dir, field_spatial["wind_dir"] = _wx(wd_r, "wind_dir", 90.0)
    precip, field_spatial["precip"] = _wx(pr_r, "precip", 0.0)

    core_wx_keys = ("tmin", "tmax", "humidity", "wind_speed", "wind_dir", "precip")
    any_wx_raster = any(field_spatial[k] for k in core_wx_keys)
    all_core_wx = all(field_spatial[k] for k in core_wx_keys)
    # Bulk weather_is_spatial only when full core set is raster-sourced
    weather_spatial = bool(all_core_wx)

    veg = _try_read_geotiff(ndvi_path, shape)
    veg_source = "ndvi" if veg is not None else None
    if veg is None:
        veg = _try_read_geotiff(fuel_path, shape)
        if veg is not None:
            veg_source = "landcover_or_fuel"
    # WorldCover / CLC codes are ~10–100; spatial_v1 vegetation stats expect NDVI-ish [0,1].
    # Without this map, normalize_with_stats (sub=0, div=1) + clip [-10,10] collapses all
    # codes ≥10 to constant 10.0 — kills fuel signal (seen in multi-fire re-emit).
    if veg is not None and float(np.nanmax(veg)) > 1.5:
        veg = _landcover_codes_to_veg01(veg)
        veg_source = (veg_source or "landcover") + "_to_veg01"
    fuel_is_spatial = veg is not None and float(np.nanstd(veg)) >= 1e-6
    if veg is None:
        # Explicit missing fuel — zero + flag (not NDVI claim)
        veg = np.zeros(shape, dtype=np.float32)
        veg_source = "missing"

    # ERC: prefer raster; else FFMC proxy from weather grids (SUGGESTION-1)
    erc_r = _try_read_geotiff(weather_dir / "erc.tif" if weather_dir else None, shape)
    if erc_r is not None:
        erc = erc_r.astype(np.float32)
        field_spatial["erc"] = _is_spatial_arr(erc)
        erc_source = "erc_raster"
    else:
        from wildfire_front.ml.feature_schema import compute_ffmc  # noqa: WPS433

        temp_c = 0.5 * (np.asarray(tmin, dtype=np.float32) + np.asarray(tmax, dtype=np.float32))
        # _as_celsius-ish: if values look like Kelvin
        if float(np.nanmax(temp_c)) > 200:
            temp_c = temp_c - 273.15
        wind_kmh = np.asarray(wind_speed, dtype=np.float32) * 3.6
        ffmc_proxy = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)
        erc = ffmc_proxy.astype(np.float32)
        # ERC proxy is spatial only if all FFMC weather inputs are spatial
        field_spatial["erc"] = all(
            field_spatial[k] for k in ("tmin", "tmax", "humidity", "wind_speed", "precip")
        )
        erc_source = "ffmc_proxy"

    fields = {
        "elevation": dem.astype(np.float32),
        "wind_dir": np.asarray(wind_dir, dtype=np.float32),
        "wind_speed": np.asarray(wind_speed, dtype=np.float32),
        "max_temp": np.asarray(tmax, dtype=np.float32),
        "min_temp": np.asarray(tmin, dtype=np.float32),
        "humidity": np.asarray(humidity, dtype=np.float32),
        "precip": np.asarray(precip, dtype=np.float32),
        "veg": veg.astype(np.float32),
        "erc": erc.astype(np.float32),
    }
    gaps: list[str] = []
    if not any_wx_raster:
        gaps.append("weather_rasters_missing")
    elif not all_core_wx:
        gaps.append("weather_partial_rasters")
    if not fuel_is_spatial:
        gaps.append("fuel_or_ndvi_missing")
    if not field_spatial.get("erc", False):
        gaps.append("erc_non_spatial")

    meta = {
        "ok": True,
        "dem_is_spatial": dem_is_spatial,
        "weather_is_spatial": weather_spatial,
        "weather_field_spatial": dict(field_spatial),
        "fuel_is_spatial": fuel_is_spatial,
        "veg_source": veg_source,
        "erc_source": erc_source,
        "gaps": gaps,
        "shape": [h, w],
    }
    return fields, meta


def export_patches_spatial_v1(
    *,
    images_dir: Path,
    masks_dir: Path,
    output_dir: Path,
    dem_path: Path | None = None,
    weather_dir: Path | None = None,
    fuel_path: Path | None = None,
    ndvi_path: Path | None = None,
    weather_scalars: dict[str, float] | None = None,
    source_id: str = "unknown",
    patch_size: int = 64,
    sequence_length: int = 1,
    max_patches: int | None = None,
    dry_run: bool = False,
    refuse_scalar_weather: bool = False,
) -> dict[str, Any]:
    """Materialize spatial_v1 NPZ patches or dry-run GAP report."""
    inv = inventory_sources(
        dem_path=dem_path,
        weather_dir=weather_dir,
        fuel_path=fuel_path,
        ndvi_path=ndvi_path,
        images_dir=images_dir,
        masks_dir=masks_dir,
    )
    gaps = gaps_from_inventory(inv)
    plan: dict[str, Any] = {
        "schema": "wfd_ml_spatial_v1_reemit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "feature_schema": "spatial_v1",
        "schema_path_id": SPATIAL_V1_SCHEMA_PATH_ID,
        "schema_map": dict(spatial_v1_schema_map().items()),
        "honesty": SPATIAL_V1_HONESTY,
        "source_id": source_id,
        "inventory": inv,
        "gaps": gaps,
        "dry_run": dry_run,
        "n_patches": 0,
        "ok": True,
        "blocked": False,
    }

    if "dem_missing" in gaps:
        plan["ok"] = False
        plan["blocked"] = True
        plan["error"] = "dem_missing — spatial_v1 requires DEM geotiff (no synthetic flat)"
        plan["note"] = "GAP: provide --dem-path; do not invent elevation"
        return plan

    if refuse_scalar_weather and "weather_rasters_missing" in gaps:
        plan["ok"] = False
        plan["blocked"] = True
        plan["error"] = "weather_rasters_missing and --refuse-scalar-weather set"
        return plan

    if dry_run or not inv["images_present"] or not inv["masks_present"]:
        # Still demonstrate channel build on synthetic spatial DEM crop if dem present
        dem_preview = _try_read_geotiff(dem_path, (32, 32))
        if dem_preview is not None:
            fields, fmeta = build_fields_from_sources(
                (32, 32),
                dem_path=dem_path,
                weather_dir=weather_dir,
                fuel_path=fuel_path,
                ndvi_path=ndvi_path,
                weather_scalars=weather_scalars,
            )
            if fields:
                ch, ch_meta = build_spatial_v1_channels(
                    fields["elevation"],
                    fields["wind_dir"],
                    fields["wind_speed"],
                    fields["max_temp"],
                    fields["min_temp"],
                    fields["humidity"],
                    fields["precip"],
                    fields["veg"],
                    fields["erc"],
                    weather_is_spatial=bool(fmeta.get("weather_is_spatial")),
                    fuel_is_spatial=bool(fmeta.get("fuel_is_spatial")),
                    dem_is_spatial=bool(fmeta.get("dem_is_spatial")),
                    weather_field_spatial=fmeta.get("weather_field_spatial"),
                )
                # drop large mask from JSON
                ch_meta = {k: v for k, v in ch_meta.items() if k != "missing_mask"}
                plan["preview_channels_shape"] = list(ch.shape)
                plan["preview_meta"] = ch_meta
                plan["preview_field_meta"] = fmeta
        plan["ok"] = True
        plan["note"] = (
            "dry-run or missing images/masks — no NPZ written; "
            "GAPs listed; re-run with full sources to emit patches"
        )
        if not inv["images_present"] or not inv["masks_present"]:
            plan["gaps"] = list(dict.fromkeys(gaps + gaps_from_inventory(inv)))
        return plan

    # Full path via WildfireDataset masks + our channel builder
    from wildfire_front.ml.dataset import WildfireDataset  # noqa: WPS433

    output_dir = Path(output_dir)
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    dataset = WildfireDataset(
        images_dir=images_dir,
        masks_dir=masks_dir,
        sequence_length=max(sequence_length, 1),
        patch_size=patch_size,
        dem_path=dem_path,
        ndvi_path=ndvi_path,
        max_patches=max_patches,
    )
    shape_full = (dataset.height, dataset.width)
    fields, fmeta = build_fields_from_sources(
        shape_full,
        dem_path=dem_path,
        weather_dir=weather_dir,
        fuel_path=fuel_path,
        ndvi_path=ndvi_path,
        weather_scalars=weather_scalars,
    )
    if not fields:
        plan["ok"] = False
        plan["blocked"] = True
        plan["error"] = "failed to build fields"
        plan["field_meta"] = fmeta
        return plan

    ch_full, ch_meta = build_spatial_v1_channels(
        fields["elevation"],
        fields["wind_dir"],
        fields["wind_speed"],
        fields["max_temp"],
        fields["min_temp"],
        fields["humidity"],
        fields["precip"],
        fields["veg"],
        fields["erc"],
        weather_is_spatial=bool(fmeta.get("weather_is_spatial")),
        fuel_is_spatial=bool(fmeta.get("fuel_is_spatial")),
        dem_is_spatial=bool(fmeta.get("dem_is_spatial")),
        weather_field_spatial=fmeta.get("weather_field_spatial"),
    )
    ch_meta_json = {k: v for k, v in ch_meta.items() if k != "missing_mask"}
    missing_full = ch_meta.get("missing_mask")

    written: list[dict[str, Any]] = []
    for i in range(len(dataset)):
        _seq, current_fire, target_fire = dataset[i]
        info = dataset.patches[i]
        r, c = int(info["row"]), int(info["col"])
        ps = patch_size
        patch_ch = ch_full[:, r : r + ps, c : c + ps]
        if patch_ch.shape[1] != ps or patch_ch.shape[2] != ps:
            continue
        cf = current_fire.numpy().astype(np.float32)
        tf = target_fire.numpy().astype(np.float32)
        # sequence (1, C, H, W)
        seq_np = patch_ch[np.newaxis, ...]
        change_fraction = float(np.mean((cf >= 0.5) != (tf >= 0.5)))
        out_path = output_dir / f"spatial_v1_{source_id}_{i:06d}.npz"
        payload: dict[str, Any] = {
            "sequence": seq_np.astype(np.float32),
            "current_fire": cf,
            "target_fire": tf,
            "change_fraction": np.float32(change_fraction),
            "source": np.array(source_id),
            "feature_schema": np.asarray("spatial_v1"),
            "schema_path_id": np.asarray(SPATIAL_V1_SCHEMA_PATH_ID),
            "in_channels": np.asarray(SPATIAL_V1_N_CHANNELS, dtype=np.int32),
        }
        if missing_full is not None:
            payload["missing_mask"] = missing_full[:, r : r + ps, c : c + ps].astype(np.float32)
        if not dry_run:
            np.savez_compressed(out_path, **payload)
        written.append(
            {
                "file": out_path.name,
                "row": r,
                "col": c,
                "change_fraction": change_fraction,
            }
        )
        if max_patches is not None and len(written) >= max_patches:
            break

    plan["n_patches"] = len(written)
    plan["output_dir"] = str(output_dir.as_posix())
    plan["channel_meta"] = ch_meta_json
    plan["field_meta"] = fmeta
    plan["channel_names"] = list(SPATIAL_V1_NAMES)
    plan["gaps"] = list(
        dict.fromkeys(gaps + list(fmeta.get("gaps") or []) + list(ch_meta.get("gaps") or []))
    )
    if not dry_run:
        man = output_dir / "manifest.json"
        # JSON-safe plan (no numpy)
        man.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
    return plan


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--images-dir", type=Path, default=None)
    p.add_argument("--masks-dir", type=Path, default=None)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUT / "reemit")
    p.add_argument("--dem-path", type=Path, default=None)
    p.add_argument(
        "--weather-dir",
        type=Path,
        default=None,
        help="Dir with tmin/tmax/humidity/wind_*/precip.tif when available",
    )
    p.add_argument("--fuel-path", type=Path, default=None)
    p.add_argument("--ndvi-path", type=Path, default=None)
    p.add_argument("--source-id", type=str, default="unknown")
    p.add_argument("--patch-size", type=int, default=64)
    p.add_argument("--max-patches", type=int, default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--refuse-scalar-weather",
        action="store_true",
        help="Block emit when weather rasters missing (honest spatial-only)",
    )
    p.add_argument(
        "--weather-scalar",
        type=str,
        default=None,
        help="CSV key=val fallback (marked non-spatial): temp=30,humidity=20",
    )
    p.add_argument(
        "--manifest-out",
        type=Path,
        default=None,
        help="Write plan JSON even on dry-run / GAP",
    )
    args = p.parse_args(argv)

    scalars: dict[str, float] | None = None
    if args.weather_scalar:
        scalars = {}
        for item in args.weather_scalar.split(","):
            k, v = item.split("=")
            scalars[k.strip()] = float(v)

    images = args.images_dir or Path("_missing_images_")
    masks = args.masks_dir or Path("_missing_masks_")

    plan = export_patches_spatial_v1(
        images_dir=images,
        masks_dir=masks,
        output_dir=args.output_dir.resolve(),
        dem_path=args.dem_path,
        weather_dir=args.weather_dir,
        fuel_path=args.fuel_path,
        ndvi_path=args.ndvi_path,
        weather_scalars=scalars,
        source_id=args.source_id,
        patch_size=args.patch_size,
        max_patches=args.max_patches,
        dry_run=bool(args.dry_run) or args.images_dir is None,
        refuse_scalar_weather=bool(args.refuse_scalar_weather),
    )

    man_out = args.manifest_out
    if man_out is None and args.dry_run:
        man_out = ROOT / "outputs" / "ml_eval" / "spatial_v1_reemit_dry_run.json"
    if man_out is not None:
        man_out = Path(man_out)
        man_out.parent.mkdir(parents=True, exist_ok=True)
        man_out.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        plan["manifest_out"] = str(man_out.as_posix())

    print(json.dumps(plan, indent=2, default=str))
    # Dry-run GAP inventory is a successful documentation pass (exit 0).
    if args.dry_run or args.images_dir is None:
        return 0
    if plan.get("blocked"):
        return 2
    return 0 if plan.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
