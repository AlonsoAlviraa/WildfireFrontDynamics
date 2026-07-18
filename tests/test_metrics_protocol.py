"""Tests for wildfire_front.metrics_protocol — anti-vanity labeled metrics."""

from __future__ import annotations

import pytest

from wildfire_front.metrics_protocol import (
    ExperimentRecord,
    MetricProtocol,
    o3_window_summary,
    score_ratio_band,
    utc_now,
)


class TestMetricProtocol:
    def test_to_dict_roundtrip_fields(self):
        m = MetricProtocol(
            domain="ml_ndws",
            metric_name="iou",
            value=0.42,
            unit="1",
            protocol="any_fire_979",
            baseline_name="copy",
            baseline_value=0.35,
            delta=0.07,
            n_samples=100,
            higher_is_better=True,
            notes="holdout",
        )
        d = m.to_dict()
        assert d["domain"] == "ml_ndws"
        assert d["metric_name"] == "iou"
        assert d["value"] == 0.42
        assert d["baseline_name"] == "copy"
        assert d["delta"] == 0.07
        assert d["n_samples"] == 100
        assert d["higher_is_better"] is True


class TestExperimentRecord:
    def test_to_dict_includes_nested_metrics(self):
        rec = ExperimentRecord(
            experiment_id="v31_metric_push",
            hypothesis="temperature scaling improves CLM IoU",
            leap_ids=["L3"],
            status="completed",
            go=True,
            verdict="GO",
            primary_metric="model_iou",
            metrics=[
                MetricProtocol(
                    domain="ml_clm",
                    metric_name="model_iou",
                    value=0.55,
                    protocol="holdout_v1",
                )
            ],
            artifacts=["docs/V31_ML_SCORECARD.json"],
            single_change="temp=0.7",
        )
        d = rec.to_dict()
        assert d["experiment_id"] == "v31_metric_push"
        assert d["go"] is True
        assert len(d["metrics"]) == 1
        assert d["metrics"][0]["metric_name"] == "model_iou"
        assert d["artifacts"] == ["docs/V31_ML_SCORECARD.json"]


class TestUtcNow:
    def test_iso_format_with_timezone(self):
        s = utc_now()
        assert "T" in s
        # timezone-aware ISO from datetime.now(UTC)
        assert s.endswith("+00:00") or s.endswith("Z") or "+00:00" in s


class TestScoreRatioBand:
    def test_pass_within_band(self):
        m = score_ratio_band(7.0, ref=7.0)
        assert m.metric_name == "ratio_vs_anchor"
        assert m.value == pytest.approx(1.0)
        assert m.notes == "PASS"
        assert m.domain == "observatorio"
        assert m.higher_is_better is False
        assert m.delta == pytest.approx(0.0)

    def test_fail_outside_band(self):
        m = score_ratio_band(21.0, ref=7.0)  # ratio=3.0 > high=2.0
        assert m.value == pytest.approx(3.0)
        assert m.notes == "FAIL/ABSTAIN"

    def test_none_value_abstains(self):
        m = score_ratio_band(None, ref=7.0)
        assert m.value is None
        assert m.delta is None
        assert m.notes == "FAIL/ABSTAIN"

    def test_nonpositive_ref_yields_none_ratio(self):
        m = score_ratio_band(5.0, ref=0.0)
        assert m.value is None
        assert m.notes == "FAIL/ABSTAIN"

    def test_custom_band(self):
        m = score_ratio_band(3.0, ref=2.0, low=1.0, high=2.0)  # ratio=1.5
        assert m.notes == "PASS"
        m_edge = score_ratio_band(2.0, ref=2.0, low=1.0, high=2.0)  # ratio=1.0 == low
        assert m_edge.notes == "PASS"
        m_fail = score_ratio_band(0.5, ref=2.0, low=1.0, high=2.0)  # ratio=0.25 < low
        assert m_fail.notes == "FAIL/ABSTAIN"


class TestO3WindowSummary:
    def test_go_when_enough_windows_pass(self):
        windows = [
            {
                "status": "ok",
                "window": "early",
                "primary_ros_m_min": 7.0,
                "ratio_infocam": 1.0,
                "n_frames": 5,
                "quality_grade": "A",
            },
            {
                "status": "ok",
                "window": "mid",
                "primary_ros_m_min": 8.0,
                "ratio_infocam": 1.14,
                "n_frames": 6,
                "quality_grade": "B",
            },
            {
                "status": "ok",
                "window": "late",
                "primary_ros_m_min": 6.5,
                "ratio_infocam": 0.93,
                "n_frames": 4,
                "quality_grade": "A",
            },
        ]
        summary = o3_window_summary(windows, ref_vp=7.0)
        assert summary["n_windows_ok"] == 3
        assert summary["n_pass_ratio_band"] == 3
        assert summary["go"] is True
        assert summary["verdict"] == "GO"
        assert len(summary["metrics"]) == 3
        assert summary["metrics"][0]["protocol"] == "window:early"
        assert summary["metrics"][0]["unit"] == "m/min"

    def test_no_go_insufficient_pass(self):
        windows = [
            {
                "status": "ok",
                "window": "early",
                "primary_ros_m_min": 7.0,
                "ratio_infocam": 1.0,
                "n_frames": 3,
            },
            {
                "status": "ok",
                "window": "mid",
                "primary_ros_m_min": 30.0,
                "ratio_infocam": 4.0,
                "n_frames": 3,
            },
            {
                "status": "error",
                "window": "late",
                "primary_ros_m_min": None,
            },
        ]
        summary = o3_window_summary(windows, ref_vp=7.0)
        assert summary["n_windows_ok"] == 2
        assert summary["n_pass_ratio_band"] == 1
        assert summary["go"] is False
        assert summary["verdict"] == "NO_GO"
        # only ok windows contribute metrics
        assert len(summary["metrics"]) == 2

    def test_ratio_computed_from_ros_when_missing(self):
        windows = [
            {
                "status": "ok",
                "window": "early",
                "primary_ros_m_min": 7.0,
                "n_frames": 2,
                "quality_grade": "C",
            },
            {
                "status": "ok",
                "window": "mid",
                "primary_ros_m_min": 7.0,
                "n_frames": 2,
            },
            {
                "status": "ok",
                "window": "late",
                "primary_ros_m_min": 7.0,
                "n_frames": 2,
            },
        ]
        summary = o3_window_summary(windows, ref_vp=7.0)
        assert summary["go"] is True
        # delta = ratio - 1 = 0
        assert summary["metrics"][0]["delta"] == pytest.approx(0.0)
