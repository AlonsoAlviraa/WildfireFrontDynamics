"""Tests for W3 inventory, Tobarra diagnose, recipe, and expert rails."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from wildfire_front.ml.w3_signal import (
    audit_lofo_zero_target_leak,
    build_w3_signal_pack,
    diagnose_tobarra_head_a,
    export_clm_patches_from_aligned,
    inventory_w3_fires,
    tobarra_finetune_recipe,
)

ROOT = Path(__file__).resolve().parents[1]


def test_inventory_structure():
    inv = inventory_w3_fires(ROOT)
    assert inv["schema"] == "w3_fire_inventory_v1"
    assert inv["rails"]["ml_product_go"] is True
    assert inv["rails"]["no_ece_retune_same_holdout"] is True
    assert "external_candidates" in inv
    assert inv["summary"]["n_in_pack_sources"] >= 1
    # Hellín should be READY if artifacts present
    by_id = {e["id"]: e for e in inv["external_candidates"]}
    if by_id.get("hellin_2024", {}).get("n_lwir_tif", 0) >= 3:
        assert by_id["hellin_2024"]["status"] == "READY"


def test_tobarra_diagnose_if_cache():
    cache = ROOT / "outputs/ml_eval/lofo_v1/tobarra_20240802/head_a_features.npz"
    cal = ROOT / "models/clm_ensemble/uncertainty_calibration_v1.json"
    if not (cache.is_file() and cal.is_file()):
        return
    diag = diagnose_tobarra_head_a(ROOT)
    assert diag["ok"] is True
    assert diag["n_patches"] >= 10
    assert 0.0 <= diag["mean_iou"] <= 1.0
    assert diag["rails"]["no_ece_retune_same_holdout"] is True
    assert "reject_locked" in diag


def test_build_pack_and_script(tmp_path):
    pack = build_w3_signal_pack(ROOT)
    assert pack["schema"] == "w3_new_signal_pack_v1"
    assert pack["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    from scripts import run_lab_ml_loop_v34_w3_signal as mod

    rc = mod.main(["--repo", str(ROOT), "--out-dir", str(tmp_path), "--no-md"])
    assert rc in (0, 2)
    if rc == 0:
        data = json.loads(
            (tmp_path / "lab_loop_v34_w3_signal_latest.json").read_text(encoding="utf-8")
        )
        assert data["iteration"] == 13
        assert data["rails"]["ml_product_go"] is True
        assert (tmp_path / "w3_fire_inventory.json").is_file()


def test_tobarra_finetune_recipe_rails_and_kill():
    recipe = tobarra_finetune_recipe(ROOT)
    assert recipe["schema"] == "w3_tobarra_finetune_recipe_v1"
    assert recipe["ok"] is True
    assert recipe["rails"]["ml_product_go"] is True
    assert recipe["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert recipe["rails"]["no_ece_retune_same_holdout"] is True
    assert recipe["rails"]["zero_target_leak_required"] is True
    ids = {k["id"] for k in recipe["kill_criteria"]}
    assert "K1_test_iou_lift" in ids
    assert "K3_zero_target_leak" in ids
    assert "K4_no_holdout_test_thr_ece" in ids
    assert "ECE" in " ".join(recipe["forbidden"]) or any("ECE" in f for f in recipe["forbidden"])
    # Never claim field promote
    assert recipe["rails"]["ml_product_go"] is True


def test_lofo_zero_target_leak_audit_synthetic(tmp_path: Path):
    fold = tmp_path / "tobarra_20240802"
    for split, sources in (
        ("train", ["CARDOSO", "LA_ESTRELLA_ACOM1"]),
        ("val", ["CARDOSO"]),
        ("test", ["tobarra_20240802", "tobarra_20240802"]),
    ):
        d = fold / split
        d.mkdir(parents=True)
        for i, src in enumerate(sources):
            np.savez_compressed(
                d / f"p_{i}.npz",
                sequence=np.zeros((1, 17, 8, 8), dtype=np.float32),
                current_fire=np.zeros((8, 8), dtype=np.float32),
                target_fire=np.zeros((8, 8), dtype=np.float32),
                source=np.array(src),
            )
    ok = audit_lofo_zero_target_leak(fold, held_out="tobarra_20240802")
    assert ok["ok"] is True
    assert ok["n_leaked_train_val"] == 0

    # inject leak
    np.savez_compressed(
        fold / "train" / "leaked.npz",
        sequence=np.zeros((1, 17, 8, 8), dtype=np.float32),
        current_fire=np.zeros((8, 8), dtype=np.float32),
        target_fire=np.zeros((8, 8), dtype=np.float32),
        source=np.array("tobarra_20240802"),
    )
    bad = audit_lofo_zero_target_leak(fold, held_out="tobarra_20240802")
    assert bad["ok"] is False
    assert bad["n_leaked_train_val"] >= 1


def test_export_clm_patches_from_aligned_tiny(tmp_path: Path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    img = tmp_path / "img"
    msk = tmp_path / "msk"
    img.mkdir()
    msk.mkdir()
    transform = from_origin(500000.0, 4200000.0, 10.0, 10.0)
    for i in range(4):
        name = f"2024-01-01_12-0{i}-00_LWIR.tif"
        data = np.zeros((64, 64), dtype=np.float32)
        data[20 : 28 + i, 20 : 28 + i] = 100 + i
        mask = np.zeros((64, 64), dtype=np.uint8)
        mask[20 : 28 + i, 20 : 28 + i] = 1
        with rasterio.open(
            img / name,
            "w",
            driver="GTiff",
            height=64,
            width=64,
            count=1,
            dtype="float32",
            crs="EPSG:32630",
            transform=transform,
        ) as ds:
            ds.write(data, 1)
        with rasterio.open(
            msk / name.replace(".tif", "_mask.tif"),
            "w",
            driver="GTiff",
            height=64,
            width=64,
            count=1,
            dtype="uint8",
            crs="EPSG:32630",
            transform=transform,
        ) as ds:
            ds.write(mask, 1)

    out = tmp_path / "patches"
    man = export_clm_patches_from_aligned(
        img,
        msk,
        out,
        "test_fire",
        patch_size=30,
        sequence_length=1,
        max_patches=10,
        min_change_fraction=0.0,  # tiny synthetic may have small change
    )
    assert man["ok"] is True
    assert man["num_patches"] >= 1
    npz = next(out.glob("*.npz"))
    with np.load(npz) as z:
        assert z["sequence"].shape[0] == 1
        assert z["sequence"].shape[1] == 17
        assert z["current_fire"].shape == (30, 30)
        assert str(z["source"]) == "test_fire"


def test_lofo_tobarra_real_fold_zero_leak_if_present():
    fold = ROOT / "artifacts/clm_ndws_patches/lofo_v1/tobarra_20240802"
    if not fold.is_dir():
        return
    audit = audit_lofo_zero_target_leak(fold, held_out="tobarra_20240802")
    assert audit["n_leaked_train_val"] == 0
