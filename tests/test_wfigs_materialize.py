"""Tests for leakage-safe WFIGS EO materialization."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon

from wildfire_front.open_if.regional.wfigs_materialize import (
    WFIGSEOMaterializer,
    _hrrr_lead_url,
    _select_hrrr_records,
    target_blind_grid,
)


def _polygon(x0: float, y0: float, span: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [x0, y0],
                [x0 + span, y0],
                [x0 + span, y0 + span],
                [x0, y0 + span],
                [x0, y0],
            ]
        ],
    }


def test_grid_position_is_independent_of_t1() -> None:
    first = Polygon(_polygon(-121.0, 45.0, 0.01)["coordinates"][0])
    grid_a, _ = target_blind_grid(first, size=64, resolution_m=60)
    grid_b, _ = target_blind_grid(first, size=64, resolution_m=60)
    assert grid_a == grid_b
    assert grid_a.size == 64
    assert grid_a.resolution_m == 60


def test_hrrr_index_selects_unique_surface_fields_and_rewrites_lead() -> None:
    index = "\n".join(
        [
            "1:0:d=2025070100:PRES:surface:4 hour fcst:",
            "2:100:d=2025070100:TMP:2 m above ground:4 hour fcst:",
            "3:200:d=2025070100:RH:2 m above ground:4 hour fcst:",
            "4:300:d=2025070100:UGRD:10 m above ground:4 hour fcst:",
            "5:400:d=2025070100:VGRD:10 m above ground:4 hour fcst:",
            "6:500:d=2025070100:APCP:surface:0-4 hour acc fcst:",
            "7:600:d=2025070100:APCP:surface:3-4 hour acc fcst:",
            "8:700:d=2025070100:TCDC:entire atmosphere:4 hour fcst:",
        ]
    )
    records = _select_hrrr_records(index)
    assert [row["element"] for row in records] == [
        "PRES",
        "TMP",
        "RH",
        "UGRD",
        "VGRD",
        "APCP",
    ]
    data, rewritten = _hrrr_lead_url(
        "https://example.test/hrrr.t00z.wrfsfcf41.grib2.idx", 5
    )
    assert rewritten.endswith("wrfsfcf05.grib2.idx")
    assert data.endswith("wrfsfcf05.grib2")


def test_materializer_writes_auditable_training_ready_pair(tmp_path: Path) -> None:
    pairs = {
        "pairs": [
            {
                "pair_id": "pair-1",
                "event_id": "2025-WANW-1",
                "approved": True,
                "split": "train",
                "t0_observation_id": "obs-0",
                "t1_observation_id": "obs-1",
                "metrics": {"delta_hours": 12.0},
            }
        ]
    }
    enrichment = {
        "pairs": [
            {
                "pair_id": "pair-1",
                "eo": {
                    "sentinel2": {
                        "candidates": [
                            {
                                "id": "S2-fixture",
                                "datetime": "2025-07-31T18:00:00Z",
                                "created": "2025-07-31T20:00:00Z",
                                "stac_created_at_or_before_t0": True,
                                "assets": {
                                    key: {"href": f"https://example.test/{key}.tif"}
                                    for key in ("blue", "green", "red", "nir", "scl")
                                },
                            }
                        ]
                    }
                },
                "weather": {
                    "status": "resolved",
                    "available_by_t0_verified": True,
                },
            }
        ]
    }
    observations = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"observation_id": "obs-0"},
                "geometry": _polygon(-121.0, 45.0, 0.01),
            },
            {
                "type": "Feature",
                "properties": {"observation_id": "obs-1"},
                "geometry": _polygon(-121.002, 44.998, 0.014),
            },
        ],
    }
    pairs_path = tmp_path / "pairs.json"
    enrichment_path = tmp_path / "enrichment.json"
    observations_path = tmp_path / "observations.geojson"
    pairs_path.write_text(json.dumps(pairs), encoding="utf-8")
    enrichment_path.write_text(json.dumps(enrichment), encoding="utf-8")
    observations_path.write_text(json.dumps(observations), encoding="utf-8")

    def fake_reader(candidate, grid):
        del candidate
        ones = np.ones((grid.size, grid.size), dtype=np.float32)
        return {
            "blue": ones * 0.1,
            "green": ones * 0.2,
            "red": ones * 0.3,
            "nir": ones * 0.4,
            "ndvi": ones / 7,
            "valid_data": ones.astype(np.uint8),
            "scl": np.full_like(ones, 4, dtype=np.uint8),
        }

    def fake_dem_reader(grid):
        ones = np.ones((grid.size, grid.size), dtype=np.float32)
        return {"dem": ones * 500.0, "dem_valid": ones.astype(np.uint8)}

    def fake_weather_reader(weather, grid, cache_root):
        del weather, cache_root
        ones = np.ones((grid.size, grid.size), dtype=np.float32)
        return {
            "wind_speed": ones * 4.0,
            "wind_direction_rad": ones,
            "temperature_k": ones * 290.0,
            "precipitation_mm": ones * 0.5,
            "humidity_pct": ones * 30.0,
            "air_density": ones * 1.2,
            "weather_valid": ones.astype(np.uint8),
            "hrrr_sampled_leads": np.asarray([1, 6, 12], dtype=np.int16),
        }

    output = tmp_path / "output"
    inventory = WFIGSEOMaterializer(
        pairs_path=pairs_path,
        enrichment_path=enrichment_path,
        observations_path=observations_path,
        output_root=output,
        limit=1,
        size=64,
        scene_reader=fake_reader,
        dem_reader=fake_dem_reader,
        weather_reader=fake_weather_reader,
    ).build()
    assert inventory["counts"] == {
        "pairs_selected": 1,
        "pairs_materialized": 1,
        "pairs_rejected": 0,
        "rejection_reasons": {},
        "training_ready": 1,
    }
    assert inventory["claims"]["model_training_ready"] is True
    row = inventory["rows"][0]
    assert row["target_blind_grid"] is True
    assert row["missing_for_training"] == []
    artifact = np.load(output / row["relative_path"])
    assert artifact["previous_fire"].shape == (64, 64)
    assert artifact["target_fire"].sum() > artifact["previous_fire"].sum()
    assert float(artifact["dem"].mean()) == 500.0
    assert float(artifact["temperature_k"].mean()) == 290.0
    assert artifact["horizon_hours"] == np.float32(12.0)


def test_materializer_rejects_candidate_not_available_by_t0(tmp_path: Path) -> None:
    pairs_path = tmp_path / "pairs.json"
    enrichment_path = tmp_path / "enrichment.json"
    observations_path = tmp_path / "observations.geojson"
    pairs_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair_id": "pair-1",
                        "event_id": "event-1",
                        "approved": True,
                        "split": "train",
                        "t0_observation_id": "obs-0",
                        "t1_observation_id": "obs-1",
                        "metrics": {"delta_hours": 8},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    enrichment_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair_id": "pair-1",
                        "eo": {
                            "sentinel2": {
                                "candidates": [
                                    {
                                        "id": "late-scene",
                                        "stac_created_at_or_before_t0": False,
                                        "assets": {},
                                    }
                                ]
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    observations_path.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    inventory = WFIGSEOMaterializer(
        pairs_path=pairs_path,
        enrichment_path=enrichment_path,
        observations_path=observations_path,
        output_root=tmp_path / "output",
        limit=1,
    ).build()
    assert inventory["counts"]["pairs_materialized"] == 0
    assert inventory["counts"]["rejection_reasons"] == {
        "no_sentinel_candidate_created_by_t0": 1
    }
