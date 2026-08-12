"""Tests for lab freeze handoff pack (rails honest, no field promote).

Architecture contracts (product ROI — no retrain)
-------------------------------------------------
* Single path: product_facade + rank_reject_protocol
  (features → calibrator → rank/reject → scorecard).
* VAL-only thr; default surface iter1_reject_only.
* Dual rails lab vs field_ops (IoU ≠ ROS, ml_product_go true, fusion OFF).
* Multi-fire honesty LOFO/W3 first-class.
* Refuse same-holdout ECE thrash + Tobarra KEEP reopen of KILL weights.
* Freeze script residual must stamp facade / architecture_freeze (not dual path).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.ml.lab_freeze import build_lab_freeze_pack, format_lab_freeze_human
from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    refuse_dead_path,
)
from wildfire_front.ml.rank_reject_protocol import (
    DEAD_PROTOCOL_PATHS,
    refuse_dead_protocol_path,
)

ROOT = Path(__file__).resolve().parents[1]

_PIPELINE = "features→calibrator→rank/reject→scorecard"
_FACADE = "wildfire_front.ml.product_facade"
_FACADE_CLASS = "ClmEnsembleV34Facade"
_RANK_REJECT = "wildfire_front.ml.rank_reject_protocol"


def test_build_freeze_from_repo():
    pack = build_lab_freeze_pack(ROOT)
    assert pack["schema"] == "wfd_ml_lab_freeze_v1"
    # Dual-product rails (lab vs field_ops)
    rails = pack["rails"]
    assert rails["ml_product_go"] is True
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails.get("field_ops_ml_live_fusion") == "OFF"
    assert rails.get("iou_is_not_ros") is True
    assert (
        rails.get("val_only_threshold_tune") is True
        or rails.get("val_only_threshold_selection") is True
    )
    assert rails.get("recommended_lab_surface") == RECOMMENDED_LAB_SURFACE == "iter1_reject_only"
    assert rails.get("freeze_iter1_reject") is True
    assert rails.get("stop_ece_thrash_on_same_test") is True
    assert rails.get("tobarra_keep_reopen") is False
    assert float(rails["locked_reject_thr"]) == pytest.approx(
        float(ITER1_LOCKED_REJECT_THR), rel=0, abs=1e-6
    )
    # product_facade + rank_reject single path (VAL iter1 freeze)
    assert pack.get("product_facade") == _FACADE
    assert pack.get("facade_class") == _FACADE_CLASS
    assert pack.get("pipeline") == _PIPELINE
    assert rails.get("product_facade") == _FACADE
    assert rails.get("pipeline") == _PIPELINE
    assert rails.get("rank_reject_protocol") == _RANK_REJECT
    assert isinstance(pack.get("rank_reject_protocol"), dict)
    rr = pack["rank_reject_protocol"]
    assert (
        rr.get("surface") == "iter1_reject_only"
        or rr.get("recommended_lab_surface") == "iter1_reject_only"
    )
    assert rr.get("reject_thr") is not None or rr.get("locked_reject_thr") is not None
    thr_rr = float(rr.get("reject_thr") or rr.get("locked_reject_thr"))
    assert thr_rr == pytest.approx(float(ITER1_LOCKED_REJECT_THR), rel=0, abs=1e-6)
    assert isinstance(pack.get("clm_ensemble_surface"), dict)
    surf = pack["clm_ensemble_surface"]
    assert surf.get("product_facade") == _FACADE
    assert surf.get("pipeline") == _PIPELINE
    assert surf.get("recommended_lab_surface") == "iter1_reject_only"
    assert float(surf["locked_reject_thr"]) == pytest.approx(
        float(rails["locked_reject_thr"]), rel=0, abs=1e-6
    )
    # Claims / checks — freeze ≠ field; dead thrash closed
    assert pack["claims"]["field_product"] is False
    assert pack["claims"]["ece_fixed"] is False
    assert pack["claims"]["iou_is_ros"] is False
    assert pack["claims"]["recommended_lab_surface"] == "iter1_reject_only"
    assert pack["claims"].get("dead_thrash_closed") is True
    assert pack["checks"]["ml_product_go_true"] is True
    assert pack["checks"]["field_ops_fusion_off"] is True
    assert pack["checks"].get("dead_thrash_not_required_for_freeze") is True
    assert pack["checks"].get("dead_paths_refused") is True
    assert pack["checks"].get("facade_rails_honest") is True
    assert pack["checks"].get("stop_ece_thrash") is True
    dps = pack.get("dead_paths_status") or {}
    assert dps.get("closed") is True
    assert dps.get("via") == "product_facade.refuse_dead_path"
    # Multi-fire honesty first-class (LOFO / W3 / Tobarra KILL — not ad-hoc)
    mf = pack.get("multi_fire_honesty")
    assert isinstance(mf, dict)
    assert mf.get("do_not_reopen_tobarra_keep") is True
    assert mf.get("do_not_universalize_u1") is True
    assert mf.get("lofo_w3_first_class") is True
    tob = mf.get("tobarra") or {}
    assert (
        tob.get("verdict") == "KILL"
        or tob.get("keep_verdict") == "KILL"
        or tob.get("class") == "hard"
    )
    assert "w3_external" in mf
    v = pack.get("verdict") or {}
    assert v.get("recommended_lab_surface") == "iter1_reject_only"
    assert v.get("ml_product_go") is bool(v.get("lab_usable_freeze"))
    assert v.get("field_product") is False
    assert v.get("dead_thrash_closed") is True
    assert v.get("product_facade") == _FACADE
    assert v.get("pipeline") == _PIPELINE
    # Loop board: iters 2–3 marked dead thrash (not freeze gates)
    board = pack.get("loop_board") or []
    dead_names = {row.get("name") for row in board if row.get("dead_path")}
    assert "ece_posthoc" in dead_names
    assert "refit" in dead_names
    # With full loop artifacts present, freeze should pass
    text = format_lab_freeze_human(pack)
    assert "lab_usable_freeze" in text
    assert "OFF" in text
    assert "Do not" in text or "do not" in text.lower()


def test_refuse_tobarra_keep_and_ece_thrash_dead_paths():
    """Architecture refuse: ECE thrash same-holdout + Tobarra KEEP reopen of KILL weights."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
    ):
        assert dead in DEAD_PATHS
        assert dead in DEAD_PROTOCOL_PATHS
        with pytest.raises(ProductFacadeError):
            refuse_dead_path(dead)
        with pytest.raises(ValueError):
            refuse_dead_protocol_path(dead)


