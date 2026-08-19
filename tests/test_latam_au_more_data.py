"""More-data frozen-decode path: CLI exits, knobs, and claim rails."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
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


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def _touch_npz(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04not-a-real-npz")


def _write_holdout_npz(path: Path, channels: int = 17) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    seq = np.zeros((1, channels, 8, 8), dtype=np.float32)
    prev = np.zeros((8, 8), dtype=np.float32)
    prev[3:5, 3:5] = 1.0
    tgt = prev.copy()
    tgt[2, 2] = 1.0
    np.savez(path, sequence=seq, current_fire=prev, target_fire=tgt)


def _write_rcda_sample(root: Path, channels: int = 12) -> Path:
    inp = root / "inputs"
    inp.mkdir(parents=True)
    arr = np.zeros((channels, 8, 8), dtype=np.float32)
    dest = inp / "UID_FIRE_1.npy"
    np.save(dest, arr)
    return dest


def _write_caldor_meta(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "meta.json").write_text(
        json.dumps(
            {
                "schema": "wfd_firebench_caldor_label_pack_v1",
                "event_id": "US_FIREBENCH_CALDOR_2021",
                "n_observations": 2,
                "n_pairs_12_to_36h": 1,
            }
        ),
        encoding="utf-8",
    )


def test_more_data_frozen_knobs_match_complete_proxy() -> None:
    more = _load_script("run_latam_au_more_data_iou.py")
    complete = _load_script("run_latam_au_complete_model_iou.py")
    assert more.OOD_GROWTH_THRESHOLD == 0.90
    assert more.GROWTH_RING_CONNECTIVITY == 8
    assert more.GROWTH_RING_MIN_NEIGHBORS == 1
    assert more.OOD_GROWTH_THRESHOLD == complete.OOD_GROWTH_THRESHOLD
    assert more.GROWTH_RING_CONNECTIVITY == complete.GROWTH_RING_CONNECTIVITY
    assert more.GROWTH_RING_MIN_NEIGHBORS == complete.GROWTH_RING_MIN_NEIGHBORS
    ring = more.fire_growth_ring(np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 0.0]]))
    assert int(ring.sum()) == 8
    parser = more.build_parser()
    flags = {opt for action in parser._actions for opt in action.option_strings}
    assert "--growth-thr" not in flags
    assert "--no-growth-ring" not in flags


def test_default_more_data_catalog_excludes_official_latam_four() -> None:
    more = _load_script("run_latam_au_more_data_iou.py")
    official = set(more.OFFICIAL_LATAM_COMPLETE_PROXY_IDS)
    assert official == {
        "AU_EMSR500_PERTH",
        "CL_EMSR647_NACIMIENTO",
        "AU_EMSR408_NSW",
        "CL_EMSR715_VALPARAISO",
    }
    assert official.isdisjoint(more.DEFAULT_PACK_IDS)
    assert "CL_EMSR715_VALPARAISO" not in more.DEFAULT_PACK_IDS


def test_extra_family_mean_never_mixes_fep_gra_or_official_latam() -> None:
    more = _load_script("run_latam_au_more_data_iou.py")
    packs = [
        {
            "pack_id": "CL_EMSR715_VALPARAISO",
            "family": "extra_latam_cems",
            "pairs": [
                {
                    "pair_class": "incompatible_product_kind",
                    "complete_proxy_model_iou": 0.088,
                },
                {
                    "pair_class": "usable",
                    "complete_proxy_model_iou": 0.41,
                },
            ],
        },
        {
            "pack_id": "BO_EMSR765",
            "family": "extra_latam_cems",
            "pairs": [
                {
                    "pair_class": "incompatible_product_kind",
                    "complete_proxy_model_iou": 0.99,
                },
                {
                    "pair_class": "usable",
                    "complete_proxy_model_iou": 0.25,
                },
                {
                    "pair_class": "usable",
                    "complete_proxy_model_iou": None,
                },
            ],
        },
        {
            "pack_id": "CLM_HOLDOUT_V1_TEST",
            "family": "clm_holdout_npz",
            "model_iou": 0.857,
            "pairs": [],
        },
        {
            "pack_id": "US_FIREBENCH_CALDOR_2021",
            "family": "firebench_caldor",
            "model_iou": None,
            "pairs": [{"pair_class": "usable", "complete_proxy_model_iou": 0.5}],
        },
    ]
    mean = more.extra_family_mean_model_ious(packs)
    assert mean == pytest.approx(0.25)
    assert mean != pytest.approx(0.088)
    assert classify_temporal_pair(
        delta_hours=44.8,
        label_mask_iou=0.56,
        prev_kind="first_estimate",
        next_kind="delineation",
    ) == "incompatible_product_kind"
    assert more.holdout_mean_model_iou(packs) == pytest.approx(0.857)
    # Families stay separate: no mixed mean helper returns a blended number.
    assert more.extra_family_mean_model_ious(packs) != more.holdout_mean_model_iou(packs)


def test_more_data_missing_weights_exit1(tmp_path: Path) -> None:
    holdout = tmp_path / "holdout"
    _touch_npz(holdout / "patch_00000.npz")
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "CLM_HOLDOUT_V1_TEST",
        "--holdout-root",
        str(holdout),
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 1, p.stdout + p.stderr
    text = (p.stderr + p.stdout).lower()
    assert "missing weights" in text
    assert "invented" in text
    assert not (tmp_path / "out" / "more_data_eval.json").is_file()


def test_more_data_missing_data_exit3(tmp_path: Path) -> None:
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "BO_EMSR765",
        "--data-root",
        str(tmp_path / "empty_latam"),
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 3, p.stdout + p.stderr
    assert "missing data" in (p.stderr + p.stdout).lower()
    assert not (tmp_path / "out" / "more_data_eval.json").is_file()


def test_more_data_unknown_pack_exit3(tmp_path: Path) -> None:
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "NOT_A_PACK",
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 3, p.stdout + p.stderr
    assert "unknown pack" in (p.stderr + p.stdout).lower()


def test_more_data_incompatible_schema_require_model_iou_exit2(tmp_path: Path) -> None:
    rcda = tmp_path / "rcda"
    _write_rcda_sample(rcda)
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "RCDA_NET",
        "--rcda-root",
        str(rcda),
        "--require-model-iou",
        "--weights",
        str(tmp_path / "no_weights.pt"),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 2, p.stdout + p.stderr
    text = (p.stderr + p.stdout).lower()
    assert "incompatible" in text
    assert not (tmp_path / "out" / "more_data_eval.json").is_file()


def test_more_data_caldor_require_model_iou_exit2(tmp_path: Path) -> None:
    caldor = tmp_path / "caldor"
    _write_caldor_meta(caldor)
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "US_FIREBENCH_CALDOR_2021",
        "--caldor-root",
        str(caldor),
        "--require-model-iou",
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 2, p.stdout + p.stderr
    assert "incompatible" in (p.stderr + p.stdout).lower()


def test_more_data_refuses_official_latam_pack(tmp_path: Path) -> None:
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "CL_EMSR715_VALPARAISO",
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 3, p.stdout + p.stderr
    assert "official" in (p.stderr + p.stdout).lower()


def test_more_data_rcda_and_caldor_not_sold_as_product(tmp_path: Path) -> None:
    rcda = tmp_path / "rcda"
    _write_rcda_sample(rcda)
    caldor = tmp_path / "caldor"
    _write_caldor_meta(caldor)
    out = tmp_path / "out"
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "RCDA_NET",
        "--pack",
        "US_FIREBENCH_CALDOR_2021",
        "--rcda-root",
        str(rcda),
        "--caldor-root",
        str(caldor),
        "--out-root",
        str(out),
        "--weights",
        str(tmp_path / "unused.pt"),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    doc = json.loads((out / "more_data_eval.json").read_text(encoding="utf-8"))
    assert doc["schema"] == "wfd_more_data_frozen_decode_v1"
    assert doc["product_id"] == "extra_data_frozen_decode"
    assert doc["product_id"] != "clm_ensemble_v34"
    assert doc["sold_as_clm_ensemble_v34"] is False
    assert doc["sold_as_go_q"] is False
    assert doc["go_q"] == "partial"
    assert doc["lab_ok_conaf"] is False
    assert doc["mixed_family_mean_model_iou"] is None
    assert doc["latam_complete_proxy_mean_includes_extra"] is False
    assert doc["latam_complete_proxy_mean_includes_fep_gra"] is False
    assert doc["growth_threshold"] == 0.90
    assert doc["growth_ring_connectivity"] == 8
    assert doc["min_fire_neighbors"] == 1
    by_id = {row["pack_id"]: row for row in doc["packs"]}
    assert set(by_id) == {"RCDA_NET", "US_FIREBENCH_CALDOR_2021"}
    for pack_id in ("RCDA_NET", "US_FIREBENCH_CALDOR_2021"):
        row = by_id[pack_id]
        assert row["model_iou"] is None
        assert row["complete_proxy_model_iou"] is None
        assert row["sold_as_clm_ensemble_v34"] is False
        assert row["sold_as_go_q"] is False
        assert row["skip_class"] == "incompatible_schema"
    assert by_id["RCDA_NET"]["sample"]["shape"][0] == 12
    assert doc["caldor_copy_is_not_catalog_08963"] is True
    assert by_id["US_FIREBENCH_CALDOR_2021"]["caldor_copy_is_not_catalog_08963"] is True
    assert by_id["US_FIREBENCH_CALDOR_2021"]["catalog_holdout_iou_08963_used"] is False
    scorecard = (out / "SCORECARD.md").read_text(encoding="utf-8")
    assert "not catalog 0.8963" in scorecard
    assert "not** `clm_ensemble_v34`" in scorecard or "not `clm_ensemble_v34`" in scorecard
    official = json.loads(
        (ROOT / "outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json").read_text(
            encoding="utf-8"
        )
    )
    assert official["n_pairs_used"] == 4
    assert official["schema"] == "wfd_latam_au_complete_proxy_model_iou_v1"


def test_more_data_does_not_write_official_json(tmp_path: Path) -> None:
    more = _load_script("run_latam_au_more_data_iou.py")
    assert more.DEFAULT_OUT.name == "more_data"
    assert more.OFFICIAL_JSON.name == "complete_proxy_model_iou.json"
    assert more.DEFAULT_OUT != more.OFFICIAL_JSON.parent or more.DEFAULT_OUT.name == "more_data"
    official = ROOT / "outputs/ml_eval/mega_goal_model/complete_proxy_model_iou.json"
    before = official.read_bytes()
    rcda = tmp_path / "rcda"
    _write_rcda_sample(rcda)
    p = _run(
        "run_latam_au_more_data_iou.py",
        "--pack",
        "RCDA_NET",
        "--rcda-root",
        str(rcda),
        "--out-root",
        str(tmp_path / "out"),
    )
    assert p.returncode == 0, p.stdout + p.stderr
    assert official.read_bytes() == before


def test_live_more_data_artifact_does_not_sell_caldor_rcda_as_product() -> None:
    path = ROOT / "outputs/ml_eval/mega_goal_model/more_data/more_data_eval.json"
    if not path.is_file():
        pytest.skip("live more-data artifact not written")
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["product_id"] == "extra_data_frozen_decode"
    assert doc["sold_as_clm_ensemble_v34"] is False
    assert doc["go_q"] == "partial"
    assert doc["lab_ok_conaf"] is False
    assert doc["mixed_family_mean_model_iou"] is None
    assert doc["latam_complete_proxy_mean_includes_fep_gra"] is False
    assert doc["growth_threshold"] == 0.90
    assert doc["min_fire_neighbors"] == 1
    assert doc["growth_ring_connectivity"] == 8
    by_id = {row["pack_id"]: row for row in doc["packs"]}
    for pack_id in ("US_FIREBENCH_CALDOR_2021", "RCDA_NET"):
        if pack_id not in by_id:
            continue
        assert by_id[pack_id]["model_iou"] is None
        assert by_id[pack_id]["sold_as_clm_ensemble_v34"] is False
        assert by_id[pack_id]["sold_as_go_q"] is False
    if "US_FIREBENCH_CALDOR_2021" in by_id:
        assert by_id["US_FIREBENCH_CALDOR_2021"].get("caldor_copy_is_not_catalog_08963") is True
    if "CL_EMSR715_VALPARAISO" in by_id:
        raise AssertionError("official EMSR715 must not enter more-data packs")
    holdout = doc.get("clm_holdout_mean_model_iou")
    if holdout is not None:
        assert holdout != pytest.approx(0.857, abs=1e-4)
        assert holdout != pytest.approx(0.8963, abs=1e-4)


def test_more_data_label_pairs_mark_fep_gra_and_null_model_iou(tmp_path: Path) -> None:
    more = _load_script("run_latam_au_more_data_iou.py")
    prev = np.zeros((4, 4), dtype=np.float32)
    prev[1:3, 1:3] = 1.0
    nxt = prev.copy()
    nxt[0, 0] = 1.0

    def _load(_path: Path, mask: np.ndarray = prev) -> np.ndarray:
        return mask if "t0" in Path(_path).name else nxt

    recs = [
        {
            "path": tmp_path / "t0.tif",
            "name": "t0.tif",
            "dt": None,
            "delivery_utc": "2024-02-04T20:02:40Z",
            "kind": "first_estimate",
        },
        {
            "path": tmp_path / "t1.tif",
            "name": "t1.tif",
            "dt": None,
            "delivery_utc": "2024-02-06T16:52:36Z",
            "kind": "delineation",
        },
    ]
    rows = more.pair_rows_from_labels(recs, load_fn=lambda p: _load(p))
    assert len(rows) == 1
    assert rows[0]["pair_class"] == "incompatible_product_kind"
    assert rows[0]["complete_proxy_model_iou"] is None
    mean = more.extra_family_mean_model_ious(
        [{"pack_id": "MX_EMSR717", "family": "extra_latam_cems", "pairs": rows}]
    )
    assert mean is None
