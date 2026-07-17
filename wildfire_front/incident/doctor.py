"""Pre-flight checks and status readout for incident_runtime_v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ingestion.geotiff import infer_timestamp
from .pipeline import TIFF_EXTENSIONS, IncidentConfig, list_inbox_tiffs
from .state import STATE_FILENAME, load_state


def read_incident_status(work_dir: Path) -> dict[str, Any]:
    """Load outbox state + ops metrics without processing new frames."""
    work_dir = Path(work_dir)
    outbox = work_dir / "outbox"
    state_path = outbox / STATE_FILENAME
    state = load_state(state_path)
    report: dict[str, Any] = {
        "product": "incident_runtime_v1",
        "command": "status",
        "work_dir": str(work_dir.resolve()),
        "outbox": str(outbox.resolve()),
        "state_path": str(state_path),
        "has_state": state is not None,
        "status": "no_state" if state is None else "ready",
    }
    if state is None:
        report["message"] = "No incident_state.json yet — run incident update/watch first"
        return report

    d = state.to_dict()
    report.update(
        {
            "event_id": d.get("event_id"),
            "sensor_id": d.get("sensor_id"),
            "n_staged": d.get("n_frames_staged"),
            "n_frames_seen": d.get("n_frames_seen"),
            "n_updates": d.get("n_updates"),
            "quality_grade": d.get("quality_grade"),
            "quality_label_es": d.get("quality_label_es"),
            "primary_ros_m_min": d.get("primary_ros_m_min"),
            "speed_n_observable": d.get("speed_n_observable"),
            "area_ha_max": d.get("area_ha_max"),
            "speed_vs_ref_ratio": d.get("speed_vs_ref_ratio"),
            "engine": d.get("engine"),
            "last_latency_s": d.get("last_latency_s"),
            "last_error": d.get("last_error"),
            "created_at_utc": d.get("created_at_utc"),
            "updated_at_utc": d.get("updated_at_utc"),
            "disclaimers": d.get("disclaimers"),
            "artifacts": d.get("artifacts"),
            "state": d,
        }
    )
    if d.get("last_error"):
        report["status"] = "error"
        report["error"] = d.get("last_error")
    elif d.get("n_frames_staged", 0) == 0:
        report["status"] = "waiting_for_frames"
    else:
        report["status"] = "ready"

    ops_path = outbox / "operational_metrics.json"
    if ops_path.is_file():
        try:
            ops = json.loads(ops_path.read_text(encoding="utf-8"))
            report["operational_metrics"] = ops
        except (OSError, json.JSONDecodeError) as exc:
            report["operational_metrics_error"] = str(exc)
    return report


def doctor_incident(
    *,
    inbox: Path,
    work_dir: Path | None = None,
    masks_dir: Path | None = None,
    event_id: str = "incident",
) -> dict[str, Any]:
    """Validate field inputs before / during an incident."""
    inbox = Path(inbox)
    work_dir = Path(work_dir) if work_dir else None
    masks_dir = Path(masks_dir) if masks_dir else None

    checks: list[dict[str, Any]] = []

    def add(level: str, cid: str, message: str, detail: str | None = None) -> None:
        checks.append({"level": level, "id": cid, "message": message, "detail": detail})

    if inbox.is_dir():
        add("pass", "inbox_exists", f"Inbox directory exists: {inbox}")
    else:
        add("fail", "inbox_exists", f"Inbox missing or not a directory: {inbox}")

    tiffs = list_inbox_tiffs(inbox) if inbox.is_dir() else []
    if tiffs:
        add("pass", "inbox_has_tiffs", f"Found {len(tiffs)} GeoTIFF(s) in inbox")
    else:
        add("warn", "inbox_has_tiffs", "No .tif/.tiff files in inbox yet (ok if waiting)")

    inbox_files: list[dict[str, Any]] = []
    n_no_ts = 0
    for p in tiffs:
        ts = infer_timestamp(p)
        if not ts:
            n_no_ts += 1
        inbox_files.append(
            {
                "name": p.name,
                "path": str(p.resolve()),
                "timestamp": ts or None,
                "size_bytes": p.stat().st_size if p.is_file() else 0,
            }
        )
    if tiffs and n_no_ts == 0:
        add("pass", "timestamps", "All filenames have parseable timestamps")
    elif tiffs and n_no_ts == len(tiffs):
        add(
            "fail",
            "timestamps",
            "No parseable timestamps in filenames — frames will be rejected",
            "Use names like 2024-08-02_16-09-52-717_LWIR.tif or burn_20260610_120000.tif",
        )
    elif tiffs:
        add(
            "warn",
            "timestamps",
            f"{n_no_ts}/{len(tiffs)} files lack timestamps (will be rejected)",
        )

    # Monotonic timestamps + gap heuristic (field kit plan S2)
    ts_parsed = []
    for row in inbox_files:
        if not row.get("timestamp"):
            continue
        try:
            from datetime import datetime

            raw = str(row["timestamp"])
            for fmt in (
                "%Y-%m-%dT%H:%M:%S",
                "%Y%m%d_%H%M%S",
                "%Y-%m-%d_%H-%M-%S",
            ):
                try:
                    ts_parsed.append((row["name"], datetime.fromisoformat(raw.replace("Z", "")) if "T" in raw else datetime.strptime(raw[:15], fmt)))
                    break
                except ValueError:
                    continue
        except Exception:  # noqa: BLE001
            continue
    if len(ts_parsed) >= 2:
        ordered = sorted(ts_parsed, key=lambda x: x[1])
        names_chrono = [n for n, _ in ordered]
        names_inbox = [r["name"] for r in inbox_files if r.get("timestamp")]
        # compare chronological order vs listing order among dated files
        dated_order = [r["name"] for r in inbox_files if r.get("timestamp")]
        if dated_order != names_chrono and sorted(dated_order) == sorted(names_chrono):
            add(
                "warn",
                "timestamps_order",
                "Inbox file order is not chronological — pipeline sorts by time, OK if intentional",
            )
        else:
            add("pass", "timestamps_order", "Timestamp sequence is consistent")
        deltas = [
            (ordered[i + 1][1] - ordered[i][1]).total_seconds()
            for i in range(len(ordered) - 1)
        ]
        if deltas:
            max_gap = max(deltas)
            if max_gap > 3600:
                add(
                    "warn",
                    "timestamp_gaps",
                    f"Largest inter-frame gap ≈ {max_gap/60:.1f} min — ROS may be noisy",
                )
            else:
                add("pass", "timestamp_gaps", f"Max inter-frame gap ≈ {max_gap:.0f}s")

    if masks_dir is None:
        add("info", "masks", "No --masks: MAD adaptive segmentation will be used")
    elif masks_dir.is_dir():
        mask_files = [
            p
            for p in masks_dir.iterdir()
            if p.is_file() and p.suffix.lower() in TIFF_EXTENSIONS
        ]
        add("pass", "masks_dir", f"Masks directory OK ({len(mask_files)} TIFF)")
        if tiffs:
            paired = 0
            for img in tiffs:
                stem = img.stem
                if any(
                    (masks_dir / f"{stem}{sfx}").is_file()
                    for sfx in (".tif", "_mask.tif", ".tiff", "_mask.tiff")
                ):
                    paired += 1
            if paired == len(tiffs):
                add("pass", "mask_pairs", f"All {paired} inbox frames have a mask pair")
            elif paired == 0:
                add(
                    "warn",
                    "mask_pairs",
                    "No mask pairs found for inbox stems — ingest may reject if MAD disabled",
                )
            else:
                add(
                    "warn",
                    "mask_pairs",
                    f"Only {paired}/{len(tiffs)} frames have mask pairs",
                )
    else:
        add("fail", "masks_dir", f"Masks path is not a directory: {masks_dir}")

    if work_dir is not None:
        if work_dir.exists() and not work_dir.is_dir():
            add("fail", "work_dir", f"work-dir exists but is not a directory: {work_dir}")
        else:
            add("pass", "work_dir", f"work-dir usable: {work_dir}")
            state = load_state(work_dir / "outbox" / STATE_FILENAME)
            if state:
                add(
                    "info",
                    "existing_state",
                    f"Existing state: event={state.event_id} frames={state.n_frames_staged} "
                    f"grade={state.quality_grade} updates={state.n_updates}",
                )

    # CRS cannot be fully validated without opening rasters; sample first file
    if tiffs:
        try:
            import rasterio

            with rasterio.open(tiffs[0]) as ds:
                if ds.crs is None:
                    add("fail", "crs", f"First file has no CRS: {tiffs[0].name}")
                elif not ds.crs.is_projected:
                    add(
                        "fail",
                        "crs",
                        f"CRS is geographic (not projected metric): {ds.crs}",
                        "Reproject to UTM (e.g. EPSG:32630) before field use",
                    )
                else:
                    add("pass", "crs", f"Sample CRS projected: {ds.crs}")
                res = (abs(ds.transform.a) + abs(ds.transform.e)) / 2.0
                add("info", "resolution", f"Sample resolution ≈ {res:.3f} m/px")
        except Exception as exc:  # noqa: BLE001
            add("warn", "crs", f"Could not open sample GeoTIFF: {exc}")

    n_fail = sum(1 for c in checks if c["level"] == "fail")
    n_warn = sum(1 for c in checks if c["level"] == "warn")
    n_pass = sum(1 for c in checks if c["level"] == "pass")

    return {
        "product": "incident_runtime_v1",
        "command": "doctor",
        "event_id": event_id,
        "inbox": str(inbox.resolve()) if inbox.exists() else str(inbox),
        "work_dir": str(work_dir.resolve()) if work_dir and work_dir.exists() else (
            str(work_dir) if work_dir else None
        ),
        "masks_dir": str(masks_dir) if masks_dir else None,
        "ok": n_fail == 0,
        "n_pass": n_pass,
        "n_warn": n_warn,
        "n_fail": n_fail,
        "checks": checks,
        "inbox_files": inbox_files,
        "n_inbox_tiffs": len(tiffs),
    }


def config_snapshot(config: IncidentConfig) -> dict[str, Any]:
    """Serialize runtime config for JSON reports."""
    return {
        "event_id": config.event_id,
        "sensor_id": config.sensor_id,
        "estimated_error_m": config.estimated_error_m,
        "inbox": str(config.inbox),
        "work_dir": str(config.work_dir),
        "masks_dir": str(config.masks_dir) if config.masks_dir else None,
        "band": config.band,
        "threshold": config.threshold,
        "mad_z": config.mad_z,
        "respect_alpha": config.respect_alpha,
        "min_component_pixels": config.min_component_pixels,
        "scientific_clean": config.scientific_clean,
        "max_components": config.max_components,
        "morph_close_pixels": config.morph_close_pixels,
        "min_component_area_m2": config.min_component_area_m2,
        "ref_name": config.ref_name,
        "ref_vp_m_min": config.ref_vp_m_min,
        "ref_area_ha": config.ref_area_ha,
        "min_file_age_s": config.min_file_age_s,
    }
