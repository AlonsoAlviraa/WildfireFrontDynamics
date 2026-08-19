"""WFIGS event-disjoint geometry baseline tests."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.open_if.regional.geometry_baseline import WFIGSGeometryBaseline


def _square(west: float, south: float, size: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [west + size, south],
                [west + size, south + size],
                [west, south + size],
                [west, south],
            ]
        ],
    }


def test_geometry_baseline_selects_on_validation_and_reports_test(tmp_path: Path) -> None:
    features = []
    pairs = []
    for index, split in enumerate(("train", "validation", "test")):
        event = f"event-{index}"
        first_id = f"obs-{index}-0"
        second_id = f"obs-{index}-1"
        features.extend(
            [
                {
                    "type": "Feature",
                    "properties": {"observation_id": first_id},
                    "geometry": _square(-121.0 + index, 45.0, 0.01),
                },
                {
                    "type": "Feature",
                    "properties": {"observation_id": second_id},
                    "geometry": _square(-121.0005 + index, 44.9995, 0.011),
                },
            ]
        )
        pairs.append(
            {
                "pair_id": f"pair-{index}",
                "event_id": event,
                "split": split,
                "t0_observation_id": first_id,
                "t1_observation_id": second_id,
            }
        )
    pairs_path = tmp_path / "pairs.json"
    observations_path = tmp_path / "observations.geojson"
    output_path = tmp_path / "baseline.json"
    pairs_path.write_text(json.dumps({"pairs": pairs}), encoding="utf-8")
    observations_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    report = WFIGSGeometryBaseline(
        pairs_path=pairs_path,
        observations_path=observations_path,
        output_path=output_path,
        radii_m=(0, 30, 120),
    ).build()
    assert report["counts"]["pairs_usable"] == 3
    assert report["selection"]["test_not_used_for_selection"] is True
    assert report["selection"]["full_iou"]["selected_radius_m"] in {0, 30, 120}
    assert report["aggregate"]["test"]["0"]["pairs"] == 1
    assert report["claims"]["learned_model_training_executed"] is False
    assert report["claims"]["wfigs_internal_noncommercial_training_allowed"] is True
    assert output_path.is_file()
