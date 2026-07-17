"""dNBR math + pack helpers (offline). Live STAC optional."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wildfire_front.open_if.dnbr import (
    classify_dnbr,
    compute_dnbr,
    compute_nbr,
    severity_fractions,
)
from wildfire_front.open_if.stac_s2 import (
    bbox_from_featurecollection,
    default_date_windows,
    item_summary,
    pick_asset_href,
)


def test_nbr_healthy_vs_burned():
    # healthy: high NIR, low SWIR → high NBR
    nir_h = np.array([[0.4, 0.45]], dtype=np.float32)
    swir_h = np.array([[0.1, 0.12]], dtype=np.float32)
    nbr_h = compute_nbr(nir_h, swir_h)
    assert np.all(nbr_h > 0.4)

    # burned-like: lower NIR, higher SWIR → lower NBR
    nir_b = np.array([[0.15, 0.12]], dtype=np.float32)
    swir_b = np.array([[0.25, 0.28]], dtype=np.float32)
    nbr_b = compute_nbr(nir_b, swir_b)
    assert np.all(nbr_b < nbr_h)


def test_dnbr_positive_when_post_lower():
    pre = np.array([[0.5, 0.6]], dtype=np.float32)
    post = np.array([[0.1, 0.2]], dtype=np.float32)
    d = compute_dnbr(pre, post)
    assert float(d[0, 0]) == np.float32(0.4)
    assert np.all(d > 0)


def test_severity_fractions_bins():
    d = np.array([-0.05, 0.15, 0.35, 0.55, 0.8, np.nan], dtype=np.float32)
    fr = severity_fractions(d)
    assert fr["n_valid"] == 5
    assert fr["fractions"]["unburned"] == 0.2
    assert fr["fractions"]["high"] == 0.2
    assert fr["burned_frac_ge_0.1"] == 0.8
    cls = classify_dnbr(d)
    assert cls[0] == 0 and cls[4] == 4 and cls[5] == -1


def test_bbox_from_fc():
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0.0, 0.0], [1.0, 0.0], [1.0, 2.0], [0.0, 2.0], [0.0, 0.0]]],
                },
            }
        ],
    }
    b = bbox_from_featurecollection(fc)
    assert b == (0.0, 0.0, 1.0, 2.0)


def test_default_date_windows_ordered():
    pre, post = default_date_windows(event_date="2022-07-15")
    assert "2022" in pre and "2022" in post
    # pre ends before post starts (string ISO still comparable for same year)
    assert pre.split("/")[1] < post.split("/")[0] or "2022-07" in pre


def test_pick_asset_href():
    item = {
        "id": "x",
        "assets": {
            "nir": {"href": "https://example.com/nir.tif"},
            "swir22": {"href": "https://example.com/swir.tif"},
        },
        "properties": {"eo:cloud_cover": 5, "datetime": "2022-01-01T00:00:00Z"},
    }
    assert pick_asset_href(item, ("nir",)).endswith("nir.tif")
    s = item_summary(item)
    assert s["nir_href"] and s["swir_href"]


def test_build_script_blocked_without_timeline(tmp_path: Path):
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "build_open_if_dnbr", root / "scripts" / "build_open_if_dnbr.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    pack = tmp_path / "emsr_test"
    pack.mkdir()
    status = mod.run_for_pack(pack)
    assert status["status"] == "BLOCKED"
    assert (pack / "dnbr_status.json").is_file()
    assert (pack / "dnbr_layer.md").is_file()
    doc = json.loads((pack / "dnbr_status.json").read_text(encoding="utf-8"))
    assert "missing_timeline" in " ".join(doc.get("reasons") or [])
