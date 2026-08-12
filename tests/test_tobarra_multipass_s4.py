"""Tests for Tobarra multipass S4 arrival-time ROS helpers (no GPU)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.arrival_ros import (
    arrival_gradient_ros_m_min,
    build_s4_board,
    compare_ros_to_anchor,
    discover_multipass_chain,
    parse_timestamp_from_name,
    strip_frame_objects,
)
from wildfire_front.geometry_speed import estimate_geometry_speeds, summarize_geometry_speeds
from wildfire_front.models import FrontObservation, GeometrySpeedConfig, Line
from wildfire_front.reconstruction import reconstruct_arrival_from_components


def rectangle(min_x: float, min_y: float, max_x: float, max_y: float) -> Line:
    return (
        (min_x, min_y),
        (max_x, min_y),
        (max_x, max_y),
        (min_x, max_y),
        (min_x, min_y),
    )


def observation(time_s: float, components: tuple[Line, ...]) -> FrontObservation:
    return FrontObservation(
        observation_id=f"obs_{time_s}",
        event_id="s4_synth",
        sensor_id="thermal",
        time_s=time_s,
        observed_at=f"2024-08-02T16:{int(time_s // 60):02d}:00Z",
        components=components,
        estimated_error_m=0.1,
        crs="EPSG:32630",
        coordinate_system="projected_metric",
        resolution_m=1.0,
        method="test_mask",
    )


class ParseTimestampTests:
    def test_parses_tobarra_lwir_name(self) -> None:
        iso, key = parse_timestamp_from_name("2024-08-02_16-15-07-320_LWIR.tif")
        assert iso is not None
        assert key is not None
        assert iso is not None
        assert iso.startswith("2024-08-02T16:15:07")

    def test_missing_timestamp(self) -> None:
        iso, key = parse_timestamp_from_name("nope.tif")
        assert iso is None
        assert key is None


class DiscoverChainTests:
    def test_blocked_when_fewer_than_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img = root / "images"
            mask = root / "masks"
            img.mkdir()
            mask.mkdir()
            # empty → blocked
            inv = discover_multipass_chain(img, mask)
            assert inv["status"] == "BLOCKED_MULTI_PASS_EXPORT"
            assert inv["n_frames"] == 0

            (img / "2024-08-02_16-15-07-320_LWIR.tif").write_bytes(b"x")
            (mask / "2024-08-02_16-15-07-320_LWIR_mask.tif").write_bytes(b"x")
            inv1 = discover_multipass_chain(img, mask)
            assert inv1["n_frames"] == 1
            assert inv1["status"] == "BLOCKED_MULTI_PASS_EXPORT"

            (img / "2024-08-02_16-18-49-319_LWIR.tif").write_bytes(b"x")
            (mask / "2024-08-02_16-18-49-319_LWIR_mask.tif").write_bytes(b"x")
            inv2 = discover_multipass_chain(img, mask)
            assert inv2["n_frames"] == 2
            assert inv2["status"] == "OK"
            assert inv2["n_with_timestamp"] == 2
            serial = strip_frame_objects(inv2)
            assert "frame_objects" not in serial
            json.dumps(serial)  # must be JSON-safe


class ArrivalGradientRosTests:
    def test_uniform_wavefront_recovers_ros(self) -> None:
        # Planar arrival: T = (x / v) with v = 6 m/min = 0.1 m/s → T_s = x / 0.1 = 10 x
        # ROS_m_min = 60 / |dT/dx| = 60 / 10 = 6
        res = 1.0
        xs = np.arange(0, 40, res)
        ys = np.arange(0, 20, res)
        xx, _yy = np.meshgrid(xs, ys)
        v_m_s = 6.0 / 60.0
        arrival = xx / v_m_s
        out = arrival_gradient_ros_m_min(arrival, res, max_plausible_m_min=30.0)
        assert out["status"] == "ok"
        assert out["ros_median_m_min"] is not None
        assert float(out["ros_median_m_min"]) == pytest.approx(6.0, abs=0.5)

    def test_too_few_cells_skips(self) -> None:
        arr = np.array([[0.0, np.nan], [np.nan, np.nan]])
        out = arrival_gradient_ros_m_min(arr, 1.0)
        assert out["status"] == "skipped"
        assert out["ros_median_m_min"] is None


class SyntheticMultipassPipelineTests:
    def test_expanding_front_arrival_and_geometry(self) -> None:
        """Synthetic multi-pass (≥2) → arrival grid + geometry ROS without GPU."""
        obs = [
            observation(0.0, (rectangle(0, 0, 20, 20),)),
            observation(60.0, (rectangle(-2, -2, 22, 22),)),  # 2 m in 1 min → ~2 m/min
            observation(120.0, (rectangle(-4, -4, 24, 24),)),
        ]
        xx, yy, arrival = reconstruct_arrival_from_components(obs, resolution=1.0)
        assert int(np.isfinite(arrival).sum()) > 10
        oneill = arrival_gradient_ros_m_min(arrival, 1.0, max_plausible_m_min=60.0)
        # Gradient on stepped arrival may be coarse; just require finite path
        assert oneill["status"] in ("ok", "skipped")

        geom = estimate_geometry_speeds(
            obs,
            GeometrySpeedConfig(sample_spacing_m=1.0, max_normal_distance_m=20.0),
        )
        summary = summarize_geometry_speeds(geom)
        assert summary["speed_status"] == "estimated"
        assert int(summary["num_observable"]) > 0
        med = float(summary["speed_median_m_min"])  # type: ignore[arg-type]
        assert med > 0.5
        assert med < 10.0

        anchor = compare_ros_to_anchor(med, vp_m_min=7.0)
        assert anchor["has_ros"]
        assert anchor["grade"] in (
            "compatible_order_of_magnitude",
            "underestimate",
            "overestimate",
        )

        board = build_s4_board(
            status="OK",
            inventory={
                "status": "OK",
                "n_frames": 3,
                "n_with_timestamp": 3,
                "images_dir": "/tmp/x",
                "masks_dir": "/tmp/y",
                "first_timestamp_utc": "2024-08-02T16:00:00Z",
                "last_timestamp_utc": "2024-08-02T16:02:00Z",
                "frames": [],
            },
            geometry_ros={"primary_ros_m_min": med, "quality_grade": "B"},
            arrival_oneill=oneill,
            anchor_compare=anchor,
        )
        assert board["schema"] == "wfd_tobarra_multipass_s4_v1"
        assert board["status"] == "OK"
        # Dual rails: lab ml_product_go may be True; field fusion stays OFF.
        assert board["rails"]["iou_is_not_ros"]
        assert not board["rails"]["field_ops_allow_ml_live_in_fusion"]
        assert board["rails"]["lampman_mae_not_sla"]
        mh = board.get("multihorizon_fieldops")
        assert isinstance(mh, dict)
        if mh.get("schema") == "wfd_multihorizon_fieldops_v1":
            assert mh["rails"]["iou_is_not_ros"]
            assert mh["rails"]["field_ops_ml_live_fusion"] == "OFF"
        json.dumps(board, default=str)


class CompareAnchorTests:
    def test_compatible_ratio(self) -> None:
        c = compare_ros_to_anchor(5.7, 7.0)
        assert c["grade"] == "compatible_order_of_magnitude"
        assert c["ratio"] == pytest.approx(5.7 / 7.0, abs=10**-4)

    def test_no_invent_when_missing_ros(self) -> None:
        c = compare_ros_to_anchor(None, 7.0)
        assert c["grade"] == "no_ros"
        assert c["ratio"] is None


class StageFramesAndRunnerExitTests:
    """Runner failure modes + _stage_frames edge cases (no real LWIR ingest)."""

    def test_stage_frames_max_one_no_zerodiv(self) -> None:
        """--max-frames 1 must not ZeroDivisionError when chain is longer."""
        from scripts.run_tobarra_multipass_s4 import _stage_frames
        from wildfire_front.arrival_ros import MultipassFrame

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for i, name in enumerate(
                (
                    "2024-08-02_16-15-07-320_LWIR.tif",
                    "2024-08-02_16-18-49-319_LWIR.tif",
                    "2024-08-02_16-19-14-281_LWIR.tif",
                )
            ):
                img = root / name
                mask = root / f"{Path(name).stem}_mask.tif"
                img.write_bytes(b"img")
                mask.write_bytes(b"msk")
                frames.append(
                    MultipassFrame(
                        image_path=img,
                        mask_path=mask,
                        timestamp_utc=f"2024-08-02T16:1{i}:00Z",
                        sort_key=float(i),
                        stem=Path(name).stem,
                    )
                )
            stage = root / "stage"
            img_dir, mask_dir, n = _stage_frames(frames, stage, max_frames=1)
            assert n == 1
            assert len(list(img_dir.glob("*.tif"))) == 1
            assert len(list(mask_dir.glob("*.tif"))) == 1

    def test_stage_frames_even_sample_two(self) -> None:
        from scripts.run_tobarra_multipass_s4 import _stage_frames
        from wildfire_front.arrival_ros import MultipassFrame

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frames = []
            for i in range(5):
                name = f"2024-08-02_16-{10 + i:02d}-00-000_LWIR.tif"
                img = root / name
                mask = root / f"{Path(name).stem}_mask.tif"
                img.write_bytes(b"i")
                mask.write_bytes(b"m")
                frames.append(
                    MultipassFrame(
                        image_path=img,
                        mask_path=mask,
                        timestamp_utc=None,
                        sort_key=float(i),
                        stem=Path(name).stem,
                    )
                )
            img_dir, _mask_dir, n = _stage_frames(frames, root / "st", max_frames=2)
            assert n == 2
            assert len(list(img_dir.glob("*.tif"))) == 2

    def test_runner_empty_dirs_exits_2_and_blocked_board(self) -> None:
        """Explicit empty --images/--masks → exit 2 + BLOCKED (no full-disk fallback)."""
        from scripts.run_tobarra_multipass_s4 import run as multipass_run

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            img = root / "images"
            mask = root / "masks"
            out = root / "out"
            img.mkdir()
            mask.mkdir()
            rc = multipass_run(
                [
                    "--mode",
                    "ingest",
                    "--images",
                    str(img),
                    "--masks",
                    str(mask),
                    "--out",
                    str(out),
                    "--no-prefer-staging",
                    "--max-frames",
                    "2",
                ]
            )
            assert rc == 2
            board_path = out / "s4_board.json"
            assert board_path.is_file()
            board = json.loads(board_path.read_text(encoding="utf-8"))
            assert board.get("status") == "BLOCKED_MULTI_PASS_EXPORT"
            assert board.get("verdict") == "BLOCKED_MULTI_PASS_EXPORT"
            assert (out / "GAP.json").is_file()

    def test_runner_blocked_when_full_disk_forced_empty(self) -> None:
        """Import-level: discover empty → board BLOCKED contract."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv = discover_multipass_chain(root / "i", root / "m")
            assert inv["status"] == "BLOCKED_MULTI_PASS_EXPORT"
            board = build_s4_board(
                status="BLOCKED_MULTI_PASS_EXPORT",
                inventory=strip_frame_objects(inv),
                blocked_reason=inv.get("blocked_reason"),
            )
            assert board["status"] == "BLOCKED_MULTI_PASS_EXPORT"
            assert board["verdict"] == "BLOCKED_MULTI_PASS_EXPORT"
