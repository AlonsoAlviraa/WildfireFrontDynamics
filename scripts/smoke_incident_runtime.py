#!/usr/bin/env python3
"""Smoke: incident_runtime_v1 watch/update on synthetic growing fire.

Usage:
  python scripts/smoke_incident_runtime.py
  python scripts/smoke_incident_runtime.py --tobarra
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.incident import IncidentConfig, process_incident_once  # noqa: E402


def write_tiff(path: Path, data: np.ndarray) -> None:
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


def synthetic_smoke() -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="incident_smoke_"))
    inbox = tmp / "inbox"
    masks = tmp / "masks"
    work = tmp / "work"
    inbox.mkdir()
    masks.mkdir()
    for i, size in enumerate((3, 5, 7)):
        ts = f"20260610_12{i:02d}00"
        img = np.zeros((2, 20, 20), dtype=np.uint16)
        img[0, 5 : 5 + size, 5 : 5 + size] = 1500
        m = np.zeros((20, 20), dtype=np.uint8)
        m[5 : 5 + size, 5 : 5 + size] = 1
        write_tiff(inbox / f"burn_{ts}.tif", img)
        write_tiff(masks / f"burn_{ts}_mask.tif", m)

    cfg = IncidentConfig(
        event_id="smoke_synthetic",
        sensor_id="thermal_smoke",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    summary = process_incident_once(cfg, force=True)
    required = [
        work / "outbox" / "incident_state.json",
        work / "outbox" / "emergency_briefing.md",
        work / "outbox" / "main_front.geojson",
    ]
    ok = summary.get("status") == "updated" and all(p.is_file() for p in required)
    return {
        "mode": "synthetic",
        "ok": ok,
        "status": summary.get("status"),
        "n_staged": summary.get("n_staged"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "latency_s": summary.get("latency_s"),
        "work_dir": str(work),
        "error": summary.get("error"),
    }


def tobarra_smoke(n: int = 4) -> dict:
    src = ROOT / "artifacts" / "tobarra_reprojected_lwir"
    masks_src = ROOT / "artifacts" / "tobarra_lwir_masks"
    tifs = sorted(src.glob("*.tif")) if src.is_dir() else []
    if len(tifs) < 2:
        return {"mode": "tobarra", "ok": False, "skipped": True, "reason": "no artifacts"}

    tmp = Path(tempfile.mkdtemp(prefix="incident_tobarra_"))
    inbox = tmp / "inbox"
    work = tmp / "work"
    inbox.mkdir()
    for tif in tifs[:n]:
        shutil.copy2(tif, inbox / tif.name)

    cfg = IncidentConfig(
        event_id="tobarra_smoke",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks_src if masks_src.is_dir() else None,
        min_file_age_s=0.0,
        min_component_pixels=50,
        scientific_clean=True,
        ref_name="INFOCAM Tobarra",
        ref_vp_m_min=7.0,
        ref_area_ha=39.0,
    )
    summary = process_incident_once(cfg, force=True)
    state_ok = (work / "outbox" / "incident_state.json").is_file()
    return {
        "mode": "tobarra",
        "ok": state_ok and summary.get("status") in ("updated", "idle"),
        "status": summary.get("status"),
        "n_staged": summary.get("n_staged"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "latency_s": summary.get("latency_s"),
        "work_dir": str(work),
        "error": summary.get("error"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tobarra", action="store_true")
    args = ap.parse_args()
    report = {"synthetic": synthetic_smoke()}
    if args.tobarra:
        report["tobarra"] = tobarra_smoke()
    ok = report["synthetic"]["ok"] and (
        not args.tobarra or report.get("tobarra", {}).get("ok") or report.get("tobarra", {}).get("skipped")
    )
    print(json.dumps({"ok": ok, **report}, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
