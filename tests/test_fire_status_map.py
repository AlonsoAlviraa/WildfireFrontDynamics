"""Fire-status map: local layers + FIRMS client (fixture/offline) + real CLI entry."""

from __future__ import annotations

import json
from pathlib import Path

from wildfire_front.cli import build_parser, main
from wildfire_front.geo_crs import looks_projected_meters
from wildfire_front.map_status import (
    build_fire_status_map_payload,
    fetch_firms_hotspots,
    parse_firms_csv,
    write_fire_status_map,
)
from wildfire_front.map_status.firms_client import FIRMS_EUROPE_VIIRS_24H
from wildfire_front.map_status.payload import ensure_wgs84_geojson, load_local_geojson_layers

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_CSV = ROOT / "tests" / "fixtures" / "firms_sample_hotspots.csv"
LOCAL_FRONT = ROOT / "outputs" / "incidents" / "_sla_measure" / "outbox" / "main_front.geojson"
DEMO_FRONTS = ROOT / "outputs" / "demo_v2" / "fronts.geojson"


def _run_main(argv: list[str], capsys) -> tuple[int, str, str]:
    try:
        main(argv)
        code = 0
    except SystemExit as exc:
        raw = exc.code
        if raw is None:
            code = 0
        elif isinstance(raw, int):
            code = raw
        else:
            code = 1
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_parse_firms_csv_bbox_filter():
    text = FIXTURE_CSV.read_text(encoding="utf-8")
    all_feats = parse_firms_csv(text, bbox=None)
    assert len(all_feats) == 4
    clipped = parse_firms_csv(text, bbox=(-3.2, 40.9, -3.0, 41.05))
    assert len(clipped) == 3
    for f in clipped:
        assert f["properties"]["not_official_perimeter"] is True
        lon, lat = f["geometry"]["coordinates"]
        assert -3.2 <= lon <= -3.0
        assert 40.9 <= lat <= 41.05


def test_fetch_firms_fixture_and_offline():
    bbox = (-3.2, 40.9, -3.0, 41.05)
    live = fetch_firms_hotspots(bbox=bbox, fixture_csv=FIXTURE_CSV, allow_network=False)
    assert live["schema"] == "wfd_firms_fetch_v1"
    assert live["connectivity"] == "fixture"
    assert live["n_hotspots"] == 3
    assert live["honesty"]["not_burned_area"] is True
    assert live["honesty"]["not_tactical_dispatch"] is True

    offline = fetch_firms_hotspots(bbox=bbox, allow_network=False)
    assert offline["connectivity"] == "skipped"
    assert offline["n_hotspots"] == 0
    assert offline["features"] == []
    assert "allow_network_false" in offline["reasons"]


def test_build_payload_local_plus_fixture(tmp_path: Path):
    paths = []
    if LOCAL_FRONT.is_file():
        paths.append(LOCAL_FRONT)
    elif DEMO_FRONTS.is_file():
        paths.append(DEMO_FRONTS)
    else:
        # minimal synthetic local layer
        gj = tmp_path / "front.geojson"
        gj.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {"name": "test_front"},
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[-3.12, 40.94], [-3.08, 40.97]],
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        paths.append(gj)

    payload = build_fire_status_map_payload(
        geojson_paths=paths,
        bbox=(-3.2, 40.9, -3.0, 41.05),
        live=False,
        fixture_csv=FIXTURE_CSV,
        title="test map",
    )
    assert payload["schema"] == "wfd_fire_status_map_v1"
    assert payload["rails"]["field_ops_ml_live_fusion"] == "OFF"
    assert payload["rails"]["not_tactical_dispatch"] is True
    assert payload["rails"]["hotspots_not_burned_area"] is True
    assert payload["connectivity"]["status"] == "fixture"
    assert payload["firms"]["n_hotspots"] == 3
    assert any(L.get("source") == "local" for L in payload["layers"])
    assert any("firms" in str(L.get("id", "")).lower() for L in payload["layers"])
    assert "despacho" in payload["disclaimer"].lower() or "dispatch" in payload["disclaimer"].lower()

    out = write_fire_status_map(payload, tmp_path / "map_out")
    html = out["html"].read_text(encoding="utf-8")
    assert "leaflet" in html.lower()
    assert "wfd_fire_status_map_v1" in html or "FIRMS" in html
    assert "connectivity" in html
    assert "not_tactical" in html.lower() or "despacho" in html.lower() or "táctico" in html.lower() or "tactico" in html.lower()
    data = json.loads(out["json"].read_text(encoding="utf-8"))
    assert data["schema"] == "wfd_fire_status_map_v1"


def test_cli_map_fixture_offline(tmp_path: Path, capsys):
    """Real entrypoint: map writes HTML with local+fixture layers."""
    out = tmp_path / "cli_map"
    geo = DEMO_FRONTS if DEMO_FRONTS.is_file() else None
    argv = [
        "map",
        "--output",
        str(out),
        "--bbox=-3.2,40.9,-3.0,41.05",
        "--fixture-csv",
        str(FIXTURE_CSV),
        "--no-live",
    ]
    if geo is not None:
        argv.extend(["--geojson", str(geo)])
    elif LOCAL_FRONT.is_file():
        argv.extend(["--work-dir", str(LOCAL_FRONT.parents[1])])
    else:
        # ensure usage path still exercises fixture-only with bbox
        pass

    code, stdout, err = _run_main(argv, capsys)
    assert code == 0, f"stdout={stdout}\nerr={err}"
    html = out / "fire_status_map.html"
    js = out / "fire_status_map.json"
    assert html.is_file()
    assert js.is_file()
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["schema"] == "wfd_fire_status_map_v1"
    assert payload["firms"]["connectivity"] == "fixture"
    assert payload["rails"]["field_ops_ml_live_fusion"] == "OFF"
    assert payload["firms"]["n_hotspots"] >= 1
    text = html.read_text(encoding="utf-8")
    assert "L.map" in text or "leaflet" in text.lower()
    assert "OFF" in text or "fusion" in text.lower()
    low = (stdout + err).lower()
    assert "mapa" in low or "map" in low or "html" in low