def test_freeze_script_isolated(tmp_path):
    # Minimal tree that fails freeze (missing artifacts); residual still stamps facade
    from scripts import run_lab_ml_loop_v34_freeze as mod

    rc = mod.main(["--repo", str(tmp_path), "--out-dir", str(tmp_path / "out"), "--no-md"])
    assert rc == 2  # not usable
    payload = json.loads(
        (tmp_path / "out" / "lab_loop_v34_freeze_latest.json").read_text(encoding="utf-8")
    )
    assert payload["iteration"] == 7
    assert payload["control_answer"] == "NO"
    assert payload["rails"]["ml_product_go"] is True
    assert payload["rails"].get("field_ops_allow_ml_live_in_fusion") is False
    assert payload["rails"].get("field_ops_ml_live_fusion") == "OFF"
    assert payload["rails"].get("iou_is_not_ros") is True
    assert payload["rails"].get("recommended_lab_surface") == "iter1_reject_only"
    assert payload["rails"].get("freeze_iter1_reject") is True
    assert payload["rails"].get("stop_ece_thrash_on_same_test") is True
    assert payload["rails"].get("tobarra_keep_reopen") is False
    assert payload["rails"].get("dead_thrash_closed") is True
    assert payload["rails"].get("product_facade") == _FACADE
    assert payload["rails"].get("pipeline") == _PIPELINE
    # Runner surfaces facade + architecture_freeze (not freeze-pack-only dual path)
    assert payload.get("product_facade") == _FACADE
    assert payload.get("pipeline") == _PIPELINE
    arch = payload.get("architecture_freeze")
    assert isinstance(arch, dict)
    assert arch.get("product_facade") == _FACADE
    assert arch.get("pipeline") == _PIPELINE
    assert arch.get("recommended_lab_surface") == "iter1_reject_only"
    assert arch.get("freeze_iter1_reject") is True
    assert arch.get("ml_product_go") is True
    assert arch.get("field_ops_ml_live_fusion") == "OFF"
    assert arch.get("iou_is_not_ros") is True
    assert arch.get("stop_ece_thrash_on_same_test") is True
    assert arch.get("tobarra_keep_reopen") is False
    assert arch.get("dead_thrash_closed") is True
    assert arch.get("dead_thrash_not_required_for_freeze") is True
    assert (
        isinstance(arch.get("rank_reject_protocol"), dict)
        or arch.get("rank_reject_protocol_mod") == _RANK_REJECT
    )
    assert (payload.get("verdict") or {}).get("dead_thrash_closed") is True
    assert (payload.get("verdict") or {}).get("freeze_iter1_reject") is True
    assert (payload.get("verdict") or {}).get("product_facade") == _FACADE
    assert (payload.get("verdict") or {}).get("field_ops_fusion") == "OFF"
    # Multi-fire honesty first-class on runner payload
    mf = payload.get("multi_fire_honesty")
    assert isinstance(mf, dict)
    assert mf.get("do_not_reopen_tobarra_keep") is True or (
        (mf.get("tobarra") or {}).get("reopen_same_recipe") is False
    )
    latest = json.loads((tmp_path / "out" / "lab_loop_v34_latest.json").read_text(encoding="utf-8"))
    assert "7_freeze" in latest["iterations"]
    assert latest["summary"].get("recommended_lab_surface") == "iter1_reject_only"
    assert latest["summary"].get("freeze_iter1_reject") is True
    assert latest["summary"].get("stop_ece_thrash_on_same_test") is True
    assert latest["summary"].get("tobarra_keep_reopen") is False
    assert latest["summary"].get("dead_thrash_not_required_for_freeze") is True
    assert latest["summary"].get("product_facade") == _FACADE
    assert latest["summary"].get("pipeline") == _PIPELINE
    assert isinstance(latest.get("architecture_freeze"), dict)
    assert latest["architecture_freeze"].get("product_facade") == _FACADE


