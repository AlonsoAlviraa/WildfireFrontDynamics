"""PR-A–H: warp hygiene, pair filters, annual block, CONAF ingest, missing-data exits."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    ANNUAL_EVAL_STATUS,
    EMSR_PACK_SPECS,
    WEAK_PACK_SPECS,
    aligned_s2_paths,
    assign_s2_roles_by_datetime,
    cems_product_url_ok,
    cession_evidence_ok,
    classify_temporal_pair,
    compatible_growth_kinds,
    distinct_s2_windows,
    gc_nested_to_cems,
    is_annual_l1_spec,
    is_nested_to_cems_name,
    mean_usable_pair_ious,
    pack_dir_for,
    rasterize_geom_to_geotiff,
    s2_source_paths,
    source_pack_ready,
    warp_proxy_from_pack,
)


def _load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def _mini_pack(tmp_path: Path, event_id: str = "AU_EMSR500_PERTH") -> Path:
    spec = EMSR_PACK_SPECS[event_id]
    pack = tmp_path / "latam_au" / spec["region"] / event_id
    labels = pack / "labels"
    labels.mkdir(parents=True)
    poly = Polygon(
        [(116.17, -31.79), (116.19, -31.79), (116.19, -31.77), (116.17, -31.77), (116.17, -31.79)]
    )
    dest = labels / f"{event_id}_20210205_203225.tif"
    rast = rasterize_geom_to_geotiff(poly, dest, epsg=int(spec["crs_epsg"]), gsd_m=30.0)
    meta = {
        "schema": "wfd_open_if_pack_meta_v1",
        "event_id": event_id,
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
                "delivery_utc": "2021-02-05T20:32:25Z",
                "positive_pixels": rast.get("positive_pixels"),
            }
        ],
        "labels": [{"rel": f"labels/{dest.name}"}],
        "not_national_cadastre": True,
        "not_lwir": True,
    }
    (pack / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return pack


def _add_s2(pack: Path, n: int = 2) -> None:
    import rasterio
    from rasterio.transform import from_bounds

    eo = pack / "eo"
    eo.mkdir(exist_ok=True)
    west, south, east, north = 116.16, -31.80, 116.20, -31.76
    h = w = 32
    transform = from_bounds(west, south, east, north, w, h)
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
    stamps = ("20210220_022620", "20210220_022634", "20210121_022636")
    for i in range(n):
        nbr = np.full((h, w), 0.2, dtype=np.float32)
        nbr[8:20, 8:20] = -0.3
        path = eo / f"{meta['event_id']}_S2NBR_{stamps[i]}.tif"
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=h,
            width=w,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=transform,
        ) as ds:
            ds.write(nbr, 1)
        meta["geotiffs"].append({"rel": f"eo/{path.name}", "role": "eo_s2_nbr_post", "crs": "EPSG:4326"})
    (pack / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


# --- PR-A warp hygiene ---


def test_nested_to_cems_name_detects_repeats() -> None:
    assert is_nested_to_cems_name("x_to_cems_to_cems.tif")
    assert is_nested_to_cems_name("x_to_cems_to_cems_to_cems.tif")
    assert not is_nested_to_cems_name("x_to_cems.tif")
    assert not is_nested_to_cems_name("eo/x.tif")


def test_s2_source_paths_ignore_aligned_and_nested(tmp_path: Path) -> None:
    pack = _mini_pack(tmp_path)
    _add_s2(pack, n=2)
    aligned = pack / "eo_aligned"
    aligned.mkdir()
    junk = aligned / "AU_EMSR500_PERTH_S2NBR_20210220_022620_to_cems_to_cems.tif"
    junk.write_bytes(b"not-a-real-tif")
    (aligned / "AU_EMSR500_PERTH_S2NBR_20210220_022620_to_cems.tif").write_bytes(b"x")
    srcs = s2_source_paths(pack, json.loads((pack / "meta.json").read_text(encoding="utf-8")))
    assert all(p.parent.name == "eo" for p in srcs)
    assert all(not p.stem.endswith("_to_cems") for p in srcs)
    assert len(srcs) == 2
    removed = gc_nested_to_cems(pack)
    assert any("to_cems_to_cems" in r for r in removed)
    assert not junk.exists()


def test_warp_twice_same_n_and_no_nested(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    mod = _load_script("warp_latam_au_s2_to_cems.py")
    pack = _mini_pack(tmp_path)
    _add_s2(pack, n=2)
    reports = tmp_path / "rep"
    first = mod.warp_pack("AU_EMSR500_PERTH", pack, nbr_threshold=-0.1, report_root=reports)
    assert first["ok"] is True, first
    n_src = len(s2_source_paths(pack))
    assert first["n_warped"] == n_src
    second = mod.warp_pack("AU_EMSR500_PERTH", pack, nbr_threshold=-0.1, report_root=reports)
    assert second["ok"] is True, second
    assert second["n_warped"] == first["n_warped"] == n_src
    assert second.get("n_skipped_existing", 0) == n_src
    names = [p.name for p in (pack / "eo_aligned").glob("*.tif")]
    assert names
    assert all("_to_cems_to_cems" not in n for n in names)
    assert len(aligned_s2_paths(pack)) == n_src


def test_warp_missing_pack_exit1(tmp_path: Path) -> None:
    p = _run(
        "warp_latam_au_s2_to_cems.py",
        "--event-id",
        "AU_EMSR500_PERTH",
        "--data-root",
        str(tmp_path / "empty"),
        "--report-root",
        str(tmp_path / "rep"),
    )
    assert p.returncode == 1, p.stdout + p.stderr


# --- PR-B domain-gap uses warp ---


def test_warp_proxy_measured_when_provenance_exists(tmp_path: Path) -> None:
    pack = _mini_pack(tmp_path)
    aligned = pack / "eo_aligned"
    aligned.mkdir()
    tif = aligned / "src_to_cems.tif"
    tif.write_bytes(b"x")
    (aligned / "WARP_PROVENANCE.json").write_text(
        json.dumps(
            {
                "schema": "wfd_latam_au_s2_warp_v1",
                "proxy_metric": {
                    "status": "measured",
                    "metric": "nbr_vs_cems_iou",
                    "nbr_vs_cems_iou": 0.42,
                    "threshold": -0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    proxy = warp_proxy_from_pack(pack)
    assert proxy is not None
    assert proxy["status"] == "measured"
    assert proxy["value"] == 0.42
    assert "no audited warp" not in (proxy.get("reason") or "").lower()


def test_domain_gap_uses_warp_not_blocked(tmp_path: Path) -> None:
    mod = _load_script("eval_latam_au_domain_gap.py")
    pack = _mini_pack(tmp_path)
    aligned = pack / "eo_aligned"
    aligned.mkdir()
    (aligned / "src_to_cems.tif").write_bytes(b"x")
    (aligned / "WARP_PROVENANCE.json").write_text(
        json.dumps({"proxy_metric": {"status": "measured", "nbr_vs_cems_iou": 0.33}}),
        encoding="utf-8",
    )
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
    meta["stac_eo"] = [{"status": "ok"}]
    meta["crs"] = "EPSG:32750"
    proxy = mod.attempt_dnbr_proxy(pack, meta)
    assert proxy["status"] == "measured"
    assert proxy["value"] == 0.33
    assert proxy["status"] != "blocked_crs_mismatch"


def test_domain_gap_blocked_without_warp(tmp_path: Path) -> None:
    mod = _load_script("eval_latam_au_domain_gap.py")
    pack = _mini_pack(tmp_path)
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
    meta["stac_eo"] = [{"status": "ok"}]
    meta["crs"] = "EPSG:32750"
    meta["label_level"] = "L2_proxy"
    proxy = mod.attempt_dnbr_proxy(pack, meta)
    assert proxy["status"] == "blocked_crs_mismatch"
    assert proxy["value"] is None


# --- PR-C honest pairs ---


def test_pair_filters_nacimiento_and_perth() -> None:
    assert classify_temporal_pair(delta_hours=2.3, label_mask_iou=0.86) == "too_short_delta"
    assert classify_temporal_pair(delta_hours=140.0, label_mask_iou=0.99) == "static_label_copy"
    assert classify_temporal_pair(delta_hours=43.0, label_mask_iou=0.86) == "usable"
    pairs = [
        {
            "pair_class": "too_short_delta",
            "complete_proxy_model_iou": 0.788,
            "delta_hours": 2.3,
        },
        {
            "pair_class": "static_label_copy",
            "complete_proxy_model_iou": 0.916,
            "label_mask_iou": 0.99,
        },
        {"pair_class": "usable", "complete_proxy_model_iou": 0.41, "delta_hours": 48.0},
    ]
    mean = mean_usable_pair_ious(pairs)
    assert mean == pytest.approx(0.41)
    assert 0.788 not in [mean]
    assert 0.916 not in [mean]


def test_fep_del_not_usable_growth_pair() -> None:
    """EMSR715 FEP→DEL is a product-type change, not next-day growth."""
    assert compatible_growth_kinds("first_estimate", "delineation") is False
    assert compatible_growth_kinds("delineation", "grading") is False
    assert compatible_growth_kinds("delineation", "delineation_monitoring") is True
    klass = classify_temporal_pair(
        delta_hours=44.8,
        label_mask_iou=0.56,
        prev_kind="first_estimate",
        next_kind="delineation",
    )
    assert klass == "incompatible_product_kind"
    assert (
        classify_temporal_pair(
            delta_hours=43.0,
            label_mask_iou=0.86,
            prev_kind="delineation",
            next_kind="delineation_monitoring",
        )
        == "usable"
    )


def test_stratified_tiles_not_scanline_only() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    mask = np.zeros((200, 200), dtype=np.float32)
    mask[10:40, 10:40] = 1.0
    mask[80:160, 80:160] = 1.0
    mask[170:190, 5:25] = 1.0
    tiles = mod.stratified_tiles(mask, max_n=12, min_pos=0.01)
    assert tiles
    kinds = {t[3] for t in tiles}
    assert kinds & {"edge", "interior", "low_density", "fallback_center"}
    # n=1 guard: tiny mask
    tiny = np.ones((8, 8), dtype=np.float32)
    tiny_tiles = mod.stratified_tiles(tiny, max_n=4, min_pos=0.0)
    assert len(tiny_tiles) >= 1


def test_copy_safety_gate_is_target_blind_and_off_by_default() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    prev = np.zeros((4, 4), dtype=np.float32)
    prev[0, 0] = 1.0
    probability = np.full((4, 4), 0.92, dtype=np.float32)
    probability[0, 0] = 0.0

    use_default, score = mod.copy_safety_use_model(probability, prev, None)
    assert use_default is True
    assert score == pytest.approx(0.92)
    assert mod.copy_safety_use_model(probability, prev, 0.93)[0] is False
    assert mod.copy_safety_use_model(probability, prev, 0.91)[0] is True


def test_decode_residual_does_not_double_add_prev() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    prev = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    probability = np.array([[0.99, 0.40], [0.91, 0.49]], dtype=np.float32)
    pred = mod.decode_complete_proxy_pred(
        probability,
        prev,
        architecture="residual",
        target_mode="delta",
        threshold=0.5,
        growth_threshold=0.90,
    )
    assert pred[0, 0] and pred[1, 1]
    assert not pred[0, 1]
    assert pred[1, 0]


def test_decode_standard_delta_uses_growth_threshold_and_ignores_t1() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    prev = np.array([[1.0, 0.0]], dtype=np.float32)
    pred = mod.decode_complete_proxy_pred(
        np.array([[0.1, 0.91]], dtype=np.float32),
        prev,
        architecture="standard",
        target_mode="delta",
        threshold=0.5,
        growth_threshold=0.90,
    )
    assert pred[0, 0]
    assert pred[0, 1]
    pred_lo = mod.decode_complete_proxy_pred(
        np.array([[0.1, 0.80]], dtype=np.float32),
        prev,
        architecture="standard",
        target_mode="delta",
        threshold=0.5,
        growth_threshold=0.90,
    )
    assert pred_lo[0, 0]
    assert not pred_lo[0, 1]


def test_ood_growth_threshold_is_round_priori_constant() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    assert mod.OOD_GROWTH_THRESHOLD == 0.90
    assert mod.GROWTH_RING_CONNECTIVITY == 8
    assert mod.GROWTH_RING_MIN_NEIGHBORS == 1


def test_oracle_frozen_decode_beats_copy_on_true_ring() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    prev = np.zeros((5, 5), dtype=np.float32)
    prev[2, 2] = 1.0
    target = prev.copy()
    target[1, 1] = 1.0
    oracle = mod.oracle_frozen_decode_mask(prev, target)
    assert oracle[2, 2] and oracle[1, 1]
    assert not oracle[0, 0]
    assert mod.binary_iou(oracle, target >= 0.5) > mod.binary_iou(prev >= 0.5, target >= 0.5)


def test_frozen_ring_loss_rewards_true_ring_and_penalizes_false_ring() -> None:
    import torch

    scratch = _load_script("run_latam_au_lab_scratch.py")
    prev = torch.zeros(1, 3, 3)
    prev[0, 1, 1] = 1.0
    target = torch.zeros(1, 3, 3)
    target[0, 1, 1] = 1.0
    target[0, 0, 0] = 1.0
    good = torch.full((1, 3, 3), -8.0)
    good[0, 0, 0] = 4.0
    bad = torch.full((1, 3, 3), -8.0)
    bad[0, 0, 1] = 4.0
    assert float(scratch.frozen_ring_decode_loss(good, prev, target)) < float(
        scratch.frozen_ring_decode_loss(bad, prev, target)
    )


def test_frozen_ring_loss_penalizes_residual_leak_below_decode_threshold() -> None:
    """Threshold hinge is silent at residual init; leak over copy must still cost."""
    import inspect

    import torch

    scratch = _load_script("run_latam_au_lab_scratch.py")
    assert inspect.signature(scratch.run_frozen_decode_finetune).parameters["fp_weight"].default == 4.0
    assert inspect.signature(scratch.run_frozen_decode_finetune).parameters["head_only"].default is False
    assert inspect.signature(scratch.run_frozen_decode_finetune).parameters["lr"].default == 1e-4
    prev = torch.zeros(1, 3, 3)
    prev[0, 1, 1] = 1.0
    target = prev.clone()
    copy = torch.logit(prev.clamp(1e-4, 1.0 - 1e-4))
    leaked = copy.clone()
    leaked[0, 0, 0] = copy[0, 0, 0] + 2.0
    assert float(torch.sigmoid(leaked[0, 0, 0])) < 0.90
    assert float(scratch.frozen_ring_decode_loss(leaked, prev, target)) > float(
        scratch.frozen_ring_decode_loss(copy, prev, target)
    )


def test_mega_goal_claim_is_single_frozen_pipeline() -> None:
    import inspect

    report = ROOT / "outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json"
    if not report.is_file():
        pytest.skip("local mega-goal evaluation artifact is not distributed")
    doc = json.loads(report.read_text(encoding="utf-8"))
    assert float(doc["growth_threshold"]) == 0.90
    weights = str(doc["weights"]).replace("\\", "/")
    assert "_fp" not in weights
    product = "models/clm_ensemble/weights_multi_if.pt"
    frozen = "outputs/ml_eval/mega_goal_model/lab_scratch_frozen/weights_pretrained_best.pt"
    assert weights in {product, frozen}
    if weights == frozen:
        man = json.loads(
            (ROOT / "outputs/ml_eval/mega_goal_model/lab_scratch_frozen/LAB_SCRATCH_MANIFEST.json").read_text(
                encoding="utf-8"
            )
        )
        assert str(man["init_weights"]).replace("\\", "/") == product
        assert man["config"]["head_only"] is False
        assert float(man["config"]["lr"]) == 1e-4
        scratch = _load_script("run_latam_au_lab_scratch.py")
        default_fp = inspect.signature(scratch.run_frozen_decode_finetune).parameters["fp_weight"].default
        assert float(man["config"]["fp_weight"]) == float(default_fp)
        assert float(default_fp) == 4.0


def test_growth_ring_is_eight_connected_k1_and_target_blind() -> None:
    mod = _load_script("run_latam_au_complete_model_iou.py")
    prev = np.zeros((5, 5), dtype=np.float32)
    prev[2, 2] = 1.0
    ring = mod.fire_growth_ring(prev)
    assert not ring[2, 2]
    assert int(ring.sum()) == 8
    isolated = np.zeros((5, 5), dtype=np.float32)
    isolated[0, 4] = 0.99
    pred = mod.decode_complete_proxy_pred(
        isolated,
        prev,
        architecture="residual",
        target_mode="delta",
        threshold=0.5,
        growth_threshold=0.90,
        require_growth_ring=True,
    )
    assert pred[2, 2]
    assert not pred[0, 4]
    on_ring = np.zeros((5, 5), dtype=np.float32)
    on_ring[1, 1] = 0.95
    pred2 = mod.decode_complete_proxy_pred(
        on_ring,
        prev,
        architecture="residual",
        target_mode="delta",
        threshold=0.5,
        growth_threshold=0.90,
        require_growth_ring=True,
    )
    assert pred2[1, 1]


def test_inventory_script_emits_all_section3_paths(tmp_path: Path) -> None:
    inv = _load_script("inventory_model_py.py")
    status = {
        path: {"status": "audited_ok", "note": "checked"}
        for paths in inv.WAVES.values()
        for path in paths
    }
    doc = inv.build_inventory(status, final=True)
    assert doc["n_pending"] == 0
    assert doc["n_rows"] == 45
    got = {row["path"] for row in doc["rows"]}
    expected = {path for paths in inv.WAVES.values() for path in paths}
    assert got == expected
    assert all(row["status"] in inv.FINAL_STATUSES for row in doc["rows"])


def test_complete_iou_missing_weights_exit1(tmp_path: Path) -> None:
    p = _run(
        "run_latam_au_complete_model_iou.py",
        "--event-id",
        "AU_EMSR500_PERTH",
        "--data-root",
        str(tmp_path / "empty"),
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "missing weights" in (p.stderr + p.stdout).lower()
    assert "invented" in (p.stderr + p.stdout).lower()


def test_complete_iou_unknown_event_exit2(tmp_path: Path) -> None:
    p = _run(
        "run_latam_au_complete_model_iou.py",
        "--event-id",
        "NOT_A_PACK",
        "--weights",
        str(tmp_path / "no.pt"),
    )
    # missing weights is checked first
    assert p.returncode == 1


# --- PR-D NBR pairing / roles ---


def test_same_civil_day_not_mid_post() -> None:
    recs = [
        {"role": "eo_s2_nbr_pre", "datetime": "2021-01-21T02:26:36Z", "file": "a.tif"},
        {"role": "eo_s2_nbr_mid", "datetime": "2021-02-20T02:26:20Z", "file": "b.tif"},
        {"role": "eo_s2_nbr_post", "datetime": "2021-02-20T02:26:34Z", "file": "c.tif"},
    ]
    out = assign_s2_roles_by_datetime(recs)
    s2 = [r for r in out if str(r["role"]).startswith("eo_s2_nbr")]
    roles = [r["role"] for r in s2]
    assert "eo_s2_nbr_same_day_tile" in roles
    assert roles.count("eo_s2_nbr_mid") == 0
    assert roles[0] == "eo_s2_nbr_pre"
    assert "eo_s2_nbr_post" in roles


def test_distinct_s2_windows_no_overlap() -> None:
    wins = distinct_s2_windows("2020-08-01")
    assert [r for r, _ in wins] == ["pre", "mid", "post"]
    spans = [rng.split("/") for _, rng in wins]
    assert spans[0][1] < spans[1][0]
    assert spans[1][1] < spans[2][0]


# --- PR-E covariates ---


def test_fill_all_forbids_silent_dem_fallback(tmp_path: Path) -> None:
    pytest.importorskip("rasterio")
    mod = _load_script("fill_latam_au_ndws_covariates.py")
    pack = _mini_pack(tmp_path)
    weather = pack / "weather"
    weather.mkdir()
    (weather / "open_meteo_era5_archive.json").write_text(
        json.dumps(
            {
                "elevation_m": 220.0,
                "hourly": {
                    "time": ["2021-02-05T20:00"],
                    "temperature_2m": [25.0],
                    "relative_humidity_2m": [40.0],
                    "wind_speed_10m": [15.0],
                    "wind_direction_10m": [180.0],
                    "precipitation": [0.0],
                },
            }
        ),
        encoding="utf-8",
    )
    row = mod.fill_pack(
        "AU_EMSR500_PERTH",
        pack,
        skip_dem_fetch=True,
        allow_dem_fallback=False,
        all_mode=True,
    )
    assert row["ok"] is False
    assert "fallback" in str(row.get("error") or "").lower() or row.get("dem_status") == "forbidden_fallback_constant"
    prov_p = pack / "covariates" / "PROVENANCE.json"
    if prov_p.is_file():
        prov = json.loads(prov_p.read_text(encoding="utf-8"))
        assert prov.get("dem", {}).get("status") != "fallback_constant"


def test_meteo_summary_declares_constant_point(tmp_path: Path) -> None:
    mod = _load_script("fill_latam_au_ndws_covariates.py")
    pack = _mini_pack(tmp_path)
    weather = pack / "weather"
    weather.mkdir()
    (weather / "open_meteo_era5_archive.json").write_text(
        json.dumps(
            {
                "elevation_m": 220.0,
                "hourly": {
                    "time": ["2021-02-05T20:00", "2021-02-11T17:00"],
                    "temperature_2m": [25.0, 30.0],
                    "relative_humidity_2m": [40.0, 35.0],
                    "wind_speed_10m": [15.0, 10.0],
                    "wind_direction_10m": [180.0, 90.0],
                    "precipitation": [0.0, 0.1],
                },
            }
        ),
        encoding="utf-8",
    )
    at = datetime(2021, 2, 11, 17, 3, 24, tzinfo=UTC)
    doc = mod.load_meteo_summary(pack, at=at)
    assert doc["status"] == "ok"
    assert doc["meteo_spatial"] == "constant_point"
    assert doc["temperature_c_mean"] == 30.0


def test_fill_missing_pack_exit1(tmp_path: Path) -> None:
    p = _run(
        "fill_latam_au_ndws_covariates.py",
        "--event-id",
        "AU_EMSR500_PERTH",
        "--data-root",
        str(tmp_path / "empty"),
        "--skip-dem-fetch",
        "--report",
        str(tmp_path / "r.json"),
    )
    assert p.returncode == 1


# --- PR-F BO + MX specs ---


def test_bo_mx_specs_are_honest_and_not_ready() -> None:
    assert "BO_EMSR765" in EMSR_PACK_SPECS
    assert "MX_EMSR717" in EMSR_PACK_SPECS
    for eid in ("BO_EMSR765", "MX_EMSR717"):
        spec = EMSR_PACK_SPECS[eid]
        assert len(spec["products"]) >= 3
        for prod in spec["products"]:
            assert cems_product_url_ok(prod["url"])
        pack = pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec)
        ok, reason = source_pack_ready(pack)
        if not (pack / "meta.json").is_file():
            assert ok is False
            assert "missing_meta" in reason


# --- PR-G annual L1 ---


def test_annual_lofo_blocked_annual_not_event() -> None:
    from wildfire_front.open_if.latam_au import build_lofo_fold_doc

    assert is_annual_l1_spec(WEAK_PACK_SPECS["BR_PANTANAL_2020_MAPBIOMAS"])
    doc = build_lofo_fold_doc(
        repo_root=ROOT,
        non_clm_event_id="BR_PANTANAL_2020_MAPBIOMAS",
    )
    fold = doc["folds"]["BR_PANTANAL_2020_MAPBIOMAS"]
    assert fold["eval_status"] == ANNUAL_EVAL_STATUS
    assert fold["model_iou"] is None
    assert "annual" in fold["reason"].lower()


def test_adapt_annual_refuses_next_mask(tmp_path: Path) -> None:
    mod = _load_script("adapt_latam_au_to_ndws_patches.py")
    spec = WEAK_PACK_SPECS["AU_NAFI_NT_SEASON_2023"]
    pack = tmp_path / "latam_au" / spec["region"] / spec["event_id"]
    labels = pack / "labels"
    labels.mkdir(parents=True)
    poly = Polygon([(130.6, -12.8), (130.8, -12.8), (130.8, -12.6), (130.6, -12.6), (130.6, -12.8)])
    dest = labels / f"{spec['event_id']}_20231231_000000.tif"
    rasterize_geom_to_geotiff(poly, dest, epsg=4326, gsd_m=250.0)
    meta = {
        "schema": "wfd_open_if_pack_meta_v1",
        "event_id": spec["event_id"],
        "region": spec["region"],
        "activation": spec["activation"],
        "license_id": spec["license_id"],
        "crs": "EPSG:4326",
        "gsd_m": 250.0,
        "class": "ml_weak",
        "label_level": "L1_annual",
        "rights_doc": "docs/data_campaigns/LATAM_AU_RIGHTS.md",
        "geotiffs": [{"rel": f"labels/{dest.name}", "role": "label_burned_nafi_annual"}],
        "labels": [{"rel": f"labels/{dest.name}"}],
        "not_national_cadastre": True,
        "not_lwir": True,
    }
    (pack / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    out = tmp_path / "npz"
    row = mod.adapt_pack(spec["event_id"], pack, out, patch_size=32, max_patches=2, mode="annual_scar_only")
    assert row["ok"] is True
    assert row["schema_mode"] == "annual_scar_only"
    assert row["compatible_with_clm_ensemble_v34"] is False
    zs = mod.run_zero_shot_eval([row], out)
    assert zs["eval_status"] == ANNUAL_EVAL_STATUS
    assert zs["model_iou"] is None


def test_adapt_missing_pack_exit1(tmp_path: Path) -> None:
    p = _run(
        "adapt_latam_au_to_ndws_patches.py",
        "--event-id",
        "AU_EMSR500_PERTH",
        "--data-root",
        str(tmp_path / "empty"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 1


# --- PR-H CONAF ingest ---


def test_conaf_ingest_roundtrip_lab_ok_false(tmp_path: Path) -> None:
    gj = tmp_path / "perim.geojson"
    gj.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-72.7, -37.52],
                                    [-72.65, -37.52],
                                    [-72.65, -37.48],
                                    [-72.7, -37.48],
                                    [-72.7, -37.52],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "latam_au"
    p = _run(
        "ingest_conaf_perimeters.py",
        "--vector",
        str(gj),
        "--event",
        "FIXTURE2023",
        "--data-root",
        str(data_root),
        "--dated",
        "20230214_120000",
    )
    assert p.returncode == 0, p.stdout + p.stderr
    doc = json.loads(p.stdout)
    assert doc["ok"] is True
    assert doc["lab_ok_conaf"] is False
    assert doc["event_id"] == "CL_CONAF_FIXTURE2023"
    assert doc["product_rails_untouched"] is True
    pack = data_root / "cl" / "CL_CONAF_FIXTURE2023"
    ok, reason = source_pack_ready(pack)
    assert ok is True, reason
    meta = json.loads((pack / "meta.json").read_text(encoding="utf-8"))
    assert meta["class"] == "ml_weak"
    assert meta["lab_ok_conaf"] is False
    if CONAF_SEND_STATUS.is_file():
        status = json.loads(CONAF_SEND_STATUS.read_text(encoding="utf-8"))
        assert (status.get("rails") or {}).get("lab_ok_conaf") is False


def test_conaf_ingest_missing_vector_exit1(tmp_path: Path) -> None:
    p = _run(
        "ingest_conaf_perimeters.py",
        "--vector",
        str(tmp_path / "no.shp"),
        "--event",
        "X",
        "--data-root",
        str(tmp_path / "latam_au"),
    )
    assert p.returncode == 1


def test_conaf_ingest_usage_exit2(tmp_path: Path) -> None:
    p = _run("ingest_conaf_perimeters.py")
    assert p.returncode == 2


def test_cession_evidence_rules(tmp_path: Path) -> None:
    ok, reason = cession_evidence_ok(None)
    assert ok is False
    missing = tmp_path / "no.pdf"
    ok, reason = cession_evidence_ok(missing)
    assert ok is False
    tiny = tmp_path / "tiny.txt"
    tiny.write_text("x", encoding="utf-8")
    ok, _ = cession_evidence_ok(tiny)
    assert ok is False
    good = tmp_path / "oficio.txt"
    good.write_text("CONAF written cession for lab use of perimeters.\n", encoding="utf-8")
    ok, reason = cession_evidence_ok(good)
    assert ok is True
    assert reason == "ok"


def test_new_cems_specs_in_all_pack_specs() -> None:
    assert ALL_PACK_SPECS["BO_EMSR765"]["country"] == "BO"
    assert ALL_PACK_SPECS["MX_EMSR717"]["country"] == "MX"


def test_all_skips_ready_pack_without_s2_or_weather(tmp_path: Path) -> None:
    """--all must skip label-ready packs that lack S2 / weather / DEM (exit 0)."""
    pytest.importorskip("rasterio")
    pack = _mini_pack(tmp_path)
    assert source_pack_ready(pack)[0] is True
    assert not list((pack / "eo").glob("*.tif")) if (pack / "eo").is_dir() else True
    data_root = tmp_path / "latam_au"
    warp = _run(
        "warp_latam_au_s2_to_cems.py",
        "--all",
        "--data-root",
        str(data_root),
        "--report-root",
        str(tmp_path / "warp_rep"),
    )
    assert warp.returncode == 0, warp.stdout + warp.stderr
    wsum = json.loads((tmp_path / "warp_rep" / "warp_summary.json").read_text(encoding="utf-8"))
    perth = next(p for p in wsum["packs"] if p["event_id"] == "AU_EMSR500_PERTH")
    assert perth.get("skipped") is True
    assert perth.get("ok") is True
    assert perth.get("nbr_vs_cems_iou") is None
    assert perth.get("error") == "no_s2_eo"

    fill = _run(
        "fill_latam_au_ndws_covariates.py",
        "--all",
        "--skip-dem-fetch",
        "--data-root",
        str(data_root),
        "--report",
        str(tmp_path / "fill_report.json"),
    )
    assert fill.returncode == 0, fill.stdout + fill.stderr
    fdoc = json.loads((tmp_path / "fill_report.json").read_text(encoding="utf-8"))
    fperth = next(p for p in fdoc["packs"] if p["event_id"] == "AU_EMSR500_PERTH")
    assert fperth.get("skipped") is True
    assert fperth.get("ok") is True
    assert fperth.get("ready_for_real_proxy_ndws") is False
    assert not (pack / "covariates" / "PROVENANCE.json").is_file()


def test_conaf_dated_traversal_exits_1(tmp_path: Path) -> None:
    gj = tmp_path / "perim.geojson"
    gj.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-72.7, -37.52],
                                    [-72.65, -37.52],
                                    [-72.65, -37.48],
                                    [-72.7, -37.48],
                                    [-72.7, -37.52],
                                ]
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    data_root = tmp_path / "latam_au"
    outside = tmp_path / "escaped.tif"
    p = _run(
        "ingest_conaf_perimeters.py",
        "--vector",
        str(gj),
        "--event",
        "TRAVERSE",
        "--data-root",
        str(data_root),
        "--dated",
        "../../../escaped",
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "dated_path_unsafe" in (p.stdout + p.stderr)
    assert not outside.is_file()
    pack = data_root / "cl" / "CL_CONAF_TRAVERSE"
    if pack.exists():
        assert not list(pack.rglob("*.tif"))
    # no writes under tmp_path except the input geojson
    stray = [q for q in tmp_path.rglob("*.tif") if q != gj]
    assert stray == []
    mod = _load_script("ingest_conaf_perimeters.py")
    ok, reason = mod.sanitize_dated("20230214_120000")
    assert ok == "20230214_120000"
    assert reason == "ok"
    bad, breason = mod.sanitize_dated("..\\..\\x")
    assert bad is None
    assert "unsafe" in breason


# --- Honesty rails (product stamps + live complete_proxy report) ---

COMPLETE_PROXY_REPORT = (
    ROOT / "outputs" / "ml_eval" / "latam_au_complete_iou" / "complete_proxy_model_iou.json"
)
PRODUCT_STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
CONAF_SEND_STATUS = ROOT / "docs" / "data_campaigns" / "conaf_send" / "send_status.json"


def test_product_stamp_go_q_partial_freeze_intact() -> None:
    """Drive the shipped checker + stamp: GO_Q stays partial, KEEP stays false."""
    stamp = json.loads(PRODUCT_STAMP.read_text(encoding="utf-8"))
    assert stamp.get("GO_Q") == "partial"
    assert stamp.get("GO_Q") not in {"complete", "true", True, "full"}
    assert (stamp.get("rails") or {}).get("tobarra_keep_reopen") is False
    report = _run("check_release_flags.py", "--json")
    assert report.returncode == 0, report.stdout + report.stderr
    doc = json.loads(report.stdout)
    assert doc["status"] == "PASS"
    assert doc["invariants"]["go_q"] == "partial_until_human_acta"
    assert doc["invariants"]["tobarra_keep_reopen"] is False
    by_id = {c["id"]: c for c in doc["checks"]}
    assert by_id["go_q_stamp_not_complete"]["ok"] is True
    assert by_id["tobarra_keep_reopen_false"]["ok"] is True
    assert "complete" not in str(stamp.get("GO_Q")).lower()


def test_product_lab_ok_conaf_false() -> None:
    """Product CONAF rail stays false; ingest must not flip send_status."""
    if not CONAF_SEND_STATUS.is_file():
        pytest.skip("private CONAF correspondence state is not distributed")
    status = json.loads(CONAF_SEND_STATUS.read_text(encoding="utf-8"))
    assert (status.get("rails") or {}).get("lab_ok_conaf") is False
    rights = (ROOT / "docs" / "data_campaigns" / "LATAM_AU_RIGHTS.md").read_text(encoding="utf-8")
    assert "lab_ok_conaf:** `false`" in rights.replace(" ", "") or "**lab_ok_conaf:** `false`" in rights
    stamp = json.loads(PRODUCT_STAMP.read_text(encoding="utf-8"))
    # product stamp must not grow a true lab_ok_conaf rail
    assert stamp.get("lab_ok_conaf") in (None, False)


def test_complete_proxy_report_emsr715_not_fep_dressed() -> None:
    """Live eval: EMSR715 stays listed; FEP→DEL is not a usable growth pair; mean ≠ 0.85."""
    if not COMPLETE_PROXY_REPORT.is_file():
        pytest.skip("local complete-proxy evaluation artifact is not distributed")
    doc = json.loads(COMPLETE_PROXY_REPORT.read_text(encoding="utf-8"))
    assert doc.get("schema") == "wfd_latam_au_complete_proxy_model_iou_v1"
    packs = {p.get("event_id"): p for p in doc.get("packs") or []}
    assert "CL_EMSR715_VALPARAISO" in packs, "EMSR715 must stay in the report"
    emsr715 = packs["CL_EMSR715_VALPARAISO"]
    pairs = list(emsr715.get("pairs") or emsr715.get("excluded") or [])
    fep_rows = [
        p
        for p in pairs
        if "20240204" in str(p.get("from") or "") or p.get("from_kind") == "first_estimate"
    ]
    assert fep_rows, "FEP pair must remain visible (not deleted to hide a low score)"
    for row in fep_rows:
        assert row.get("pair_class") != "usable"
        assert row.get("pair_class") in {
            "incompatible_product_kind",
            "static_label_copy",
            "too_short_delta",
        }
    assert int(emsr715.get("n_pairs_used") or 0) == 0
    assert emsr715.get("complete_proxy_model_iou") is None
    mean = doc.get("mean_complete_proxy_model_iou")
    assert mean is not None
    assert not (0.80 <= float(mean) <= 0.90), f"cross-pack mean must not be the dressed ~0.85, got {mean}"
    claims = " ".join(str(x) for x in (doc.get("not_claims") or []))
    assert "not sealed transfer IoU" in claims
    assert "not GO_Q complete" in claims
    assert "not FREEZE lift" in claims
    rails = doc.get("rails") or {}
    assert rails.get("go_q") == "partial"
    assert rails.get("freeze_intact") is True
    assert rails.get("no_retrain") is True


def test_campaign_docs_do_not_sell_dressed_085_as_current() -> None:
    """Status surfaces must not present the old Perth+Nacimiento ~0.85 as the live mean."""
    scorecard = (ROOT / "docs" / "SCORECARD_1M_GO_LATAM_2026-08-13.md").read_text(encoding="utf-8")
    assert "mean **~0.85** on Perth+Nacimiento only" not in scorecard
    assert "not" in scorecard.lower() and "transfer" in scorecard.lower()
    handoff_path = ROOT / "docs" / "HANDOFF_1M_TO_MES3_2026-08-13.md"
    if not handoff_path.is_file():
        pytest.skip("local handoff document is not distributed")
    handoff = handoff_path.read_text(encoding="utf-8")
    assert "complete_proxy IoU ~0.85" not in handoff
