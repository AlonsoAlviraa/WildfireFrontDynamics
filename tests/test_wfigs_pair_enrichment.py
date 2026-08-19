"""Leakage-aware WFIGS pair enrichment tests."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.open_if.regional import pair_enrichment
from wildfire_front.open_if.regional.pair_enrichment import WFIGSPairEnricher


class _FakeEarthSearch:
    def search(self, *, collection, bbox, start, end, max_items=600):
        del bbox, start, end, max_items
        sensor_assets = (
            {"red": {"href": "https://example.test/s2-red.tif"}}
            if collection == "sentinel-2-l2a"
            else {"red": {"href": "https://example.test/landsat-red.tif"}}
        )
        return (
            [
                {
                    "id": f"{collection}-item",
                    "collection": collection,
                    "bbox": [-121.1, 44.9, -120.9, 45.1],
                    "properties": {
                        "datetime": "2025-07-30T18:00:00Z",
                        "eo:cloud_cover": 10.0,
                        "platform": "fixture",
                    },
                    "assets": sensor_assets,
                }
            ],
            False,
        )


def test_pair_enrichment_resolves_pre_t0_eo_and_hrrr(
    tmp_path: Path, monkeypatch
) -> None:
    pairs_path = tmp_path / "PAIRS.json"
    pairs_path.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "pair_id": "pair-1",
                        "event_id": "2025-WANW-000001",
                        "split": "train",
                        "t0_observation_id": "obs-0",
                        "t0": "2025-08-01T10:00:00Z",
                        "t1": "2025-08-01T20:00:00Z",
                        "metrics": {"delta_hours": 10.0},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    observations_path = tmp_path / "observations.geojson"
    observations_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "observation_id": "obs-0",
                            "event_id": "2025-WANW-000001",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-121.0, 45.0],
                                    [-120.95, 45.0],
                                    [-120.95, 45.05],
                                    [-121.0, 45.05],
                                    [-121.0, 45.0],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        pair_enrichment,
        "_probe_head",
        lambda url: {
            "status": 200,
            "last_modified": "2025-08-01T08:30:00Z",
            "content_length": 100,
            "url": url,
        },
    )
    output = tmp_path / "enrichment"
    inventory = WFIGSPairEnricher(
        pairs_path=pairs_path,
        observations_path=observations_path,
        output_root=output,
        workers=2,
        earth_search=_FakeEarthSearch(),
    ).build()
    counts = inventory["counts"]
    assert counts["pairs"] == 1
    assert counts["pairs_sentinel2_pre_t0"] == 1
    assert counts["pairs_landsat_pre_t0"] == 1
    assert counts["pairs_hrrr_available_by_t0_and_full_window"] == 1
    enriched = json.loads((output / "PAIR_ENRICHMENT.json").read_text(encoding="utf-8"))
    row = enriched["pairs"][0]
    assert row["weather"]["available_by_t0_verified"] is True
    assert row["weather"]["last_lead"] == 14
    assert row["eo"]["sentinel2"]["candidates"][0]["datetime"] < row["t0"]
    assert inventory["rights"]["internal_noncommercial_training_allowed"] is True
    assert inventory["rights"]["training_blocked_by_wfigs_rights"] is False
    assert inventory["rights"]["raw_data_redistribution_allowed"] is False


def test_alaska_is_not_misclassified_as_hrrr_conus_covered() -> None:
    pair = {
        "t0": "2025-08-01T10:00:00Z",
        "t1": "2025-08-01T20:00:00Z",
    }
    assert pair_enrichment._weather_candidates(
        pair, [-150.0, 64.0, -149.0, 65.0]
    ) == []
    assert pair_enrichment._weather_candidates(
        pair, [-121.1, 44.9, -120.9, 45.1]
    )
