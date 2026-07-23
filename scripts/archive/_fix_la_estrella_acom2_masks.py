#!/usr/bin/env python
"""Force-regenerate masks for la_estrella_acom2_2024.

The fire has 67 reprojected TIFs but only 17 masks (partial run).
This script clears old masks and re-runs the ingest pipeline.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

# scripts/archive/<this file> → repo root is parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest

ARTIFACTS = PROJECT_ROOT / "artifacts"
OUTPUTS = PROJECT_ROOT / "outputs"

fire_id = "la_estrella_acom2_2024"
event_id = "la_estrella_acom2"
reprojected_dir = ARTIFACTS / f"{fire_id}_reprojected_lwir"
masks_dir = ARTIFACTS / f"{fire_id}_lwir_masks"
output_dir = OUTPUTS / f"{fire_id}_lwir"

print(f"Reprojected TIFs: {len(list(reprojected_dir.glob('*.tif')))}")
print(f"Existing masks:   {len(list(masks_dir.glob('*_mask.tif')))}")

# Clear stale masks
if masks_dir.exists():
    shutil.rmtree(masks_dir)
masks_dir.mkdir(parents=True, exist_ok=True)
output_dir.mkdir(parents=True, exist_ok=True)

print("\nRe-running ingest pipeline (mad_z=3.5) ...")
result = ingest_geotiff_sequence(
    images_dir=reprojected_dir,
    masks_dir=None,
    event_id=event_id,
    sensor_id="lwir_thermal",
    estimated_error_m=2.0,
    mad_z=3.5,
    persist_masks_dir=masks_dir,
)

write_ingest_manifest(result.records, output_dir / "ingest_manifest.csv")

accepted = sum(1 for r in result.records if r.status == "accepted")
review = sum(1 for r in result.records if r.status == "review")
rejected = sum(1 for r in result.records if r.status == "rejected")
num_masks = len(list(masks_dir.glob("*_mask.tif")))

print(f"\nDone: accepted={accepted} review={review} rejected={rejected} masks={num_masks}")
