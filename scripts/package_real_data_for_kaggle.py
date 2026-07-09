#!/usr/bin/env python3
"""Package real wildfire data for Kaggle dataset upload.

This script scans the organized real-fire Dropbox folder, collects
geotagged photos (JPG) and fire perimeter overlays (KMZ/KML),
and packages them into a structured ZIP ready for Kaggle upload.

The resulting ZIP follows this structure::

    real_wildfire_data/
    ├── manifest.csv          # fire_name, timestamp, file, lat, lon, type
    ├── RETUERTA/
    │   ├── photos/...
    │   └── kmz/...
    ├── BRAZATORTAS/
    ├── POLAN/
    ├── CARDOSO/
    ├── HELLIN/
    ├── LA_ESTRELLA_ACOM2/
    └── TOBARRA/

Usage::

    python scripts/package_real_data_for_kaggle.py \\
        --source data/real_if/raw_dropbox/organized \\
        --tobarra data/real_if/raw_dropbox/20260707_transfer_01 \\
        --output kaggle_data/real_wildfire_data.zip
"""
from __future__ import annotations

import argparse
import csv
import shutil
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Mapping from raw folder names to clean fire names
FIRE_NAME_MAP = {
    "04_09_2025_IF.RETUERTA": "RETUERTA",
    "05_10_2025_IF.BRAZATORTAS": "BRAZATORTAS",
    "13_09_2025_IF.POLAN": "POLAN",
    "CARDOSO": "CARDOSO",
    "HELLIN20240719": "HELLIN",
    "LA_ESTRELLA_ACOM2": "LA_ESTRELLA_ACOM2",
    "LA_ESTRELLA_ACOM1": "LA_ESTRELLA_ACOM1",
    "TOBARRA": "TOBARRA",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
VECTOR_EXTENSIONS = {".kmz", ".kml"}


def scan_fire_folder(folder: Path, fire_name: str) -> list[dict]:
    """Scan a fire folder and return a list of file records."""
    records = []
    for filepath in folder.rglob("*"):
        if not filepath.is_file():
            continue
        ext = filepath.suffix.lower()
        if ext not in IMAGE_EXTENSIONS and ext not in VECTOR_EXTENSIONS:
            continue

        file_type = "photo" if ext in IMAGE_EXTENSIONS else "kmz"

        # Try to extract timestamp from filename or folder
        ts = ""
        name_lower = filepath.stem.lower()
        for fmt_part in ["hd-eo", "acom2", "acom1"]:
            if fmt_part in name_lower:
                ts = filepath.parent.name
                break
        if not ts:
            ts = folder.name

        records.append(
            {
                "fire_name": fire_name,
                "timestamp": ts,
                "filename": filepath.name,
                "relative_path": str(filepath.relative_to(folder)),
                "type": file_type,
                "extension": ext,
                "size_bytes": filepath.stat().st_size,
            }
        )
    return records


def package_to_zip(
    source_dir: Path,
    tobarra_dir: Path | None,
    output_zip: Path,
) -> None:
    """Package all fire data into a ZIP for Kaggle."""
    all_records: list[dict] = []

    # Create a temporary staging directory
    staging = output_zip.parent / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    base = staging / "real_wildfire_data"
    base.mkdir(parents=True)

    # Process each fire folder
    for raw_name, clean_name in FIRE_NAME_MAP.items():
        fire_folder = source_dir / raw_name
        if not fire_folder.exists():
            continue

        print(f"  Processing: {clean_name} ({raw_name})")
        dest = base / clean_name
        dest.mkdir(parents=True, exist_ok=True)

        records = scan_fire_folder(fire_folder, clean_name)
        if not records:
            print(f"    WARNING: no image/vector files found in {fire_folder}")
            continue

        # Copy files into photo/ and kmz/ subfolders
        photos_dir = dest / "photos"
        kmz_dir = dest / "kmz"
        photos_dir.mkdir(exist_ok=True)
        kmz_dir.mkdir(exist_ok=True)

        for rec in records:
            src_file = fire_folder / rec["relative_path"]
            if rec["type"] == "photo":
                dst_file = photos_dir / rec["filename"]
            else:
                dst_file = kmz_dir / rec["filename"]

            # Avoid name collisions
            if dst_file.exists():
                dst_file = dst_file.with_name(
                    f"{src_file.stem}_{hash(str(src_file)) % 10000}{src_file.suffix}"
                )

            shutil.copy2(src_file, dst_file)

        all_records.extend(records)
        print(f"    {len(records)} files ({sum(1 for r in records if r['type']=='photo')} photos, "
              f"{sum(1 for r in records if r['type']=='kmz')} kmz)")

    # Process Tobarra if provided
    if tobarra_dir and tobarra_dir.exists():
        print("  Processing: TOBARRA")
        dest = base / "TOBARRA"
        dest.mkdir(parents=True, exist_ok=True)
        photos_dir = dest / "photos"
        kmz_dir = dest / "kmz"
        photos_dir.mkdir(exist_ok=True)
        kmz_dir.mkdir(exist_ok=True)

        records = scan_fire_folder(tobarra_dir, "TOBARRA")
        for rec in records:
            src_file = tobarra_dir / rec["relative_path"]
            if rec["type"] == "photo":
                dst_file = photos_dir / rec["filename"]
            else:
                dst_file = kmz_dir / rec["filename"]
            if dst_file.exists():
                dst_file = dst_file.with_name(
                    f"{src_file.stem}_{hash(str(src_file)) % 10000}{src_file.suffix}"
                )
            shutil.copy2(src_file, dst_file)
        all_records.extend(records)
        print(f"    {len(records)} files")

    # Write manifest CSV
    manifest_path = base / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "fire_name",
                "timestamp",
                "filename",
                "relative_path",
                "type",
                "extension",
                "size_bytes",
            ],
        )
        writer.writeheader()
        writer.writerows(all_records)

    print(f"\n  Total files: {len(all_records)}")
    print(f"  Total size: {sum(r['size_bytes'] for r in all_records) / 1e6:.1f} MB")

    # Create ZIP
    print(f"  Creating ZIP: {output_zip}")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in base.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(staging)
                zf.write(file, arcname)

    # Cleanup staging
    shutil.rmtree(staging)

    final_size = output_zip.stat().st_size
    print(f"  ZIP created: {final_size / 1e6:.1f} MB")
    print("\nUpload to Kaggle with:")
    print(f"  kaggle datasets version -p {output_zip.parent} -m \"Real wildfire data update\"")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Package real wildfire data for Kaggle upload"
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "data" / "real_if" / "raw_dropbox" / "organized",
        help="Organized real-fire data directory",
    )
    parser.add_argument(
        "--tobarra",
        type=Path,
        default=PROJECT_ROOT / "data" / "real_if" / "raw_dropbox" / "20260707_transfer_01",
        help="Tobarra fire data directory (original transfer)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "kaggle_data" / "real_wildfire_data.zip",
        help="Output ZIP file path",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"ERROR: source directory not found: {args.source}")
        sys.exit(1)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print("Packaging real wildfire data for Kaggle")
    print(f"  Source:  {args.source}")
    print(f"  Tobarra: {args.tobarra}")
    print(f"  Output:  {args.output}")
    print()

    package_to_zip(args.source, args.tobarra, args.output)


if __name__ == "__main__":
    main()
