"""ML LEAP E1b — selective/FNR method note pins + lab proxy (no invented scores)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from wildfire_front.ml.reliability_metrics import (
    fnr_proxy_at_budget,
    patch_miss_rate_at_coverage,
    selective_beats_random,
    selective_iou_at_coverage,
)

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "docs" / "ML_LEAP_SELECTIVE_FNR.md"
CLAIMS = ROOT / "docs" / "CLAIM_BOARD_ML_LEAP_2026-08-12.md"
PLAN = ROOT / "docs" / "PLAN_ML_LEAP_2026-08-12.md"
ANCHORS = ROOT / "data" / "infocam_anchors.json"
STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"


def test_e1b_note_has_coverage_grid_and_fnr_map():
    assert NOTE.is_file()
    text = NOTE.read_text(encoding="utf-8")
    for token in ("50%", "80%", "90%", "@50", "@80", "@90"):
        assert token in text, token
    assert "not run" in text
    assert "FNR" in text
    assert "GO" in text and "HOLD" in text and "ABSTAIN" in text
    assert "dispatch" in text.lower() or "despacho" in text.lower()
    assert "delta_vs_random" in text or "Δ vs" in text or "delta" in text.lower()
    assert "fnr_proxy_at_budget" in text
    assert "patch_miss_rate_at_coverage" in text
    assert "FREEZE" in text
    assert "fusion" in text.lower()


def test_e1b_note_enforces_claim_board_l1_l8():
    text = NOTE.read_text(encoding="utf-8")
    for lid in ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"):
        assert lid in text, lid
    claims = CLAIMS.read_text(encoding="utf-8")
    for lid in ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"):
        assert lid in claims, lid
    # no vanity
    assert "not tactical" in text.lower() or "no es despacho" in text.lower() or "despacho" in text.lower()
    assert "0.8963" in text
    assert "ROS" in text


def test_e1b_note_does_not_invent_50_90_or_promote_hellin():
    text = NOTE.read_text(encoding="utf-8")
    # grid must keep not-run for unsold coverages
    assert text.lower().count("not run") >= 3
    anchors = json.loads(ANCHORS.read_text(encoding="utf-8"))
    assert anchors["anchors"]["hellin_2024"]["status"] == "pending_external"
    stamp = json.loads(STAMP.read_text(encoding="utf-8"))
    assert stamp["field_ops_allow_ml_live_in_fusion"] is True
    assert stamp["GO_Q"] == "partial"
    assert stamp["GO_MES_plus"] is False


def test_plan_points_at_e1b_note():
    plan = PLAN.read_text(encoding="utf-8")
    assert "ML_LEAP_SELECTIVE_FNR.md" in plan or "selective" in plan.lower()


def test_patch_miss_rate_ranks_high_conf_first():
    ious = [0.9, 0.85, 0.1, 0.05]
    conf = [0.95, 0.9, 0.2, 0.1]
    miss = patch_miss_rate_at_coverage(ious, conf, coverage=0.5, tau=0.5)
    assert miss["n_keep"] == 2.0
    assert miss["miss_rate"] == 0.0
    bad = patch_miss_rate_at_coverage(ious, [0.1, 0.2, 0.9, 0.95], coverage=0.5, tau=0.5)
    assert bad["miss_rate"] == 1.0


def test_fnr_proxy_budget_is_one_minus_coverage():
    ious = np.array([0.9, 0.8, 0.7, 0.1])
    conf = np.array([0.9, 0.8, 0.7, 0.1])
    proxy = fnr_proxy_at_budget(ious, conf, budget=0.25, tau=0.5)
    assert proxy["coverage"] == 0.75
    assert proxy["fnr_proxy"] == proxy["miss_rate"]
    assert proxy["n_keep"] == 3.0
    assert proxy["miss_rate"] == 0.0
    full_abstain = fnr_proxy_at_budget(ious, conf, budget=1.0, tau=0.5)
    assert not np.isfinite(full_abstain["fnr_proxy"])


def test_e1b_helpers_agree_with_selective_keep_set():
    ious = [0.9, 0.2, 0.85, 0.1]
    conf = [0.99, 0.4, 0.8, 0.1]
    sel = selective_iou_at_coverage(ious, conf, coverage=0.5)
    miss = patch_miss_rate_at_coverage(ious, conf, coverage=0.5, tau=0.5)
    assert sel["n_keep"] == int(miss["n_keep"])
    util = selective_beats_random(ious, conf, coverage=0.5, n_trials=20, seed=1)
    assert util["beats_random"] is True