def test_cli_map_json_and_missing_args(capsys):
    code, out, err = _run_main(["map"], capsys)
    assert code == 2
    blob = (out + err).lower()
    assert "bbox" in blob or "work-dir" in blob or "geojson" in blob

    out_dir = ROOT / "outputs" / "maps" / "_pytest_map_json"
    code2, out2, err2 = _run_main(
        [
            "map",
            "--json",
            "--output",
            str(out_dir),
            "--west",
            "-3.2",
            "--south",
            "40.9",
            "--east",
            "-3.0",
            "--north",
            "41.05",
            "--fixture-csv",
            str(FIXTURE_CSV),
            "--no-live",
        ],
        capsys,
    )
    assert code2 == 0, err2
    data = json.loads(out2)
    assert data["schema"] == "wfd_fire_status_map_v1"
    assert data["artifacts"]["html"]
    assert data["connectivity"]["status"] == "fixture"


def test_parser_registers_map():
    p = build_parser()
    args = p.parse_args(
        ["map", "--no-live", "--bbox=-4,39,-3,40", "--output", "x"]
    )
    assert args.command == "map"
    assert args.no_live is True
    assert args.bbox == "-4,39,-3,40"
    args2 = p.parse_args(
        ["map", "--west", "-4", "--south", "39", "--east", "-3", "--north", "40", "--no-live"]
    )
    assert args2.west == -4.0
    help_text = p.format_help().lower()
    assert "map" in help_text


def test_public_europe_url_documented():
    """Structural: public open CSV endpoint is the no-key connectivity path."""
    assert "firms.modaps.eosdis.nasa.gov" in FIRMS_EUROPE_VIIRS_24H
    assert "Europe" in FIRMS_EUROPE_VIIRS_24H or "europe" in FIRMS_EUROPE_VIIRS_24H.lower()


def _assert_geojson_wgs84(fc: dict) -> None:
    for f in fc.get("features") or []:
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords:
            continue
        # walk first leaf point
        node = coords
        while node and isinstance(node[0], (list, tuple)):
            node = node[0]
        lon, lat = float(node[0]), float(node[1])
        assert abs(lon) <= 180.0, f"lon out of range: {lon}"
        assert abs(lat) <= 90.0, f"lat out of range: {lat}"
        assert not looks_projected_meters(lon, lat)


def test_ensure_wgs84_reprojects_utm_outbox():
    """SLA outbox main_front is EPSG:32630 meters — must become lon/lat for Leaflet."""
    if not LOCAL_FRONT.is_file():
        # synthetic UTM feature collection
        fc = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "EPSG:32630"}},
            "features": [
                {
                    "type": "Feature",
                    "properties": {"crs": "EPSG:32630"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [500080.0, 4099920.0],
                                [500080.0, 4099880.0],
                                [500120.0, 4099880.0],
                                [500120.0, 4099920.0],
                                [500080.0, 4099920.0],
                            ]
                        ],
                    },
                }
            ],
        }
        wgs, meta = ensure_wgs84_geojson(fc)
    else:
        raw = json.loads(LOCAL_FRONT.read_text(encoding="utf-8"))
        wgs, meta = ensure_wgs84_geojson(raw)
    assert meta["reprojected"] is True
    assert meta["crs_output"] == "EPSG:4326"
    _assert_geojson_wgs84(wgs)
    # Spain-ish after UTM 30N
    pt = wgs["features"][0]["geometry"]["coordinates"][0][0]
    assert -10.0 < float(pt[0]) < 5.0
    assert 35.0 < float(pt[1]) < 44.0


def test_load_local_layers_reproject_work_dir():
    work = LOCAL_FRONT.parents[1] if LOCAL_FRONT.is_file() else None
    if work is None:
        return
    layers = load_local_geojson_layers(work_dir=work)
    assert layers
    for L in layers:
        if L.get("source") != "local":
            continue
        _assert_geojson_wgs84(L["geojson"])
        # main_front / fronts from SLA are projected on disk
        if "main_front" in str(L.get("name")) or L.get("name") == "fronts.geojson":
            assert (L.get("crs") or {}).get("reprojected") is True


def test_payload_bbox_center_are_geographic_after_reproject():
    work = LOCAL_FRONT.parents[1] if LOCAL_FRONT.is_file() else None
    if work is None:
        return
    payload = build_fire_status_map_payload(
        work_dir=work,
        live=False,
        fixture_csv=FIXTURE_CSV,
        # force bbox from layers (no explicit FIRMS box) when possible
    )
    # When fixture forces bbox from default Spain if layers geographic now
    lon = payload["center"]["lon"]
    lat = payload["center"]["lat"]
    assert abs(lon) <= 180 and abs(lat) <= 90
    assert not looks_projected_meters(lon, lat)
    bb = payload["bbox"]
    assert abs(bb["west"]) <= 180 and abs(bb["east"]) <= 180
    for L in payload["layers"]:
        if L.get("source") == "local":
            _assert_geojson_wgs84(L["geojson"])
    # span of geographic bbox must not look like half of Spain in meters
    span = abs(bb["east"] - bb["west"])
    assert span < 5.0, f"bbox span too large for local fire: {span}"
