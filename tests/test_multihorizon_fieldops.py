"""Unit tests for multi-horizon field_ops (not ML next-day IoU)."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

from wildfire_front.arrival_ros import build_s4_board, compare_ros_to_anchor
from wildfire_front.cli import build_parser
from wildfire_front.cli_multihorizon import run_multihorizon
from wildfire_front.multihorizon_fieldops import (
    DEFAULT_LEAD_TIMES_H,
    DEFAULT_RAILS,
    METHOD_ANISOTROPIC,
    METHOD_HYBRID,
    METHOD_REINIT,
    FieldOpsRails,
    MultiHorizonError,
    advance_distance_m,
    apply_wind_sector_boost,
    attach_multihorizon_for_ops,
    build_anisotropic_multihorizon,
    build_hybrid_multihorizon,
    build_multihorizon_forecast,
    circle_area_ha,
    equivalent_ros_from_area_duration,
    format_multihorizon_human,
    from_arrival_ros_result,
    from_psb_duration,
    from_s4_board_sources,
    multihorizon_to_geojson,
    multipass_envelope_scorecard,
    normalize_lead_times_h,
    reinit_multihorizon_from_frame,
    sector_ros_from_primary,
)
from wildfire_front.progressive_burn import (
    ProgressiveBurnConfig,
    build_stage_sequence,
    multihorizon_from_stage_sequence,
)


class TestNormalizeAndPhysics:
    def test_default_lead_times(self) -> None:
        assert DEFAULT_LEAD_TIMES_H == (1.0, 3.0, 5.0, 12.0, 24.0)

    def test_normalize_sorts_and_dedupes(self) -> None:
        assert normalize_lead_times_h([5, 1, 1, 3]) == [1.0, 3.0, 5.0]

    def test_normalize_rejects_non_positive(self) -> None:
        with pytest.raises(MultiHorizonError):
            normalize_lead_times_h([0, 1])
        with pytest.raises(MultiHorizonError):
            normalize_lead_times_h([-2])

    def test_advance_distance(self) -> None:
        # 7 m/min × 1 h = 7 * 60 = 420 m
        assert advance_distance_m(7.0, 1.0) == pytest.approx(420.0)
        assert advance_distance_m(7.0, 5.0) == pytest.approx(2100.0)

    def test_circle_area_ha(self) -> None:
        # r=100 m → pi*10000 / 10000 = pi ha
        assert circle_area_ha(100.0) == pytest.approx(math.pi, abs=10**-6)


class TestBuildForecast:
    def test_horizons_and_rails(self) -> None:
        card = build_multihorizon_forecast(7.0, ros_source="test")
        assert card.product_id == "front_dynamics_v1"
        assert len(card.horizons) == 5
        assert card.lead_times_h == list(DEFAULT_LEAD_TIMES_H)
        d = card.as_dict()
        assert d["rails"]["iou_is_not_ros"]
        assert d["rails"]["field_ops_ml_live_fusion"] == "OFF"
        assert not d["rails"]["field_ops_allow_ml_live_in_fusion"]
        assert d["rails"]["product_rail"] == "field_ops"
        # 1h advance
        h1 = next(h for h in card.horizons if h.lead_time_h == 1.0)
        assert h1.advance_m == pytest.approx(420.0)
        assert h1.area_ha_circle is not None
        assert float(h1.area_ha_circle) > 0

    def test_rails_reject_fusion_on(self) -> None:
        bad = FieldOpsRails(field_ops_allow_ml_live_in_fusion=True)
        with pytest.raises(MultiHorizonError):
            build_multihorizon_forecast(1.0, rails=bad)

    def test_rails_reject_iou_as_ros(self) -> None:
        bad = FieldOpsRails(iou_is_not_ros=False)
        with pytest.raises(MultiHorizonError):
            build_multihorizon_forecast(1.0, rails=bad)

    def test_zero_ros(self) -> None:
        card = build_multihorizon_forecast(0.0)
        for h in card.horizons:
            assert h.advance_m == 0.0
            assert "ros_zero_no_advance" in h.notes

    def test_polygon_buffer_when_shapely(self) -> None:
        # unit square 100m → buffer
        poly = [(0, 0), (100, 0), (100, 100), (0, 100), (0, 0)]
        card = build_multihorizon_forecast(1.0, lead_times_h=[1.0], polygon_xy_m=poly)
        h = card.horizons[0]
        assert h.geometry_type == "polygon_buffer"
        assert h.buffer_area_ha is not None
        assert float(h.buffer_area_ha) > 1.0  # > original 1 ha

    def test_human_format(self) -> None:
        text = format_multihorizon_human(build_multihorizon_forecast(7.0))
        assert "not ML next-day" in text
        assert "7" in text


class TestArrivalAndS4:
    def test_from_arrival_ros(self) -> None:
        arr = {
            "status": "ok",
            "ros_median_m_min": 6.0,
            "ros_mean_m_min": 6.5,
            "method": "oneill_arrival_gradient_v1",
            "n_ros_cells": 10,
        }
        card = from_arrival_ros_result(arr)
        assert card.ros_m_min == pytest.approx(6.0)
        assert "ros_median_m_min" in card.ros_source

    def test_from_s4_prefers_geometry(self) -> None:
        card = from_s4_board_sources(
            geometry_ros={"primary_ros_m_min": 8.0},
            arrival_oneill={"status": "ok", "ros_median_m_min": 6.0},
        )
        assert card is not None
        assert card.ros_m_min == pytest.approx(8.0)

    def test_build_s4_board_attaches_multihorizon(self) -> None:
        board = build_s4_board(
            status="ok",
            inventory={"n_frames": 2, "frames": []},
            geometry_ros={"primary_ros_m_min": 7.0},
            arrival_oneill={"status": "ok", "ros_median_m_min": 6.5, "method": "oneill"},
        )
        mh = board.get("multihorizon_fieldops")
        assert isinstance(mh, dict)
        assert mh.get("schema") == "wfd_multihorizon_fieldops_v1"
        assert float(mh["ros_m_min"]) == pytest.approx(7.0)
        assert mh["rails"]["iou_is_not_ros"]
        assert mh["rails"]["field_ops_ml_live_fusion"] == "OFF"
        assert "Multi-horizon" in " ".join(board["honesty"])

    def test_build_s4_board_skipped_without_ros(self) -> None:
        board = build_s4_board(
            status="blocked",
            inventory={"n_frames": 0},
            attach_multihorizon=True,
        )
        mh = board["multihorizon_fieldops"]
        assert mh.get("status") == "skipped"

    def test_anchor_compare_not_iou(self) -> None:
        c = compare_ros_to_anchor(7.0, vp_m_min=7.0)
        assert c["grade"] == "compatible_order_of_magnitude"


class TestPsbHook:
    def test_equiv_ros_from_area_duration(self) -> None:
        # 39 ha circle, 24 h → radius from area, ROS = r / (24*60)
        ros = equivalent_ros_from_area_duration(39.0, 86_400.0)
        assert ros > 0
        r_m = math.sqrt(39.0 * 10_000.0 / math.pi)
        assert ros == pytest.approx(r_m / (86_400.0 / 60.0), abs=10**-6)

    def test_from_psb_duration(self) -> None:
        card = from_psb_duration(86_400.0, 39.0, lead_times_h=[1.0, 5.0])
        assert len(card.horizons) == 2
        assert card.honesty.get("psb_synthetic_not_lwir")
        assert "psb" in card.extra

    def test_multihorizon_from_stage_sequence(self) -> None:
        try:
            from shapely.geometry import box
        except ImportError:
            self.skipTest("shapely required")
        # ~1 ha box in metric CRS coords (metres)
        geom = box(0, 0, 100, 100)
        seq = build_stage_sequence(
            geom,
            ProgressiveBurnConfig(
                n_stages=3,
                total_duration_s=3600.0,
                source_crs="EPSG:6933",
                metric_crs="EPSG:6933",
            ),
            source_crs="EPSG:6933",
        )
        mh = multihorizon_from_stage_sequence(seq, lead_times_h=[1.0])
        assert mh["schema"] == "wfd_multihorizon_fieldops_v1"
        assert float(mh["ros_m_min"]) > 0
        assert mh["honesty"]["psb_synthetic_not_lwir"]


class TestCliMultihorizon:
    def test_parser_has_command(self) -> None:
        p = build_parser()
        args = p.parse_args(["multihorizon", "--ros-m-min", "7", "--json"])
        assert args.command == "multihorizon"
        assert args.ros_m_min == pytest.approx(7.0)

    def test_run_tobarra_vp(self) -> None:
        p = build_parser()
        args = p.parse_args(["multihorizon", "--tobarra-vp", "--json"])
        # Capture via output file
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "mh.json"
            args.output = out
            args.json = True
            rc = run_multihorizon(args)
            assert rc == 0
            data = json.loads(out.read_text(encoding="utf-8"))
            assert float(data["ros_m_min"]) == pytest.approx(7.0)
            assert len(data["horizons"]) == 5
            assert data["rails"]["iou_is_not_ros"]

    def test_run_requires_source(self) -> None:
        p = build_parser()
        args = p.parse_args(["multihorizon"])
        rc = run_multihorizon(args)
        assert rc == 2

    def test_default_rails_banner(self) -> None:
        assert "field_ops" in DEFAULT_RAILS.banner
        assert "IoU" in DEFAULT_RAILS.banner

    def test_cli_anisotropic_and_geojson(self) -> None:
        p = build_parser()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "mh.json"
            gj = Path(td) / "rings.geojson"
            args = p.parse_args(
                [
                    "multihorizon",
                    "--ros-m-min",
                    "6.14",
                    "--method",
                    "anisotropic",
                    "--geojson",
                    str(gj),
                    "--json",
                    "-o",
                    str(out),
                ]
            )
            rc = run_multihorizon(args)
            assert rc == 0
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data["method"] == METHOD_ANISOTROPIC
            assert gj.is_file()
            geo = json.loads(gj.read_text(encoding="utf-8"))
            assert geo["type"] == "FeatureCollection"
            assert geo["properties"]["iou_is_not_ros"]
            assert geo["properties"]["guidance_not_tactical"]

    def test_cli_reinit(self) -> None:
        p = build_parser()
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "reinit.json"
            args = p.parse_args(
                [
                    "multihorizon",
                    "--ros-m-min",
                    "6.0",
                    "--method",
                    "anisotropic",
                    "--reinit-frame",
                    "frame_03",
                    "-o",
                    str(out),
                    "--json",
                ]
            )
            rc = run_multihorizon(args)
            assert rc == 0
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data["method"] == METHOD_REINIT
            assert data.get("reinit_from_frame") == "frame_03"


class TestAnisotropicPR5:
    def test_head_ge_flank_ge_rear(self) -> None:
        card = build_anisotropic_multihorizon(10.0, lead_times_h=[1.0, 3.0])
        assert card.method == METHOD_ANISOTROPIC
        sec = card.sector_ros_m_min or {}
        assert sec["head"] >= sec["flank"]
        assert sec["flank"] >= sec["rear"]
        h1 = next(h for h in card.horizons if h.lead_time_h == 1.0)
        assert h1.head_advance_m is not None
        assert float(h1.head_advance_m) >= float(h1.flank_advance_m)  # type: ignore[arg-type]
        assert float(h1.flank_advance_m) >= float(h1.rear_advance_m)  # type: ignore[arg-type]
        # head = 10 m/min → 600 m/h
        assert float(h1.head_advance_m) == pytest.approx(600.0)  # type: ignore[arg-type]
        assert float(h1.flank_advance_m) == pytest.approx(300.0)  # type: ignore[arg-type]
        assert float(h1.rear_advance_m) == pytest.approx(180.0)  # type: ignore[arg-type]
        assert card.honesty.get("head_ge_flank_ge_rear")
        assert card.rails["iou_is_not_ros"]
        assert card.rails["field_ops_ml_live_fusion"] == "OFF"

    def test_sector_override_ordered(self) -> None:
        # Intentionally reverse input — must enforce head≥flank≥rear
        sec = sector_ros_from_primary(
            8.0, sectors_override={"head": 2.0, "flank": 5.0, "rear": 9.0}
        )
        assert sec["head"] >= sec["flank"]
        assert sec["flank"] >= sec["rear"]


class TestHybridPR7:
    def test_hybrid_method_and_horizons(self) -> None:
        card = build_hybrid_multihorizon(6.14, lead_times_h=DEFAULT_LEAD_TIMES_H)
        assert card.method == METHOD_HYBRID
        assert card.lead_times_h == list(DEFAULT_LEAD_TIMES_H)
        for need in (1.0, 3.0, 5.0, 12.0, 24.0):
            assert need in card.lead_times_h
        assert card.honesty.get("guidance_not_tactical")
        assert card.honesty.get("not_tactical_dispatch")
        sec = card.sector_ros_m_min or {}
        assert sec["head"] >= sec["flank"]
        assert sec["flank"] >= sec["rear"]


class TestWindPR13:
    def test_missing_weather_fallback(self) -> None:
        base = sector_ros_from_primary(10.0)
        boosted, prov = apply_wind_sector_boost(base, weather=None)
        assert not prov["weather_used"]
        assert boosted["head"] == pytest.approx(base["head"])

    def test_zero_wind_leaves_sectors_identity(self) -> None:
        """Calm/zero wind must not reshape sectors (identity + weather_used=False)."""
        base = sector_ros_from_primary(10.0)
        boosted, prov = apply_wind_sector_boost(
            base,
            weather={"wind_10m_ms": 0.0, "wind_from_deg": 270.0, "source": "test"},
        )
        assert not prov["weather_used"]
        assert prov.get("reason") == "calm_or_zero_wind"
        assert boosted["head"] == pytest.approx(base["head"])
        assert boosted["flank"] == pytest.approx(base["flank"])
        assert boosted["rear"] == pytest.approx(base["rear"])
        assert boosted["primary"] == pytest.approx(base["primary"])
        # Explicit kwargs path
        boosted2, prov2 = apply_wind_sector_boost(base, wind_10m_ms=0.0, wind_from_deg=90.0)
        assert not prov2["weather_used"]
        assert boosted2["rear"] == pytest.approx(base["rear"])

    def test_near_calm_tapers_all_sector_scales(self) -> None:
        """Near-calm wind tapers head/flank/rear scales together (not rear-only)."""
        base = sector_ros_from_primary(10.0)
        # Full wind for reference
        full, _ = apply_wind_sector_boost(
            base, weather={"wind_10m_ms": 5.0, "wind_from_deg": 270.0}
        )
        # Near calm: 0.5 m/s → half of scale delta from identity
        half, prov = apply_wind_sector_boost(
            base, weather={"wind_10m_ms": 0.5, "wind_from_deg": 270.0}
        )
        assert prov["weather_used"]
        # Head between identity and full boost
        assert half["head"] > base["head"]
        assert half["head"] < full["head"]
        # Rear not fully scaled by 0.9 at half wind (tapered toward 1.0)
        assert half["rear"] > full["rear"] - 1e-9
        assert half["head"] >= half["flank"]
        assert half["flank"] >= half["rear"]

    def test_wind_boost_provenance(self) -> None:
        base = sector_ros_from_primary(10.0)
        boosted, prov = apply_wind_sector_boost(
            base, weather={"wind_10m_ms": 5.0, "wind_from_deg": 270.0, "source": "test"}
        )
        assert prov["weather_used"]
        assert boosted["head"] > base["head"]
        assert boosted["head"] >= boosted["flank"]
        assert boosted["flank"] >= boosted["rear"]
        assert "head_bearing_deg" in boosted
        card = build_anisotropic_multihorizon(
            10.0,
            lead_times_h=[1.0],
            weather={"wind_10m_ms": 4.0, "wind_from_deg": 90.0},
        )
        assert (card.extra.get("wind") or {}).get("weather_used")


class TestScorecardPR8:
    def test_partial_short_span(self) -> None:
        card = build_multihorizon_forecast(6.14)
        sc = multipass_envelope_scorecard(
            card,
            lead_time_h=1.0,
            multipass_span_s=1650.0,  # Tobarra-like ~27 min
            observed_advance_m=100.0,
        )
        assert sc["schema"] == "wfd_multihorizon_multipass_scorecard_v1"
        assert sc["status"] == "PARTIAL"
        assert sc["metrics_are_not_ml_iou"]
        assert sc["metrics"]["ml_iou"] is None
        assert sc["metrics"]["model_iou"] is None
        assert "model_iou" not in str(sc.get("label_note", "").lower() or "x")
        # Must not claim ML IoU label
        assert sc["honesty"]["not_ml_iou"]

    def test_abstain_without_obs(self) -> None:
        card = build_anisotropic_multihorizon(7.0, lead_times_h=[1.0])
        sc = multipass_envelope_scorecard(card, lead_time_h=1.0, multipass_span_s=7200.0)
        assert sc["status"] in ("PARTIAL", "ABSTAIN")


class TestReinitPR9:
    def test_reinit_stamp(self) -> None:
        card = reinit_multihorizon_from_frame(
            6.14,
            frame_id="2024-08-02_16-42-37-447_LWIR",
            method=METHOD_ANISOTROPIC,
            lead_times_h=[1.0, 3.0],
        )
        assert card.method == METHOD_REINIT
        assert card.extra.get("reinit_from_frame") == "2024-08-02_16-42-37-447_LWIR"
        assert card.honesty.get("never_ml_mask_as_1h_truth")
        d = card.as_dict()
        assert d["reinit_from_frame"] == "2024-08-02_16-42-37-447_LWIR"


class TestGeojsonPR10:
    def test_geojson_honesty(self) -> None:
        card = build_anisotropic_multihorizon(7.0, lead_times_h=[1.0, 5.0], head_bearing_deg=45.0)
        gj = multihorizon_to_geojson(card, center_xy=(100.0, 200.0))
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) == 2
        props = gj["properties"]
        assert props["iou_is_not_ros"]
        assert props["guidance_not_tactical"]
        assert props["field_ops_ml_live_fusion"] == "OFF"
        f0 = gj["features"][0]["properties"]
        assert f0["not_tactical_dispatch"]


class TestDecideAttachPR12:
    def test_attach_when_ops_ros(self) -> None:
        mh = attach_multihorizon_for_ops({"primary_ros_m_min": 6.14})
        assert mh is not None
        assert mh is not None
        assert mh["status"] == "ok"
        assert mh["rails"]["iou_is_not_ros"]
        assert mh["rails"]["field_ops_ml_live_fusion"] == "OFF"

    def test_omit_without_ros(self) -> None:
        assert attach_multihorizon_for_ops({}) is None
        assert attach_multihorizon_for_ops(None) is None

    def test_decide_service_surface(self) -> None:
        from wildfire_front.product.decide_service import decide_from_request

        payload = decide_from_request(
            {
                "event_id": "test_mh",
                "ops_metrics": {"primary_ros_m_min": 6.14, "quality_grade": "A"},
                "channel": "unit_test",
            },
            trust_client_reliability=True,
        )
        mh = payload.get("multihorizon_fieldops")
        assert isinstance(mh, dict)
        assert mh.get("status") == "ok"
        assert float(mh["ros_m_min"]) == pytest.approx(6.14)
        assert mh["rails"]["field_ops_ml_live_fusion"] == "OFF"

        empty = decide_from_request({"event_id": "empty", "channel": "unit_test"})
        mh2 = empty.get("multihorizon_fieldops")
        assert mh2.get("status") == "ABSTAIN"


class TestLabKillPR11:
    def test_protocol_rails_no_larger_unet_default(self) -> None:
        from wildfire_front.ml.protocol_rails import (
            DEAD_PATHS,
            LAB_LARGER_UNET_DEFAULT_BET,
            LAB_LARGER_UNET_FIELD_FUSION_PATH,
        )

        assert not LAB_LARGER_UNET_DEFAULT_BET
        assert not LAB_LARGER_UNET_FIELD_FUSION_PATH
        assert "larger_unet_as_field_product" in DEAD_PATHS

    def test_catalog_rails_stamp(self) -> None:
        from wildfire_front.ml.product_catalog import dual_product_rails

        rails = dual_product_rails()
        assert not rails["lab_larger_unet_default_bet"]
        assert not rails["lab_scale_field_fusion_path"]
        assert not rails["field_ops_allow_ml_live_in_fusion"]
