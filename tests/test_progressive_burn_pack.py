"""Pack attach + optional gold Níjar progressive tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from shapely.geometry import mapping
from shapely.geometry import box

from wildfire_front.progressive_burn.pack_attach import attach_progressive_burn
from wildfire_front.progressive_burn.pipeline import ProgressiveBurnConfig
from wildfire_front.progressive_burn.schemas import ATTRIBUTION_REDIAM, PRODUCT_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "outputs" / "open_if" / "and_2024040053_20240606"
FIXTURE = ROOT / "tests" / "fixtures" / "rediam_and" / "sample_perim_3042.geojson"


def _mini_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "and_fixture_pack"
    pack.mkdir()
    (pack / "vectors").mkdir()
    # simple metric-like box published as WGS84-ish tiny polygon
    # Use a real-ish lon/lat box in Almería area
    from shapely.geometry import box as sbox

    poly = sbox(-2.15, 36.90, -2.05, 36.98)
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"CODIGO": "TEST001"},
                "geometry": mapping(poly),
            }
        ],
    }
    (pack / "vectors" / "perimeter_rediam.geojson").write_text(
        json.dumps(fc), encoding="utf-8"
    )
    (pack / "manifest.json").write_text(
        json.dumps(
            {
                "pack_id": "and_fixture_pack",
                "codigo": "TEST001",
                "vp_tactical": None,
                "scorecard_verdict": "GO_OPEN_AND_O2",
                "artifacts": {"perimeter": "vectors/perimeter_rediam.geojson"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (pack / "scorecard_and_industrial.json").write_text(
        json.dumps(
            {
                "verdict": "GO_OPEN_AND_O2",
                "vp_invented": False,
                "vp_tactical": None,
                "firms_hull_is_official_burned_area": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return pack


def test_pack_attach_fixture(tmp_path):
    pack = _mini_pack(tmp_path)
    cfg = ProgressiveBurnConfig(n_stages=5, schedule="linear", seed=0)
    result = attach_progressive_burn(pack, cfg, run_fd=True)
    assert result["verdict"] in ("GO_PROGRESSIVE_SYNTHETIC", "PARTIAL")
    assert (pack / "progressive" / "timeline_progressive.geojson").is_file()
    assert (pack / "progressive" / "metrics_progressive.json").is_file()
    assert (pack / "progressive" / "scorecard_progressive.json").is_file()
    assert (pack / "progressive" / "brief_progressive_addendum.md").is_file()

    man = json.loads((pack / "manifest.json").read_text(encoding="utf-8"))
    assert man["artifacts"]["progressive_timeline"].endswith("timeline_progressive.geojson")
    assert man["progressive_synthetic_burn"]["schema"] == PRODUCT_SCHEMA
    # Industrial fields untouched
    assert man.get("vp_tactical") is None
    assert man.get("scorecard_verdict") == "GO_OPEN_AND_O2"

    industrial = json.loads((pack / "scorecard_and_industrial.json").read_text(encoding="utf-8"))
    assert industrial["vp_invented"] is False
    assert industrial["verdict"] == "GO_OPEN_AND_O2"

    brief = (pack / "progressive" / "brief_progressive_addendum.md").read_text(encoding="utf-8")
    assert "sintético" in brief.lower() or "synthetic" in brief.lower()
    assert "REDIAM" in brief

    metrics = json.loads((pack / "progressive" / "metrics_progressive.json").read_text(encoding="utf-8"))
    assert metrics["vp_tactical"] is None
    assert metrics["gates"]["PSB_HONESTY"] == "PASS"
    assert metrics["gates"]["PSB_NO_FALSE_DISPATCH"] == "PASS"


def test_official_timeline_not_overwritten(tmp_path):
    pack = _mini_pack(tmp_path)
    # plant pure official timeline
    official = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"layer_role": "official_final", "synthetic": False},
                "geometry": mapping(box(-2.15, 36.90, -2.05, 36.98)),
            }
        ],
    }
    (pack / "timeline_perimeters.geojson").write_text(json.dumps(official), encoding="utf-8")
    attach_progressive_burn(pack, ProgressiveBurnConfig(n_stages=4), run_fd=False)
    tl = json.loads((pack / "timeline_perimeters.geojson").read_text(encoding="utf-8"))
    assert len(tl["features"]) == 1
    assert tl["features"][0]["properties"].get("synthetic") is False


@pytest.mark.skipif(not GOLD.is_dir(), reason="gold Níjar pack not present")
def test_gold_nijar_progressive(tmp_path):
    # Copy pack so pytest does not overwrite live progressive/ n_stages
    dest = tmp_path / "and_2024040053_20240606"
    shutil.copytree(
        GOLD,
        dest,
        ignore=shutil.ignore_patterns("progressive"),
    )
    cfg = ProgressiveBurnConfig(
        n_stages=8,
        engine="area_fraction",
        schedule="sqrt",
        seed=0,
        codigo="2024040053",
        attribution=ATTRIBUTION_REDIAM,
    )
    result = attach_progressive_burn(dest, cfg, run_fd=True)
    assert result["verdict"] in ("GO_PROGRESSIVE_SYNTHETIC", "PARTIAL")
    assert result["final_area_ha"] == pytest.approx(2169.34, rel=0.02)

    metrics = json.loads(
        (dest / "progressive" / "metrics_progressive.json").read_text(encoding="utf-8")
    )
    assert metrics["final_n_parts"] >= 2  # MultiPolygon gold
    assert metrics["gates"]["PSB_TERMINAL_IDENTITY"] == "PASS"
    assert metrics["gates"]["PSB_NESTED"] == "PASS"
    assert metrics["gates"]["PSB_HONESTY"] == "PASS"
    assert metrics["vp_tactical"] is None

    # Terminal feature geometry matches official pack perimeter (KD1 publish)
    tl = json.loads((dest / "progressive" / "timeline_progressive.geojson").read_text(encoding="utf-8"))
    official = json.loads((dest / "vectors" / "perimeter_rediam.geojson").read_text(encoding="utf-8"))
    term = tl["features"][-1]["geometry"]
    off = official["features"][0]["geometry"] if "features" in official else official["geometry"]
    assert term == off

    # Industrial scorecard independent
    if (dest / "scorecard_and_industrial.json").is_file():
        sc = json.loads((dest / "scorecard_and_industrial.json").read_text(encoding="utf-8"))
        assert sc.get("vp_invented") is not True
