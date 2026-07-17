"""Unit tests for Pista B open IF helpers (no network)."""

from __future__ import annotations

import math

from shapely.geometry import Polygon

# import module under test
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_open_if_pack", ROOT / "scripts" / "build_open_if_pack.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_area_ha_square_approx():
    # ~0.01 deg x 0.01 deg near equator ~ 1.23e6 m2 ~ 123 ha (rough)
    poly = Polygon(
        [
            (0.0, 0.0),
            (0.01, 0.0),
            (0.01, 0.01),
            (0.0, 0.01),
            (0.0, 0.0),
        ]
    )
    ha = mod._area_ha_wgs84(poly)
    assert 80 < ha < 200


def test_parse_product_kind():
    assert (
        mod._parse_product_kind(".../EMSR578_AOI01_DEL_MONIT01_r1_vector.zip")
        == "delineation_monitoring"
    )
    assert (
        mod._parse_product_kind(".../EMSR578_AOI01_DEL_PRODUCT_r1_vector.zip")
        == "delineation"
    )
    assert mod._parse_product_kind(".../EMSR578_AOI01_GRA_PRODUCT_r1_vector.zip") == "grading"


def test_geoms_from_fc():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    gs = mod._geoms_from_fc(fc)
    assert len(gs) == 1
    assert not gs[0].is_empty


def test_scorecard_exists_if_built():
    sc = ROOT / "outputs" / "open_if" / "emsr578" / "scorecard_pista_b.json"
    if not sc.is_file():
        return  # optional when pack not built in CI
    import json

    data = json.loads(sc.read_text(encoding="utf-8"))
    assert data["status"] == "GO_OPEN_DATA_PACK"
    assert data["lwir_heligraphics"] is False
    assert data["max_area_ha"] > 100
