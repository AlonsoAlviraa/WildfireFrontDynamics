"""Tests for incident_runtime_v1 (watch + update)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from wildfire_front.cli import build_parser, main
from wildfire_front.incident import (
    IncidentConfig,
    process_incident_once,
    run_incident_watch,
)
from wildfire_front.incident.state import load_state


def write_tiff(path: Path, data: np.ndarray, *, crs: str = "EPSG:32630") -> None:
    array = data if data.ndim == 3 else data[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[2],
        height=array.shape[1],
        count=array.shape[0],
        dtype=array.dtype,
        crs=crs,
        transform=from_origin(500000.0, 4100000.0, 10.0, 10.0),
    ) as dataset:
        dataset.write(array)


def make_frame(path: Path, size: int, timestamp: str) -> Path:
    """Growing hot blob with parseable timestamp in filename."""
    image = np.zeros((2, 16, 16), dtype=np.uint16)
    image[0, 4 : 4 + size, 4 : 4 + size] = 1200
    mask = np.zeros((16, 16), dtype=np.uint8)
    mask[4 : 4 + size, 4 : 4 + size] = 1
    write_tiff(path, image)
    return path


def make_mask(path: Path, size: int) -> Path:
    mask = np.zeros((16, 16), dtype=np.uint8)
    mask[4 : 4 + size, 4 : 4 + size] = 1
    write_tiff(path, mask)
    return path


def test_process_incident_once_streaming(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    masks = tmp_path / "masks"
    work = tmp_path / "work"
    inbox.mkdir()
    masks.mkdir()

    # Frame 1 only
    make_frame(inbox / "burn_20260610_120000.tif", 3, "20260610_120000")
    make_mask(masks / "burn_20260610_120000_mask.tif", 3)

    cfg = IncidentConfig(
        event_id="test_incident",
        sensor_id="thermal_test",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    s1 = process_incident_once(cfg, force=True)
    assert s1["status"] in ("updated", "error")
    assert s1["n_staged"] == 1
    assert (work / "outbox" / "incident_state.json").is_file()

    # Frame 2 → ROS becomes possible
    make_frame(inbox / "burn_20260610_120100.tif", 5, "20260610_120100")
    make_mask(masks / "burn_20260610_120100_mask.tif", 5)
    s2 = process_incident_once(cfg, force=True)
    assert s2["status"] == "updated"
    assert s2["n_staged"] == 2
    outbox = work / "outbox"
    assert (outbox / "operational_metrics.json").is_file()
    assert (outbox / "main_front.geojson").is_file()
    assert (outbox / "emergency_briefing.md").is_file()
    assert (outbox / "emergency_envelope.json").is_file()
    assert (outbox / "incident_state.json").is_file()
    assert (outbox / "watch_heartbeat.json").is_file()
    assert (outbox / "incident_log.jsonl").is_file()
    # M2.1 — Fire Decision Card in operator outbox
    assert (outbox / "fire_decision_card.json").is_file()
    assert (outbox / "fire_decision_card.md").is_file()
    fdc = json.loads((outbox / "fire_decision_card.json").read_text(encoding="utf-8"))
    assert fdc.get("decision") in ("GO", "HOLD", "ABSTAIN")
    assert "confidence_pred" in fdc
    assert fdc.get("audit", {}).get("schema") == "fire_decision_card_v1"
    assert s2.get("decision") == fdc.get("decision")
    # M2.9 — forensic acta + radio + replay
    assert (outbox / "fire_decision_radio.txt").is_file()
    assert (outbox / "fire_decision_acta.md").is_file()
    assert (outbox / "forensic_manifest.json").is_file()
    assert (outbox / "replay_sources.json").is_file()
    man = json.loads((outbox / "forensic_manifest.json").read_text(encoding="utf-8"))
    assert man.get("self_replay_ok") is True
    radio = (outbox / "fire_decision_radio.txt").read_text(encoding="utf-8")
    assert fdc.get("decision") in radio
    brief = (outbox / "emergency_briefing.md").read_text(encoding="utf-8")
    assert "Decision Card" in brief or "Decision:" in brief
    hb = json.loads((outbox / "watch_heartbeat.json").read_text(encoding="utf-8"))
    assert hb.get("status") == "updated"
    assert hb.get("decision") == fdc.get("decision")
    log_lines = (outbox / "incident_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) >= 1
    last_log = json.loads(log_lines[-1])
    assert last_log.get("decision") == fdc.get("decision")

    state = load_state(outbox / "incident_state.json")
    assert state is not None
    assert state.n_frames_staged == 2
    assert state.n_updates >= 1
    assert "not_validated_tactical_dispatch" in state.disclaimers

    # Idle when no new frames
    s3 = process_incident_once(cfg, force=False)
    assert s3["status"] == "idle"


def test_watch_max_frames(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    masks = tmp_path / "masks"
    work = tmp_path / "work"
    inbox.mkdir()
    masks.mkdir()
    for i, size in enumerate((3, 4, 5)):
        ts = f"20260610_120{i:02d}00"
        make_frame(inbox / f"burn_{ts}.tif", size, ts)
        make_mask(masks / f"burn_{ts}_mask.tif", size)

    cfg = IncidentConfig(
        event_id="watch_test",
        sensor_id="thermal_test",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    result = run_incident_watch(
        cfg,
        interval_s=0.0,
        max_frames=3,
        max_iterations=5,
        once=False,
    )
    assert result["mode"] == "watch"
    assert result["iterations"] >= 1
    last = result["last"]
    assert last.get("n_staged") == 3
    assert (work / "outbox" / "incident_state.json").is_file()


def test_cli_incident_update(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    masks = tmp_path / "masks"
    work = tmp_path / "work"
    inbox.mkdir()
    masks.mkdir()
    make_frame(inbox / "burn_20260610_120000.tif", 3, "t0")
    make_mask(masks / "burn_20260610_120000_mask.tif", 3)
    make_frame(inbox / "burn_20260610_120100.tif", 5, "t1")
    make_mask(masks / "burn_20260610_120100_mask.tif", 5)

    main(
        [
            "incident",
            "update",
            "--inbox",
            str(inbox),
            "--work-dir",
            str(work),
            "--event-id",
            "cli_inc",
            "--sensor-id",
            "t",
            "--estimated-error-m",
            "2",
            "--masks",
            str(masks),
            "--min-file-age-s",
            "0",
            "--min-component-pixels",
            "1",
            "--force",
            "--json",
        ]
    )
    assert (work / "outbox" / "emergency_briefing.md").is_file()
    state = json.loads((work / "outbox" / "incident_state.json").read_text(encoding="utf-8"))
    assert state["product"] == "incident_runtime_v1"
    assert state["n_frames_staged"] == 2


def test_parser_has_incident_watch() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "incident",
            "watch",
            "--inbox",
            "in",
            "--work-dir",
            "out",
            "--once",
            "--max-frames",
            "2",
        ]
    )
    assert args.command == "incident"
    assert args.incident_command == "watch"
    assert args.once is True
    assert args.max_frames == 2


def test_cli_doctor_and_status(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    inbox.mkdir()
    make_frame(inbox / "burn_20260610_120000.tif", 3, "t0")
    make_frame(inbox / "burn_20260610_120100.tif", 5, "t1")
    main(
        [
            "incident",
            "doctor",
            "--inbox",
            str(inbox),
            "--work-dir",
            str(work),
            "--json",
        ]
    )
    # status without state → exit 2
    try:
        main(["incident", "status", "--work-dir", str(work), "--json"])
        raised = False
    except SystemExit as e:
        raised = True
        assert e.code == 2
    assert raised


def test_same_name_overwrite_updates_stage(tmp_path: Path) -> None:
    """Re-drop same filename with new content must overwrite stage."""
    inbox = tmp_path / "inbox"
    masks = tmp_path / "masks"
    work = tmp_path / "work"
    inbox.mkdir()
    masks.mkdir()
    name = "burn_20260610_120000.tif"
    make_frame(inbox / name, 3, "t0")
    make_mask(masks / "burn_20260610_120000_mask.tif", 3)
    cfg = IncidentConfig(
        event_id="overwrite",
        sensor_id="t",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    process_incident_once(cfg, force=True)
    staged = work / "stage" / "images" / name
    old_sha = staged.read_bytes()
    make_frame(inbox / name, 7, "t0")  # larger blob, same name
    process_incident_once(cfg, force=True)
    assert staged.read_bytes() != old_sha


def test_retry_after_error_not_idle(tmp_path: Path, monkeypatch) -> None:
    inbox = tmp_path / "inbox"
    masks = tmp_path / "masks"
    work = tmp_path / "work"
    inbox.mkdir()
    masks.mkdir()
    make_frame(inbox / "burn_20260610_120000.tif", 3, "t0")
    make_mask(masks / "burn_20260610_120000_mask.tif", 3)
    make_frame(inbox / "burn_20260610_120100.tif", 5, "t1")
    make_mask(masks / "burn_20260610_120100_mask.tif", 5)
    cfg = IncidentConfig(
        event_id="retry",
        sensor_id="t",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        masks_dir=masks,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
    )
    ok = process_incident_once(cfg, force=True)
    assert ok["status"] == "updated"

    import wildfire_front.incident.pipeline as pipe

    calls = {"n": 0}
    real = pipe.run_geotiff_ingest

    def boom(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected_failure")
        return real(*a, **k)

    monkeypatch.setattr(pipe, "run_geotiff_ingest", boom)
    # force=True triggers recompute so inject fires (idle would skip ingest)
    err = process_incident_once(cfg, force=True)
    assert err["status"] == "error"
    assert "injected_failure" in str(err.get("error") or "")
    # Next poll without force must NOT idle while last_error is set
    nxt = process_incident_once(cfg, force=False)
    assert nxt["status"] != "idle"


def test_corrupt_state_recovers(tmp_path: Path) -> None:
    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    inbox.mkdir()
    outbox = work / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "incident_state.json").write_text("{not json", encoding="utf-8")
    make_frame(inbox / "burn_20260610_120000.tif", 3, "t0")
    cfg = IncidentConfig(
        event_id="corrupt",
        sensor_id="t",
        estimated_error_m=2.0,
        inbox=inbox,
        work_dir=work,
        min_file_age_s=0.0,
        min_component_pixels=1,
        scientific_clean=False,
        mad_z=3.0,
    )
    s = process_incident_once(cfg, force=True)
    assert s["status"] in ("updated", "error", "waiting_for_frames")
    # State rewritten as valid JSON
    data = json.loads((outbox / "incident_state.json").read_text(encoding="utf-8"))
    assert data["product"] == "incident_runtime_v1"


def test_tobarra_stream_optional(tmp_path: Path) -> None:
    """Optional integration: stream first Tobarra frames if artifacts present."""
    root = Path(__file__).resolve().parents[1]
    src = root / "artifacts" / "tobarra_reprojected_lwir"
    masks_src = root / "artifacts" / "tobarra_lwir_masks"
    tifs = sorted(src.glob("*.tif")) if src.is_dir() else []
    if len(tifs) < 3:
        return  # skip silently like other optional tests

    inbox = tmp_path / "inbox"
    work = tmp_path / "work"
    inbox.mkdir()
    # Copy 3 frames one-by-one simulating drops
    for tif in tifs[:3]:
        shutil.copy2(tif, inbox / tif.name)

    cfg = IncidentConfig(
        event_id="tobarra_stream",
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
    assert summary["n_staged"] == 3
    # May update or error depending on FOV/mask quality; state must exist
    assert (work / "outbox" / "incident_state.json").is_file()
    if summary["status"] == "updated":
        assert (work / "outbox" / "emergency_briefing.md").is_file()
