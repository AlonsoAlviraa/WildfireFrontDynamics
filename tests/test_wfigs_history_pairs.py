"""Historical WFIGS harvesting and temporal-pair audit tests."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from wildfire_front.open_if.regional.base import FetchPayload, make_observation_feature
from wildfire_front.open_if.regional.temporal_pairs import RegionalTemporalPairBuilder
from wildfire_front.open_if.regional.wfigs_history import (
    HarvestPartition,
    WFIGSHistoricalHarvester,
    _partition_url,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "regional_adapters"


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


def _feature(
    event_id: str,
    observed_at: str,
    geometry: dict,
    *,
    semantic: str = "wildfire_daily_perimeter",
    candidate: bool = True,
    gacc: str = "NWCC",
    state: str = "US-WA",
    suffix: str = "x",
) -> dict:
    return make_observation_feature(
        source_id="us_wfigs_daily_perimeters",
        upstream_item_id=f"{event_id}-{observed_at}-{suffix}",
        event_id=event_id,
        geometry=geometry,
        observation_kind="perimeter",
        geometry_semantics=semantic,
        role="progression_label",
        observed_at=observed_at,
        published_at=None,
        source_updated_at=observed_at,
        retrieved_at="2026-08-18T20:00:00Z",
        source_url="fixture:wfigs-daily",
        licence_id="nifc-wfigs-public-research-no-redistribution-v1",
        provisional=True,
        candidate_progression_label=candidate,
        upstream_properties={
            "poly_FeatureCategory": "Wildfire Daily Fire Perimeter",
            "attr_IncidentTypeCategory": "WF",
            "poly_FeatureAccess": "Public",
            "poly_FeatureStatus": "Approved",
            "poly_IncidentName": f"Fire {event_id}",
            "attr_GACC": gacc,
            "attr_POOState": state,
        },
    )


def test_partition_url_has_year_region_and_strict_daily_filters() -> None:
    partition = HarvestPartition(year=2025, region="northwest", gacc="NWCC")
    url = _partition_url(partition, as_of=date(2026, 8, 18), offset=2000, page_size=500)
    params = parse_qs(urlparse(url).query)
    where = params["where"][0]
    assert "Wildfire Daily Fire Perimeter" in where
    assert "attr_IncidentTypeCategory = 'WF'" in where
    assert "attr_GACC = 'NWCC'" in where
    assert "attr_UniqueFireIdentifier LIKE '2025-%'" in where
    assert "2025-01-01" in where and "2025-12-31" in where
    assert params["resultOffset"] == ["2000"]
    assert params["resultRecordCount"] == ["500"]
    assert params["f"] == ["geojson"]


def test_harvest_partition_materializes_and_resumes(tmp_path: Path, monkeypatch) -> None:
    harvester = WFIGSHistoricalHarvester(
        output_root=tmp_path,
        as_of=date(2026, 8, 18),
        page_size=2000,
    )
    fixture_body = (FIXTURES / "wfigs.geojson").read_bytes()

    def fake_request(url: str, *, name: str, accept: str = "*/*") -> FetchPayload:
        body = b'{"count":2}' if "returnCountOnly" in url else fixture_body
        return FetchPayload(name=name, url=url, body=body, content_type="application/json")

    monkeypatch.setattr(harvester.adapter, "request", fake_request)
    partition = HarvestPartition(year=2026, region="northwest", gacc="NWCC")
    first = harvester.harvest_partition(partition)
    assert first["status"] == "complete"
    assert first["counts"]["raw_received"] == 2
    assert first["counts"]["normalized"] == 2
    assert Path(first["manifest"]).is_file()

    def should_not_fetch(*args, **kwargs):
        raise AssertionError("resume should not fetch")

    monkeypatch.setattr(harvester.adapter, "request", should_not_fetch)
    resumed = harvester.harvest_partition(partition, resume=True)
    assert resumed["resumed"] is True


def test_pair_builder_metrics_rejections_inventory_and_event_splits(tmp_path: Path) -> None:
    features = [
        _feature("2025-WANW-000001", "2025-08-01T00:00:00Z", _square(-121.0, 45.0, 0.10), suffix="a0"),
        _feature("2025-WANW-000001", "2025-08-01T08:00:00Z", _square(-121.01, 44.99, 0.12), suffix="a1"),
        _feature("2025-WANW-000001", "2025-08-01T20:00:00Z", _square(-121.02, 44.98, 0.14), suffix="a2"),
        _feature("2025-ORNW-000002", "2025-07-01T00:00:00Z", _square(-123.0, 43.0, 0.10), suffix="b0"),
        _feature("2025-ORNW-000002", "2025-07-02T00:00:00Z", _square(-123.01, 42.99, 0.12), suffix="b1"),
        # Same event/time duplicate: smaller geometry must be rejected.
        _feature("2025-ORNW-000002", "2025-07-02T00:00:00Z", _square(-123.0, 43.0, 0.05), suffix="dup"),
        # Ambiguous local timestamp.
        _feature("2025-IDGB-000003", "2025-06-01T12:00:00", _square(-115.0, 44.0, 0.10), suffix="amb"),
        # Explicitly forbidden semantics.
        _feature("2025-CAON-000004", "2025-05-01T00:00:00Z", _square(-120.0, 38.0, 0.10), semantic="final_burn_scar", suffix="scar"),
        _feature("2025-CASO-000005", "2025-05-01T00:00:00Z", _square(-118.0, 34.0, 0.10), semantic="buffered_hotspot_m3_proxy", suffix="m3"),
        _feature("2025-AKAI-000006", "2025-05-01T00:00:00Z", _square(-150.0, 64.0, 0.10), semantic="thermal_hotspot", suffix="hot"),
    ]
    observations = tmp_path / "observations.geojson"
    observations.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8"
    )
    out = tmp_path / "pairs"
    inventory = RegionalTemporalPairBuilder(
        observations_path=observations,
        output_root=out,
        as_of=datetime(2026, 8, 18, tzinfo=UTC),
        split_salt="fixture-salt",
    ).build()
    assert inventory["n_eventos_descargados"] == 6
    assert inventory["n_eventos_con_2_mas_perimetros"] == 2
    assert inventory["n_eventos_con_pares_aprobados"] == 2
    assert inventory["n_pares_aprobados"] == 3
    assert inventory["n_pares_6_12h"] == 1
    assert inventory["n_pares_12_24h"] == 1
    assert inventory["n_pares_24_48h"] == 1
    rejected = inventory["n_observaciones_rechazadas_y_motivo"]
    assert rejected["duplicate_event_timestamp"] == 1
    assert rejected["timestamp_ambiguous_or_not_utc"] == 1
    assert rejected["final_scar_rejected"] == 1
    assert rejected["m3_proxy_rejected"] == 1
    assert rejected["hotspot_rejected"] == 1
    rights = inventory["derechos_resueltos"]
    assert rights["rights_resolved_for_internal_noncommercial_training"] is True
    assert rights["rights_resolved_for_training_and_redistribution"] is False
    assert rights["raw_data_redistribution_allowed"] is False
    assert inventory["claims"]["training_blocked_until_rights_resolved"] is False
    assert (out / "RIGHTS_POLICY.json").is_file()

    pairs = json.loads((out / "PAIRS.json").read_text(encoding="utf-8"))["pairs"]
    assert all(pair["metrics"]["iou"] > 0 for pair in pairs)
    assert all(pair["metrics"]["growth_ha"] > 0 for pair in pairs)
    splits = json.loads((out / "SPLITS.json").read_text(encoding="utf-8"))
    split_sets = [set(splits["events"][name]) for name in ("train", "validation", "test")]
    assert not (split_sets[0] & split_sets[1])
    assert not (split_sets[0] & split_sets[2])
    assert not (split_sets[1] & split_sets[2])
    for pair in pairs:
        assert pair["split"] == splits["event_to_split"][pair["event_id"]]
