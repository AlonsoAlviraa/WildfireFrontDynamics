"""End-to-end offline coverage for WFIGS, CWFIS, and INPE adapters."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from wildfire_front.open_if.regional import (
    INDEX_SCHEMA,
    OBSERVATION_SCHEMA,
    SNAPSHOT_SCHEMA,
    STATE_SCHEMA,
    CWFISAdapter,
    INPEFireEventsAdapter,
    RegionalQuery,
    WFIGSAdapter,
)
from wildfire_front.open_if.regional.inpe import parse_description

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "regional_adapters"


def _payloads(adapter, name: str):
    return adapter.fixture_payloads([FIXTURES / name])


def _props(result):
    return [feature["properties"] for feature in result.features]


def test_wfigs_normalizes_daily_perimeter_without_promoting_other_categories() -> None:
    adapter = WFIGSAdapter()
    query = RegionalQuery(limit=10)
    result = adapter.normalize(
        _payloads(adapter, "wfigs.geojson"),
        query,
        retrieved_at="2026-08-18T18:00:00Z",
    )
    assert len(result.features) == 2
    by_event = {row["event_id"]: row for row in _props(result)}
    daily = by_event["2026-CAABC-000101"]
    assert daily["schema"] == OBSERVATION_SCHEMA
    assert daily["geometry_semantics"] == "wildfire_daily_perimeter"
    assert daily["observed_at"] == "2026-08-17T10:00:00Z"
    assert daily["published_at"] is None
    assert daily["candidate_progression_label"] is True
    assert daily["requires_temporal_pair_audit"] is True
    prescribed = by_event["2026-CAABC-000102"]
    assert prescribed["candidate_progression_label"] is False
    assert "not_daily_fire_perimeter_category" in prescribed["quality_flags"]


def test_wfigs_bbox_and_date_filter_are_applied_to_normalized_features() -> None:
    adapter = WFIGSAdapter()
    result = adapter.normalize(
        _payloads(adapter, "wfigs.geojson"),
        RegionalQuery(bbox=(-120.3, 39.8, -119.9, 40.2), start="2026-08-17", limit=10),
        retrieved_at="2026-08-18T18:00:00Z",
    )
    assert [row["properties"]["event_id"] for row in result.features] == [
        "2026-CAABC-000101"
    ]


def test_wfigs_query_is_bounded_and_uses_server_side_space_time_filters() -> None:
    query = RegionalQuery(
        bbox=(-125.0, 32.0, -114.0, 42.0),
        start="2026-08-01",
        end="2026-08-18",
        limit=50,
    )
    url = WFIGSAdapter.query_url(query, offset=20, count=30)
    params = parse_qs(urlparse(url).query)
    assert params["resultOffset"] == ["20"]
    assert params["resultRecordCount"] == ["30"]
    assert params["geometryType"] == ["esriGeometryEnvelope"]
    assert "poly_PolygonDateTime" in params["where"][0]
    assert params["f"] == ["geojson"]


def test_cwfis_active_fire_stays_a_location_not_a_perimeter() -> None:
    adapter = CWFISAdapter()
    query = RegionalQuery(cwfis_layer="activefires", limit=10)
    result = adapter.normalize(
        _payloads(adapter, "cwfis_activefires.geojson"),
        query,
        retrieved_at="2026-08-18T18:00:00Z",
    )
    assert len(result.features) == 1
    props = result.features[0]["properties"]
    assert props["event_id"] == "2026_NT_SS046-26"
    assert props["geometry_semantics"] == "reported_active_fire_location"
    assert props["observation_kind"] == "incident_location"
    assert props["candidate_progression_label"] is False
    assert "incident_location_not_perimeter" in props["quality_flags"]


def test_cwfis_query_uses_current_cwfif_wfs_contract() -> None:
    query = RegionalQuery(
        bbox=(-141.0, 41.0, -52.0, 84.0), cwfis_layer="activefires", limit=25
    )
    url = CWFISAdapter.query_url(query, offset=0, count=25)
    params = parse_qs(urlparse(url).query)
    assert "geoserver.cwfif.nrcan.gc.ca" in url
    assert params["typeNames"] == ["public:cwfif_national_activefires"]
    assert params["count"] == ["25"]
    assert params["srsName"] == ["EPSG:4326"]


def test_inpe_parses_event_extent_front_and_focus_with_honest_semantics() -> None:
    adapter = INPEFireEventsAdapter()
    query = RegionalQuery(inpe_status="active", limit=10)
    result = adapter.normalize(
        _payloads(adapter, "inpe_eventos_ativos.kml"),
        query,
        retrieved_at="2026-08-18T18:00:00Z",
    )
    assert len(result.features) == 3
    by_semantic = {row["geometry_semantics"]: row for row in _props(result)}
    front = by_semantic["provisional_active_fire_front"]
    assert front["event_id"] == "INPE-837945"
    assert front["observed_at"] == "2026-08-17T18:41:00"
    assert front["candidate_progression_label"] is True
    assert front["provisional"] is True
    assert "timestamp_local_timezone_unspecified" in front["quality_flags"]
    focus = by_semantic["active_fire_focus_point"]
    assert focus["candidate_progression_label"] is False
    assert "focus_point_not_perimeter" in focus["quality_flags"]
    extent = by_semantic["provisional_event_extent_estimate"]
    assert extent["candidate_progression_label"] is False
    assert "event_extent_not_active_front" in extent["quality_flags"]
    assert extent["upstream_properties"]["total_de_focos"] == "6"


def test_inpe_description_parser_handles_accents_and_html() -> None:
    fields = parse_description(
        "<table><tr><td><b>Último foco</b></td><td>2026-08-17 18:41:00</td></tr>"
        "<tr><td><b>Município</b></td><td>ÁGUA BOA</td></tr></table>"
    )
    assert fields == {"ultimo_foco": "2026-08-17 18:41:00", "municipio": "ÁGUA BOA"}


@pytest.mark.parametrize(
    ("adapter", "fixture", "query", "expected_source", "expected_count"),
    [
        (WFIGSAdapter(), "wfigs.geojson", RegionalQuery(limit=10), "us_wfigs_perimeters", 2),
        (
            CWFISAdapter(),
            "cwfis_activefires.geojson",
            RegionalQuery(cwfis_layer="activefires", limit=10),
            "ca_cwfis_ogc",
            1,
        ),
        (
            INPEFireEventsAdapter(),
            "inpe_eventos_ativos.kml",
            RegionalQuery(inpe_status="active", limit=10),
            "br_inpe_queimadas",
            3,
        ),
    ],
)
def test_materialization_writes_raw_normalized_manifest_index_and_state(
    tmp_path: Path, adapter, fixture: str, query: RegionalQuery, expected_source: str, expected_count: int
) -> None:
    report = adapter.ingest(
        output_root=tmp_path,
        query=query,
        fixtures=[FIXTURES / fixture],
        retrieved_at="2026-08-18T18:00:00Z",
    )
    assert report["ok"] is True
    assert report["source_id"] == expected_source
    assert report["counts"]["normalized"] == expected_count
    manifest = json.loads(Path(report["manifest"]).read_text(encoding="utf-8"))
    assert manifest["schema"] == SNAPSHOT_SCHEMA
    assert manifest["fixture_mode"] is True
    assert manifest["raw"][0]["sha256"]
    assert Path(report["index"]).is_file()
    index = json.loads(Path(report["index"]).read_text(encoding="utf-8"))
    assert index["schema"] == INDEX_SCHEMA
    assert index["n_features"] == expected_count
    state = json.loads(Path(report["state"]).read_text(encoding="utf-8"))
    assert state["schema"] == STATE_SCHEMA
    assert state["n_snapshots"] == 1
    assert state["n_index_features"] == expected_count
    raw_file = Path(report["manifest"]).parents[2] / manifest["raw"][0]["file"]
    assert raw_file.is_file()


def test_incremental_repeat_is_idempotent_in_index_but_preserves_snapshot(tmp_path: Path) -> None:
    adapter = WFIGSAdapter()
    kwargs = {
        "output_root": tmp_path,
        "query": RegionalQuery(limit=10),
        "fixtures": [FIXTURES / "wfigs.geojson"],
    }
    first = adapter.ingest(**kwargs, retrieved_at="2026-08-18T18:00:00Z")
    second = adapter.ingest(**kwargs, retrieved_at="2026-08-18T19:00:00Z")
    assert first["counts"]["index_total"] == 2
    assert second["counts"]["index_total"] == 2
    state = json.loads(Path(second["state"]).read_text(encoding="utf-8"))
    assert state["n_snapshots"] == 2
    index = json.loads(Path(second["index"]).read_text(encoding="utf-8"))
    assert {f["properties"]["first_seen_at"] for f in index["features"]} == {
        "2026-08-18T18:00:00Z"
    }
    assert {f["properties"]["last_seen_at"] for f in index["features"]} == {
        "2026-08-18T19:00:00Z"
    }


def test_cli_ingest_regional_fixture_end_to_end(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "wildfire_front",
            "ingest-regional",
            "--provider",
            "inpe",
            "--fixture",
            str(FIXTURES / "inpe_eventos_ativos.kml"),
            "--output-root",
            str(tmp_path),
            "--limit",
            "10",
            "--json",
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        capture_output=True,
        text=True,
    )
    assert process.returncode == 0, process.stderr
    payload = json.loads(process.stdout)
    assert payload["source_id"] == "br_inpe_queimadas"
    assert payload["counts"]["normalized"] == 3
    assert Path(payload["manifest"]).is_file()
    assert Path(payload["index"]).is_file()


def test_common_query_rejects_unbounded_or_invalid_values() -> None:
    with pytest.raises(ValueError, match="positive"):
        RegionalQuery(limit=0).validate()
    with pytest.raises(ValueError, match="bbox"):
        RegionalQuery(bbox=(10.0, 0.0, -10.0, 1.0)).validate()
    with pytest.raises(ValueError, match="start"):
        RegionalQuery(start="2026-08-19", end="2026-08-18").validate()
    with pytest.raises(ValueError, match="ISO-8601"):
        RegionalQuery(start="not-a-date").validate()
