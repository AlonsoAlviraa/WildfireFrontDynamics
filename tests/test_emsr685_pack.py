"""EMSR685 Tenerife additional pack: spec, rails, 898 observedEvent raster path."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import Polygon, mapping

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALLOWED_PACK_REGIONS,
    EMSR_PACK_SPECS,
    RAPID_BACKEND,
    cems_product_url_ok,
    dated_geotiff_ok,
    is_allowed_pack_path,
    pack_dir_for,
)
from wildfire_front.open_if.same_fire_model import rasterize_records  # noqa: E402


def _load(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_emsr685_spec_is_additional_not_official() -> None:
    more = _load("run_latam_au_more_data_iou.py")
    spec = EMSR_PACK_SPECS["ES_EMSR685_TENERIFE"]
    assert spec["activation"] == "EMSR685"
    assert spec["region"] == "es"
    assert spec["aoi"] == "AOI01"
    assert spec["class"] == "ml_weak"
    assert spec["crs_epsg"] == 32628
    kinds = [p["kind"] for p in spec["products"]]
    assert kinds.count("delineation") == 1
    assert kinds.count("delineation_monitoring") >= 2
    assert "ES_EMSR685_TENERIFE" not in more.OFFICIAL_LATAM_COMPLETE_PROXY_IDS
    assert "ES_EMSR685_TENERIFE" in more.DEFAULT_PACK_IDS
    assert spec["event_id"] not in more.OFFICIAL_LATAM_COMPLETE_PROXY_IDS
    for prod in spec["products"]:
        assert cems_product_url_ok(prod["url"])
        assert dated_geotiff_ok(prod["dated"])
        assert prod["url"].startswith(RAPID_BACKEND)
        assert prod["url"].endswith(".zip")


def test_es_region_is_allowlisted() -> None:
    assert "es" in ALLOWED_PACK_REGIONS
    pack = ROOT / "data" / "open_if" / "latam_au" / "es" / "ES_EMSR685_TENERIFE"
    assert is_allowed_pack_path(pack, repo_root=ROOT)
    spec = EMSR_PACK_SPECS["ES_EMSR685_TENERIFE"]
    assert pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec) == pack


def test_more_data_default_does_not_include_official_four() -> None:
    more = _load("run_latam_au_more_data_iou.py")
    assert "ES_EMSR685_TENERIFE" in more.DEFAULT_PACK_IDS
    assert "CL_EMSR715_VALPARAISO" not in more.DEFAULT_PACK_IDS


def test_matching_raw_observed_picks_smaller_json(tmp_path: Path) -> None:
    mod = _load("run_same_fire_multi_geometry.py")
    raw = tmp_path / "raw_cems"
    raw.mkdir()
    big = raw / "EMSR898_AOI01_DEL_MONIT03_observedEventA_v2.json"
    small = raw / "EMSR898_AOI01_DEL_MONIT03_observedEventA_v1.json"
    big.write_text("{" + ("a" * 200) + "}", encoding="utf-8")
    small.write_text("{}", encoding="utf-8")
    hit = mod.matching_raw_observed(raw, "AOI01", "delineation_monitoring", 3)
    assert hit == small


def test_rasterize_records_uses_observed_json_not_skip(tmp_path: Path) -> None:
    poly = Polygon([(-16.5, 28.3), (-16.4, 28.3), (-16.4, 28.4), (-16.5, 28.4), (-16.5, 28.3)])
    path = tmp_path / "EMSR898_AOI01_DEL_PRODUCT_observedEventA_v1.json"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"obj_type": "observedEventA"},
                        "geometry": mapping(poly),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    recs = [
        {
            "name": "EMSR898_AOI01_DEL_PRODUCT",
            "kind": "delineation",
            "geom": None,
            "path": str(path),
        }
    ]
    masks, meta = rasterize_records(recs, skip_bytes=None, ref_geom=poly)
    assert meta.get("ok") is True
    assert masks[0] is not None
    assert int(np.asarray(masks[0]).sum()) > 0


def test_observed_json_over_cap_is_skipped(tmp_path: Path) -> None:
    from wildfire_front.open_if.same_fire_model import MAX_OBSERVED_JSON_BYTES

    path = tmp_path / "EMSR898_AOI01_DEL_MONIT03_observedEventA_v2.json"
    path.write_bytes(b"{" + b"0" * (MAX_OBSERVED_JSON_BYTES + 10) + b"}")
    recs = [{"name": "monit03", "kind": "delineation_monitoring", "geom": None, "path": str(path)}]
    poly = Polygon([(-16.5, 28.3), (-16.4, 28.3), (-16.4, 28.4), (-16.5, 28.4), (-16.5, 28.3)])
    masks, meta = rasterize_records(recs, skip_bytes=None, ref_geom=poly)
    assert masks[0] is None
    assert recs[0].get("raster_skip") == "observed_json_too_large"
    assert meta.get("ok") is False


def test_same_fire_eval_does_not_pass_2mb_skip() -> None:
    src = (ROOT / "scripts" / "run_same_fire_multi_geometry.py").read_text(encoding="utf-8")
    assert "skip_bytes=None" in src
    assert "skip_bytes=2_000_000" not in src


def test_more_data_runner_refuses_to_overwrite_official(tmp_path: Path) -> None:
    official = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
    before = official.read_bytes() if official.is_file() else None
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_latam_au_more_data_iou.py"),
            "--pack",
            "ES_EMSR685_TENERIFE",
            "--data-root",
            str(tmp_path / "empty"),
            "--out-root",
            str(tmp_path / "out"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert p.returncode == 3, p.stdout + p.stderr
    if before is not None:
        assert official.read_bytes() == before
