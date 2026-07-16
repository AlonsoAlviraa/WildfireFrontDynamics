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
    out = enrich_ops_dict(ops, expansion_bearing_deg=90.0)
    assert "sector_ros" in out
    assert out["sector_ros"]["sectors"]["head_m_min"] > 0
    assert out["short_horizon_envelope"]["status"] == "ok"
    assert out["short_horizon_envelope"].get("sector_aware") is True
    assert "head_radius_m" in out["short_horizon_envelope"]["envelopes"][0]
    assert out["not_a_product"] == "validated_tactical_dispatch"


def test_emergency_briefing_cli_tobarra():
    pack = ROOT / "outputs" / "observatorio" / "tobarra_20240802"
    if not (pack / "operational_metrics.json").is_file():
        return  # skip if pack not present in environment
    out = pack / "emergency_briefing.md"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "emergency_briefing.py"),
            "--fire",
            "tobarra_20240802",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    path = Path(r.stdout.strip().splitlines()[-1])
    assert path.is_file()
    text = path.read_text(encoding="utf-8").lower()
    assert "grade" in text or "grado" in text or "quality" in text
    assert "ros" in text
    assert "head" in text and "flank" in text
    assert "15" in text and "60" in text
    assert "blocked" in text or "perimeter" in text or "perímetro" in text


def test_hausdorff_official_blocked_and_synthetic(tmp_path: Path):
    # blocked without reference
    obs = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
                    ],
                },
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[1, 1], [11, 1], [11, 11], [1, 11], [1, 1]]
                    ],
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
