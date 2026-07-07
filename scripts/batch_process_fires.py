#!/usr/bin/env python
"""Batch-process all newly extracted real wildfire sequences.

For each fire:
  1. Reproject LWIR GeoTIFFs to a flat metric directory (EPSG:32630)
  2. Run the full ingest pipeline (ingest_geotiff_sequence) with mask persistence
  3. Audit the result

Usage:
    set PYTHONPATH=. && python scripts\\batch_process_fires.py
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_real_if_geotiffs import _resampling, prepare_sequence
from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest

# ─── Configuration ───────────────────────────────────────────────────────────

ORGANIZED_DIR = PROJECT_ROOT / "data" / "real_if" / "raw_dropbox" / "organized"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# UTM zone 30N — all fires are in Castilla-La Mancha (Spain)
DST_CRS = "EPSG:32630"
RESOLUTION_M = 0.5
RESAMPLING = "nearest"
MAD_Z = 3.5

# Fire configurations: (fire_id, source_dir_relative_to_organized, event_id, estimated_error_m)
FIRES = [
    ("cardoso_2025", "CARDOSO", "cardoso_2025", 2.0),
    ("la_estrella_acom1_2024", "LA_ESTRELLA_ACOM1", "la_estrella_acom1", 2.0),
    ("la_estrella_acom2_2024", "LA_ESTRELLA_ACOM2", "la_estrella_acom2", 2.0),
    ("hellin_2024", "HELLIN20240719", "hellin_2024", 2.0),
    ("retuerta_2025", "04_09_2025_IF.RETUERTA", "retuerta_2025", 2.0),
    ("brazatortas_2025", "05_10_2025_IF.BRAZATORTAS", "brazatortas_2025", 2.0),
    ("polan_2025", "13_09_2025_IF.POLAN/13_09_2025_IF.POLAN", "polan_2025", 2.0),
]

# ─── Pipeline ────────────────────────────────────────────────────────────────


def process_fire(
    fire_id: str,
    source_rel: str,
    event_id: str,
    estimated_error_m: float,
    skip_if_done: bool = True,
) -> dict:
    """Process a single fire through the full pipeline. Returns metrics dict."""
    source_dir = ORGANIZED_DIR / source_rel
    reprojected_dir = ARTIFACTS_DIR / f"{fire_id}_reprojected_lwir"
    masks_dir = ARTIFACTS_DIR / f"{fire_id}_lwir_masks"
    output_dir = OUTPUTS_DIR / f"{fire_id}_lwir"
    manifest_path = ARTIFACTS_DIR / f"{fire_id}_reproject_manifest.csv"
    ingest_manifest = output_dir / "ingest_manifest.csv"

    print(f"\n{'=' * 70}")
    print(f"  FIRE: {fire_id}")
    print(f"  Source: {source_dir}")
    print(f"{'=' * 70}")

    # Resume check: skip if already fully processed
    if (
        skip_if_done
        and ingest_manifest.exists()
        and reprojected_dir.exists()
        and masks_dir.exists()
    ):
        reproj_count = len(list(reprojected_dir.glob("*.tif")))
        mask_count = len(list(masks_dir.glob("*_mask.tif")))
        if reproj_count > 0 and mask_count > 0:
            print(f"  SKIP (already processed): {reproj_count} TIFs, {mask_count} masks")
            return {
                "fire_id": fire_id,
                "event_id": event_id,
                "total_tifs": reproj_count,
                "accepted": mask_count,
                "review": 0,
                "rejected": 0,
                "observations": mask_count,
                "masks_persisted": mask_count,
                "reprojected_dir": str(reprojected_dir),
                "masks_dir": str(masks_dir),
                "output_dir": str(output_dir),
                "skipped": True,
            }

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    # ── Step 1: Reproject LWIR GeoTIFFs ──
    print(f"\n[1/3] Reprojecting LWIR TIFs -> {DST_CRS} @ {RESOLUTION_M}m ...")
    reprojected_dir.mkdir(parents=True, exist_ok=True)
    masks_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    written = prepare_sequence(
        source=source_dir,
        output=reprojected_dir,
        pattern="*_LWIR.tif",
        dst_crs=DST_CRS,
        resolution_m=RESOLUTION_M,
        resampling=_resampling(RESAMPLING),
        overwrite=True,
        manifest_path=manifest_path,
    )
    print(f"  Reprojected {len(written)} GeoTIFFs")

    # ── Step 2: Ingest + materialize masks ──
    print(f"\n[2/3] Running ingest pipeline (mad_z={MAD_Z}) ...")
    result = ingest_geotiff_sequence(
        images_dir=reprojected_dir,
        masks_dir=None,
        event_id=event_id,
        sensor_id="lwir_thermal",
        estimated_error_m=estimated_error_m,
        mad_z=MAD_Z,
        persist_masks_dir=masks_dir,
    )

    # Write manifest
    write_ingest_manifest(result.records, output_dir / "ingest_manifest.csv")

    accepted = sum(1 for r in result.records if r.status == "accepted")
    review = sum(1 for r in result.records if r.status == "review")
    rejected = sum(1 for r in result.records if r.status == "rejected")
    num_obs = len(result.observations)
    num_masks = len(list(masks_dir.glob("*_mask.tif")))

    print(f"  accepted={accepted}  review={review}  rejected={rejected}")
    print(f"  observations={num_obs}  masks_persisted={num_masks}")

    # ── Step 3: Summary ──
    summary = {
        "fire_id": fire_id,
        "event_id": event_id,
        "total_tifs": len(written),
        "accepted": accepted,
        "review": review,
        "rejected": rejected,
        "observations": num_obs,
        "masks_persisted": num_masks,
        "reprojected_dir": str(reprojected_dir),
        "masks_dir": str(masks_dir),
        "output_dir": str(output_dir),
    }
    print(f"\n  Summary: {json.dumps(summary, indent=2)}")
    return summary


def main() -> int:
    print("=" * 70)
    print("  BATCH PROCESSING: 7 NEW WILDFIRES")
    print("=" * 70)
    print(f"  Organized dir: {ORGANIZED_DIR}")
    print(f"  CRS: {DST_CRS}  Resolution: {RESOLUTION_M}m  MAD-Z: {MAD_Z}")
    print(f"  Fires: {len(FIRES)}")

    results = []
    failures = []

    for fire_id, source_rel, event_id, error_m in FIRES:
        try:
            summary = process_fire(fire_id, source_rel, event_id, error_m)
            results.append(summary)
        except Exception as exc:
            print(f"\n  !!! FAILED: {fire_id}: {exc}")
            traceback.print_exc()
            failures.append({"fire_id": fire_id, "error": str(exc)})

    # ── Final report ──
    print("\n" + "=" * 70)
    print("  BATCH PROCESSING COMPLETE")
    print("=" * 70)
    print(f"\n  Succeeded: {len(results)}/{len(FIRES)}")
    print(f"  Failed:    {len(failures)}/{len(FIRES)}")

    if results:
        print(
            f"\n  {'Fire':<28} {'TIFs':>5} {'Acc':>5} {'Rev':>5} {'Rej':>5} {'Obs':>5} {'Mask':>5}"
        )
        print(f"  {'-' * 28} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
        for r in results:
            print(
                f"  {r['fire_id']:<28} {r['total_tifs']:>5} {r['accepted']:>5} {r['review']:>5} {r['rejected']:>5} {r['observations']:>5} {r['masks_persisted']:>5}"
            )

        total_tifs = sum(r["total_tifs"] for r in results)
        total_acc = sum(r["accepted"] for r in results)
        total_obs = sum(r["observations"] for r in results)
        total_masks = sum(r["masks_persisted"] for r in results)
        print(f"  {'-' * 28} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5} {'-' * 5}")
        print(
            f"  {'TOTAL':<28} {total_tifs:>5} {total_acc:>5} {'':>5} {'':>5} {total_obs:>5} {total_masks:>5}"
        )

    if failures:
        print("\n  Failures:")
        for f in failures:
            print(f"    - {f['fire_id']}: {f['error']}")

    # Save results JSON
    report_path = OUTPUTS_DIR / "batch_processing_report.json"
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump({"results": results, "failures": failures}, fh, indent=2)
    print(f"\n  Report saved: {report_path}")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
