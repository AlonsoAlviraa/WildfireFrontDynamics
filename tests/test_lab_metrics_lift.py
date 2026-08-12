"""Tests for metrics lift board (E0 instrumentation — no retrain)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.ml.lab_metrics_lift import (
    BASELINE_LOFO_MEAN,
    BASELINE_LOFO_MIN,
    BASELINE_U1_IOU,
    G1_TARGET,
    G2_TARGET,
    L2_PASS_THR,
    L2_TARGET_THR,
    SCHEMA,
    assert_dead_paths_closed,
    build_metrics_lift_board,
    l2_floor_checks,
    l4_u1_check,
    metrics_lift_rails,
    north_star_flags,
    sealed_baselines,
    write_metrics_lift_board,
)
from wildfire_front.ml.product_facade import ProductFacadeError, refuse_dead_path

ROOT = Path(__file__).resolve().parents[1]


def test_sealed_baselines_match_design():
    b = sealed_baselines()
    assert b["lofo_mean_iou"] == pytest.approx(0.7580534465179306)
    assert b["lofo_min_iou"] == pytest.approx(0.6931861844919686)
    assert b["lofo_weakest_fold"] == "LA_ESTRELLA_ACOM2"
    assert b["u1_test_mean_iou"] == pytest.approx(0.8568865373678947)
    assert b["lofo_mean_iou"] == pytest.approx(BASELINE_LOFO_MEAN)
    assert b["lofo_min_iou"] == pytest.approx(BASELINE_LOFO_MIN)
    assert abs(b["lofo_mean_iou"] - 0.7581) < 1e-3
    assert abs(b["lofo_min_iou"] - 0.6932) < 1e-3
    assert abs(b["u1_test_mean_iou"] - 0.8569) < 1e-3


def test_rails_fusion_off_iou_not_ros():
    rails = metrics_lift_rails()
    assert rails["field_ops_allow_ml_live_in_fusion"] is False
    assert rails["iou_is_not_ros"] is True
    assert rails["ml_product_go"] is True
    assert rails["tobarra_keep_reopen"] is False
    assert rails["stop_ece_thrash_on_same_test"] is True
    assert rails["larger_unet_default"] is False
    assert rails["rails_source"] == "product_facade.DEFAULT_RAILS+scorecard"


def test_dead_paths_refused():
    assert_dead_paths_closed()
    with pytest.raises(ProductFacadeError):
        refuse_dead_path("same_holdout_ece_retune")
    with pytest.raises(ProductFacadeError):
        refuse_dead_path("tobarra_keep_reopen_same_recipe")


def test_l2_pass_vs_target_met():
    # Between 0.700 and 0.720: L2_pass True, L2_target_met False
    mid = l2_floor_checks(0.705, profile="E2")
    assert mid["L2_pass"] is True
    assert mid["L2_target_met"] is False
    assert mid["threshold"] == L2_PASS_THR
    # Below 0.700: both false
    low = l2_floor_checks(0.695, profile="E2")
    assert low["L2_pass"] is False
    assert low["L2_target_met"] is False
    # At G2: both true
    high = l2_floor_checks(0.720, profile="E2")
    assert high["L2_pass"] is True
    assert high["L2_target_met"] is True
    # E4 KEEP uses 0.720
    e4 = l2_floor_checks(0.710, profile="E4")
    assert e4["threshold"] == L2_TARGET_THR
    assert e4["L2_pass"] is False
    e4ok = l2_floor_checks(0.720, profile="E4")
    assert e4ok["L2_pass"] is True


def test_l4_skipped_not_pass():
    sk = l4_u1_check(None, champion_candidate=False, u1_status="SKIPPED")
    assert sk["status"] == "SKIPPED"
    assert sk["pass"] is None  # not True
    assert sk["pass"] is not True
    # champion missing → hard fail
    req = l4_u1_check(None, champion_candidate=True)
    assert req["pass"] is False
    assert req["status"] == "REQUIRED_MISSING"
    # MEASURED at floor
    floor = BASELINE_U1_IOU - 0.01
    ok = l4_u1_check(floor, champion_candidate=True, u1_status="MEASURED")
    assert ok["pass"] is True
    bad = l4_u1_check(floor - 0.001, champion_candidate=True, u1_status="MEASURED")
    assert bad["pass"] is False
    # never use −0.015
    assert ok["threshold"] == pytest.approx(0.01)


def test_north_star_t2_independent_of_keep():
    ns = north_star_flags(0.76, 0.70)
    assert ns["g1_met"] is False
    assert ns["g2_met"] is False
    assert ns["design_success_closed"] is False
    ns2 = north_star_flags(G1_TARGET, G2_TARGET)
    assert ns2["g1_met"] is True
    assert ns2["g2_met"] is True
    assert ns2["design_success_closed"] is True
    # T1 KEEP can exist while T2 false — tested via board kill_verdict vs north_star


def test_baselines_only_board(tmp_path):
    board = build_metrics_lift_board(ROOT, baselines_only=True)
    assert board["schema"] == SCHEMA
    assert board["field_ops_allow_ml_live_in_fusion"] is False
    assert board["iou_is_not_ros"] is True
    assert board["rails_ok"] is True
    assert board["baselines"]["lofo_mean_iou"] == pytest.approx(BASELINE_LOFO_MEAN)
    assert board["baselines"]["lofo_min_iou"] == pytest.approx(BASELINE_LOFO_MIN)
    assert board["candidate"]["lofo_mean_iou"] is None
    assert board["kill_verdict"] == "PENDING"
    assert board["north_star"]["design_success_closed"] is False
    assert board["tier"] == "none"
    # no KEEP claim without scoring
    assert board["kill_verdict"] != "KEEP"
    out = tmp_path / "board.json"
    write_metrics_lift_board(board, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["schema"] == SCHEMA


def test_candidate_root_lofo_v1_if_present():
    root = ROOT / "outputs" / "ml_eval" / "lofo_v1"
    if not root.is_dir():
        pytest.skip("lofo_v1 eval missing")
    board = build_metrics_lift_board(
        ROOT,
        candidate_root=root,
        experiment_id="BASELINE_REFERENCE",
        kill_verdict="PENDING",
    )
    c = board["candidate"]
    if c.get("lofo_mean_iou") is not None:
        assert c["lofo_mean_iou"] == pytest.approx(BASELINE_LOFO_MEAN, rel=0, abs=1e-4)
        assert c["lofo_min_iou"] == pytest.approx(BASELINE_LOFO_MIN, rel=0, abs=1e-4)
        # deltas near zero for baseline reference
        assert abs(c["delta_lofo_mean"]) < 1e-4
        # T2 not met on baseline
        assert board["north_star_g1_met"] is False
        assert board["north_star_g2_met"] is False


def test_script_baselines_only(tmp_path):
    from scripts.run_lab_ml_loop_v34_metrics_lift import main

    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out-dir",
            str(tmp_path),
            "--baselines-only",
        ]
    )
    assert rc == 0
    data = json.loads(
        (tmp_path / "lab_loop_v34_metrics_lift_latest.json").read_text(encoding="utf-8")
    )
    assert data["schema"] == SCHEMA
    assert data["baselines"]["lofo_mean_iou"] == pytest.approx(0.7580534465179306)
    assert data["baselines"]["lofo_min_iou"] == pytest.approx(0.6931861844919686)
    assert data["baselines"]["u1_test_mean_iou"] == pytest.approx(0.8568865373678947)
    assert data["field_ops_allow_ml_live_in_fusion"] is False
    assert data["iou_is_not_ros"] is True


def test_reject_candidate_dir_flag():
    from scripts.run_lab_ml_loop_v34_metrics_lift import main

    rc = main(["--baselines-only", "--candidate-dir", "foo"])
    assert rc == 2
