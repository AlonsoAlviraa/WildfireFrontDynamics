"""Shared rank / reject protocol for clm_ensemble_v34 lab ML.

Architecture role (product ROI — no retrain)
--------------------------------------------
**Protocol layer** for VAL thr selection + frozen thr report, used by reject
calibration, selective-SDC bake-off, LOFO / W3 boards, and lab runners.

Orchestration (product path) lives in ``product_facade``::

    features → calibrator conf → rank/reject thr (VAL only) → scorecard

This module does **not** reimplement ranking formulas or product orchestration.
Metric primitives (AURC / selective / reject thr metrics) live in
``reliability_metrics``; dual-product rails + thr freeze constants live in
``protocol_rails``. Confidence path is ``lab_reject_calibration`` /
``uncertainty`` (shared with the facade).

Rails
-----
* Dual product: **lab ML** vs **field_ops**; IoU ≠ ROS.
* ``ml_product_go`` **promoted true** (human authorize 2026-08-05); never *auto*-flip;
  field fusion stays **OFF** (lab GO ≠ field fusion).
* Thr tune / score-family select on **VAL only**; TEST / LOFO / external report-only.
* Default frozen lab surface: ``iter1_reject_only`` (locked thr **0.795**).
* Multi-fire honesty first-class (Tobarra hard / W3 external / LOFO).
* Dead thrash closed: same-holdout ECE retune, Tobarra KEEP reopen of KILL weights,
  ``auto_ml_product_go`` silent thrash (explicit promoted true is allowed).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np

from wildfire_front.ml.lab_reject_calibration import confidences_from_features
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    LOCKED_REJECT_THR_DEFAULT,
    MULTI_FIRE_HONESTY,
    RECOMMENDED_LAB_SURFACE_DEFAULT,
    assert_not_forbidden_thrash,
    assert_split_role,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
    rank_abstain_protocol_dict,
)
from wildfire_front.ml.reliability_metrics import (
    DEFAULT_RANK_COVERAGES,
    PROTOCOL_ID,
    PROTOCOL_SURFACE,
    aurc_from_curve,
    reject_thr_metrics,
    score_ranking,
)
from wildfire_front.ml.uncertainty import LogisticCalibrator

# Re-export metric primitives so selective-SDC / callers keep one import site.
# Canonical implementations: reliability_metrics (no fork of AURC / ranking).
__all__ = [
    "DEFAULT_LAB_SURFACE",
    "DEFAULT_REJECT_THR",
    "LOCKED_ITER1_THR",
    "LAB_RAILS",
    "DEAD_PROTOCOL_PATHS",
    "default_val_thr_grid",
    "lab_rails",
    "multi_fire_honesty",
    "protocol_payload",
    "conf_from_features",
    "apply_reject_thr_metrics",
    "select_thr_val_only",
    "frozen_thr_from_val_selection",
    "aurc_from_curve",
    "score_ranking",
    "rank_reject_val_then_test",
    "refuse_dead_protocol_path",
]

# ---------------------------------------------------------------------------
# Frozen product surface defaults (aligned with product_facade / protocol_rails)
# ---------------------------------------------------------------------------

DEFAULT_LAB_SURFACE: Final[str] = RECOMMENDED_LAB_SURFACE_DEFAULT  # iter1_reject_only
# Single locked thr: iter1 VAL freeze (~0.795). Do not fork a parallel 0.80 default.
LOCKED_ITER1_THR: Final[float] = float(LOCKED_REJECT_THR_DEFAULT)
DEFAULT_REJECT_THR: Final[float] = LOCKED_ITER1_THR

# Explicitly closed dead paths (same set as facade / protocol_rails).
DEAD_PROTOCOL_PATHS: Final[frozenset[str]] = frozenset(FORBIDDEN_THRASH_PATHS) | frozenset(
    {
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "auto_ml_product_go",
        "field_ops_ml_live_fusion_on",
        "sdc_auto_promote_over_iter1",
    }
)

LAB_RAILS: Final[dict[str, Any]] = {
    **dual_product_rails_dict(),
    # Human promote authorized 2026-08-05 (owner directive): lab ML product GO.
    # dual_product_rails_dict may still default false; stamp true after merge.
    # Field fusion remains OFF (lab GO ≠ field fusion).
    "ml_product_go": True,
    "field_ops_allow_ml_live_in_fusion": False,
    "field_ops_ml_live_fusion": "OFF",
    "val_only_selection": True,
    "iou_is_not_ros": True,
    "lab_only": True,
    "default_lab_surface": DEFAULT_LAB_SURFACE,
    "recommended_lab_surface": DEFAULT_LAB_SURFACE,
    "default_reject_thr": DEFAULT_REJECT_THR,
    "locked_reject_thr": LOCKED_ITER1_THR,
    "freeze_iter1_reject": True,
    "stop_ece_thrash_on_same_test": True,
    "tobarra_keep_reopen_forbidden": True,
    "protocol": PROTOCOL_ID,
    "surface": PROTOCOL_SURFACE,
    "pipeline": "features→calibrator→rank/reject→scorecard",
    "product_facade": "wildfire_front.ml.product_facade",
    "dead_paths": sorted(DEAD_PROTOCOL_PATHS),
}


def lab_rails() -> dict[str, Any]:
    """Copy of dual-product rails (ml_product_go promoted true; field fusion OFF)."""
    return dict(LAB_RAILS)


def multi_fire_honesty() -> dict[str, Any]:
    """First-class multi-fire honesty (Tobarra hard, W3 external, LOFO)."""
    out = dict(multi_fire_honesty_dict())
    out.setdefault("tobarra", dict(MULTI_FIRE_HONESTY.get("tobarra") or {}))
    out.setdefault("w3_external", dict(MULTI_FIRE_HONESTY.get("w3_external") or {}))
    out["do_not_reopen_tobarra_keep"] = True
    out["report_only_external"] = True
    return out


def protocol_payload(*, locked_reject_thr: float | None = None) -> dict[str, Any]:
    """Shared rank+abstain protocol dict (VAL thr; freeze iter1 default)."""
    thr = float(locked_reject_thr) if locked_reject_thr is not None else LOCKED_ITER1_THR
    return {
        **rank_abstain_protocol_dict(
            locked_reject_thr=thr,
            recommended_lab_surface=DEFAULT_LAB_SURFACE,
        ),
        "pipeline": "features→calibrator→rank/reject→scorecard",
        "product_facade": "wildfire_front.ml.product_facade",
        "metrics": "wildfire_front.ml.reliability_metrics",
        "multi_fire_honesty": multi_fire_honesty(),
        "dead_paths": sorted(DEAD_PROTOCOL_PATHS),
    }


def refuse_dead_protocol_path(path_id: str) -> None:
    """Hard refuse closed thrash / promote hooks (protocol + facade dead set)."""
    key = str(path_id).strip().lower().replace("-", "_").replace(" ", "_")
    if key in DEAD_PROTOCOL_PATHS:
        raise ValueError(
            f"dead path refused: {path_id!r} "
            f"(iter1 reject frozen thr={LOCKED_ITER1_THR}; no same-holdout ECE thrash; "
            f"no Tobarra KEEP reopen; no auto ml_product_go / field fusion ON)"
        )
    assert_not_forbidden_thrash(path_id)


def conf_from_features(
    cal: LogisticCalibrator,
    features: np.ndarray,
) -> np.ndarray:
    """Head A batch confidences via production calibrator (shared path)."""
    return confidences_from_features(cal, features)


def apply_reject_thr_metrics(
    conf: np.ndarray,
    ious: np.ndarray,
    thr: float,
) -> dict[str, float]:
    """Risk / abstain metrics at a frozen conf threshold (no labels required).

    Delegates to ``reliability_metrics.reject_thr_metrics`` (canonical abstain
    formulas). Thr selection is **not** performed here.
    """
    full = reject_thr_metrics(conf, ious, thr=float(thr), labels=None)
    # Keep a stable core subset used by CRC-lite / selective-SDC callers.
    return {
        "thr": float(full["thr"]),
        "n_keep": float(full["n_keep"]),
        "abstain_rate": float(full["abstain_rate"]),
        "mean_iou_accepted": float(full["mean_iou_accepted"]),
        "risk": float(full["risk"]),
    }


def default_val_thr_grid() -> list[float]:
    """VAL thr candidates: 0.01 steps on [0.50, 0.95] **plus** locked iter1 thr.

    ``np.linspace(0.5, 0.95, 46)`` lands on 0.79 / 0.80 but **never** exact
    0.795 (LOCKED_ITER1_THR). Product freeze must be selectable on the grid.
    """
    grid = [round(0.50 + i * 0.01, 2) for i in range(46)]  # 0.50 .. 0.95
    locked = float(LOCKED_ITER1_THR)
    if not any(abs(g - locked) < 1e-12 for g in grid):
        grid.append(locked)
        grid.sort()
    return grid


def select_thr_val_only(
    conf: np.ndarray,
    ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
    thr_grid: Sequence[float] | None = None,
    split: str = "val",
) -> dict[str, Any]:
    """VAL-only: lowest thr with accepted risk (mean 1-IoU) ≤ alpha (CRC-lite).

    Refuses tune/select on test/lofo/external. Morphological CP needs masks;
    this is patch-level conformal risk control for the reject gate.
    Default grid always includes :data:`LOCKED_ITER1_THR` (0.795).
    """
    assert_split_role(split, "select")
    conf = np.asarray(conf, dtype=np.float64).ravel()
    ious = np.asarray(ious, dtype=np.float64).ravel()
    if conf.size == 0 or conf.size != ious.size:
        return {"ok": False, "reason": "empty_or_mismatch"}
    if thr_grid is not None:
        grid = list(thr_grid)
        locked = float(LOCKED_ITER1_THR)
        if not any(abs(float(g) - locked) < 1e-12 for g in grid):
            grid = sorted({float(g) for g in grid} | {locked})
    else:
        grid = default_val_thr_grid()
    best: dict[str, Any] | None = None
    for thr in grid:
        thr = float(thr)
        keep = conf >= thr
        n_keep = int(keep.sum())
        if n_keep < max(5, int(0.05 * conf.size)):
            continue
        risk = float(1.0 - ious[keep].mean())
        abstain = 1.0 - n_keep / conf.size
        row = {
            "thr": thr,
            "risk": risk,
            "mean_iou_accepted": float(ious[keep].mean()),
            "abstain_rate": float(abstain),
            "n_keep": n_keep,
        }
        if risk <= float(risk_alpha) and (best is None or thr < float(best["thr"])):
            best = row
    if best is None:
        candidates: list[dict[str, Any]] = []
        for thr in grid:
            thr = float(thr)
            keep = conf >= thr
            n_keep = int(keep.sum())
            if n_keep < max(5, int(0.05 * conf.size)):
                continue
            risk = float(1.0 - ious[keep].mean())
            candidates.append(
                {
                    "thr": thr,
                    "risk": risk,
                    "mean_iou_accepted": float(ious[keep].mean()),
                    "abstain_rate": float(1.0 - n_keep / conf.size),
                    "n_keep": n_keep,
                }
            )
        if not candidates:
            return {"ok": False, "reason": "no_valid_thr"}
        best = min(candidates, key=lambda r: (r["risk"], -r["n_keep"]))
        best["meets_alpha"] = False
        return {
            "ok": True,
            "risk_alpha": float(risk_alpha),
            "selected": best,
            "split": "val",
            "note": "no thr met alpha; returned min-risk thr",
        }
    best["meets_alpha"] = True
    return {
        "ok": True,
        "risk_alpha": float(risk_alpha),
        "selected": best,
        "split": "val",
        "note": "VAL thr with risk <= alpha (lowest thr)",
    }


def frozen_thr_from_val_selection(
    selection: dict[str, Any],
    *,
    fallback: float = DEFAULT_REJECT_THR,
) -> float:
    """Extract thr from VAL selection payload; default locked iter1 reject thr."""
    selected = selection.get("selected") if isinstance(selection, dict) else None
    if isinstance(selected, dict) and selected.get("thr") is not None:
        return float(selected["thr"])
    return float(fallback)


# aurc_from_curve / score_ranking: re-exported from reliability_metrics (above).
# Do not reimplement trapezoid AURC or selective@0.8 here.


def rank_reject_val_then_test(
    cal: LogisticCalibrator,
    val_features: np.ndarray,
    val_ious: np.ndarray,
    test_features: np.ndarray,
    test_ious: np.ndarray,
    *,
    risk_alpha: float = 0.15,
) -> dict[str, Any]:
    """Shared conf + VAL thr + TEST-at-frozen-thr path (no ranking bake-off).

    Protocol slice of the product pipeline; full product orchestration is
    ``product_facade`` (features→calibrator→rank/reject→scorecard).
    """
    conf_v = conf_from_features(cal, val_features)
    conf_t = conf_from_features(cal, test_features)
    val_sel = select_thr_val_only(conf_v, val_ious, risk_alpha=risk_alpha, split="val")
    thr = frozen_thr_from_val_selection(val_sel, fallback=DEFAULT_REJECT_THR)
    return {
        "conf_val": conf_v,
        "conf_test": conf_t,
        "val_thr_selection": val_sel,
        "frozen_thr": thr,
        "test_at_val_thr": apply_reject_thr_metrics(conf_t, test_ious, thr),
        "recommended_lab_surface": DEFAULT_LAB_SURFACE,
        "rails": lab_rails(),
        "protocol": protocol_payload(locked_reject_thr=thr),
        "multi_fire_honesty": multi_fire_honesty(),
        "coverages_default": list(DEFAULT_RANK_COVERAGES),
    }
