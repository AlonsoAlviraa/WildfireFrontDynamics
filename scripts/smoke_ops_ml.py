#!/usr/bin/env python3
"""Unified field smoke: OPS (incident) + ML (catalog products).

Exit codes:
  0 = all critical checks pass
  1 = catalog / structural failure
  2 = ML delta or ops grade failure
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.incident import IncidentConfig, process_incident_once  # noqa: E402
from wildfire_front.ml.ndws_metrics import evaluate_sample  # noqa: E402
from wildfire_front.ml.product_catalog import (  # noqa: E402
    list_products,
    load_predictor_for_product,
)


def _ml_eval(product_id: str, paths: list[Path]) -> dict:
    pred = load_predictor_for_product(product_id)
    ious, copies = [], []
    for path in paths:
        with np.load(path) as d:
            pp = pred.predict(d["sequence"], d["current_fire"])
            s = evaluate_sample(pp, d["current_fire"], d["target_fire"])
            ious.append(float(s["model_full"].iou))
            copies.append(float(s["copy_full"].iou))
    delta = float(np.mean(np.array(ious) - np.array(copies))) if ious else 0.0
    return {
        "product": product_id,
        "n": len(ious),
        "mean_iou": float(np.mean(ious)) if ious else None,
        "mean_delta": delta,
        "pass": delta > 0 if ious else False,
        "n_members": getattr(pred, "n_members", 1),
    }


def _ops_incident_smoke() -> dict:
    """Synthetic growing fire through incident update."""
    tmp = Path(tempfile.mkdtemp(prefix="ops_ml_incident_"))
    inbox = tmp / "inbox"
    masks = tmp / "masks"
    work = tmp / "work"
    inbox.mkdir()
    masks.mkdir()

    import rasterio
    from rasterio.transform import from_origin

    def write_tiff(path: Path, data: np.ndarray) -> None:
        arr = data if data.ndim == 3 else data[np.newaxis, ...]
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            width=arr.shape[2],
            height=arr.shape[1],
            count=arr.shape[0],
            dtype=arr.dtype,
            crs="EPSG:32630",
            transform=from_origin(500000.0, 4100000.0, 10.0, 10.0),
        ) as ds:
            ds.write(arr)

    for i, size in enumerate((3, 5, 7)):
        ts = f"20260610_12{i:02d}00"
        img = np.zeros((2, 20, 20), dtype=np.uint16)
        img[0, 5 : 5 + size, 5 : 5 + size] = 1500
        m = np.zeros((20, 20), dtype=np.uint8)
        m[5 : 5 + size, 5 : 5 + size] = 1
        write_tiff(inbox / f"burn_{ts}.tif", img)
        write_tiff(masks / f"burn_{ts}_mask.tif", m)

    cfg = IncidentConfig(
        event_id="smoke_ops_ml",
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
    outbox = work / "outbox"
    required = [
        outbox / "incident_state.json",
        outbox / "emergency_briefing.md",
        outbox / "watch_heartbeat.json",
        outbox / "incident_log.jsonl",
        outbox / "main_front.geojson",
    ]
    missing = [p.name for p in required if not p.is_file()]
    return {
        "status": summary.get("status"),
        "n_staged": summary.get("n_staged"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "latency_s": summary.get("latency_s"),
        "missing_artifacts": missing,
        "pass": summary.get("status") == "updated" and not missing,
        "work_dir": str(work),
    }


def _ops_tobarra_stream(n_frames: int = 4) -> dict:
    src = ROOT / "artifacts" / "tobarra_reprojected_lwir"
    masks = ROOT / "artifacts" / "tobarra_lwir_masks"
    tifs = sorted(src.glob("*.tif")) if src.is_dir() else []
    if len(tifs) < 2:
        return {"skipped": True, "reason": "no tobarra artifacts", "pass": True}

    tmp = Path(tempfile.mkdtemp(prefix="ops_tobarra_"))
    inbox = tmp / "inbox"
    work = tmp / "work"
    inbox.mkdir()
    for tif in tifs[:n_frames]:
        shutil.copy2(tif, inbox / tif.name)

    cfg = IncidentConfig(
        event_id="tobarra_stream_smoke",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks if masks.is_dir() else None,
        min_file_age_s=0.0,
        min_component_pixels=50,
        scientific_clean=True,
        ref_name="INFOCAM Tobarra",
        ref_vp_m_min=7.0,
        ref_area_ha=39.0,
    )
    summary = process_incident_once(cfg, force=True)
    outbox = work / "outbox"
    hb = outbox / "watch_heartbeat.json"
    return {
        "status": summary.get("status"),
        "n_staged": summary.get("n_staged"),
        "quality_grade": summary.get("quality_grade"),
        "primary_ros_m_min": summary.get("primary_ros_m_min"),
        "latency_s": summary.get("latency_s"),
        "heartbeat": hb.is_file(),
        "pass": summary.get("status") in ("updated", "idle") and hb.is_file(),
        "error": summary.get("error"),
    }


def main() -> int:
    report: dict = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "ok": True,
        "tracks": {},
    }

    # --- ML catalog ---
    products = list_products()
    not_ready = [p["id"] for p in products if not p.get("ready")]
    report["tracks"]["catalog"] = {
        "products": products,
        "not_ready": not_ready,
        "pass": not not_ready,
    }
    if not_ready:
        report["ok"] = False

    test_dir = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
    paths = sorted(test_dir.glob("*.npz"))[:15]
    ml_evals = []
    if paths:
        for pid in ("clm_v28", "clm_ensemble_v34", "clm_ensemble_v30"):
            try:
                ml_evals.append(_ml_eval(pid, paths))
            except Exception as exc:  # noqa: BLE001
                ml_evals.append({"product": pid, "pass": False, "error": str(exc)})
        report["tracks"]["ml"] = {"evals": ml_evals, "pass": all(e.get("pass") for e in ml_evals)}
        if not report["tracks"]["ml"]["pass"]:
            report["ok"] = False
        # soft: ensemble mean_delta not much worse
        by = {e["product"]: e for e in ml_evals if "mean_delta" in e}
        ens_id = "clm_ensemble_v34" if "clm_ensemble_v34" in by else "clm_ensemble_v30"
        if "clm_v28" in by and ens_id in by:
            soft = by[ens_id]["mean_delta"] >= by["clm_v28"]["mean_delta"] - 0.05
            report["tracks"]["ml"]["ensemble_competitive"] = soft
            if not soft:
                report["ok"] = False
    else:
        report["tracks"]["ml"] = {"skipped": True, "pass": True}

    # --- OPS synthetic incident ---
    ops_syn = _ops_incident_smoke()
    report["tracks"]["ops_synthetic"] = ops_syn
    if not ops_syn.get("pass"):
        report["ok"] = False

    # --- OPS Tobarra stream ---
    ops_tob = _ops_tobarra_stream(4)
    report["tracks"]["ops_tobarra"] = ops_tob
    if not ops_tob.get("pass"):
        report["ok"] = False

    # Optional prebuilt pack
    pack = ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "operational_metrics.json"
    if pack.is_file():
        ops = json.loads(pack.read_text(encoding="utf-8"))
        report["tracks"]["ops_pack_tobarra"] = {
            "present": True,
            "quality_grade": ops.get("quality_grade"),
            "ros": ops.get("speed_median_m_min"),
            "pass": True,
        }
    else:
        report["tracks"]["ops_pack_tobarra"] = {"present": False, "pass": True}

    print(json.dumps(report, indent=2, default=str))
    out = ROOT / "docs" / "OPS_ML_SMOKE_SNAPSHOT.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("Wrote", out)

    if not report["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