def test_freeze_script_real_repo_if_artifacts():
    loop = ROOT / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_latest.json"
    if not loop.is_file():
        return
    import tempfile

    from scripts import run_lab_ml_loop_v34_freeze as mod

    with tempfile.TemporaryDirectory() as td:
        # Run against real repo inputs, write outputs to temp (still reads real loop)
        # Script uses --repo for pack inputs and --out-dir for writes
        out = Path(td)
        # Copy is not needed: build reads from repo; out-dir only for freeze+latest write
        rc = mod.main(["--repo", str(ROOT), "--out-dir", str(out), "--no-md"])
        # If real artifacts exist, expect usable
        payload = json.loads((out / "lab_loop_v34_freeze_latest.json").read_text(encoding="utf-8"))
        if payload["freeze_pack"]["checks"]["artifacts_complete"]:
            assert rc == 0
            assert payload["control_answer"] == "YES"
            assert payload["verdict"]["lab_usable_freeze"] is True
        assert payload["rails"]["field_ops_allow_ml_live_in_fusion"] is False
        assert payload["rails"]["ml_product_go"] is True
        assert payload.get("product_facade") == _FACADE
        assert payload.get("pipeline") == _PIPELINE
        arch = payload.get("architecture_freeze") or {}
        assert arch.get("recommended_lab_surface") == "iter1_reject_only"
        assert arch.get("ml_product_go") is True
        assert arch.get("field_ops_ml_live_fusion") == "OFF"
        assert arch.get("dead_thrash_closed") is True
        assert arch.get("product_facade") == _FACADE
        assert (payload.get("verdict") or {}).get("dead_thrash_closed") is True
        assert (payload.get("verdict") or {}).get("freeze_iter1_reject") is True
        mf = payload.get("multi_fire_honesty")
        assert isinstance(mf, dict)
        assert mf.get("do_not_reopen_tobarra_keep") is True or (
            (mf.get("tobarra") or {}).get("reopen_same_recipe") is False
        )
