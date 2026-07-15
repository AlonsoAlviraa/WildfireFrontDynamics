"""Tests for operator GIS / brief exports."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.models import FrontObservation
from wildfire_front.observatory_export import (
    export_operator_bundle,
    write_main_front_geojson,
    write_ros_timeline_csv,
)


def _obs(t: float, half: float = 10.0) -> FrontObservation:
    ring = (
        (0.0, 0.0),
        (half * 2, 0.0),
        (half * 2, half * 2),
        (0.0, half * 2),
        (0.0, 0.0),
    )
    return FrontObservation(
        observation_id=f"o{t}",
        event_id="e",
        sensor_id="s",
        time_s=t,
        observed_at=f"t{t}",
        components=(ring,),
        estimated_error_m=1.0,
        crs="EPSG:32630",
        coordinate_system="projected_metric",
        resolution_m=1.0,
        method="test",
    )


def test_main_front_geojson(tmp_path: Path) -> None:
    path = write_main_front_geojson([_obs(0), _obs(60, 12)], tmp_path / "mf.geojson", event_id="e")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) == 2


def test_export_bundle(tmp_path: Path) -> None:
    ops = {
        "quality_grade": "A",
        "quality_label_es": "ok",
        "speed_median_m_min": 7.0,
        "speed_n_observable": 3,
        "primary_methods_used": ["area_isotropic"],
        "area_ha_max": 10.0,
        "engine": "front_dynamics_v1",
        "structural": {
            "pairs": [
                {
                    "time_start_s": 0,
                    "time_end_s": 60,
                    "dt_min": 1.0,
                    "primary_ros_m_min": 7.0,
                    "primary_method": "area_isotropic",
                }
            ],
            "calibration": {"has_reference": False},
        },
    }
    paths = export_operator_bundle([_obs(0), _obs(60)], ops, tmp_path, event_id="e")
    assert Path(paths["brief_md"]).is_file()
    assert Path(paths["ros_timeline_csv"]).is_file()
    assert Path(paths["main_front_geojson"]).is_file()
