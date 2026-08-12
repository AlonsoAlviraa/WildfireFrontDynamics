"""Kill scorer profile predicates E2/E3/E4/E5 (synthetic boards)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wildfire_front.ml.lab_metrics_lift import (
    BASELINE_LOFO_MEAN,
    BASELINE_LOFO_MIN,
    CORE3_FOLD_BASELINES,
    d3_applicability,
    score_kill_criteria,
)

ROOT = Path(__file__).resolve().parents[1]


def _core3_rows(
    mean_boost: float = 0.0,
    min_boost: float = 0.0,
    *,
    beat_copy: bool = True,
) -> dict:
    # Build fold rows around baselines with boosts
    base = dict(CORE3_FOLD_BASELINES)
    # apply min boost to ACOM2 only for floor tests
    base["LA_ESTRELLA_ACOM2"] = BASELINE_LOFO_MIN + min_boost
    # distribute mean roughly: adjust all slightly so mean ~ baseline + mean_boost
    target_mean = BASELINE_LOFO_MEAN + mean_boost
    # simple: set all three so average is target_mean while keeping ACOM2 as weak
    acom2 = base["LA_ESTRELLA_ACOM2"]
    # other two share remaining
    rem = target_mean * 3 - acom2
    c = rem / 2
    a1 = rem / 2
    rows = {
        "CARDOSO": {
            "fold": "CARDOSO",
            "model_iou": c,
            "improvement_vs_copy_iou": 0.15 if beat_copy else -0.01,
            "n_test": 200,
        },
        "LA_ESTRELLA_ACOM1": {
            "fold": "LA_ESTRELLA_ACOM1",
            "model_iou": a1,
            "improvement_vs_copy_iou": 0.40 if beat_copy else -0.01,
            "n_test": 200,
        },
        "LA_ESTRELLA_ACOM2": {
            "fold": "LA_ESTRELLA_ACOM2",
            "model_iou": acom2,
            "improvement_vs_copy_iou": 0.30 if beat_copy else -0.01,
            "n_test": 200,
        },
    }
    return rows


def test_baseline_numbers_t2_false_e2_kill():
    """Baseline-like: Δmean=0 → E2 L1 fail → KILL; T2 false."""
    rows = _core3_rows(0.0, 0.0)
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E2",
        experiment_id="baseline_ref",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    assert kill["north_star_g1_met"] is False
    assert kill["north_star_g2_met"] is False
    assert kill["design_success_closed"] is False
    assert kill["checks"]["L1_lofo_mean_lift"]["pass"] is False
    assert kill["verdict"] == "KILL"
    assert kill["tier"] == "none"


def test_e2_keep_t1_not_t2():
    """E2 KEEP with +0.012 mean and min≥0.700 but below G1/G2 → T1 only."""
    rows = _core3_rows(mean_boost=0.012, min_boost=0.01)  # min ~0.703
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    assert mean >= BASELINE_LOFO_MEAN + 0.010
    assert mn >= 0.700
    kill = score_kill_criteria(
        profile="E2",
        experiment_id="E2a_keep",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    assert kill["checks"]["L1_lofo_mean_lift"]["pass"] is True
    assert kill["checks"]["L2_weak_floor"]["L2_pass"] is True
    assert kill["checks"]["L2_weak_floor"]["L2_target_met"] is False  # <0.720
    assert kill["verdict"] == "KEEP"
    assert kill["tier"] == "T1_KEEP_MEMBER"
    assert kill["north_star_g1_met"] is False or mean < 0.780
    assert kill["design_success_closed"] is False


def test_l2_pass_not_or_with_target():
    """KEEP floor uses L2_pass (0.700) only — not OR/AND with 0.720."""
    rows = _core3_rows(mean_boost=0.015, min_boost=0.008)  # min ~0.701
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E3",
        experiment_id="e3_floor",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    l2 = kill["checks"]["L2_weak_floor"]
    assert l2["L2_pass"] is True
    assert l2["L2_target_met"] is False
    assert l2["pass"] == l2["L2_pass"]
    assert kill["verdict"] == "KEEP"


def test_e3_d3_skipped_does_not_block_keep():
    rows = _core3_rows(mean_boost=0.02, min_boost=0.01)
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E3",
        experiment_id="E3a_hellin_pool_only",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,  # no new-fire fold
        train_complete=True,
    )
    d3 = kill["profile_extra"]["D3"]
    assert d3["applicable"] is False
    assert d3["status"] == "SKIPPED"
    assert d3["pass"] is None
    assert kill["verdict"] == "KEEP"


def test_e3_d3_measured_requires_delta():
    rows = _core3_rows(mean_boost=0.02, min_boost=0.01)
    rows["hellin_2024"] = {
        "fold": "hellin_2024",
        "model_iou": 0.75,
        "improvement_vs_copy_iou": 0.02,  # < 0.05
        "n_test": 80,
    }
    mean = (
        sum(rows[f]["model_iou"] for f in ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")) / 3
    )
    mn = min(rows[f]["model_iou"] for f in ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2"))
    kill = score_kill_criteria(
        profile="E3",
        experiment_id="E3_with_hellin_fold",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    d3 = kill["profile_extra"]["D3"]
    assert d3["applicable"] is True
    assert d3["status"] == "MEASURED"
    assert d3["pass"] is False
    assert kill["verdict"] == "KILL"

    # pass when delta >= 0.05
    rows["hellin_2024"]["improvement_vs_copy_iou"] = 0.11
    kill2 = score_kill_criteria(
        profile="E3",
        experiment_id="E3_hellin_ok",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    assert kill2["profile_extra"]["D3"]["pass"] is True
    assert kill2["verdict"] == "KEEP"


def test_d3_n_test_below_50_skipped():
    folds = {
        "hellin_2024": {
            "fold": "hellin_2024",
            "model_iou": 0.8,
            "improvement_vs_copy_iou": 0.2,
            "n_test": 20,
        }
    }
    d3 = d3_applicability(folds)
    assert d3["applicable"] is False
    assert d3["status"] == "SKIPPED"


def test_l4_skipped_exempt_research_t1():
    rows = _core3_rows(mean_boost=0.02, min_boost=0.01)
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E2",
        experiment_id="research",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        champion_candidate=False,
        u1_status="SKIPPED",
        train_complete=True,
    )
    assert kill["checks"]["L4_u1_no_silent_regress"]["status"] == "SKIPPED"
    assert kill["checks"]["L4_u1_no_silent_regress"]["pass"] is None
    assert kill["verdict"] == "KEEP"


def test_l4_required_missing_blocks_champion():
    rows = _core3_rows(mean_boost=0.02, min_boost=0.01)
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E5",
        experiment_id="champ",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        champion_candidate=True,
        u1_iou=None,
        train_complete=True,
    )
    assert kill["checks"]["L4_u1_no_silent_regress"]["pass"] is False
    assert kill["verdict"] in ("KILL", "INCONCLUSIVE")


def test_incomplete_train_not_keep():
    kill = score_kill_criteria(
        profile="E3",
        experiment_id="incomplete",
        lofo_mean=None,
        lofo_min=None,
        fold_rows={},
        train_complete=False,
    )
    assert kill["verdict"] in ("INCONCLUSIVE", "KILL")
    assert kill["verdict"] != "KEEP"


def test_e4_floor_uses_0_720():
    rows = _core3_rows(mean_boost=0.0, min_boost=0.01)  # min ~0.703
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    # stabilize CARDOSO/ACOM1 near baseline for C2
    rows["CARDOSO"]["model_iou"] = CORE3_FOLD_BASELINES["CARDOSO"]
    rows["LA_ESTRELLA_ACOM1"]["model_iou"] = CORE3_FOLD_BASELINES["LA_ESTRELLA_ACOM1"]
    kill = score_kill_criteria(
        profile="E4",
        experiment_id="e4_low_floor",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        train_complete=True,
    )
    assert kill["checks"]["L2_weak_floor"]["threshold"] == pytest.approx(0.720)
    assert kill["checks"]["L2_weak_floor"]["L2_pass"] is False
    assert kill["verdict"] == "KILL"

    rows2 = _core3_rows(mean_boost=0.0, min_boost=0.03)  # min ~0.723
    rows2["CARDOSO"]["model_iou"] = CORE3_FOLD_BASELINES["CARDOSO"]
    rows2["LA_ESTRELLA_ACOM1"]["model_iou"] = CORE3_FOLD_BASELINES["LA_ESTRELLA_ACOM1"]
    mean2 = (
        rows2["CARDOSO"]["model_iou"]
        + rows2["LA_ESTRELLA_ACOM1"]["model_iou"]
        + rows2["LA_ESTRELLA_ACOM2"]["model_iou"]
    ) / 3
    mn2 = rows2["LA_ESTRELLA_ACOM2"]["model_iou"]
    kill2 = score_kill_criteria(
        profile="E4",
        experiment_id="e4_ok",
        lofo_mean=mean2,
        lofo_min=mn2,
        fold_rows=rows2,
        train_complete=True,
    )
    assert kill2["checks"]["L2_weak_floor"]["L2_pass"] is True
    assert kill2["verdict"] == "KEEP"


def test_rails_hard_fail_kill():
    rows = _core3_rows(mean_boost=0.02, min_boost=0.01)
    mean = sum(r["model_iou"] for r in rows.values()) / 3
    mn = min(r["model_iou"] for r in rows.values())
    kill = score_kill_criteria(
        profile="E2",
        experiment_id="leak",
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=rows,
        n_leaked_train_val=3,
        train_complete=True,
    )
    assert kill["checks"]["L5_zero_leak"]["pass"] is False
    assert kill["verdict"] == "KILL"


def test_script_smoke_and_baseline(tmp_path):
    from scripts.score_metrics_lift_kill_criteria import main

    rc = main(
        [
            "--repo",
            str(ROOT),
            "--profile",
            "E3",
            "--smoke",
            "--out",
            str(tmp_path / "smoke_kill.json"),
        ]
    )
    assert rc == 0
    data = json.loads((tmp_path / "smoke_kill.json").read_text(encoding="utf-8"))
    assert data["verdict"] != "KEEP"

    rc2 = main(
        [
            "--repo",
            str(ROOT),
            "--profile",
            "E2",
            "--baselines-as-candidate",
            "--write-board",
            "--out",
            str(tmp_path / "base_kill.json"),
        ]
    )
    assert rc2 == 0
    data2 = json.loads((tmp_path / "base_kill.json").read_text(encoding="utf-8"))
    assert data2["north_star_g1_met"] is False
    assert data2["north_star_g2_met"] is False
    # baseline Δ=0 → E2 L1 fail → KILL
    assert data2["verdict"] == "KILL"
    assert data2["checks"]["L2_weak_floor"]["L2_pass"] is False  # min 0.693 < 0.700
