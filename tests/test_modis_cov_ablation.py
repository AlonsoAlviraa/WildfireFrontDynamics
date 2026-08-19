"""MODIS covariate ablation rails: knobs, exits, no official JSON, no invented IoU."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import classify_temporal_pair  # noqa: E402

OPTIONAL_LST_NOTE = "modis_lst_as_temp is a contract change (LST ≠ Open-Meteo t2m)"


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_ablation_frozen_knobs_match_complete_proxy() -> None:
    abl = _load_script("run_modis_cov_ablation.py")
    complete = _load_script("run_latam_au_complete_model_iou.py")
    assert abl.OOD_GROWTH_THRESHOLD == 0.90
    assert abl.GROWTH_RING_CONNECTIVITY == 8
    assert abl.GROWTH_RING_MIN_NEIGHBORS == 1
    assert abl.OOD_GROWTH_THRESHOLD == complete.OOD_GROWTH_THRESHOLD
    assert abl.GROWTH_RING_CONNECTIVITY == complete.GROWTH_RING_CONNECTIVITY
    assert abl.GROWTH_RING_MIN_NEIGHBORS == complete.GROWTH_RING_MIN_NEIGHBORS
    ring = abl.fire_growth_ring(np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]))
    assert int(ring.sum()) == 8
    parser = abl.build_parser()
    flags = {opt for action in parser._actions for opt in action.option_strings}
    assert "--growth-thr" not in flags
    assert "--no-growth-ring" not in flags
    assert classify_temporal_pair(
        delta_hours=44.8,
        label_mask_iou=0.56,
        prev_kind="first_estimate",
        next_kind="delineation",
    ) == "incompatible_product_kind"
    assert classify_temporal_pair(
        delta_hours=6.0,
        label_mask_iou=0.4,
        prev_kind="delineation",
        next_kind="delineation_monitoring",
    ) == "too_short_delta"
    assert classify_temporal_pair(
        delta_hours=24.0,
        label_mask_iou=0.99,
        prev_kind="delineation",
        next_kind="delineation_monitoring",
    ) == "static_label_copy"


def test_ablation_default_out_is_not_official() -> None:
    abl = _load_script("run_modis_cov_ablation.py")
    assert abl.DEFAULT_OUT.name == "modis_cov_ablation"
    assert abl.OFFICIAL_JSON.name == "complete_proxy_model_iou.json"
    assert abl.DEFAULT_OUT.resolve() != abl.OFFICIAL_JSON.resolve()
    assert abl.DEFAULT_OUT.resolve() != abl.OFFICIAL_JSON.parent.resolve()
    assert abl.is_forbidden_out_root(abl.OFFICIAL_JSON.parent) is True
    assert abl.is_forbidden_out_root(abl.OFFICIAL_JSON) is True
    assert abl.is_forbidden_out_root(abl.PRODUCT_WEIGHTS.parent) is True
    assert abl.is_forbidden_out_root(abl.DEFAULT_OUT) is False


def test_ablation_refuses_official_out_root(tmp_path: Path) -> None:
    official = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
    before = official.read_bytes() if official.is_file() else None
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(tmp_path / "empty"),
        "--out-root",
        str(ROOT / "outputs" / "ml_eval" / "mega_goal_model"),
    )
    assert p.returncode == 2, p.stdout + p.stderr
    text = p.stderr + p.stdout
    assert "refuses_official_out_root" in text
    assert "complete_proxy_model_iou.json" in text
    if before is not None:
        assert official.read_bytes() == before
    assert not (tmp_path / "empty").exists() or not list((tmp_path / "empty").rglob("modis_cov_ablation.json"))


def test_ablation_missing_pack_exit_nonzero(tmp_path: Path) -> None:
    official = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
    before = official.read_bytes() if official.is_file() else None
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(tmp_path / "empty_latam"),
        "--out-root",
        str(tmp_path / "out"),
        "--weights",
        str(tmp_path / "no_weights.pt"),
    )
    assert p.returncode == 3, p.stdout + p.stderr
    assert p.returncode != 0
    text = (p.stderr + p.stdout).lower()
    assert "missing pack" in text
    assert "es_emsr685_tenerife" in text
    assert not (tmp_path / "out" / "modis_cov_ablation.json").is_file()
    if before is not None:
        assert official.read_bytes() == before


def test_ablation_unknown_event_exit_3(tmp_path: Path) -> None:
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "..\\etc\\passwd",
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 3, p.stdout + p.stderr
    assert "unknown pack" in (p.stderr + p.stdout).lower() or "missing data" in (p.stderr + p.stdout).lower()


def _mini_cems_pack(tmp_path: Path) -> Path:
    pytest.importorskip("rasterio")
    import rasterio
    from shapely.geometry import Polygon

    from wildfire_front.open_if.latam_au import (
        EMSR_PACK_SPECS,
        pack_dir_for,
        rasterize_geom_to_geotiff,
    )

    spec = EMSR_PACK_SPECS["ES_EMSR685_TENERIFE"]
    pack = pack_dir_for(tmp_path / "latam_au", spec)
    labels = pack / "labels"
    labels.mkdir(parents=True)
    poly = Polygon(
        [(-16.49, 28.34), (-16.47, 28.34), (-16.47, 28.36), (-16.49, 28.36), (-16.49, 28.34)]
    )
    dest = labels / "ES_EMSR685_TENERIFE_20230819_045000.tif"
    rasterize_geom_to_geotiff(poly, dest, epsg=int(spec["crs_epsg"]), gsd_m=30.0)
    dest2 = labels / "ES_EMSR685_TENERIFE_20230822_003000.tif"
    rasterize_geom_to_geotiff(poly, dest2, epsg=int(spec["crs_epsg"]), gsd_m=30.0)
    meta = {
        "schema": "wfd_open_if_pack_meta_v1",
        "event_id": "ES_EMSR685_TENERIFE",
        "region": spec["region"],
        "activation": spec["activation"],
        "license_id": spec["license_id"],
        "crs": f"EPSG:{spec['crs_epsg']}",
        "gsd_m": 30.0,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "rights_doc": "docs/data_campaigns/LATAM_AU_RIGHTS.md",
        "geotiffs": [
            {
                "rel": f"labels/{dest.name}",
                "role": "label_burned_cems_rasterized",
                "kind": "delineation",
                "delivery_utc": "2023-08-19T04:50:00Z",
            },
            {
                "rel": f"labels/{dest2.name}",
                "role": "label_burned_cems_rasterized",
                "kind": "delineation_monitoring",
                "delivery_utc": "2023-08-22T00:30:00Z",
            },
        ],
        "labels": [{"rel": f"labels/{dest.name}"}, {"rel": f"labels/{dest2.name}"}],
        "not_national_cadastre": True,
        "not_lwir": True,
    }
    (pack / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    cov = pack / "covariates"
    cov.mkdir()
    with rasterio.open(dest) as src:
        h, w = src.height, src.width
        profile = {
            "driver": "GTiff",
            "height": h,
            "width": w,
            "count": 1,
            "dtype": "float32",
            "crs": src.crs,
            "transform": src.transform,
        }
        for name, val in [
            ("elevation_m.tif", 400.0),
            ("temperature_c.tif", 24.0),
            ("humidity_pct.tif", 35.0),
            ("wind_speed_ms.tif", 4.0),
            ("wind_dir_deg.tif", 180.0),
            ("precip_mm.tif", 0.0),
            ("vegetation_proxy.tif", 0.55),
        ]:
            with rasterio.open(cov / name, "w", **profile) as ds:
                ds.write(np.full((h, w), val, dtype=np.float32), 1)
        with rasterio.open(cov / "s2_nbr_aligned.tif", "w", **profile) as ds:
            ds.write(np.full((h, w), 0.1, dtype=np.float32), 1)
    (cov / "PROVENANCE.json").write_text(
        json.dumps(
            {
                "schema": "wfd_latam_au_ndws_covariates_v1",
                "channels_ready": {"meteo": True, "dem": True, "veg": True},
                "vegetation": {"status": "ok", "nbr_rel": "covariates/s2_nbr_aligned.tif", "source": "s2_nbr"},
            }
        ),
        encoding="utf-8",
    )
    return pack


def test_ablation_missing_modis_ndvi_skips_without_inventing_iou(tmp_path: Path) -> None:
    pack = _mini_cems_pack(tmp_path)
    assert not (pack / "covariates" / "modis_ndvi.tif").is_file()
    official = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
    before = official.read_bytes() if official.is_file() else None
    product = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
    product_before = product.read_bytes() if product.is_file() else None
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(tmp_path / "latam_au"),
        "--out-root",
        str(tmp_path / "out"),
        "--variant",
        "modis_ndvi_veg",
        "--weights",
        str(tmp_path / "no_weights.pt"),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    doc = json.loads((tmp_path / "out" / "modis_cov_ablation.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "wfd_modis_cov_ablation_v1"
    assert doc["sold_as_clm_ensemble_v34"] is False
    assert doc["go_q"] == "partial"
    assert doc["lab_ok_conaf"] is False
    row = doc["rows"][0]
    assert row["variant"] == "modis_ndvi_veg"
    assert row["skip_class"] == "missing_modis_ndvi"
    assert row["model_iou"] is None
    assert row["complete_proxy_model_iou"] is None
    assert row["observed"] is False
    score = (tmp_path / "out" / "SCORECARD.md").read_text(encoding="utf-8")
    assert "not official LATAM MET" in score
    assert "not catalog 0.8963" in score
    assert "lab_ok_conaf false" in score
    assert "missing_modis_ndvi" in score
    if before is not None:
        assert official.read_bytes() == before
    if product_before is not None:
        assert product.read_bytes() == product_before
    assert not (tmp_path / "out" / "complete_proxy_model_iou.json").is_file()
    assert not (tmp_path / "out" / "weights_multi_if.pt").is_file()


def test_ablation_require_model_iou_missing_weights_no_invented_iou(tmp_path: Path) -> None:
    _mini_cems_pack(tmp_path)
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(tmp_path / "latam_au"),
        "--out-root",
        str(tmp_path / "out"),
        "--variant",
        "nbr_veg",
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--require-model-iou",
    )
    assert p.returncode == 1, p.stdout + p.stderr
    text = (p.stderr + p.stdout).lower()
    assert "missing weights" in text
    assert "invented" in text
    assert not (tmp_path / "out" / "modis_cov_ablation.json").is_file()


def test_ablation_require_model_iou_missing_modis_exit_2(tmp_path: Path) -> None:
    _mini_cems_pack(tmp_path)
    p = _run(
        "run_modis_cov_ablation.py",
        "--event-id",
        "ES_EMSR685_TENERIFE",
        "--data-root",
        str(tmp_path / "latam_au"),
        "--out-root",
        str(tmp_path / "out"),
        "--variant",
        "modis_ndvi_veg",
        "--require-model-iou",
        "--weights",
        str(tmp_path / "no_weights.pt"),
    )
    assert p.returncode == 2, p.stdout + p.stderr
    text = p.stderr + p.stdout
    assert "missing_modis_ndvi" in text
    assert not (tmp_path / "out" / "modis_cov_ablation.json").is_file()


def test_ablation_not_claims_do_not_sell_catalog_or_go_q() -> None:
    abl = _load_script("run_modis_cov_ablation.py")
    claims = " ".join(abl.NOT_CLAIMS)
    assert "not official LATAM MET" in claims
    assert "not GO_Q" in claims
    assert "not v34" in claims
    assert "not catalog 0.8963" in claims
    assert "not sealed" in claims
    assert "not ROS" in claims
    assert "lab_ok_conaf false" in claims
    assert OPTIONAL_LST_NOTE in claims
    assert "contract change" in claims
