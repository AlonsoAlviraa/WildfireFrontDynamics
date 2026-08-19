from __future__ import annotations

import json
from pathlib import Path

import pytest
from shapely.geometry import Polygon

from wildfire_front.open_if.firebench_caldor import materialize_caldor_label_pack, parse_caldor_kml


def _write_kml(path: Path, polygons: list[list[tuple[float, float]]]) -> None:
    parts = []
    for ring in polygons:
        coords = " ".join(f"{x},{y},0" for x, y in ring)
        parts.append(
            "<Placemark><MultiGeometry><Polygon><outerBoundaryIs><LinearRing>"
            f"<coordinates>{coords}</coordinates>"
            "</LinearRing></outerBoundaryIs></Polygon></MultiGeometry></Placemark>"
        )
    path.write_text(
        '<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
        + "".join(parts)
        + "</Document></kml>",
        encoding="utf-8",
    )


def test_parse_caldor_kml_unions_all_polygon_components(tmp_path: Path) -> None:
    path = tmp_path / "multi.kml"
    _write_kml(
        path,
        [
            [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)],
            [(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)],
        ],
    )
    parsed = parse_caldor_kml(path)
    assert parsed["n_polygon_elements"] == 2
    assert parsed["geometry_wgs84"].area == pytest.approx(2.0)


def test_materialize_keeps_raw_and_marks_cumulative_as_derived(tmp_path: Path) -> None:
    source = tmp_path / "source"
    kml = source / "kml"
    licenses = source / "DATA_LICENSES"
    kml.mkdir(parents=True)
    licenses.mkdir()
    (source / "LICENSE").write_text("dataset", encoding="utf-8")
    (source / "data_term_of_use.md").write_text("terms", encoding="utf-8")
    ring_a = [(-120.4, 38.6), (-120.39, 38.6), (-120.39, 38.61), (-120.4, 38.61), (-120.4, 38.6)]
    ring_b = [(-120.38, 38.6), (-120.37, 38.6), (-120.37, 38.61), (-120.38, 38.61), (-120.38, 38.6)]
    _write_kml(kml / "Caldor_2021_08_17T20_20_07_00.kml", [ring_a])
    _write_kml(kml / "Caldor_2021_08_18T20_20_07_00.kml", [ring_b])
    _write_kml(kml / "Caldor_perimeter_mtbs.kml", [ring_a, ring_b])

    out = tmp_path / "out"
    meta = materialize_caldor_label_pack(source, out, gsd_m=100.0, max_dim=128)

    assert meta["n_observations"] == 2
    assert meta["n_pairs_12_to_36h"] == 1
    assert meta["cumulative_masks_are_derived"] is True
    assert meta["rights"]["training_allowed"] is False
    assert meta["observations"][1]["cumulative_area_ha"] > meta["observations"][1]["raw_area_ha"]
    assert (out / meta["observations"][0]["raw_mask"]).is_file()
    assert "20210818T032000Z" in meta["observations"][0]["raw_mask"]
    assert (out / meta["observations"][1]["cumulative_mask"]).is_file()
    pairs = json.loads((out / "pairs.json").read_text(encoding="utf-8"))
    assert pairs["pairs"][0]["recommended_target"] == "cumulative_mask"
    assert meta["mtbs_final_reference"]["excluded_from_temporal_pairs"] is True


def test_polygon_helper_fixture_is_valid() -> None:
    assert Polygon([(0, 0), (1, 0), (1, 1), (0, 0)]).is_valid
