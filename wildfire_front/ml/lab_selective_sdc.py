"""Lab selective prediction: Soft-Dice-Confidence proxy + ranking bake-off.

Implements deep-research S1 without pixel soft-masks: Head A features are
(mean_entropy, member_disagreement, mean_margin). Ranking scores are compared
via selective IoU @ coverage and AURC (area under risk–coverage).

Architecture (product ROI — no retrain)
---------------------------------------
Single product path (orchestration in ``product_facade``)::

    features → calibrator → conf → rank / reject → scorecard

This module owns **SDC ranking score families** and the bake-off verdict only.
Confidences, VAL-only thr selection, reject metrics, ranking *metric* primitives,
dual-product rails, and scorecard assembly live in ``product_facade`` +
``rank_reject_protocol`` — do **not** reimplement them here.

Rails
-----
* Tune / select score family on **VAL only**.
* Report TEST once (no thrash loop).
* Dual rails: lab ML vs field_ops; IoU ≠ ROS; ``ml_product_go`` true (promoted);
  no auto-flip; fusion OFF (lab GO ≠ field fusion).
* Frozen product reject surface default: ``iter1_reject_only`` (locked thr **0.795**).
  CRC thr fallback is that locked thr — **not** a divergent 0.80 default.
* Multi-fire honesty first-class (LOFO / W3 / Tobarra) — report-only boards.
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP re-promote of KILL
  weights, ``sdc_auto_promote_over_iter1``.

Kill (product promote of SDC proxy)
-----------------------------------
SDC proxy must beat **entropy-based** ranking on VAL selective@0.8 by
``min_lift_sel80`` (default +0.02) **and** not lose on AURC by more than
``max_aurc_rel_degrade``. Otherwise verdict = KILL_SDC_PROMOTE (keep iter1 reject).
Even on KEEP_SDC_PROXY_LAB the frozen reject surface stays iter1_reject_only
(ranking family is reported separately; no auto surface flip).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from wildfire_front.ml.rank_reject_protocol import (
    DEFAULT_LAB_SURFACE,
    LOCKED_ITER1_THR,
    apply_reject_thr_metrics,
    aurc_from_curve,
    frozen_thr_from_val_selection,
    lab_rails,
    multi_fire_honesty,
    protocol_payload,
    refuse_dead_protocol_path,
    score_ranking,
    select_thr_val_only,
)
from wildfire_front.ml.uncertainty import LogisticCalibrator

# Locked iter1 reject thr (~0.795). Explicit name so CRC fallback cannot drift
# back to a parallel 0.80 default. Same value as product_facade.ITER1_LOCKED_*.
_ITER1_FALLBACK_THR: Final[float] = float(LOCKED_ITER1_THR)
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"

# Re-exports for callers/tests that import ranking metrics from this module.
__all__ = [
    "ranking_scores_from_head_a",
    "aurc_from_curve",
    "score_ranking",
    "bakeoff_rankings",
    "conformal_selective_thr",
    "apply_thr_metrics",
    "decide_sdc_verdict",
    "run_selective_sdc_protocol",
]


def _norm01(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64).ravel()
    lo, hi = float(np.min(x)), float(np.max(x))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo + 1e-12:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def ranking_scores_from_head_a(
    features: np.ndarray,
    conf_logistic: np.ndarray,
) -> dict[str, np.ndarray]:
    """Build comparable [0,1]-ish ranking scores (higher = keep first).

    Features columns: 0 entropy, 1 disagreement, 2 margin.
    """
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 3:
        raise ValueError(f"features must be (N,3), got {x.shape}")
    conf = np.clip(np.asarray(conf_logistic, dtype=np.float64).ravel(), 1e-6, 1.0 - 1e-6)
    if conf.size != x.shape[0]:
        raise ValueError("conf_logistic length mismatch")

    entropy = x[:, 0]
    disagree = x[:, 1]
    margin = x[:, 2]

    inv_entropy = 1.0 - _norm01(entropy)
    inv_disagree = 1.0 - _norm01(disagree)
    margin_n = _norm01(margin)

    # Soft Dice Confidence *proxy* (Borges et al. spirit): agreement of two
    # soft reliability channels (calibrated conf × margin).
    sdc = (2.0 * conf * margin_n) / (conf + margin_n + 1e-9)

    # SHRUG-ish multi-signal: average of inv-entropy, inv-disagree, conf
    multi = (inv_entropy + inv_disagree + conf) / 3.0

    return {
        "logistic_conf": conf,
        "inv_entropy": inv_entropy,
        "margin": margin_n,
        "inv_disagreement": inv_disagree,
        "soft_dice_proxy": sdc,
        "multi_signal": multi,
    }


def bakeoff_rankings(
    features: np.ndarray,
    conf_logistic: np.ndarray,
    ious: np.ndarray,
    *,
    coverages: Sequence[float] | None = None,
) -> dict[str, dict[str, Any]]:
    scores = ranking_scores_from_head_a(features, conf_logistic)
    ious_a = np.asarray(ious, dtype=np.float64).ravel()
    out: dict[str, dict[str, Any]] = {}
    for name, s in scores.items():
        out[name] = score_ranking(s, ious_a, coverages=coverages)
    return out


def conformal_selective_thr(
    conf: np.ndarray,
    ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
    thr_grid: Sequence[float] | None = None,
) -> dict[str, Any]:
    """VAL-only thr select via shared rank/reject protocol (compat wrapper)."""
    return select_thr_val_only(conf, ious, risk_alpha=risk_alpha, thr_grid=thr_grid, split="val")


def apply_thr_metrics(conf: np.ndarray, ious: np.ndarray, thr: float) -> dict[str, float]:
    """Reject metrics at thr via shared protocol (compat wrapper)."""
    return apply_reject_thr_metrics(conf, ious, thr)


def decide_sdc_verdict(
    val_bake: dict[str, dict[str, Any]],
    *,
    min_lift_sel80: float = 0.02,
    max_aurc_rel_degrade: float = 0.05,
    champion: str = "soft_dice_proxy",
    baseline: str = "inv_entropy",
) -> dict[str, Any]:
    """Kill/keep SDC proxy vs entropy ranking (VAL only).

    Frozen product reject surface always stays ``iter1_reject_only``; ranking
    family preference is reported in ``ranking_family`` only (no surface flip).
    """
    ch = val_bake.get(champion) or {}
    bl = val_bake.get(baseline) or {}
    s80_c = float(ch.get("selective_iou_at_80", float("nan")))
    s80_b = float(bl.get("selective_iou_at_80", float("nan")))
    aurc_c = float(ch.get("aurc", float("nan")))
    aurc_b = float(bl.get("aurc", float("nan")))
    lift = s80_c - s80_b if np.isfinite(s80_c) and np.isfinite(s80_b) else float("nan")
    aurc_ok = True
    aurc_rel = float("nan")
    if np.isfinite(aurc_c) and np.isfinite(aurc_b) and aurc_b > 1e-9:
        # lower AURC better; degrade if champion much worse
        aurc_rel = (aurc_c - aurc_b) / aurc_b
        aurc_ok = aurc_rel <= max_aurc_rel_degrade
    keep = bool(np.isfinite(lift) and lift >= min_lift_sel80 and aurc_ok)
    ranking_family = "soft_dice_proxy_ranking" if keep else DEFAULT_LAB_SURFACE
    return {
        "champion": champion,
        "baseline": baseline,
        "val_sel80_champion": s80_c,
        "val_sel80_baseline": s80_b,
        "val_lift_sel80": lift,
        "min_lift_sel80": min_lift_sel80,
        "val_aurc_champion": aurc_c,
        "val_aurc_baseline": aurc_b,
        "val_aurc_rel_delta": aurc_rel,
        "max_aurc_rel_degrade": max_aurc_rel_degrade,
        "verdict": "KEEP_SDC_PROXY_LAB" if keep else "KILL_SDC_PROMOTE",
        # Product reject surface is frozen; ranking bake-off cannot flip it.
        "recommended_lab_surface": DEFAULT_LAB_SURFACE,
        "ranking_family": ranking_family,
        "freeze_iter1_reject": True,
        "sdc_auto_promote_over_iter1": False,
        "note": (
            "Lab ranking only; frozen surface=iter1_reject_only thr≈"
            f"{_ITER1_FALLBACK_THR}; no auto_ml_product_go / field fusion flip "
            "(explicit ml_product_go promote is separate)"
        ),
    }


def _confidences_via_facade(cal: LogisticCalibrator, features: np.ndarray) -> np.ndarray:
    """Head A conf via product_facade (lazy — facade imports this module)."""
    # product_facade imports bakeoff_rankings from this file at import time;
    # lazy import keeps the features→calibrator→conf path on the facade.
    from wildfire_front.ml.product_facade import confidences_from_head_a

    return confidences_from_head_a(cal, features)


def _seal_sdc_dead_paths() -> None:
    """Refuse ECE thrash / Tobarra KEEP reopen / SDC auto-promote hooks."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
        "sdc_auto_promote_over_iter1",
    ):
        try:
            refuse_dead_protocol_path(dead)
        except ValueError:
            pass  # expected — path is sealed
        else:
            raise RuntimeError(f"dead path still open: {dead!r}")


