"""Tests for LOFO multi-fire scoreboard (no ECE retune).

Architecture contracts (product ROI — no retrain)
-------------------------------------------------
* Single path: product_facade + rank_reject_protocol
  (features → calibrator → rank/reject → scorecard).
* VAL-only thr; default surface iter1_reject_only.
* Dual rails lab vs field_ops (IoU ≠ ROS, ml_product_go false, fusion OFF).
* Multi-fire honesty LOFO/W3 first-class.
* Refuse same-holdout ECE thrash + Tobarra KEEP reopen of KILL weights.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.ml.lab_lofo_board import (
    build_lofo_scoreboard,
    classify_fold_honesty,
    collect_lofo_board,
    format_lofo_board_human,
    summarize_lofo_board,
)
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    ITER1_LOCKED_REJECT_THR,
    ProductFacadeError,
    RECOMMENDED_LAB_SURFACE,
    refuse_dead_path,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    refuse_dead_protocol_path,
)

ROOT = Path(__file__).resolve().parents[1]

_PIPELINE = "features→calibrator→rank/reject→scorecard"
_FACADE = "wildfire_front.ml.product_facade"


def test_collect_and_summarize_from_repo():
    rows = collect_lofo_board(ROOT / "outputs" / "ml_eval" / "lofo_v1")
    if not rows:
        return
    assert all("fold" in r for r in rows)
    s = summarize_lofo_board(rows)
    assert s["n_folds"] == len(rows)
    assert s["model_iou_min"] <= s["model_iou_mean"] <= s["model_iou_max"]
    assert s.get("weakest_fold")


def test_build_pack_rails():
    pack = build_lofo_scoreboard(ROOT)
    assert pack["schema"] == "wfd_ml_lofo_board_v1"
    rails = pack["rails"]
    assert rails["ml_product_go"] is False
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails["lofo_is_not_u1_ece"] is True
    assert rails.get("iou_is_not_ros") is True
    assert rails.get("field_ops_ml_live_fusion") == "OFF"
    assert rails.get("val_only_threshold_tune") is True or rails.get(
        "val_only_threshold_selection"
    ) is True
    assert rails.get("recommended_lab_surface") == "iter1_reject_only"
    assert rails.get("freeze_iter1_reject") is True
    assert rails.get("tobarra_keep_reopen") is False
    assert float(rails["locked_reject_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    # product_facade + rank_reject_protocol thr/report path (VAL iter1 freeze)
    assert pack.get("product_facade") == _FACADE
    assert pack.get("pipeline") == _PIPELINE
    assert isinstance(pack.get("rank_reject_protocol"), dict)
    rr = pack["rank_reject_protocol"]
    assert rr.get("locked_reject_thr") is not None
    assert float(rr["locked_reject_thr"]) == pytest.approx(float(ITER1_LOCKED_REJECT_THR))
    assert rr.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
    assert rr.get("pipeline") == _PIPELINE
    assert rr.get("freeze_iter1_reject") is True
    assert rr.get("stop_ece_thrash_on_same_test") is True
    assert rr.get("ml_product_go") is False
    assert rr.get("field_ops_allow_ml_live_in_fusion") is False
    assert isinstance(pack.get("frozen_thr_report"), dict)
    # Multi-fire honesty first-class (LOFO / W3 / Tobarra KILL — not ad-hoc)
    mf = pack.get("multi_fire_honesty")
    assert isinstance(mf, dict)
    assert mf.get("do_not_reopen_tobarra_keep") is True
    assert mf.get("do_not_universalize_u1") is True
    tob = mf.get("tobarra") or {}
    assert tob.get("keep_verdict") == "KILL" or tob.get("verdict") == "KILL"
    assert tob.get("reopen_same_recipe") is False
    assert "w3_external" in mf or "w3_external_on_disk" in mf
    v = pack.get("verdict") or {}
    assert v.get("recommended_lab_surface") == "iter1_reject_only"
    assert v.get("freeze_iter1_reject") is True
    assert v.get("ml_product_go") is False
    assert v.get("field_ops_fusion") == "OFF"
    assert v.get("pipeline") == _PIPELINE
    if pack["summary"].get("n_folds", 0) >= 1:
        assert pack["verdict"]["lofo_board_built"] is True
        text = format_lofo_board_human(pack)
        assert "LOFO" in text or "lofo" in text.lower()
        assert "OFF" in text


def test_classify_fold_honesty_tobarra_hard_keep_forbidden():
    """Tobarra-class LOFO fold is hard_transfer; KEEP reopen forbidden via facade tag."""
    h = classify_fold_honesty("TOBARRA")
    assert h["hard"] is True
    assert h["role"] == "hard_transfer"
    assert h.get("in_pack") is False
    tag = h.get("facade_tag") or {}
    assert tag.get("keep_reopen") is False
    note = (h.get("note") or "").lower()
    assert "keep" in note or "hard" in note


def test_refuse_tobarra_keep_and_ece_thrash_dead_paths():
    """Architecture refuse: ECE thrash same-holdout + Tobarra KEEP reopen of KILL weights."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        assert dead in DEAD_PATHS or dead in DEAD_PROTOCOL_PATHS
        with pytest.raises(ProductFacadeError):
            refuse_dead_path(dead)
        with pytest.raises(ValueError):
            refuse_dead_protocol_path(dead)


