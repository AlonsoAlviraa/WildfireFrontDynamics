"""Pure reject / rank **math** for clm_ensemble_v34 (under product_facade).

Not the product entry point. Orchestration is::

    product_facade + rank_reject_protocol
    features → calibrator → conf → rank/reject thr (VAL only) → scorecard

This module owns **DRY math only** (no dual-rail policy, no thrash loops):

* ``confidences_from_features`` — batch Head A conf via calibrator
* temperature / metrics / risk–coverage / thr operating points
* VAL-only historical thr+temp discovery (``tune_reject_and_temperature``)

Product policy lives elsewhere
------------------------------
* Dual rails (lab vs field_ops, IoU≠ROS, ``ml_product_go`` true promoted, fusion OFF)
  → ``protocol_rails`` / ``product_facade``
* Frozen default surface ``iter1_reject_only`` (thr ≈ 0.795) → facade / rails
* Multi-fire honesty (LOFO / W3 / Tobarra) → facade / protocol_rails
* Same-holdout ECE retune → **removed** (dead thrash; sealed at ece runner)

Compatibility shims ``lab_product_rails`` / ``rank_reject_scorecard`` thin-wrap
protocol rails + pure metrics so older lab scripts do not re-encode product
policy here. Prefer ``product_facade`` for new code.

Does not retrain models.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from wildfire_front.ml.protocol_rails import (
    LOCKED_REJECT_THR_DEFAULT,
    RECOMMENDED_LAB_SURFACE_DEFAULT,
    dual_product_rails_dict,
)
from wildfire_front.ml.reliability_metrics import ece_patch_conf, selective_iou_at_coverage
from wildfire_front.ml.uncertainty import (
    LogisticCalibrator,
    predict_proba_rows,
)

# ---------------------------------------------------------------------------
# Frozen surface constants (math defaults — policy ownership is product_facade)
# ---------------------------------------------------------------------------

DEFAULT_PRODUCT_ID: Final = "clm_ensemble_v34"
RECOMMENDED_LAB_SURFACE: Final = RECOMMENDED_LAB_SURFACE_DEFAULT  # iter1_reject_only
# Locked from lab_loop_v34_reject (VAL-tuned thr; TEST reported once).
ITER1_LOCKED_REJECT_THR: Final = float(LOCKED_REJECT_THR_DEFAULT)  # 0.795
ITER1_LOCKED_TEMPERATURE: Final = 1.0
# Legacy product calibrator default — never rejects on Head A conf band.
LEGACY_PRODUCT_ABSTAIN_THR: Final = 0.35


# ---------------------------------------------------------------------------
# Compatibility: dual rails snapshot (delegates to protocol_rails — not parallel)
# ---------------------------------------------------------------------------


def lab_product_rails() -> dict[str, Any]:
    """Thin shim → ``protocol_rails.dual_product_rails_dict`` (not a second policy).

    Prefer ``product_facade.DEFAULT_RAILS`` / ``ClmEnsembleV34Facade.rails_snapshot``
    for product path. Kept for lab scripts that still import this name.
    Extra keys are metadata only; field fusion stays clamped OFF here.
    ``ml_product_go`` follows product default True (human promote 2026-08-05;
    ``dual_product_rails_dict`` no longer clamps go to false).
    """
    return dual_product_rails_dict(
        overrides={
            "product_id": DEFAULT_PRODUCT_ID,
            "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
            "locked_reject_thr": ITER1_LOCKED_REJECT_THR,
            "locked_temperature": ITER1_LOCKED_TEMPERATURE,
            "fit_split": "val",
            "test_never_used_for_tune": True,
            "no_ece_retune_same_holdout": True,
            "multi_fire_report_only": True,  # Tobarra hard, W3 external: freeze thr
        }
    )


# ---------------------------------------------------------------------------
# Layer: features → calibrator → confidences (pure math; facade wraps this)
# ---------------------------------------------------------------------------


def confidences_from_features(
    cal: LogisticCalibrator,
    features: np.ndarray,
) -> np.ndarray:
    """Batch confidences from (N,3) Head A features.

    Pure math over ``uncertainty.predict_proba_rows``. Product callers should
    prefer ``product_facade.confidences_from_head_a`` / facade ``.confidences``.
    """
    x = np.asarray(features, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 3:
        raise ValueError(f"features must be (N,3), got {x.shape}")
    rows = [x[i] for i in range(x.shape[0])]
    return np.asarray(predict_proba_rows(cal, rows), dtype=np.float64)


def apply_confidence_temperature(conf: np.ndarray, temperature: float) -> np.ndarray:
    """Post-hoc temperature on calibrated confidences (math helper).

    conf' = sigmoid(logit(conf) / T). T=1 is identity.
    """
    t = float(temperature)
    if t <= 0:
        raise ValueError(f"temperature must be > 0, got {t}")
    c = np.clip(np.asarray(conf, dtype=np.float64), 1e-6, 1.0 - 1e-6)
    if abs(t - 1.0) < 1e-12:
        return c.copy()
    logit = np.log(c / (1.0 - c))
    z = logit / t
    return 1.0 / (1.0 + np.exp(-z))


# ---------------------------------------------------------------------------
# Layer: conf → thr / rank metrics (pure evaluation; no thrash, no promote)
# ---------------------------------------------------------------------------


def metrics_at_threshold(
    conf: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    *,
    thr: float,
    coverage_for_selective: float = 0.8,
) -> dict[str, float]:
    """ECE full, ECE on accepted (conf>=thr), abstain rate, IoU accepted, selective@cov."""
    conf = np.asarray(conf, dtype=np.float64).ravel()
    labels = np.asarray(labels, dtype=np.float64).ravel()
    ious = np.asarray(ious, dtype=np.float64).ravel()
    n = conf.size
    if n == 0:
        return {
            "n": 0.0,
            "abstain_rate": float("nan"),
            "keep_rate": float("nan"),
            "ece_full": float("nan"),
            "ece_accepted": float("nan"),
            "mean_iou_accepted": float("nan"),
            "mean_conf_accepted": float("nan"),
            "selective_iou_at_coverage": float("nan"),
        }
    keep = conf >= float(thr)
    n_keep = int(keep.sum())
    ece_full = ece_patch_conf(conf, labels)
    if n_keep > 0:
        ece_acc = ece_patch_conf(conf[keep], labels[keep])
        iou_acc = float(ious[keep].mean())
        conf_acc = float(conf[keep].mean())
    else:
        ece_acc = float("nan")
        iou_acc = float("nan")
        conf_acc = float("nan")
    sel = selective_iou_at_coverage(ious, conf, coverage=coverage_for_selective)
    return {
        "n": float(n),
        "abstain_rate": float(1.0 - n_keep / n),
        "keep_rate": float(n_keep / n),
        "ece_full": float(ece_full),
        "ece_accepted": float(ece_acc),
        "mean_iou_accepted": iou_acc,
        "mean_conf_accepted": conf_acc,
        "selective_iou_at_coverage": float(sel["selective_iou"]),
        "n_keep": float(n_keep),
        "threshold": float(thr),
    }


def rank_reject_scorecard(
    cal: LogisticCalibrator,
    features: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    *,
    thr: float = ITER1_LOCKED_REJECT_THR,
    temperature: float = ITER1_LOCKED_TEMPERATURE,
    coverage_for_selective: float = 0.8,
) -> dict[str, Any]:
    """Pure math path: features → conf → (optional T) → thr reject metrics.

    Compatibility helper for lab scripts. Prefer
    ``product_facade.ClmEnsembleV34Facade.run_pipeline`` / ``build_scorecard``
    for the product scorecard. Default thr/temp are frozen iter1 reject;
    report-only on TEST/LOFO/W3 — do not re-tune thr on holdout.
    """
    conf = confidences_from_features(cal, features)
    conf_t = apply_confidence_temperature(conf, float(temperature))
    metrics = metrics_at_threshold(
        conf_t,
        labels,
        ious,
        thr=float(thr),
        coverage_for_selective=coverage_for_selective,
    )
    return {
        "product_id": DEFAULT_PRODUCT_ID,
        "surface": RECOMMENDED_LAB_SURFACE,
        "thr": float(thr),
        "temperature": float(temperature),
        "conf_band": conf_band_summary(conf_t),
        "metrics": metrics,
        "rails": lab_product_rails(),
        "note": (
            "math scorecard under product_facade; prefer ClmEnsembleV34Facade for product path"
        ),
    }


def score_val_candidate(
    m: dict[str, float],
    *,
    min_keep_rate: float = 0.45,
    baseline_ece_full: float,
    baseline_mean_iou: float,
    prefer_explicit_reject: bool = True,
) -> float:
    """Higher is better — lab objective (not a field promote gate).

    Primary win for this friction: **explicit mask reject** + higher IoU on
    accepted patches. ECE is secondary: confidences may stay overconfident
    even after reject (honest finding).
    """
    keep = float(m.get("keep_rate") or 0.0)
    abstain = float(m.get("abstain_rate") or 0.0)
    if keep < min_keep_rate or not np.isfinite(m.get("mean_iou_accepted", float("nan"))):
        return -1e9
    iou_a = float(m["mean_iou_accepted"])
    ece_a = float(m.get("ece_accepted") or 1.0)
    if not np.isfinite(ece_a):
        return -1e9
    # Reward IoU lift vs baseline full set; mild ECE penalty
    score = (iou_a - float(baseline_mean_iou)) - 0.25 * ece_a
    if prefer_explicit_reject:
        # Prefer visible reject band ~10–55% (product teaching: ABSTAIN de máscara)
        if 0.10 <= abstain <= 0.55:
            score += 0.08
        elif abstain < 0.02:
            score -= 0.15  # thr too low → no reject surface
        elif abstain > 0.70:
            score -= 0.10
    if ece_a < baseline_ece_full:
        score += 0.03
    return float(score)


def risk_coverage_curve(
    conf: np.ndarray,
    ious: np.ndarray,
    *,
    coverages: Sequence[float] | None = None,
) -> list[dict[str, float]]:
    """Selective prediction curve: mean IoU on top-coverage fraction by confidence.

    Does **not** tune thresholds. Pure evaluation of ranking quality.
    Coverage 1.0 = full set mean IoU. Shares conf protocol with thr-reject.
    """
    conf = np.asarray(conf, dtype=np.float64).ravel()
    ious = np.asarray(ious, dtype=np.float64).ravel()
    if conf.size == 0 or conf.size != ious.size:
        return []
    covs = (
        list(coverages)
        if coverages is not None
        else [
            1.0,
            0.9,
            0.8,
            0.7,
            0.6,
            0.5,
            0.4,
        ]
    )
    rows: list[dict[str, float]] = []
    full_mean = float(ious.mean())
    for cov in covs:
        c = float(cov)
        if c <= 0.0:
            continue
        sel = selective_iou_at_coverage(ious, conf, coverage=min(c, 1.0))
        siou = float(sel["selective_iou"])
        rows.append(
            {
                "coverage_target": min(c, 1.0),
                "coverage_actual": float(sel["coverage_actual"]),
                "n_keep": float(sel["n_keep"]),
                "selective_iou": siou,
                "lift_vs_full": siou - full_mean if np.isfinite(siou) else float("nan"),
            }
        )
    return rows


def thr_operating_points(
    conf: np.ndarray,
    labels: np.ndarray,
    ious: np.ndarray,
    thresholds: Sequence[float],
) -> list[dict[str, float]]:
    """Frozen thr-based operating points (not a tune)."""
    out: list[dict[str, float]] = []
    for thr in thresholds:
        m = metrics_at_threshold(conf, labels, ious, thr=float(thr))
        out.append(
            {
                "threshold": float(thr),
                "keep_rate": float(m["keep_rate"]),
                "abstain_rate": float(m["abstain_rate"]),
                "mean_iou_accepted": float(m["mean_iou_accepted"]),
                "mean_conf_accepted": float(m["mean_conf_accepted"]),
                "ece_full": float(m["ece_full"]),
                "ece_accepted": float(m["ece_accepted"]),
                "n_keep": float(m.get("n_keep") or 0.0),
            }
        )
    return out


def conf_band_summary(conf: np.ndarray) -> dict[str, float]:
    """Where confidences live (explains thr=0.35 never rejects)."""
    c = np.asarray(conf, dtype=np.float64).ravel()
    if c.size == 0:
        return {"n": 0.0}
    qs = [0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0]
    pct = np.quantile(c, qs)
    return {
        "n": float(c.size),
        "mean": float(c.mean()),
        "std": float(c.std()),
        "min": float(pct[0]),
        "p05": float(pct[1]),
        "p25": float(pct[2]),
        "p50": float(pct[3]),
        "p75": float(pct[4]),
        "p95": float(pct[5]),
        "max": float(pct[6]),
    }


@dataclass(frozen=True)
class LabRejectTuneResult:
    best_threshold: float
    best_temperature: float
    val_metrics: dict[str, float]
    test_metrics_baseline: dict[str, float]
    test_metrics_tuned: dict[str, float]
    val_sweep_top: list[dict[str, float]]
    protocol_note: str


def tune_reject_and_temperature(
    cal: LogisticCalibrator,
    val_features: np.ndarray,
    val_labels: np.ndarray,
    val_ious: np.ndarray,
    test_features: np.ndarray,
    test_labels: np.ndarray,
    test_ious: np.ndarray,
    *,
    thr_grid: Sequence[float] | None = None,
    temp_grid: Sequence[float] | None = None,
    min_keep_rate: float = 0.45,
    baseline_thr: float = LEGACY_PRODUCT_ABSTAIN_THR,
) -> LabRejectTuneResult:
    """VAL-only tune of confidence temperature + abstain threshold; TEST frozen eval.

    Product default after iter1 is **frozen** (``ITER1_LOCKED_REJECT_THR`` /
    ``RECOMMENDED_LAB_SURFACE``). Prefer facade scorecards for report-only
    multi-fire eval. This sweep is historical VAL discovery, not ECE thrash.

    Note: Head A confidences for v34 cluster tightly (~0.74–0.81). Useful
    reject thresholds are typically **near that band** (e.g. 0.74–0.81), not
    the legacy product default 0.35 (which yields abstain_rate≈0).
    """
    # Dense band around Head A conf (~0.74–0.81) + exact locked iter1 thr.
    thr_grid = list(thr_grid) if thr_grid is not None else list(np.linspace(0.72, 0.82, 21))
    locked = float(ITER1_LOCKED_REJECT_THR)
    if not any(abs(float(t) - locked) < 1e-12 for t in thr_grid):
        thr_grid = sorted({float(t) for t in thr_grid} | {locked})
    temp_grid = list(temp_grid) if temp_grid is not None else [0.85, 1.0, 1.15, 1.3]

    conf_val_raw = confidences_from_features(cal, val_features)
    conf_test_raw = confidences_from_features(cal, test_features)

    baseline_test = metrics_at_threshold(conf_test_raw, test_labels, test_ious, thr=baseline_thr)
    baseline_val_full_ece = float(ece_patch_conf(conf_val_raw, val_labels))
    baseline_val_mean_iou = float(np.asarray(val_ious, dtype=np.float64).mean())

    best_score = -1e18
    best: dict[str, Any] = {
        "thr": baseline_thr,
        "temp": 1.0,
        "val": metrics_at_threshold(conf_val_raw, val_labels, val_ious, thr=baseline_thr),
    }
    ranked: list[tuple[float, dict[str, float]]] = []

    for temp in temp_grid:
        conf_v = apply_confidence_temperature(conf_val_raw, temp)
        for thr in thr_grid:
            m = metrics_at_threshold(conf_v, val_labels, val_ious, thr=float(thr))
            sc = score_val_candidate(
                m,
                min_keep_rate=min_keep_rate,
                baseline_ece_full=baseline_val_full_ece,
                baseline_mean_iou=baseline_val_mean_iou,
            )
            row = {**m, "temperature": float(temp), "score_val": float(sc)}
            ranked.append((sc, row))
            if sc > best_score:
                best_score = sc
                best = {"thr": float(thr), "temp": float(temp), "val": m}

    ranked.sort(key=lambda x: -x[0])
    top = [r for _, r in ranked[:8]]

    conf_test_t = apply_confidence_temperature(conf_test_raw, float(best["temp"]))
    test_tuned = metrics_at_threshold(conf_test_t, test_labels, test_ious, thr=float(best["thr"]))

    return LabRejectTuneResult(
        best_threshold=float(best["thr"]),
        best_temperature=float(best["temp"]),
        val_metrics={**best["val"], "score_val": float(best_score)},
        test_metrics_baseline=baseline_test,
        test_metrics_tuned=test_tuned,
        val_sweep_top=top,
        protocol_note=(
            "Tuned on VAL only (temperature + abstain_threshold). "
            "TEST metrics are frozen evaluation — not used for selection. "
            f"Product default surface remains {RECOMMENDED_LAB_SURFACE} "
            f"(thr={ITER1_LOCKED_REJECT_THR}). "
            "Lab research_open path only; field_ops fusion OFF; "
            "ml_product_go true (human promote 2026-08-05; no silent auto-flip). "
            "Same-holdout ECE retune thrash is removed (not available from this module)."
        ),
    )


# ---------------------------------------------------------------------------
# Dead thrash REMOVED: same-holdout ECE post-hoc retune
# ---------------------------------------------------------------------------
# Historical ``tune_ece_recalibration`` / ``LabEceRecalResult`` / opt-in
# ``allow_same_holdout_ece_thrash`` are gone. ECE same-holdout thrash is sealed
# at scripts/run_lab_ml_loop_v34_ece.py + product_facade.refuse_dead_path.
# Do not re-add thrash APIs here.


__all__ = [
    "DEFAULT_PRODUCT_ID",
    "ITER1_LOCKED_REJECT_THR",
    "ITER1_LOCKED_TEMPERATURE",
    "LEGACY_PRODUCT_ABSTAIN_THR",
    "LabRejectTuneResult",
    "RECOMMENDED_LAB_SURFACE",
    "apply_confidence_temperature",
    "conf_band_summary",
    "confidences_from_features",
    "lab_product_rails",
    "metrics_at_threshold",
    "rank_reject_scorecard",
    "risk_coverage_curve",
    "score_val_candidate",
    "thr_operating_points",
    "tune_reject_and_temperature",
]
