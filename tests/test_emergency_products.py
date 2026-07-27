"""Unit tests for emergency sector ROS and envelope (pure math)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from wildfire_front.emergency_products import (
    compute_sector_ros,
    compute_short_horizon_envelope,
    enrich_ops_dict,
    envelope_to_geojson,
    expansion_bearing_deg_from_centroids,
    ring_centroid,
)

ROOT = Path(__file__).resolve().parents[1]


def test_sector_ros_estimated():
    s = compute_sector_ros(5.71, 2.8, 6.9, expansion_bearing_deg=240.0, n_estimates=5)
    assert s["status"] in ("estimated", "estimated_low_n")
    assert s["sectors"]["primary_m_min"] == 5.71
    assert s["sectors"]["head_m_min"] >= s["sectors"]["flank_m_min"]
    assert s["sectors"]["flank_m_min"] >= s["sectors"]["rear_m_min"]
    assert s["uncertainty_m_min"]["p25"] is not None
    assert "despacho" in s["label_es"].lower() or "táctico" in s["label_es"].lower()


def test_sector_ros_abstained():
    s = compute_sector_ros(None)
    assert s["status"] == "abstained"
    assert s["sectors"] is None


def test_envelope_labels_not_dispatch():
    e = compute_short_horizon_envelope(5.71, quality_grade="A")
    assert e["status"] == "ok"
    assert len(e["envelopes"]) == 3
    assert e["envelopes"][0]["horizon_min"] == 15
    assert e["envelopes"][2]["horizon_min"] == 60
    assert e["envelopes"][0]["radius_m"] == round(5.71 * 15, 2)
    lab = (e["label_en"] + e["label_es"]).lower()
    assert "not" in lab or "no es" in lab
    assert "dispatch" in lab or "despacho" in lab


def test_envelope_sector_aware_radii():
    e = compute_short_horizon_envelope(
        5.71,
        head_ros_m_min=6.9,
        flank_ros_m_min=5.71,
        rear_ros_m_min=2.8,
        expansion_bearing_deg=204.0,
        quality_grade="A",
    )
    assert e["status"] == "ok"
    assert e.get("sector_aware") is True
    assert e["product"] == "short_horizon_envelope_v2_sector"
    h15 = e["envelopes"][0]
    assert h15["head_radius_m"] > h15["flank_radius_m"] >= h15["rear_radius_m"]
    assert h15["head_radius_m"] == round(6.9 * 15, 2)
    assert h15["rear_radius_m"] == round(2.8 * 15, 2)
    assert "head_bearing_deg" in h15


def test_envelope_abstained():
    e = compute_short_horizon_envelope(None)
    assert e["status"] == "abstained"


def test_bearing_and_centroid():
    c = ring_centroid([(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0), (0.0, 0.0)])
    assert abs(c[0] - 1.0) < 1e-6
    b = expansion_bearing_deg_from_centroids([(0.0, 0.0), (0.0, 10.0)])
    assert b is not None
    assert abs(b - 0.0) < 1.0  # north


def test_enrich_ops_dict():
    ops = {
        "speed_median_m_min": 5.71,
        "speed_p25_m_min": 2.8,
        "speed_p75_m_min": 6.9,
        "speed_n_observable": 5,
        "quality_grade": "A",
    }
    # Default path: cn_hybrid OFF — no invented wind / hybrid ROS
    out = enrich_ops_dict(ops, expansion_bearing_deg=90.0)
    assert "sector_ros" in out
    assert out["sector_ros"]["sectors"]["head_m_min"] > 0
    assert out["short_horizon_envelope"]["status"] == "ok"
    assert out["short_horizon_envelope"].get("sector_aware") is True
    assert "head_radius_m" in out["short_horizon_envelope"]["envelopes"][0]
    assert out["not_a_product"] == "validated_tactical_dispatch"
    assert "cn_hybrid_ros" not in out


def test_enrich_ops_dict_cn_hybrid_off_by_default_no_invented_wind():
    ops = {
        "speed_median_m_min": 5.71,
        "speed_p25_m_min": 2.8,
        "speed_p75_m_min": 6.9,
        "speed_n_observable": 5,
        "quality_grade": "A",
    }
    out = enrich_ops_dict(ops, expansion_bearing_deg=90.0)
    assert "cn_hybrid_ros" not in out
    # Explicit cn_hybrid without wind → inputs_assumed / abstained, no operational numeric ROS
    out2 = enrich_ops_dict(ops, expansion_bearing_deg=90.0, cn_hybrid=True)
    cn = out2.get("cn_hybrid_ros") or {}
    assert cn.get("status") in ("inputs_assumed", "abstained")
    assert "ros_head_m_min" not in cn
    assert cn.get("vp_tactical") is None


def test_enrich_ops_dict_cn_hybrid_with_explicit_wind():
    ops = {
        "speed_median_m_min": 5.71,
        "speed_p25_m_min": 2.8,
        "speed_p75_m_min": 6.9,
        "speed_n_observable": 5,
        "quality_grade": "A",
    }
    out = enrich_ops_dict(ops, expansion_bearing_deg=90.0, cn_hybrid=True, wind_from_deg=270.0)
    assert out["cn_hybrid_ros"]["status"] == "ok"
    assert out["cn_hybrid_ros"]["ros_head_m_min"] >= out["cn_hybrid_ros"]["ros_rear_m_min"]
    assert out["cn_hybrid_ros"]["scale_factor"] > 0
    assert out["cn_hybrid_ros"]["wind_from_deg"] == 270.0
    assert out["cn_hybrid_ros"].get("not_tactical") is True


def test_envelope_to_geojson_feature_collection():
    e = compute_short_horizon_envelope(
        5.71,
        head_ros_m_min=6.9,
        flank_ros_m_min=5.71,
        rear_ros_m_min=2.8,
        expansion_bearing_deg=204.0,
    )
    gj = envelope_to_geojson(
        e, center_xy=(500000.0, 4200000.0), fire_id="test", expansion_bearing_deg=204.0
    )
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) >= 3  # flank + head + rear for at least one horizon
    for feat in gj["features"]:
        props = feat["properties"]
        assert props.get("not_official_perimeter") is True
        assert props.get("not_tactical_dispatch") is True
        assert feat["geometry"]["type"] == "Polygon"
        ring = feat["geometry"]["coordinates"][0]
        assert len(ring) >= 4


def test_emergency_briefing_cli_multi_if():
    import pytest

    packs_root = ROOT / "outputs" / "observatorio"
    if not (packs_root / "tobarra_20240802" / "operational_metrics.json").is_file():
        pytest.skip("observatorio pack for tobarra_20240802 not built (optional artifact)")
    second = None
    for cand in ("cardoso_2025", "hellin_2024", "brazatortas_2025"):
        if (packs_root / cand / "operational_metrics.json").is_file():
            second = cand
            break
    fires = "tobarra_20240802" + (f",{second}" if second else "")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "emergency_briefing.py"),
            "--fires",
            fires,
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr + r.stdout
    paths = [Path(line.strip()) for line in r.stdout.strip().splitlines() if line.strip()]
    assert paths
    for path in paths:
        assert path.is_file()
        text = path.read_text(encoding="utf-8").lower()
        assert "ros" in text
        assert "head" in text and "flank" in text
        assert "15" in text and "60" in text
        assert "blocked" in text or "perimeter" in text or "perímetro" in text
        # GIS next to brief
        gis = path.parent / "emergency_envelope_guidance.geojson"
        assert gis.is_file(), f"missing GIS for {path.parent.name}"
        gj = json.loads(gis.read_text(encoding="utf-8"))
        assert gj["type"] == "FeatureCollection"
        assert len(gj["features"]) > 0
        assert gj["features"][0]["properties"].get("not_official_perimeter") is True


def test_hausdorff_official_blocked_and_synthetic(tmp_path: Path):
    # blocked without reference
    obs = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]],
                },
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[1, 1], [11, 1], [11, 11], [1, 11], [1, 1]]],
                },
                "properties": {},
            },
        ],
    }
    op = tmp_path / "obs.geojson"
    op.write_text(json.dumps(obs), encoding="utf-8")
    out_b = tmp_path / "blocked.json"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_perimeter_hausdorff.py"),
            "--observed",
            str(op),
            "--mode",
            "official",
            "--output",
            str(out_b),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0
    blocked = json.loads(out_b.read_text(encoding="utf-8"))
    assert blocked["verdict"] == "BLOCKED_NO_OFFICIAL_PERIMETER"

    ref = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.5, 0.5], [10.5, 0.5], [10.5, 10.5], [0.5, 10.5], [0.5, 0.5]]
                    ],
                },
                "properties": {},
            }
        ],
    }
    rp = tmp_path / "ref.geojson"
    rp.write_text(json.dumps(ref), encoding="utf-8")
    out_ok = tmp_path / "ok.json"
    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_perimeter_hausdorff.py"),
            "--observed",
            str(op),
            "--mode",
            "official",
            "--reference",
            str(rp),
            "--sample-spacing-m",
            "2",
            "--output",
            str(out_ok),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r2.returncode == 0, r2.stderr
    ok = json.loads(out_ok.read_text(encoding="utf-8"))
    assert ok.get("o2_official") is True
    assert "metrics_m" in ok
    assert ok["metrics_m"]["front_hausdorff"] >= 0
