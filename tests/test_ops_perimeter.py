"""Tests for operational KMZ/KML perimeter parser (Pablo/GEACAM Tobarra drop)."""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DROP = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
KMZ_1830 = DROP / "2024020124_TOBARRA_20240802_1830.kmz"
KMZ_2143 = DROP / "2024020124_TOBARRA_20240802_2143.kmz"
KML_1830 = DROP / "2024020124_TOBARRA_20240802_1830.kml"
MAIN_FRONT = ROOT / "outputs" / "observatorio" / "tobarra_20240802" / "main_front.geojson"

# Real-file tests skip when drop absent
real_drop = pytest.mark.skipif(
    not KMZ_1830.is_file(),
    reason="Pablo Tobarra KMZ drop not present under data/real_if/",
)


# ---------------------------------------------------------------------------
# Unit helpers (no real drop required)
# ---------------------------------------------------------------------------


def test_parse_spanish_float_variants():
    from wildfire_front.ops_perimeter import parse_spanish_float

    assert parse_spanish_float("21,489832") == pytest.approx(21.489832)
    assert parse_spanish_float("37.075054") == pytest.approx(37.075054)
    assert parse_spanish_float("1.234,56") == pytest.approx(1234.56)
    assert parse_spanish_float("1,234.56") == pytest.approx(1234.56)
    assert parse_spanish_float("42") == pytest.approx(42.0)
    assert parse_spanish_float("<Nulo>") is None
    assert parse_spanish_float("&lt;Nulo&gt;") is None
    assert parse_spanish_float("") is None


def test_time_from_filename_and_unparsed():
    from wildfire_front.ops_perimeter import time_from_filename

    t, src = time_from_filename("2024020124_TOBARRA_20240802_1830.kmz")
    assert t == "2024-08-02T18:30:00"
    assert "filename" in src
    t2, src2 = time_from_filename("no_time_here.kmz")
    assert t2 is None
    assert src2 == "unparsed"


def test_kmz_without_kml_raises(tmp_path: Path):
    from wildfire_front.ops_perimeter import extract_kml_bytes

    kmz = tmp_path / "empty.kmz"
    with zipfile.ZipFile(kmz, "w") as zf:
        zf.writestr("readme.txt", "no kml here")
    with pytest.raises(ValueError, match="no .kml"):
        extract_kml_bytes(kmz)


def test_latlonquad_only_parses_as_polygon(tmp_path: Path):
    """4-corner ring is accepted when it is the only geometry (footprint-like)."""
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    kml = tmp_path / "quad.kml"
    kml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <Placemark><name>footprint</name>
        <Polygon><outerBoundaryIs><LinearRing>
        <coordinates>
        -1.70,38.63,0 -1.69,38.63,0 -1.69,38.64,0 -1.70,38.64,0 -1.70,38.63,0
        </coordinates>
        </LinearRing></outerBoundaryIs></Polygon>
        </Placemark></Document></kml>
        """,
        encoding="utf-8",
    )
    p = parse_ops_perimeter(kml, root=tmp_path)
    assert p.sup_ha is None
    assert p.n_vertices >= 4
    assert p.time_local_inferred is None


def test_missing_sup_ha_nulo(tmp_path: Path):
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    kml = tmp_path / "nulo_20240802_1200.kml"
    kml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <Placemark><name>Perímetro activo</name>
        <description><![CDATA[
        <table><tr><td>Sup_ha</td><td>&lt;Nulo&gt;</td></tr></table>
        ]]></description>
        <Polygon><outerBoundaryIs><LinearRing>
        <coordinates>
        -1.71,38.63,0 -1.70,38.63,0 -1.70,38.64,0 -1.71,38.64,0 -1.71,38.63,0
        </coordinates>
        </LinearRing></outerBoundaryIs></Polygon>
        </Placemark></Document></kml>
        """,
        encoding="utf-8",
    )
    p = parse_ops_perimeter(kml, root=tmp_path)
    assert p.sup_ha is None
    assert "null" in p.sup_ha_source or p.sup_ha_source == "missing"
    assert p.time_local_inferred == "2024-08-02T12:00:00"


