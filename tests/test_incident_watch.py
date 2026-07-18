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
    import pytest

    root = Path(__file__).resolve().parents[1]
    src = root / "artifacts" / "tobarra_reprojected_lwir"
    masks_src = root / "artifacts" / "tobarra_lwir_masks"
    tifs = sorted(src.glob("*.tif")) if src.is_dir() else []
    if len(tifs) < 3:
        pytest.skip("Tobarra reprojected LWIR artifacts not present (optional integration)")

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


def test_publish_this_run_reliability_gate(tmp_path: Path) -> None:
    """publish_decision_card writes this-run gate and can unlock field_ops GO."""
    from wildfire_front.incident.pipeline import (
        publish_decision_card,
        write_this_run_reliability_gate,
    )

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    ops = {
        "quality_grade": "A",
        "speed_median_m_min": 5.5,
        "n_frames_staged": 12,
        "area_ha_max": 40,
        "speed_vs_ref_ratio": 0.9,
    }
    gate = write_this_run_reliability_gate(
        outbox,
        "inc_evt",
        {
            "quality_grade": "A",
            "primary_ros_m_min": 5.5,
            "n_frames_staged": 12,
            "area_ha_max": 40,
            "speed_vs_ref_ratio": 0.9,
        },
        open_metrics={"max_area_ha": 2000, "n_timeline_steps": 5},
        decision_policy="field_ops",
    )
    data = json.loads(gate.read_text(encoding="utf-8"))
    assert data["event_id"] == "inc_evt"
    assert data["provenance"]["kind"] == "this_run"
    assert data["field_unlock"] is True
    assert data["system_reliability"]["system_reliability_pass"] is True

    artifacts = publish_decision_card(
        outbox,
        "inc_evt",
        ops,
        n_frames=12,
        include_ml_metrics=False,
        open_metrics={"max_area_ha": 2000, "n_timeline_steps": 5},
        decision_policy="field_ops",
        write_this_run_gate=True,
    )
    assert artifacts["decision"] == "GO"
    assert (outbox / "reliability_gate_report.json").is_file()


def test_suite_only_outbox_gate_does_not_unlock(tmp_path: Path) -> None:
    """Neutralized suite sample in outbox must not unlock field_ops."""
    from wildfire_front.incident.pipeline import publish_decision_card

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    suite = {
        "suite_only": True,
        "field_unlock": False,
        "event_id": "x",
        "system_reliability": {
            "checks": {
                "R1_determinism": True,
                "R2_gates": True,
                "R3_abstention_enforced": True,
                "R4_provenance": True,
            }
        },
    }
    (outbox / "reliability_gate_report.json").write_text(json.dumps(suite), encoding="utf-8")
    ops = {
        "quality_grade": "A",
        "speed_median_m_min": 6.0,
        "n_frames_staged": 20,
        "area_ha_max": 50,
        "speed_vs_ref_ratio": 0.9,
    }
    artifacts = publish_decision_card(
        outbox,
        "x",
        ops,
        n_frames=20,
        include_ml_metrics=False,
        open_metrics={"max_area_ha": 2000, "n_timeline_steps": 5},
        decision_policy="field_ops",
        reliability_gate=outbox / "reliability_gate_report.json",
        write_this_run_gate=False,
    )
    assert artifacts["decision"] == "ABSTAIN"


def test_should_use_incremental_force_and_first_run() -> None:
    from wildfire_front.incident.pipeline import should_use_incremental_ingest

    assert (
        should_use_incremental_ingest(
            force=True,
            n_new_frames=1,
            n_staged=5,
            n_updates=3,
            has_ops_file=True,
            last_error=None,
        )
        is False
    )
    assert (
        should_use_incremental_ingest(
            force=False,
            n_new_frames=1,
            n_staged=5,
            n_updates=0,
            has_ops_file=True,
            last_error=None,
        )
        is False
    )
    assert (
        should_use_incremental_ingest(
            force=False,
            n_new_frames=1,
            n_staged=5,
            n_updates=2,
            has_ops_file=True,
            last_error=None,
        )
        is True
    )


def test_prepare_incremental_ingest_last_pair(tmp_path: Path) -> None:
    from wildfire_front.incident.pipeline import (
        IncidentConfig,
        _prepare_incremental_ingest,
    )

    work = tmp_path / "work"
    images = work / "stage" / "images"
    images.mkdir(parents=True)
    for i, name in enumerate(["a.tif", "b.tif", "c.tif"]):
        (images / name).write_bytes(b"II*\x00" + bytes([i]))
    cfg = IncidentConfig(
        event_id="inc",
        sensor_id="t",
        estimated_error_m=1.0,
        inbox=tmp_path / "inbox",
        work_dir=work,
        min_file_age_s=0.0,
    )
    cfg.inbox.mkdir(exist_ok=True)
    inc_images, _masks = _prepare_incremental_ingest(cfg, n_keep=2)
    assert inc_images is not None
    kept = sorted(p.name for p in inc_images.iterdir() if p.is_file() or p.is_symlink())
    assert kept == ["b.tif", "c.tif"]


def test_weak_ops_this_run_does_not_unlock(tmp_path: Path) -> None:
    """Single-frame / low grade ops must not field_unlock via this-run gate."""
    from wildfire_front.incident.pipeline import write_this_run_reliability_gate

    outbox = tmp_path / "outbox"
    gate = write_this_run_reliability_gate(
        outbox,
        "weak",
        {
            "quality_grade": "C",
            "primary_ros_m_min": 1.0,
            "n_frames_staged": 1,
        },
        decision_policy="field_ops",
    )
    data = json.loads(gate.read_text(encoding="utf-8"))
    assert data["field_unlock"] is False
    assert data["system_reliability"]["system_reliability_pass"] is False
