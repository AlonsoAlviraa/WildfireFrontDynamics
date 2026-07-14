#!/usr/bin/env python3
"""Convert Castilla-La Mancha LWIR GeoTIFFs to 64x64 NDWS-compatible NPZ patches.

Scans organized fire folders + Tobarra transfer, materializes MAD-threshold masks,
and exports patches matching ``NpzWildfireDataset`` / U-Net v19 contract:

    sequence      (1, 17, 64, 64)
    current_fire  (64, 64)
    target_fire   (64, 64)
    change_fraction  scalar
    source        'clm_<fire_name>'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wildfire_front.ingestion.geotiff import materialize_lwir_masks  # noqa: E402
from wildfire_front.ml.dataset import WildfireDataset  # noqa: E402


# Tobarra weather context (AEMET station 7103Y, 2024-08-02 afternoon)
TOBARRA_WEATHER = {
    "temp": 38.0,
    "humidity": 15.0,
    "wind_speed": 12.0,
    "wind_dir": 270.0,
    "precip": 0.0,
    "pressure": 1013.0,
    "cloud": 5.0,
    "visibility": 15.0,
    "dew_point": 8.0,
    "ffmc": 88.0,
}

FIRE_WEATHER_DEFAULTS = {
    "HELLIN20240719": {"temp": 36.0, "humidity": 20.0, "ffmc": 86.0},
    "CARDOSO": {"temp": 35.0, "humidity": 18.0, "ffmc": 87.0},
    "LA_ESTRELLA_ACOM1": {"temp": 37.0, "humidity": 16.0, "ffmc": 88.0},
    "LA_ESTRELLA_ACOM2": {"temp": 37.0, "humidity": 16.0, "ffmc": 88.0},
    "04_09_2025_IF.RETUERTA": {"temp": 32.0, "humidity": 25.0, "ffmc": 82.0},
    "05_10_2025_IF.BRAZATORTAS": {"temp": 28.0, "humidity": 35.0, "ffmc": 78.0},
    "13_09_2025_IF.POLAN": {"temp": 30.0, "humidity": 30.0, "ffmc": 80.0},
    "tobarra_20240802": TOBARRA_WEATHER,
}

FIRE_SOURCES = [
    ("data/real_if/raw_dropbox/20260707_transfer_01/fotos", "tobarra_20240802"),
    ("data/real_if/raw_dropbox/organized/CARDOSO", "CARDOSO"),
    ("data/real_if/raw_dropbox/organized/LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM1"),
    ("data/real_if/raw_dropbox/organized/LA_ESTRELLA_ACOM2", "LA_ESTRELLA_ACOM2"),
    ("data/real_if/raw_dropbox/organized/HELLIN20240719", "HELLIN20240719"),
    ("data/real_if/raw_dropbox/organized/04_09_2025_IF.RETUERTA", "RETUERTA"),
    ("data/real_if/raw_dropbox/organized/05_10_2025_IF.BRAZATORTAS", "BRAZATORTAS"),
    ("data/real_if/raw_dropbox/organized/13_09_2025_IF.POLAN", "POLAN"),
]

TRAIN_FIRES = {"tobarra_20240802", "CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2", "HELLIN20240719"}
VAL_FIRES = {"RETUERTA", "POLAN"}
TEST_FIRES = {"BRAZATORTAS"}


def _find_lwir_images(images_dir: Path) -> list[Path]:
    return sorted(images_dir.rglob("*_LWIR.tif"))


def _flatten_lwir_images(source_dir: Path, flat_dir: Path) -> Path:
    """Symlink all *_LWIR.tif into a flat directory for dataset compatibility."""
    flat_dir.mkdir(parents=True, exist_ok=True)
    for old in flat_dir.glob("*.tif"):
        old.unlink()
    for src in _find_lwir_images(source_dir):
        dest = flat_dir / src.name
        if dest.exists():
            dest.unlink()
        try:
            dest.symlink_to(src.resolve())
        except OSError:
            import shutil
            shutil.copy2(src, dest)
    return flat_dir


def _prepare_masks(images_dir: Path, masks_dir: Path, mad_z: float) -> int:
    masks_dir.mkdir(parents=True, exist_ok=True)
    succeeded, failed = materialize_lwir_masks(images_dir, masks_dir, mad_z=mad_z)
    for src, reason in failed:
        print(f"  [mask FAIL] {src.name}: {reason}")
    return len(succeeded)


def export_fire_patches(
    images_dir: Path,
    masks_dir: Path,
    output_split_dir: Path,
    fire_name: str,
    *,
    patch_size: int = 64,
    sequence_length: int = 1,
    max_patches: int | None = None,
    weather: dict | None = None,
    start_index: int = 0,
) -> tuple[int, list[dict]]:
    """Export NPZ patches for one fire event."""
    output_split_dir.mkdir(parents=True, exist_ok=True)
    weather_data = {**TOBARRA_WEATHER, **(weather or {})}

    dataset = WildfireDataset(
        images_dir=images_dir,
        masks_dir=masks_dir,
        sequence_length=max(sequence_length, 1),
        patch_size=patch_size,
        weather_data=weather_data,
        max_patches=max_patches,
    )

    written: list[dict] = []
    idx = start_index
    for i in range(len(dataset)):
        sequence, current_fire, target_fire = dataset[i]
        cf = current_fire.numpy().astype(np.float32)
        tf = target_fire.numpy().astype(np.float32)
        change_fraction = float(np.mean((cf >= 0.5) != (tf >= 0.5)))

        # U-Net v19 expects (1, C, H, W) even for single timestep
        seq_np = sequence.numpy().astype(np.float32)
        if seq_np.ndim == 4 and seq_np.shape[0] > 1:
            seq_np = seq_np[-1:]  # use last frame channels as single-step input
        elif seq_np.ndim == 3:
            seq_np = seq_np[np.newaxis, ...]

        out_path = output_split_dir / f"clm_{fire_name}_{idx:06d}.npz"
        np.savez_compressed(
            out_path,
            sequence=seq_np,
            current_fire=cf,
            target_fire=tf,
            change_fraction=np.float32(change_fraction),
            source=np.array(fire_name),
        )
        patch_info = dataset.patches[i]
        written.append({
            "file": out_path.name,
            "fire": fire_name,
            "change_fraction": change_fraction,
            "row": patch_info["row"],
            "col": patch_info["col"],
        })
        idx += 1

    return idx, written


def main() -> int:
    parser = argparse.ArgumentParser(description="CLM LWIR -> NDWS NPZ patches")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/clm_ndws_patches"))
    parser.add_argument("--patch-size", type=int, default=64)
    parser.add_argument("--mad-z", type=float, default=3.5)
    parser.add_argument("--max-patches-per-fire", type=int, default=500)
    parser.add_argument("--work-dir", type=Path, default=Path("artifacts/clm_work"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    analysis: dict = {"fires": [], "totals": {}}

    split_counts = {"train": 0, "val": 0, "test": 0}
    split_indices = {"train": 0, "val": 0, "test": 0}

    for rel_path, fire_name in FIRE_SOURCES:
        images_dir = ROOT / rel_path
        if not images_dir.exists():
            print(f"[skip] {fire_name}: {images_dir} not found")
            continue

        lwir = _find_lwir_images(images_dir)
        if len(lwir) < 2:
            print(f"[skip] {fire_name}: only {len(lwir)} LWIR.tif files")
            continue

        if fire_name in TRAIN_FIRES or fire_name.replace("04_09_2025_IF.", "") in TRAIN_FIRES:
            split = "train"
        elif fire_name in VAL_FIRES or fire_name.replace("04_09_2025_IF.", "") in VAL_FIRES:
            split = "val"
        elif fire_name in TEST_FIRES:
            split = "test"
        else:
            split = "train"

        print(f"\n=== {fire_name} -> {split} ({len(lwir)} LWIR frames) ===")
        work = args.work_dir / fire_name
        flat_images = _flatten_lwir_images(images_dir, work / "images_flat")
        masks_dir = work / "masks"
        n_masks = _prepare_masks(flat_images, masks_dir, args.mad_z)
        print(f"  masks materialized: {n_masks}")

        weather = FIRE_WEATHER_DEFAULTS.get(fire_name, TOBARRA_WEATHER)
        try:
            next_idx, records = export_fire_patches(
                flat_images,
                masks_dir,
                args.output_dir / split,
                fire_name,
                patch_size=args.patch_size,
                max_patches=args.max_patches_per_fire,
                weather=weather,
                start_index=split_indices[split],
            )
        except ValueError as exc:
            print(f"  [skip] dataset error: {exc}")
            continue

        split_indices[split] = next_idx
        n_written = len(records)
        split_counts[split] += n_written
        if records:
            changes = [r["change_fraction"] for r in records]
            analysis["fires"].append({
                "fire": fire_name,
                "split": split,
                "lwir_frames": len(lwir),
                "masks": n_masks,
                "patches": n_written,
                "mean_change_fraction": float(np.mean(changes)),
                "max_change_fraction": float(np.max(changes)),
            })
        print(f"  patches written: {n_written}")

    analysis["totals"] = split_counts
    manifest_path = args.output_dir / "clm_analysis.json"
    manifest_path.write_text(json.dumps(analysis, indent=2), encoding="utf-8")
    print(f"\n=== CLM preprocessing done ===")
    print(f"  train={split_counts['train']}  val={split_counts['val']}  test={split_counts['test']}")
    print(f"  analysis: {manifest_path}")
    return 0 if sum(split_counts.values()) > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())