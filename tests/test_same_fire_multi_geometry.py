"""Same-fire multi-geometry runner: pair protocol, AOI isolation, real CLI exits."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import classify_temporal_pair  # noqa: E402


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*args: str) -> subprocess.CompletedProcess:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_same_fire_multi_geometry.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_shipped_classifier_excludes_fep_gra_from_usable() -> None:
    assert (
        classify_temporal_pair(
            delta_hours=48.0,
            label_mask_iou=0.7,
            prev_kind="first_estimate",
            next_kind="delineation",
        )
        == "incompatible_product_kind"
    )
    assert (
        classify_temporal_pair(
            delta_hours=48.0,
            label_mask_iou=0.7,
            prev_kind="delineation",
            next_kind="grading",
        )
        == "incompatible_product_kind"
    )
    assert (
        classify_temporal_pair(
            delta_hours=3.2,
            label_mask_iou=0.6,
            prev_kind="delineation_monitoring",
            next_kind="delineation_monitoring",
        )
        == "too_short_delta"
    )


def test_aoi_token_and_kind_parsers() -> None:
    mod = _load_script("run_same_fire_multi_geometry.py")
    assert mod.parse_aoi_token("EMSR578_AOI01_DEL_PRODUCT.zip") == "AOI01"
    assert mod.parse_aoi_token("EMSR578_AOI02_GRA_PRODUCT.zip") == "AOI02"
    assert mod.parse_product_kind("EMSR578_AOI01_FEP_PRODUCT") == "first_estimate"
    assert mod.parse_product_kind("EMSR578_AOI01_DEL_MONIT02") == "delineation_monitoring"
    assert mod.parse_product_kind("EMSR632_AOI01_GRA_PRODUCT") == "grading"
    assert mod.parse_product_kind("EMSR632_AOI01_DEL_PRODUCT") == "delineation"


def test_family_means_do_not_mix_or_include_isolation_aoi() -> None:
    mod = _load_script("run_same_fire_multi_geometry.py")
    fires = [
        {
            "fire_id": "EMSR578_AOI01",
            "family": "cems_vector",
            "pairs": [
                {"pair_class": "incompatible_product_kind", "copy_mask_iou": 0.2},
                {"pair_class": "usable", "copy_mask_iou": 0.5},
            ],
        },
        {
            "fire_id": "EMSR578_AOI02",
            "family": "cems_vector",
            "pairs": [{"pair_class": "usable", "copy_mask_iou": 0.99}],
        },
        {
            "fire_id": "TOBARRA_20240802",
            "family": "infocam_kmz",
            "pairs": [{"pair_class": "too_short_delta", "copy_mask_iou": 0.4}],
        },
        {
            "fire_id": "US_FIREBENCH_CALDOR_2021",
            "family": "firebench_caldor",
            "pairs": [{"pair_class": "usable", "copy_mask_iou": 0.7}],
        },
    ]
    cems = mod.family_usable_copy_mean(fires, "cems_vector")
    assert cems == pytest.approx(0.5)
    assert cems != pytest.approx(0.99)
    assert mod.family_usable_copy_mean(fires, "infocam_kmz") is None
    assert mod.family_usable_copy_mean(fires, "firebench_caldor") == pytest.approx(0.7)
    assert mod.mixed_family_mean(fires) is None


def test_same_fire_unknown_exit3(tmp_path: Path) -> None:
    p = _run("--fire", "NOT_A_FIRE", "--out-root", str(tmp_path / "out"))
    assert p.returncode == 3, p.stdout + p.stderr
    assert "unknown fire" in (p.stderr + p.stdout).lower()
    assert not (tmp_path / "out" / "same_fire_eval.json").is_file()


def test_same_fire_official_latam_excluded_exit3(tmp_path: Path) -> None:
    p = _run("--fire", "CL_EMSR715_VALPARAISO", "--out-root", str(tmp_path / "out"))
    assert p.returncode == 3, p.stdout + p.stderr
    assert "official" in (p.stderr + p.stdout).lower()


def test_same_fire_missing_weights_require_model_iou_exit1(tmp_path: Path) -> None:
    p = _run(
        "--fire",
        "US_FIREBENCH_CALDOR_2021",
        "--require-model-iou",
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 1, p.stdout + p.stderr
    text = (p.stderr + p.stdout).lower()
    assert "missing weights" in text
    assert "invented" in text
    assert not (tmp_path / "out" / "same_fire_eval.json").is_file()


def test_same_fire_caldor_require_model_iou_runs_unet(tmp_path: Path) -> None:
    weights = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
    lab = (
        ROOT
        / "outputs"
        / "ml_eval"
        / "mega_goal_model"
        / "lab_scratch_frozen"
        / "weights_pretrained_best.pt"
    )
    ckpt = lab if lab.is_file() else weights
    if not ckpt.is_file():
        pytest.skip("frozen UNet weights not on disk")
    p = _run(
        "--fire",
        "US_FIREBENCH_CALDOR_2021",
        "--require-model-iou",
        "--weights",
        str(ckpt),
        "--max-patches",
        "2",
        "--max-pairs",
        "1",
        "--meteo-mode",
        "constant",
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    doc = json.loads((tmp_path / "out" / "same_fire_eval.json").read_text(encoding="utf-8"))
    caldor = next(f for f in doc["fires"] if f["fire_id"] == "US_FIREBENCH_CALDOR_2021")
    assert caldor.get("scored_model_iou") is not None
    assert isinstance(caldor.get("scored_model_iou"), float)
    assert caldor.get("sold_as_clm_ensemble_v34") is False
    assert caldor.get("schema_mode") == "caldor_physical_to_legacy17"


def test_same_fire_entry_point_aoi_isolation_and_no_official_overwrite(tmp_path: Path) -> None:
    if not (ROOT / "outputs" / "open_if" / "emsr578").is_dir():
        pytest.skip("EMSR578 source pack is not distributed")
    official = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
    before = official.read_bytes() if official.is_file() else None
    out = tmp_path / "same_fire_out"
    p = _run(
        "--fire",
        "EMSR578_AOI01",
        "--include-isolation-aois",
        "--max-patches",
        "4",
        "--meteo-mode",
        "constant",
        "--out-root",
        str(out),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    doc = json.loads((out / "same_fire_eval.json").read_text(encoding="utf-8"))
    ids = [f["fire_id"] for f in doc["fires"]]
    assert "EMSR578_AOI01" in ids
    aoi01 = next(f for f in doc["fires"] if f["fire_id"] == "EMSR578_AOI01")
    assert aoi01["n_geometries"] >= 2
    weights = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
    lab = (
        ROOT
        / "outputs"
        / "ml_eval"
        / "mega_goal_model"
        / "lab_scratch_frozen"
        / "weights_pretrained_best.pt"
    )
    if weights.is_file() or lab.is_file():
        assert aoi01.get("scored_model_iou") is not None or aoi01.get("model_iou") is not None
        assert aoi01.get("sold_as_clm_ensemble_v34") is False
    names01 = {(pair.get("from"), pair.get("to")) for pair in aoi01.get("pairs") or []}
    if "EMSR578_AOI02" in ids:
        aoi02 = next(f for f in doc["fires"] if f["fire_id"] == "EMSR578_AOI02")
        for pair in aoi02.get("pairs") or []:
            assert (pair.get("from"), pair.get("to")) not in names01
        assert all("AOI02" not in str(pair.get("from") or "") for pair in aoi01.get("pairs") or [])
    for pair in aoi01.get("pairs") or []:
        if pair.get("pair_class") == "usable":
            assert pair.get("from_kind") in {"delineation", "delineation_monitoring"}
            assert pair.get("to_kind") in {"delineation", "delineation_monitoring"}
        if {pair.get("from_kind"), pair.get("to_kind")} & {"first_estimate", "grading"}:
            assert pair.get("pair_class") == "incompatible_product_kind"
    assert doc["mixed_family_mean"] is None
    assert doc["lab_ok_conaf"] is False
    assert doc["go_q"] == "partial"
    assert doc["sold_as_clm_ensemble_v34"] is False
    if before is not None:
        assert official.read_bytes() == before
    assert "catalog 0.8963" in " ".join(doc.get("not_claims") or [])


def test_iso_datestamp_from_emsr578_xml() -> None:
    mod = _load_script("run_same_fire_multi_geometry.py")
    pack = ROOT / "outputs" / "open_if" / "emsr578"
    if not pack.is_dir():
        pytest.skip("EMSR578 pack not on disk")
    times = mod._iso_datestamps_from_raw_xml(pack)
    assert times["AOI01:delineation:0"].year == 2022
    assert times["AOI01:delineation:0"].month == 6
    assert times["AOI01:delineation:0"].day == 17
    assert times["AOI01:delineation_monitoring:1"].day == 18


def test_stream_geojson_features(tmp_path: Path) -> None:
    from shapely.geometry import box, mapping

    from wildfire_front.open_if.same_fire_model import iter_geojson_geoms_streaming

    doc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": mapping(box(0, 0, 1, 1))},
            {"type": "Feature", "properties": {}, "geometry": mapping(box(2, 2, 3, 3))},
        ],
    }
    path = tmp_path / "tiny.geojson"
    path.write_text(json.dumps(doc), encoding="utf-8")
    geoms = list(iter_geojson_geoms_streaming(path))
    assert len(geoms) == 2
    assert geoms[0].area == pytest.approx(1.0)


def test_score_raster_pair_returns_non_null_iou() -> None:
    import numpy as np

    from wildfire_front.open_if.same_fire_model import (
        constant_cov,
        default_same_fire_weights,
        load_frozen_unet,
        score_raster_pair,
    )

    weights = default_same_fire_weights(ROOT)
    if not weights.is_file():
        pytest.skip("frozen UNet weights not on disk")
    prev = np.zeros((96, 96), dtype=np.float32)
    nxt = np.zeros((96, 96), dtype=np.float32)
    prev[20:60, 20:60] = 1.0
    nxt[18:64, 18:64] = 1.0
    cov = constant_cov(96, 96)
    model, device = load_frozen_unet(weights)
    out = score_raster_pair(prev, nxt, cov, model, device, max_patches=4)
    assert out["ok"] is True
    assert out["model_iou"] is not None
    assert 0.0 <= float(out["model_iou"]) <= 1.0
    assert int(out["n_tiles"]) >= 1


def test_score_raster_pair_pads_sub_tile_masks() -> None:
    import numpy as np

    from wildfire_front.open_if.same_fire_model import (
        constant_cov,
        default_same_fire_weights,
        load_frozen_unet,
        score_raster_pair,
    )

    weights = default_same_fire_weights(ROOT)
    if not weights.is_file():
        pytest.skip("frozen UNet weights not on disk")
    prev = np.zeros((20, 22), dtype=np.float32)
    nxt = np.zeros((20, 22), dtype=np.float32)
    prev[4:16, 4:16] = 1.0
    nxt[3:18, 3:18] = 1.0
    cov = constant_cov(20, 22)
    model, device = load_frozen_unet(weights)
    out = score_raster_pair(prev, nxt, cov, model, device, max_patches=2)
    assert out["ok"] is True
    assert out["model_iou"] is not None
    assert int(out["n_tiles"]) >= 1
