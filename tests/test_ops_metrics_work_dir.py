"""PR2: ops metrics from temporal window layout (no weights)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.product.decide_service import (
    attach_infocam_anchor_audit,
    load_infocam_anchor,
    load_ops_metrics_from_work_dir,
    operational_files_to_ops_metrics,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "tests" / "fixtures" / "pilot"
OPS_WIN = PILOT / "ops_tobarra_min"
ANCHORS = PILOT / "anchors_tobarra_snippet.json"


def test_window_fixture_ros_and_grade():
    m = load_ops_metrics_from_work_dir(OPS_WIN, base=ROOT, include_repo_root=True)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(6.7520810792516155)
    assert m["quality_grade"] == "B"
    assert m["ros_source"] == "operational_metrics.speed_median_m_min"
    assert m["area_ha_max"] == pytest.approx(26.5503001953125)
    assert m["n_frames_staged"] >= 1
    assert m.get("engine") == "front_dynamics_v1"


def test_structural_primary_ros_priority(tmp_path: Path):
    """Only nested structural.primary_ros_m_min present → still resolves."""
    wd = tmp_path / "struct_only"
    wd.mkdir()
    (wd / "operational_metrics.json").write_text(
        json.dumps(
            {
                "quality_grade": "B",
                "structural": {"primary_ros_m_min": 5.5, "structural_grade": "B"},
                "observation_count": 3,
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(5.5)
    assert m["ros_source"] == "operational_metrics.structural.primary_ros_m_min"


def test_front_dynamics_ros_fallback(tmp_path: Path):
    wd = tmp_path / "fd_only"
    wd.mkdir()
    (wd / "front_dynamics.json").write_text(
        json.dumps(
            {
                "primary_ros_m_min": 4.2,
                "structural_grade": "C",
                "engine": "front_dynamics_v1",
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(4.2)
    assert m["ros_source"] == "front_dynamics.primary_ros_m_min"
    assert m["quality_grade"] == "C"


def test_grade_only_returns_none(tmp_path: Path):
    wd = tmp_path / "grade_only"
    wd.mkdir()
    (wd / "operational_metrics.json").write_text(
        json.dumps({"quality_grade": "A", "area_ha_max": 10.0}),
        encoding="utf-8",
    )
    assert load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False) is None


def test_anchor_only_not_ops(tmp_path: Path):
    """Anchor alone never yields ops_metrics (H10)."""
    empty = tmp_path / "empty_wd"
    empty.mkdir()
    assert load_ops_metrics_from_work_dir(empty, base=tmp_path, include_repo_root=False) is None
    anchor = load_infocam_anchor(ANCHORS, "tobarra_20240802", base=ROOT)
    assert anchor is not None
    assert anchor["status"] == "confirmed"
    # attach without ops → None
    assert attach_infocam_anchor_audit(None, anchor, fire_id="tobarra_20240802") is None


def test_summary_does_not_overwrite_ros(tmp_path: Path):
    wd = tmp_path / "sum_no_overwrite"
    wd.mkdir()
    (wd / "operational_metrics.json").write_text(
        json.dumps(
            {
                "speed_median_m_min": 6.0,
                "quality_grade": "B",
                "speed_n_observable": 2,
            }
        ),
        encoding="utf-8",
    )
    (wd / "summary.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "speed_median_m_min": 99.0,
                    "primary_ros_m_min": 99.0,
                    "quality_grade": "A",
                    "speed_status": "abstained",
                }
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(6.0)
    assert m["quality_grade"] == "B"  # not overwritten by summary A
    assert m["ros_source"] == "operational_metrics.speed_median_m_min"


def test_summary_fills_missing_only(tmp_path: Path):
    wd = tmp_path / "sum_fill"
    wd.mkdir()
    (wd / "operational_metrics.json").write_text(
        json.dumps({"speed_median_m_min": 3.0}),
        encoding="utf-8",
    )
    (wd / "summary.json").write_text(
        json.dumps(
            {
                "metrics": {
                    "quality_grade": "B",
                    "area_ha_max": 12.5,
                    "n_frames_staged": 5,
                }
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(3.0)
    assert m["quality_grade"] == "B"
    assert m["area_ha_max"] == pytest.approx(12.5)
    assert m["n_frames_staged"] == 5


def test_operational_files_helper_ros_none():
    assert operational_files_to_ops_metrics({"quality_grade": "A"}, None) is None
    assert operational_files_to_ops_metrics(None, None) is None


def test_outbox_path_still_works(tmp_path: Path):
    wd = tmp_path / "incident"
    outbox = wd / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "operational_metrics.json").write_text(
        json.dumps(
            {
                "quality_grade": "A",
                "speed_median_m_min": 8.0,
                "n_frames_staged": 6,
                "area_ha_max": 40.0,
                "speed_vs_ref_ratio": 1.0,
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(8.0)
    assert m["quality_grade"] == "A"


def test_attach_anchor_audit_fields():
    ops = {
        "quality_grade": "B",
        "primary_ros_m_min": 6.752,
        "n_frames_staged": 4,
        "ros_source": "operational_metrics.speed_median_m_min",
    }
    anchor = load_infocam_anchor(ANCHORS, "tobarra_20240802", base=ROOT)
    assert anchor is not None
    out = attach_infocam_anchor_audit(ops, anchor, fire_id="tobarra_20240802")
    assert out is not None
    assert out["primary_ros_m_min"] == pytest.approx(6.752)  # never from Vp
    assert out["anchor_vp_m_min"] == pytest.approx(7.0)
    assert out["anchor_area_ha"] == pytest.approx(39.0)
    assert out["anchor_status"] == "confirmed"
    assert out["fire_id"] == "tobarra_20240802"
    # speed_vs_ref filled from ROS/Vp when missing
    assert out["speed_vs_ref_ratio"] == pytest.approx(6.752 / 7.0)


def test_outbox_ros_less_falls_through_to_window_root(tmp_path: Path):
    """Stub outbox without ROS must not shadow window-root ROS (Issue 2)."""
    wd = tmp_path / "window_with_stub_outbox"
    outbox = wd / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "incident_state.json").write_text(
        json.dumps({"quality_grade": "A", "primary_ros_m_min": None}),
        encoding="utf-8",
    )
    (wd / "operational_metrics.json").write_text(
        json.dumps(
            {
                "speed_median_m_min": 6.5,
                "quality_grade": "B",
                "observation_count": 4,
            }
        ),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(6.5)
    assert m["quality_grade"] == "B"


def test_outbox_bad_json_falls_through(tmp_path: Path):
    wd = tmp_path / "bad_outbox"
    outbox = wd / "outbox"
    outbox.mkdir(parents=True)
    (outbox / "incident_state.json").write_text("{not-json", encoding="utf-8")
    (wd / "front_dynamics.json").write_text(
        json.dumps({"primary_ros_m_min": 3.3, "structural_grade": "C"}),
        encoding="utf-8",
    )
    m = load_ops_metrics_from_work_dir(wd, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["primary_ros_m_min"] == pytest.approx(3.3)


def test_n_frames_prefers_first_positive_over_zero():
    m = operational_files_to_ops_metrics(
        {
            "speed_median_m_min": 2.0,
            "n_frames_staged": 0,
            "observation_count": 4,
            "quality_grade": "B",
        },
        None,
    )
    assert m is not None
    assert m["n_frames_staged"] == 4
