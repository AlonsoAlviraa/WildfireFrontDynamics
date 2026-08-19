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
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.incident import IncidentConfig, process_incident_once  # noqa: E402
from wildfire_front.incident.pipeline import ops_metrics_for_decision  # noqa: E402
from wildfire_front.product.decide_service import decide_from_request  # noqa: E402

DEFAULT_TOBARRA_OPS = (
    ROOT / "outputs" / "temporal_windows" / "tobarra_20240802" / "mid" / "operational_metrics.json"
)
DECIDE_P95_BUDGET_MS = 500.0
REBUILD_BUDGET_S = 600.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return float(ordered[index])


def measure_decide_from_ops_json(
    ops_path: Path,
    *,
    n: int = 40,
    policy_id: str = "field_ops",
) -> dict:
    """Time the shipped decide path on a real operational_metrics.json."""
    ops = json.loads(Path(ops_path).read_text(encoding="utf-8"))
    if not isinstance(ops, dict):
        raise ValueError(f"ops json is not an object: {ops_path}")
    n_frames = int(ops.get("input_count") or ops.get("num_observations") or 0)
    ops_m = ops_metrics_for_decision(ops, n_frames=n_frames)
    times_ms: list[float] = []
    last: dict | None = None
    for _ in range(max(int(n), 1)):
        t0 = time.perf_counter()
        last = decide_from_request(
            {
                "event_id": "sla_tobarra_mid",
                "ops_metrics": ops_m,
                "policy_id": policy_id,
                "channel": "decide_service",
            }
        )
        times_ms.append((time.perf_counter() - t0) * 1000.0)
    p95 = _percentile(times_ms, 95)
    return {
        "schema": "wfd_industrial_decide_sla_v1",
        "ops_path": str(Path(ops_path)),
        "n": len(times_ms),
        "p50_ms": round(_percentile(times_ms, 50), 3),
        "p95_ms": round(p95, 3),
        "max_ms": round(max(times_ms), 3),
        "budget_p95_ms": DECIDE_P95_BUDGET_MS,
        "sla_pass": p95 < DECIDE_P95_BUDGET_MS,
        "last_decision": None if last is None else last.get("decision"),
        "system_reliability_pass": None
        if last is None
        else last.get("system_reliability_pass"),
        "quality_grade": ops_m.get("quality_grade"),
        "n_frames_staged": ops_m.get("n_frames_staged"),
    }


def measure_tobarra_rebuild(mid_dir: Path) -> dict:
    """Rebuild incident from existing staged Tobarra LWIR frames."""
    import shutil

    images = Path(mid_dir) / "_stage" / "images"
    masks = Path(mid_dir) / "_stage" / "masks"
    if not images.is_dir():
        return {"skipped": True, "reason": f"missing {images}"}
    work = ROOT / "outputs" / "incidents" / "_sla_tobarra_mid"
    if work.exists():
        shutil.rmtree(work)
    inbox = work / "inbox"
    mask_dir = work / "masks"
    inbox.mkdir(parents=True)
    mask_dir.mkdir(parents=True)
    for src in sorted(images.glob("*.tif")):
        shutil.copy2(src, inbox / src.name)
    if masks.is_dir():
        for src in sorted(masks.glob("*.tif")):
            shutil.copy2(src, mask_dir / src.name)
    cfg = IncidentConfig(
        event_id="SLA_TOBARRA_MID",
        sensor_id="tobarra_mid",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=mask_dir,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    t0 = time.perf_counter()
    summary = process_incident_once(cfg, force=True)
    wall_s = time.perf_counter() - t0
    return {
        "schema": "wfd_industrial_rebuild_sla_v1",
        "mid_dir": str(mid_dir),
        "wall_clock_s": round(wall_s, 4),
        "pipeline_latency_s": summary.get("latency_s"),
        "status": summary.get("status"),
        "n_staged": summary.get("n_staged"),
        "decision": summary.get("decision"),
        "rebuild_budget_s": REBUILD_BUDGET_S,
        "sla_pass": wall_s < REBUILD_BUDGET_S,
    }


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
        "measured_at_utc": datetime.now(UTC).isoformat(),
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

    if DEFAULT_TOBARRA_OPS.is_file():
        real = measure_decide_from_ops_json(DEFAULT_TOBARRA_OPS)
        real["rebuild_budget_s"] = REBUILD_BUDGET_S
        real_path = ROOT / "docs" / "INDUSTRIAL_SLA.json"
        real_path.write_text(json.dumps(real, indent=2), encoding="utf-8")
        print(json.dumps(real, indent=2))
        print(f"wrote: {real_path}")
        if not real["sla_pass"]:
            return 1
    else:
        skip = {
            "schema": "wfd_industrial_decide_sla_v1",
            "skipped": True,
            "reason": f"missing {DEFAULT_TOBARRA_OPS}",
        }
        (ROOT / "docs" / "INDUSTRIAL_SLA.json").write_text(
            json.dumps(skip, indent=2) + "\n", encoding="utf-8"
        )

    return 0 if report["sla_pass"] and summary.get("status") == "updated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
