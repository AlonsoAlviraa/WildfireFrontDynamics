"""E4 — GeoTIFF contract validate helper smoke."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "validate_geotiff_contract.py"
    spec = importlib.util.spec_from_file_location("validate_geotiff_contract", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validate_missing_file(tmp_path: Path):
    mod = _load()
    r = mod.validate_one(tmp_path / "nope.tif")
    assert r["status"] == "rejected"
    assert "file_not_found" in r["reasons"]


def test_validate_geotiff_with_crs(tmp_path: Path):
    rasterio = pytest.importorskip("rasterio")
    from affine import Affine
    from rasterio.crs import CRS

    mod = _load()
    path = tmp_path / "20240802_161507_scene.tif"
    data = np.zeros((8, 8), dtype=np.float32)
    data[2:5, 2:5] = 1.0
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=8,
        width=8,
        count=1,
        dtype="float32",
        crs=CRS.from_epsg(32630),
        transform=Affine(2.0, 0.0, 500000.0, 0.0, -2.0, 4300000.0),
    ) as ds:
        ds.write(data, 1)

    sidecar = {
        "platform": "helicopter_lwir",
        "provider_id": "test_provider",
        "timestamp_utc": "2024-08-02T16:15:07Z",
    }
    path.with_suffix(".json").write_text(json.dumps(sidecar), encoding="utf-8")

    r = mod.validate_one(path)
    assert r["status"] in {"accepted", "review"}
    assert r["resolution_m"] == pytest.approx(2.0)
    assert r["crs"]
    assert r["platform"] == "helicopter_lwir"
    assert r["provider_id"] == "test_provider"


def test_validate_no_crs_rejected(tmp_path: Path):
    rasterio = pytest.importorskip("rasterio")

    mod = _load()
    path = tmp_path / "20240802_161507_nogeo.tif"
    data = np.ones((4, 4), dtype=np.float32)
    # No CRS / identity georef → contract reject
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="float32",
    ) as ds:
        ds.write(data, 1)

    r = mod.validate_one(path)
    assert r["status"] == "rejected"
    assert "no_georeferencing" in r["reasons"]


def test_validate_geographic_crs_review(tmp_path: Path):
    rasterio = pytest.importorskip("rasterio")
    from affine import Affine
    from rasterio.crs import CRS

    mod = _load()
    path = tmp_path / "20240802_161507_wgs84.tif"
    data = np.ones((4, 4), dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="float32",
        crs=CRS.from_epsg(4326),
        transform=Affine(0.0001, 0.0, -3.0, 0.0, -0.0001, 40.0),
    ) as ds:
        ds.write(data, 1)

    r = mod.validate_one(path)
    assert r["status"] == "review"
    assert "crs_not_projected_metric_ros_abstain" in r["reasons"]
    assert r.get("coordinate_system") == "geographic"


def test_cli_exit_2_on_reject(tmp_path: Path):
    rasterio = pytest.importorskip("rasterio")

    path = tmp_path / "20240802_120000_bad.tif"
    data = np.ones((4, 4), dtype=np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=4,
        width=4,
        count=1,
        dtype="float32",
    ) as ds:
        ds.write(data, 1)

    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate_geotiff_contract.py"), str(path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
        check=False,
    )
    assert proc.returncode == 2
    assert "rejected" in proc.stdout
