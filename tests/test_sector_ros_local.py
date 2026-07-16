"""Local-speed sector ROS precision."""

from __future__ import annotations

from wildfire_front.sector_ros_local import sector_ros_from_local_samples


def test_sector_from_directional_samples():
    # Head ~180°, flank ~90°, rear ~0°
    samples = (
        [{"speed_m_min": 10.0, "angle_deg": 180.0} for _ in range(20)]
        + [{"speed_m_min": 5.0, "angle_deg": 90.0} for _ in range(20)]
        + [{"speed_m_min": 2.0, "angle_deg": 0.0} for _ in range(20)]
    )
    out = sector_ros_from_local_samples(samples, expansion_bearing_deg=180.0)
    assert out["status"] == "estimated"
    assert out["n_samples"] == 60
    s = out["sectors"]
    assert s["head_m_min"] > s["flank_m_min"] > s["rear_m_min"]
    assert out["n_head"] >= 15
    assert "local_normal_ray" in out["method"]


def test_sector_abstain_empty():
    out = sector_ros_from_local_samples([], expansion_bearing_deg=100.0)
    assert out["status"] == "abstained"


def test_sector_scale_to_bulk_primary():
    samples = (
        [{"speed_m_min": 20.0, "angle_deg": 180.0} for _ in range(15)]
        + [{"speed_m_min": 10.0, "angle_deg": 90.0} for _ in range(15)]
        + [{"speed_m_min": 5.0, "angle_deg": 0.0} for _ in range(15)]
    )
    out = sector_ros_from_local_samples(
        samples, expansion_bearing_deg=180.0, scale_to_primary_m_min=5.71
    )
    assert out["status"] == "estimated"
    assert abs(out["sectors"]["primary_m_min"] - 5.71) < 1e-6
    assert out["sectors"]["head_m_min"] > out["sectors"]["rear_m_min"]
    assert out.get("scale_to_primary") is not None
