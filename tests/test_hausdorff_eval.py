"""Smoke tests for perimeter Hausdorff evaluator."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_official_mode_blocked_without_reference(tmp_path: Path):
    # minimal two-ring geojson
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
                    ],
                },
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[1.0, 1.0], [11.0, 1.0], [11.0, 11.0], [1.0, 11.0], [1.0, 1.0]]
                    ],
                },
                "properties": {},
            },
        ],
    }
    obs = tmp_path / "obs.geojson"
    obs.write_text(json.dumps(gj), encoding="utf-8")
    out = tmp_path / "official.json"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_perimeter_hausdorff.py"),
            "--observed",
            str(obs),
            "--mode",
            "official",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["verdict"] == "BLOCKED_NO_OFFICIAL_PERIMETER"
    assert rep["o2_official"] is False


def test_temporal_mode_ok(tmp_path: Path):
    gj = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0], [0.0, 0.0]]
                    ],
                },
                "properties": {},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [[2.0, 2.0], [22.0, 2.0], [22.0, 22.0], [2.0, 22.0], [2.0, 2.0]]
                    ],
                },
                "properties": {},
            },
        ],
    }
    obs = tmp_path / "obs.geojson"
    obs.write_text(json.dumps(gj), encoding="utf-8")
    out = tmp_path / "temporal.json"
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval_perimeter_hausdorff.py"),
            "--observed",
            str(obs),
            "--mode",
            "temporal",
            "--sample-spacing-m",
            "2",
            "--output",
            str(out),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert r.returncode == 0, r.stderr
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["status"] == "OK_PROXY"
    assert "summary" in rep
    assert rep["summary"]["mean_hausdorff"] >= 0