def test_integer_sup_ha_html(tmp_path: Path):
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    kml = tmp_path / "int_20240802_1300.kml"
    kml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <Placemark><name>Perímetro activo</name>
        <description><![CDATA[
        <table><tr><td>Sup_ha</td><td>42</td></tr></table>
        ]]></description>
        <Polygon><outerBoundaryIs><LinearRing>
        <coordinates>
        -1.71,38.63,0 -1.70,38.63,0 -1.70,38.64,0 -1.71,38.64,0 -1.71,38.63,0
        </coordinates>
        </LinearRing></outerBoundaryIs></Polygon>
        </Placemark></Document></kml>
        """,
        encoding="utf-8",
    )
    p = parse_ops_perimeter(kml, root=tmp_path)
    assert p.sup_ha == pytest.approx(42.0)


def test_metric_crs_requires_pyproj_no_silent_fallback():
    from wildfire_front.ops_perimeter import MetricCrsError, pyproj_available, wgs84_to_utm30n

    if not pyproj_available():
        with pytest.raises(MetricCrsError, match="pyproj"):
            wgs84_to_utm30n(-1.7, 38.63)
    else:
        x, y = wgs84_to_utm30n(-1.7, 38.63)
        # True UTM30N for Tobarra region
        assert 500_000 < x < 700_000
        assert 4_000_000 < y < 4_500_000


def test_geojson_no_top_level_crs(tmp_path: Path):
    from wildfire_front.ops_perimeter import parse_ops_perimeter, to_geojson_collection

    kml = tmp_path / "g_20240802_1400.kml"
    kml.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2"><Document>
        <Placemark><name>Perímetro activo</name>
        <description><![CDATA[<td>Sup_ha</td><td>10,5</td>]]></description>
        <Polygon><outerBoundaryIs><LinearRing>
        <coordinates>
        -1.71,38.63,0 -1.70,38.63,0 -1.70,38.64,0 -1.71,38.64,0 -1.71,38.63,0
        </coordinates>
        </LinearRing></outerBoundaryIs></Polygon>
        </Placemark></Document></kml>
        """,
        encoding="utf-8",
    )
    p = parse_ops_perimeter(kml, root=tmp_path)
    fc = to_geojson_collection([p])
    assert "crs" not in fc
    assert "properties" not in fc  # no nonstandard top-level properties
    assert fc["features"][0]["properties"]["crs"] == "EPSG:4326"
    lon, lat = fc["features"][0]["geometry"]["coordinates"][0][0][:2]
    assert lon < 0  # lon first (RFC 7946)


def test_repo_relative_path():
    from wildfire_front.ops_perimeter import repo_relative_path

    p = ROOT / "data" / "real_if" / "x.kmz"
    rel = repo_relative_path(p, root=ROOT)
    assert rel.startswith("data/")
    assert ":" not in rel or rel.count(":") == 0  # no drive letter


# ---------------------------------------------------------------------------
# Real-drop integration
# ---------------------------------------------------------------------------


@real_drop
def test_parse_kmz_1830_sup_ha_and_polygon():
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    p = parse_ops_perimeter(KMZ_1830, root=ROOT)
    assert p.sup_ha == pytest.approx(21.489832, abs=1e-5)
    assert p.sup_ha_source.startswith("description")
    assert p.time_local_inferred == "2024-08-02T18:30:00"
    assert p.n_vertices == 34
    assert len(p.coords_wgs84) >= 34
    assert p.coords_wgs84[0] == p.coords_wgs84[-1]
    lon, lat = p.coords_wgs84[0]
    assert -1.72 < lon < -1.69
    assert 38.62 < lat < 38.65
    assert "Perímetro" in p.name or "perimetro" in p.name.lower()
    # portable provenance
    assert p.source_path.startswith("data/")


@real_drop
def test_parse_kmz_2143_sup_ha():
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    p = parse_ops_perimeter(KMZ_2143, root=ROOT)
    assert p.sup_ha == pytest.approx(37.075054, abs=1e-5)
    assert p.time_local_inferred == "2024-08-02T21:43:00"
    assert p.n_vertices == 50


@real_drop
def test_kml_matches_kmz():
    from wildfire_front.ops_perimeter import parse_ops_perimeter

    a = parse_ops_perimeter(KMZ_1830, root=ROOT)
    b = parse_ops_perimeter(KML_1830, root=ROOT)
    assert a.sup_ha == b.sup_ha
    assert a.n_vertices == b.n_vertices
    assert len(a.coords_wgs84) == len(b.coords_wgs84)


@real_drop
def test_geom_area_near_sup_ha():
    pytest.importorskip("pyproj")
    from wildfire_front.ops_perimeter import area_ha_from_ring_wgs84, parse_ops_perimeter

    p = parse_ops_perimeter(KMZ_1830, root=ROOT)
    geom_ha = area_ha_from_ring_wgs84(p.coords_wgs84)
    assert p.sup_ha is not None
    # pyproj UTM should match attribute to sub-0.001 ha on this product
    assert abs(geom_ha - p.sup_ha) < 1e-3