def run_selective_sdc_protocol(
    cal: LogisticCalibrator,
    val_features: np.ndarray,
    val_ious: np.ndarray,
    test_features: np.ndarray,
    test_ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
    min_lift_sel80: float = 0.02,
) -> dict[str, Any]:
    """Ranking bake-off + shared VAL-only thr/reject under product_facade path.

    Conf via ``product_facade.confidences_from_head_a``; thr select / reject
    metrics via ``rank_reject_protocol``. CRC thr fallback is locked iter1
    reject thr (~0.795), never a divergent 0.80 default. Does not retrain.
    """
    _seal_sdc_dead_paths()

    conf_v = _confidences_via_facade(cal, val_features)
    conf_t = _confidences_via_facade(cal, test_features)
    val_bake = bakeoff_rankings(val_features, conf_v, val_ious)
    test_bake = bakeoff_rankings(test_features, conf_t, test_ious)
    verdict = decide_sdc_verdict(val_bake, min_lift_sel80=min_lift_sel80)

    # Shared VAL-only thr (CRC-lite) on logistic conf; TEST frozen at that thr.
    # Fallback = locked iter1 thr (0.795), not a parallel 0.80 default.
    conf_crc = select_thr_val_only(conf_v, val_ious, risk_alpha=risk_alpha, split="val")
    thr = frozen_thr_from_val_selection(conf_crc, fallback=_ITER1_FALLBACK_THR)
    test_at_crc = apply_reject_thr_metrics(conf_t, test_ious, thr)

    rails = lab_rails()
    # Dual-product rails: stamp explicit promoted ml_product_go; never auto-flip
    # or enable field fusion from SDC bake-off (lab GO ≠ field fusion).
    rails = {
        **rails,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "iou_is_not_ros": True,
        "recommended_lab_surface": DEFAULT_LAB_SURFACE,
        "locked_reject_thr": float(_ITER1_FALLBACK_THR),
        "freeze_iter1_reject": True,
        "sdc_auto_promote_over_iter1": False,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
    }

    return {
        "val_bakeoff": {
            k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in val_bake.items()
        },
        "test_bakeoff": {
            k: {kk: vv for kk, vv in v.items() if kk != "curve"} for k, v in test_bake.items()
        },
        "val_curves": {k: v.get("curve") for k, v in val_bake.items()},
        "test_curves": {k: v.get("curve") for k, v in test_bake.items()},
        "sdc_verdict": verdict,
        "conformal_crc_lite": {
            "val": conf_crc,
            "test_at_val_thr": test_at_crc,
            "score_space": "logistic_conf",
            "frozen_thr": thr,
            "fallback_thr": float(_ITER1_FALLBACK_THR),
            "thr_source": "val_crc_lite_or_iter1_fallback",
            "recommended_lab_surface": DEFAULT_LAB_SURFACE,
        },
        "rails": rails,
        "rank_reject_protocol": protocol_payload(locked_reject_thr=thr),
        "multi_fire_honesty": multi_fire_honesty(),
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "dead_thrash_closed": True,
    }
