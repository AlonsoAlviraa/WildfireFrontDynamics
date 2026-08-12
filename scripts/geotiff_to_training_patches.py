#!/usr/bin/env python3
"""Export GeoTIFF images + masks into training-ready 30x30x17 .npz patches.

This is **Stage 5** of the real-fire data pipeline.  It closes the gap between
the (already implemented) mask-materialization stage and the
:class:`~wildfire_front.ml.dataset.NpzWildfireDataset` that powers cloud
training on Kaggle.

Pipeline position
-----------------
::

    [1] inventory_real_if_material.py   (crudo)
    [2] build_real_if_frame_manifest.py (frame manifest + QA)
    [3] prepare_real_if_geotiffs.py     (reproyeccion a CRS metrico)
    [4] materialize_lwir_masks.py       (GeoTIFF masks binarias)
    [5] geotiff_to_training_patches.py  <-- ESTE SCRIPT  ->  .npz

The .npz contract matches ``NpzWildfireDataset`` exactly:

    sequence     : float32 (seq_len, 17, 30, 30)
    current_fire : float32 (30, 30)
    target_fire  : float32 (30, 30)

Usage
-----

    python scripts/geotiff_to_training_patches.py \\
        --images-dir outputs/tobarra_lwir/reprojected \\
        --masks-dir  outputs/tobarra_lwir/masks \\
        --output-dir outputs/tobarra_lwir/patches

Optionally supply DEM / NDVI / FSM GeoTIFFs and custom weather data for
physically richer channel construction.

E2-P2 spatial re-emit (``--schema spatial_v1``) delegates to
``scripts/reemit_spatial_v1_patches.py`` so DEM/weather/fuel honesty stays
centralized. Prefer that script for full spatial_v1 LOFO packs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

# Re-use the identical channel-construction logic so there is a single source
# of truth for the 17-channel contract.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wildfire_front.ml.dataset import WildfireDataset  # noqa: E402


def export_patches(
    images_dir: Path,
    masks_dir: Path,
    output_dir: Path,
    sequence_length: int = 3,
    patch_size: int = 30,
    dem_path: Path | None = None,
    ndvi_path: Path | None = None,
    fsm_path: Path | None = None,
    weather_data: dict[str, float] | None = None,
    max_patches: int | None = None,
    fire_name: str | None = None,
    *,
    schema: str = "legacy17",
    weather_dir: Path | None = None,
    fuel_path: Path | None = None,
    dry_run: bool = False,
) -> dict[str, object]:
    """Materialize GeoTIFF pairs into ``.npz`` training patches.

    Returns a summary dict with counts and provenance, also written as
    ``manifest.json`` inside ``output_dir``.

    For ``schema in {spatial_v1, physics14_spatial}`` delegates to the E2-P2
    re-emit path (honest GAP if DEM/weather missing).
    """

    if schema in ("spatial_v1", "physics14_spatial"):
        from reemit_spatial_v1_patches import export_patches_spatial_v1  # noqa: WPS433

        return export_patches_spatial_v1(  # type: ignore[return-value]
            images_dir=images_dir,
            masks_dir=masks_dir,
            output_dir=output_dir,
            dem_path=dem_path,
            weather_dir=weather_dir,
            fuel_path=fuel_path,
            ndvi_path=ndvi_path,
            weather_scalars=weather_data,
            source_id=fire_name or images_dir.parent.name,
            patch_size=patch_size,
            sequence_length=sequence_length,
            max_patches=max_patches,
            dry_run=dry_run,
        )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = WildfireDataset(
        images_dir=images_dir,
        masks_dir=masks_dir,
        sequence_length=sequence_length,
        patch_size=patch_size,
        dem_path=dem_path,
        ndvi_path=ndvi_path,
        fsm_path=fsm_path,
        weather_data=weather_data,
        max_patches=max_patches,
    )

    written: list[dict[str, object]] = []
    for idx in range(len(dataset)):
        sequence, current_fire, target_fire = dataset[idx]
        out_path = output_dir / f"patch_{idx:05d}.npz"
        np.savez_compressed(
            out_path,
            sequence=sequence.numpy().astype(np.float32),
            current_fire=current_fire.numpy().astype(np.float32),
            target_fire=target_fire.numpy().astype(np.float32),
        )
        patch_info = dataset.patches[idx]
        written.append(
            {
                "file": out_path.name,
                "start_idx": patch_info["start_idx"],
                "target_idx": patch_info["target_idx"],
                "row": patch_info["row"],
                "col": patch_info["col"],
                "fire_pixels_target": int(target_fire.sum().item()),
            }
        )

    manifest = {
        "fire_name": fire_name or images_dir.parent.name,
        "images_dir": str(images_dir),
        "masks_dir": str(masks_dir),
        "dem_path": str(dem_path) if dem_path else None,
        "ndvi_path": str(ndvi_path) if ndvi_path else None,
        "fsm_path": str(fsm_path) if fsm_path else None,
        "weather_data": dataset.weather_data,
        "sequence_length": sequence_length,
        "patch_size": patch_size,
        "num_samples_matched": len(dataset.samples),
        "num_patches": len(written),
        "feature_schema": schema,
        "patches": written,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _parse_weather(raw: str | None) -> dict[str, float] | None:
    if not raw:
        return None
    try:
        return {k: float(v) for k, v in (item.split("=") for item in raw.split(","))}
    except Exception as exc:  # noqa: BLE001
        raise argparse.ArgumentTypeError(f"invalid --weather '{raw}': {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export GeoTIFF pairs into .npz training patches for NpzWildfireDataset.",
    )
    parser.add_argument(
        "--images-dir", type=Path, required=True, help="Dir with input GeoTIFF frames."
    )
    parser.add_argument(
        "--masks-dir", type=Path, required=True, help="Dir with binary mask GeoTIFFs."
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Where to write .npz patches."
    )
    parser.add_argument("--sequence-length", type=int, default=3)
    parser.add_argument("--patch-size", type=int, default=30)
    parser.add_argument("--dem-path", type=Path, default=None)
    parser.add_argument("--ndvi-path", type=Path, default=None)
    parser.add_argument("--fsm-path", type=Path, default=None)
    parser.add_argument(
        "--weather", type=str, default=None, help="CSV key=val, e.g. temp=30,humidity=35"
    )
    parser.add_argument("--max-patches", type=int, default=None)
    parser.add_argument("--fire-name", type=str, default=None)
    parser.add_argument(
        "--schema",
        type=str,
        default="legacy17",
        choices=["legacy17", "spatial_v1", "physics14_spatial"],
        help="legacy17 default; spatial_v1/physics14_spatial = E2-P2 re-emit",
    )
    parser.add_argument(
        "--weather-dir",
        type=Path,
        default=None,
        help="Dir of weather rasters for spatial_v1 (tmin/tmax/… .tif)",
    )
    parser.add_argument("--fuel-path", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Ensure scripts/ is importable for reemit_spatial_v1_patches
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    manifest = export_patches(
        images_dir=args.images_dir,
        masks_dir=args.masks_dir,
        output_dir=args.output_dir,
        sequence_length=args.sequence_length,
        patch_size=args.patch_size,
        dem_path=args.dem_path,
        ndvi_path=args.ndvi_path,
        fsm_path=args.fsm_path,
        weather_data=_parse_weather(args.weather),
        max_patches=args.max_patches,
        fire_name=args.fire_name,
        schema=args.schema,
        weather_dir=args.weather_dir,
        fuel_path=args.fuel_path,
        dry_run=bool(args.dry_run),
    )
    n = manifest.get("num_patches", manifest.get("n_patches", 0))
    print(f"[OK] schema={args.schema} patches={n} → {args.output_dir}")
    if manifest.get("gaps"):
        print(f"     gaps={manifest['gaps']}")
    if "fire_name" in manifest:
        print(f"     fire={manifest['fire_name']} samples={manifest.get('num_samples_matched')}")
    return 0 if manifest.get("ok", True) and not manifest.get("blocked") else 2


if __name__ == "__main__":
    raise SystemExit(main())
