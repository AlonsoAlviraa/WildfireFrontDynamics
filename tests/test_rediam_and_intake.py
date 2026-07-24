"""REDIAM Andalucía intake tests — schema, CRS, area (no live WFS by default)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "rediam_and" / "sample_perim_3042.geojson"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fixture_exists_and_schema():
    assert FIXTURE.is_file()
    fc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    feats = fc["features"]
    assert len(feats) >= 3
    required = {"CODIGO", "FECHA_INC", "Municipio", "Provincia"}
    for f in feats:
        props = f["properties"]
        assert required <= set(props.keys())
        assert f.get("geometry") is not None
        g = shape(f["geometry"])
        assert not g.is_empty
        assert g.area > 0


def test_crs_transform_and_area_positive():
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    fc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    f = fc["features"][0]
    f["_source_year"] = 2024
    f["_source_path"] = str(FIXTURE)
    f["_feature_index"] = 0
    row = inv.feature_row(f)
    assert row["qa_geometry"] in {"ok", "repaired", "assumed_epsg3042_sanity"} or (
        "assumed_epsg3042_sanity" in str(row["qa_geometry"])
    )
    assert float(row["ha_geom"]) > 10
    assert float(row["ha_best"]) > 10
    assert row["fecha_inc"] == "2024-07-15"
    assert row["codigo"] == "TEST2024070001"
    # centroid should land near Andalucía after 3042→4326
    assert row["centroid_lon"] != ""
    lon = float(row["centroid_lon"])
    lat = float(row["centroid_lat"])
    assert -8.0 < lon < -1.0
    assert 35.5 < lat < 39.0


def test_parse_fecha_and_score():
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    assert inv.parse_fecha_inc("20240715") == "2024-07-15"
    assert inv.parse_fecha_inc("2024-07-15") == "2024-07-15"
    assert inv.parse_fecha_inc(None) is None
    assert inv.score_firms_bonus(25)[0] == 25
    assert inv.score_firms_bonus(0)[0] == 0


def test_inventory_from_fixture_cache(tmp_path: Path):
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    # Stage cache layout year/perim_incendios_YYYY.geojson
    cache = tmp_path / "wfs_cache"
    year_dir = cache / "2024"
    year_dir.mkdir(parents=True)
    (year_dir / "perim_incendios_2024.geojson").write_text(
        FIXTURE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    out = tmp_path / "inventory"
    result = inv.build_inventory(cache, out, years=[2024], probe_firms=False, firms_top_n=5)
    assert result["stats"]["n_events"] == 3
    assert (out / "event_catalog.csv").is_file()
    assert (out / "selection_gold.json").is_file()
    sel = json.loads((out / "selection_gold.json").read_text(encoding="utf-8"))
    assert len(sel["gold"]) >= 1
    assert "REDIAM" in sel["attribution"]
    # largest should be preferred for gold
    gold = sel["gold"][0]
    assert float(gold["ha_best"]) > 100


def test_fetch_url_builder():
    fetch = _load("fetch_rediam_perimeters", ROOT / "scripts" / "fetch_rediam_perimeters.py")
    url = fetch.build_wfs_url(2024, count=3)
    assert "TYPENAMES=ms%3Aperim_incendios_2024" in url or "perim_incendios_2024" in url
    assert "GetFeature" in url
    assert "COUNT=3" in url


def test_smoke_count_does_not_use_full_year_path(tmp_path: Path):
    fetch = _load("fetch_rediam_perimeters", ROOT / "scripts" / "fetch_rediam_perimeters.py")
    dest, meta, is_smoke = fetch._dest_paths(tmp_path, 2024, count=3)
    assert is_smoke is True
    assert dest.parent.name == "2024"
    assert dest.parent.parent.name == "_smoke"
    assert "count3" in dest.name
    full_dest, _, is_smoke2 = fetch._dest_paths(tmp_path, 2024, count=None)
    assert is_smoke2 is False
    assert full_dest.name == "perim_incendios_2024.geojson"
    assert full_dest.parent.name == "2024"
    assert full_dest.parent.parent == tmp_path  # not under _smoke


def test_inventory_missing_crs_projected_outside_sanity(tmp_path: Path):
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    # Projected coords far outside REDIAM UTM30N box, no CRS member
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "CODIGO": "X1",
                    "FECHA_INC": "20240101",
                    "Municipio": "X",
                    "Provincia": "Y",
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [2_000_000, 100_000],
                            [2_001_000, 100_000],
                            [2_001_000, 101_000],
                            [2_000_000, 101_000],
                            [2_000_000, 100_000],
                        ]
                    ],
                },
            }
        ],
    }
    f = fc["features"][0]
    f["_source_year"] = 2024
    f["_source_path"] = "x"
    f["_feature_index"] = 0
    f["_source_crs"] = None  # parse returned None
    row = inv.feature_row(f)
    assert "missing_crs_projected" in row["qa_geometry"]
    assert row["and_bbox_ok"] is False or row["centroid_lon"] == ""


def test_inventory_assumed_3042_when_in_sanity_box():
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    # Fixture-like coords in AND UTM range, no CRS
    fc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    # strip any crs if present
    fc.pop("crs", None)
    if isinstance(fc.get("properties"), dict):
        fc["properties"].pop("crs_native", None)
    f = dict(fc["features"][0])
    f["_source_year"] = 2024
    f["_source_path"] = str(FIXTURE)
    f["_feature_index"] = 0
    f["_source_crs"] = None
    row = inv.feature_row(f)
    assert "assumed_epsg3042_sanity" in row["qa_geometry"] or row["qa_geometry"] in {
        "ok",
        "repaired",
    }
    assert float(row["ha_best"]) > 10


def test_selection_no_junk_fallback():
    inv = _load("inventory_rediam_and", ROOT / "scripts" / "inventory_rediam_and.py")
    bad_rows = [
        {
            "codigo": "BAD1",
            "year": 2024,
            "fecha_inc": "",
            "municipio": "",
            "provincia": "",
            "ha_best": 0,
            "score_total": 99,
            "score_reasons": "",
            "centroid_lon": "",
            "centroid_lat": "",
            "bbox_wgs84": "",
            "source_path": "x",
            "feature_index": 0,
            "firms_n": "",
            "qa_geometry": "empty",
            "and_bbox_ok": False,
        }
    ]
    sel = inv.select_tiers(bad_rows)
    assert sel["gold"] == []
    assert sel["silver"] == []
    assert sel.get("selection_error")


def test_live_wfs_optional():
    """Optional live WFS — skipped unless RUN_LIVE=1."""
    import os

    if os.environ.get("RUN_LIVE") != "1":
        pytest.skip("set RUN_LIVE=1 for live WFS")
    fetch = _load("fetch_rediam_perimeters", ROOT / "scripts" / "fetch_rediam_perimeters.py")
    out = ROOT / "data" / "open_if" / "rediam_andalucia" / "wfs_cache"
    r = fetch.fetch_year(2024, out, count=2, force=True, timeout=90)
    assert r.get("ok"), r
    assert int(r.get("n_features") or 0) >= 1
