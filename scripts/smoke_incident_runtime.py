#!/usr/bin/env python3
"""Smoke: incident_runtime_v1 on synthetic and/or real IF artifacts.

Usage:
  python scripts/smoke_incident_runtime.py
  python scripts/smoke_incident_runtime.py --tobarra
  python scripts/smoke_incident_runtime.py --hellin
  python scripts/smoke_incident_runtime.py --p1-two-real
    # P1 for GO_MES: Tobarra + Hellín real IF smoke without crash
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


def _real_if_smoke(
    *,
    mode: str,
    images: Path,
    masks: Path,
    event_id: str,
    n: int,
    ref_name: str | None = None,
    ref_vp: float | None = None,
    ref_area: float | None = None,
    min_component_pixels: int = 50,
) -> dict:
    tifs = sorted(images.glob("*.tif")) if images.is_dir() else []
    if len(tifs) < 2:
        return {
            "mode": mode,
            "ok": False,
            "skipped": True,
            "reason": "no artifacts",
        }

    tmp = Path(tempfile.mkdtemp(prefix=f"incident_{mode}_"))
    inbox = tmp / "inbox"
    work = tmp / "work"
    inbox.mkdir()
    # Prefer frames that have a matching mask when masks dir uses *_mask.tif
    selected: list[Path] = []
    for tif in tifs:
        if len(selected) >= n:
            break
        if masks.is_dir():
            m1 = masks / f"{tif.stem}_mask.tif"
            m2 = masks / tif.name
            if not m1.is_file() and not m2.is_file():
                continue
        selected.append(tif)
    if len(selected) < 2:
        selected = tifs[:n]
    for tif in selected:
        shutil.copy2(tif, inbox / tif.name)

    cfg = IncidentConfig(
        event_id=event_id,
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks if masks.is_dir() else None,
        min_file_age_s=0.0,
        min_component_pixels=min_component_pixels,
        scientific_clean=True,
        ref_name=ref_name,
        ref_vp_m_min=ref_vp,
        ref_area_ha=ref_area,
    )
    summary = process_incident_once(cfg, force=True)
    state_ok = (work / "outbox" / "incident_state.json").is_file()
    status = summary.get("status")
    ok = state_ok and status in ("updated", "idle") and not summary.get("error")
    return {
        "mode": mode,
        "ok": bool(ok),
        "status": status,
        "n_staged": summary.get("n_staged"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "latency_s": summary.get("latency_s"),
        "work_dir": str(work),
        "error": summary.get("error"),
        "n_inbox": len(selected),
    }


def tobarra_smoke(n: int = 4) -> dict:
    return _real_if_smoke(
        mode="tobarra",
        images=ROOT / "artifacts" / "tobarra_reprojected_lwir",
        masks=ROOT / "artifacts" / "tobarra_lwir_masks",
        event_id="tobarra_smoke",
        n=n,
        ref_name="INFOCAM Tobarra",
        ref_vp=7.0,
        ref_area=39.0,
    )


def hellin_smoke(n: int = 4) -> dict:
    return _real_if_smoke(
        mode="hellin",
        images=ROOT / "artifacts" / "hellin_2024_reprojected_lwir",
        masks=ROOT / "artifacts" / "hellin_2024_lwir_masks",
        event_id="hellin_smoke",
        n=n,
        ref_name="INFOCAM Hellin UNAP 2024-07-20",
        ref_vp=50.0,
        ref_area=100.0,
        min_component_pixels=50,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tobarra", action="store_true")
    ap.add_argument("--hellin", action="store_true")
    ap.add_argument(
        "--p1-two-real",
        action="store_true",
        help="GO_MES P1: smoke Tobarra + Hellín real IFs without crash",
    )
    ap.add_argument("--skip-synthetic", action="store_true")
    args = ap.parse_args()

    report: dict = {}
    if not args.skip_synthetic:
        report["synthetic"] = synthetic_smoke()

    if args.p1_two_real:
        args.tobarra = True
        args.hellin = True

    if args.tobarra:
        report["tobarra"] = tobarra_smoke()
    if args.hellin:
        report["hellin"] = hellin_smoke()

    ok = True
    if "synthetic" in report:
        ok = ok and bool(report["synthetic"].get("ok"))
    for key in ("tobarra", "hellin"):
        if key not in report:
            continue
        r = report[key]
        ok = False if r.get("skipped") else ok and bool(r.get("ok"))

    if args.p1_two_real:
        t_ok = bool(report.get("tobarra", {}).get("ok"))
        h_ok = bool(report.get("hellin", {}).get("ok"))
        report["p1_two_real_if"] = {
            "ok": t_ok and h_ok,
            "definition": ("PLAN_1_MES: incident_runtime smoke on 2 real IFs without crash"),
            "tobarra_ok": t_ok,
            "hellin_ok": h_ok,
        }
        ok = ok and t_ok and h_ok

    print(json.dumps({"ok": ok, **report}, indent=2, default=str))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
