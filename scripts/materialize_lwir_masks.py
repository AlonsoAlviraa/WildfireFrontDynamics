"""Materialize binary fire masks from LWIR GeoTIFFs and refresh the ingest manifest.

Closes Gap B: the ingest pipeline accepted on-the-fly MAD-thresholded masks but
never persisted them as GeoTIFFs. ``WildfireDataset`` requires paired image/mask
files on disk, so this script writes one ``*_mask.tif`` per source image and
rewrites the manifest with the ``mask_path`` column populated.

Usage::

    python scripts/materialize_lwir_masks.py \
        --images-dir artifacts/tobarra_reprojected_lwir \
        --output-dir artifacts/tobarra_lwir_masks \
        --manifest outputs/tobarra_lwir/ingest_manifest.csv \
        --mad-z 3.5
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from wildfire_front.ingestion.geotiff import (
    ingest_geotiff_sequence,
    write_ingest_manifest,
    materialize_lwir_masks,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--images-dir", type=Path, required=True, help="Directory with source LWIR GeoTIFFs")
    parser.add_argument("--output-dir", type=Path, required=True, help="Directory where *_mask.tif files are written")
    parser.add_argument("--manifest", type=Path, default=None, help="Existing ingest manifest CSV to update (optional)")
    parser.add_argument("--mad-z", type=float, default=3.5, help="MAD z-score threshold (default: 3.5)")
    parser.add_argument("--event-id", type=str, default="tobarra_2024")
    parser.add_argument("--sensor-id", type=str, default="lwir_thermal")
    parser.add_argument("--estimated-error-m", type=float, default=2.0)
    parser.add_argument("--mode", choices=["ingest", "standalone"], default="ingest",
                        help="ingest=re-run ingest with persist_masks_dir; standalone=just write masks")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "standalone":
        succeeded, failed = materialize_lwir_masks(args.images_dir, args.output_dir, mad_z=args.mad_z)
        print(f"[standalone] masks written: {len(succeeded)}, failed: {len(failed)}")
        for src, reason in failed:
            print(f"  FAILED {src.name}: {reason}")
        if args.manifest:
            _update_manifest_mask_paths(args.manifest, dict(succeeded))
        return 0

    # ingest mode: re-run the full pipeline with persist_masks_dir enabled
    result = ingest_geotiff_sequence(
        args.images_dir,
        masks_dir=None,
        event_id=args.event_id,
        sensor_id=args.sensor_id,
        estimated_error_m=args.estimated_error_m,
        mad_z=args.mad_z,
        persist_masks_dir=args.output_dir,
    )

    accepted = sum(1 for r in result.records if r.status == "accepted")
    review = sum(1 for r in result.records if r.status == "review")
    rejected = sum(1 for r in result.records if r.status == "rejected")
    print(f"[ingest] accepted={accepted} review={review} rejected={rejected}")
    print(f"[ingest] observations={len(result.observations)} masks persisted={accepted}")

    if args.manifest:
        write_ingest_manifest(result.records, args.manifest)
        print(f"[ingest] manifest rewritten: {args.manifest}")
    return 0


def _update_manifest_mask_paths(manifest: Path, mapping: dict[Path, Path]) -> None:
    """Rewrite the mask_path column of an existing manifest in-place."""
    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []
    with manifest.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            source = Path(row.get("source_path", ""))
            if source in mapping:
                row["mask_path"] = str(mapping[source])
            rows.append(row)
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())