@real_drop
def test_area_growth_summary():
    from wildfire_front.ops_perimeter import area_growth_summary, parse_ops_perimeter

    perims = [
        parse_ops_perimeter(KMZ_1830, root=ROOT),
        parse_ops_perimeter(KMZ_2143, root=ROOT),
    ]
    g = area_growth_summary(perims)
    assert g["status"] == "ok"
    assert g["delta_ha"] == pytest.approx(15.585222, abs=1e-4)
    assert g["delta_minutes"] == pytest.approx(193.0, abs=0.1)
    assert g["mean_ha_per_hour"] == pytest.approx(4.84, abs=0.05)


@real_drop
def test_geojson_export(tmp_path: Path):
    from wildfire_front.ops_perimeter import parse_ops_perimeter, write_geojson

    p = parse_ops_perimeter(KMZ_1830, root=ROOT)
    out = tmp_path / "p.geojson"
    write_geojson([p], out)
    fc = json.loads(out.read_text(encoding="utf-8"))
    assert fc["type"] == "FeatureCollection"
    assert "crs" not in fc
    assert len(fc["features"]) == 1
    assert fc["features"][0]["properties"]["sup_ha"] == pytest.approx(21.489832)


@real_drop
def test_eval_script_smoke_no_main_front(tmp_path: Path):
    out = tmp_path / "report.json"
    gj = tmp_path / "gj"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_tobarra_pablo_perimeters.py"),
            "--drop-dir",
            str(DROP),
            "--output",
            str(out),
            "--geojson-dir",
            str(gj),
            "--export-geojson",
            "--no-main-front",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["verdict"] == "PARTIAL_O2_TOBARRA_OPS_PROXY"
    assert rep["o2_status"]["national_cadastre_official"] == "BLOCKED"
    assert rep["o2_status"]["tobarra_ops_proxy"] == "PARTIAL_GO"
    assert len(rep["perimeters"]) == 2
    assert rep["area_growth"]["status"] == "ok"
    assert all(c["match"] for c in rep["sup_ha_inventory_checks"] if c["match"] is not None)
    # repo-relative source paths
    assert rep["source_drop"].startswith("data/")
    assert rep["perimeters"][0]["source_path"].startswith("data/")
    joined = " ".join(rep["disclaimers"]).lower()
    assert "cadastre" in joined or "catastr" in joined
    assert "vp" in joined
    # GeoJSON not forced into drop
    assert (gj / "tobarra_ops_perimeters.geojson").is_file()


@real_drop
@pytest.mark.skipif(not MAIN_FRONT.is_file(), reason="Tobarra main_front pack missing")
def test_eval_script_with_main_front(tmp_path: Path):
    pytest.importorskip("pyproj")
    out = tmp_path / "report_mf.json"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_tobarra_pablo_perimeters.py"),
            "--drop-dir",
            str(DROP),
            "--main-front",
            str(MAIN_FRONT),
            "--output",
            str(out),
            "--no-export-geojson",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    rep = json.loads(out.read_text(encoding="utf-8"))
    mf = rep["vs_reconstructed_main_front"]
    assert mf["o2_official"] is False
    assert mf["status"] in {
        "OK_PROXY_TEMPORAL_MISMATCH",
        "OK_PROXY_MIXED_TEMPORAL",
        "DEGRADED",
    }
    assert "clock_model" in mf or "clock_model" in rep
    if mf["status"] != "DEGRADED":
        assert mf.get("comparisons")
        for c in mf["comparisons"]:
            h = c["vs_largest_main_front"]["metrics_m"]["front_hausdorff"]
            assert h == h  # finite
            assert h < 1e5  # sanity: not CRS-poisoned
            assert "time_alignment" in c
            assert c["time_alignment"]["status"] in {
                "TEMPORAL_MISMATCH",
                "POSSIBLE_OVERLAP_WALLCLOCK",
                "POSSIBLE_OVERLAP_ONLY_IF_MF_Z_IS_UTC",
                "unparsed_time",
            }
        # largest frame ring and props come from same selection
        for c in mf["comparisons"]:
            assert c["vs_largest_main_front"]["selection"] == "max_geometric_ring_area_utm"


@real_drop
def test_sup_ha_checks_keyed_by_basename_not_order():
    """Single reverse-order file still matches inventory by basename."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "eval_tobarra", ROOT / "scripts" / "eval_tobarra_pablo_perimeters.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rep = mod.build_report(
        DROP,
        ["2024020124_TOBARRA_20240802_2143.kmz"],  # only second file
        None,
        5.0,
        export_geojson=False,
    )
    assert len(rep["sup_ha_inventory_checks"]) == 1
    c = rep["sup_ha_inventory_checks"][0]
    assert c["sup_ha_expected_inventory"] == pytest.approx(37.075054)
    assert c["match"] is True
