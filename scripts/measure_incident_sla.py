#!/usr/bin/env python3
"""Measure incident update latency (M2.5 pilot SLA).

Creates a tiny synthetic two-frame incident, runs process_incident_once,
and writes docs/INCIDENT_SLA_LATENCY.json.

Target (plan): rebuild pack / update path under 10 minutes for field pilot.
Synthetic path should be << 60 s on a normal laptop.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.incident import IncidentConfig, process_incident_once


def _write_tiff(path: Path, data: np.ndarray) -> None:
    array = data if data.ndim == 3 else data[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[2],
        height=array.shape[1],
        count=array.shape[0],
        dtype=array.dtype,
        crs="EPSG:32630",
        transform=from_origin(500000.0, 4100000.0, 10.0, 10.0),
    ) as ds:
        ds.write(array)


def _frame(path: Path, size: int) -> None:
    image = np.zeros((2, 32, 32), dtype=np.uint16)
    image[0, 8 : 8 + size, 8 : 8 + size] = 1400
    _write_tiff(path, image)


def _mask(path: Path, size: int) -> None:
    mask = np.zeros((32, 32), dtype=np.uint8)
    mask[8 : 8 + size, 8 : 8 + size] = 1
    _write_tiff(path, mask)


def main() -> int:
    work = ROOT / "outputs" / "incidents" / "_sla_measure"
    inbox = work / "inbox"
    masks = work / "masks"
    if work.exists():
        import shutil

        shutil.rmtree(work)
    inbox.mkdir(parents=True)
    masks.mkdir(parents=True)

    _frame(inbox / "sla_20260717_100000.tif", 4)
    _mask(masks / "sla_20260717_100000_mask.tif", 4)
    _frame(inbox / "sla_20260717_100100.tif", 8)
    _mask(masks / "sla_20260717_100100_mask.tif", 8)

    cfg = IncidentConfig(
        event_id="SLA_MEASURE",
        sensor_id="sla_synthetic",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )

    t0 = time.perf_counter()
    summary = process_incident_once(cfg, force=True)
    wall_s = time.perf_counter() - t0

    outbox = work / "outbox"
    fdc_ok = (outbox / "fire_decision_card.json").is_file()
    decision = summary.get("decision")
    pipeline_latency = summary.get("latency_s")

    report = {
        "schema": "incident_sla_latency_v1",
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scenario": "synthetic_2_frame_lwir",
        "wall_clock_s": round(wall_s, 4),
        "pipeline_latency_s": pipeline_latency,
        "status": summary.get("status"),
        "decision": decision,
        "confidence_pred": summary.get("confidence_pred"),
        "quality_grade": summary.get("quality_grade"),
        "n_staged": summary.get("n_staged"),
        "fdc_written": fdc_ok,
        "sla_target_s": 600.0,
        "sla_pass": wall_s < 600.0,
        "pilot_note": (
            "Synthetic 2-frame path. Field packs with dozens of LWIR frames "
            "will be slower; still target < 10 min for pilot rebuild."
        ),
        "outbox": str(outbox.resolve()),
    }

    out_path = ROOT / "docs" / "INCIDENT_SLA_LATENCY.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote: {out_path}")
    return 0 if report["sla_pass"] and summary.get("status") == "updated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