def test_lofo_script(tmp_path):
    from scripts import run_lab_ml_loop_v34_lofo_board as mod

    rc = mod.main(["--repo", str(ROOT), "--out-dir", str(tmp_path), "--no-md"])
    data = json.loads((tmp_path / "lab_loop_v34_lofo_board_latest.json").read_text(encoding="utf-8"))
    assert data["iteration"] == 9
    assert data["rails"]["ml_product_go"] is False
    assert data["rails"].get("field_ops_allow_ml_live_in_fusion") is False
    # Runner surfaces facade + rank_reject thr/report (not board-only dual path)
    assert data.get("product_facade") == _FACADE or (
        data.get("verdict") or {}
    ).get("product_facade") == _FACADE
    assert isinstance(data.get("rank_reject_protocol"), dict)
    assert data["rank_reject_protocol"].get("locked_reject_thr") is not None
    assert float(data["rank_reject_protocol"]["locked_reject_thr"]) == pytest.approx(
        float(ITER1_LOCKED_REJECT_THR)
    )
    assert (data.get("verdict") or {}).get("recommended_lab_surface") == "iter1_reject_only"
    assert (data.get("verdict") or {}).get("freeze_iter1_reject") is True
    assert (data.get("verdict") or {}).get("ece_thrash_reopen") is False
    assert (data.get("verdict") or {}).get("tobarra_keep_reopen") is False
    assert (data.get("verdict") or {}).get("dead_thrash_closed") is True
    assert isinstance(data.get("frozen_thr_report"), dict)
    assert isinstance(data.get("architecture_lofo_board"), dict)
    arch = data["architecture_lofo_board"]
    assert arch.get("pipeline") == _PIPELINE
    assert arch.get("ml_product_go") is False
    assert arch.get("field_ops_ml_live_fusion") == "OFF"
    assert arch.get("product_facade") == _FACADE
    assert arch.get("tobarra_keep_reopen") is False
    assert arch.get("stop_ece_thrash_on_same_test") is True
    # Multi-fire honesty first-class on runner payload
    mf = data.get("multi_fire_honesty")
    assert isinstance(mf, dict)
    assert mf.get("do_not_reopen_tobarra_keep") is True
    tob = mf.get("tobarra") or {}
    if tob:
        assert tob.get("keep_verdict") == "KILL" or tob.get("verdict") == "KILL"
        assert tob.get("reopen_same_recipe") is False
    latest = json.loads((tmp_path / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "9_lofo_board" in latest["iterations"]
    assert latest["summary"].get("recommended_lab_surface") == "iter1_reject_only"
    assert latest["summary"].get("dead_thrash_closed") is True
    assert latest["summary"].get("tobarra_keep_reopen") is False
    assert latest["summary"].get("ece_thrash_reopen") is False
    assert isinstance(latest["summary"].get("multi_fire_honesty"), dict)
    assert latest["summary"]["multi_fire_honesty"].get("do_not_reopen_tobarra_keep") is True
    if data["board"]["verdict"]["lofo_board_built"]:
        assert rc == 0
    else:
        assert rc == 2
