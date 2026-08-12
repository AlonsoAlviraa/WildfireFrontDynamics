"""Reliability / selective / AURC primitives for the unified rank-reject protocol.

Architecture role (clm_ensemble_v34 lab ML product)
---------------------------------------------------
Shared **evaluation** layer used by reject calibration, selective-SDC ranking,
LOFO / multi-fire honesty, product facade, and scorecards. Ranking and abstain
paths must share one protocol surface; these primitives back that API:

  features -> calibrator conf -> rank/reject thr (VAL only) -> scorecard
                         ^
                         |
              ECE / selective IoU / risk-coverage / AURC (this module)

Protocol consumers (do not reimplement these formulas)
------------------------------------------------------
* ``rank_reject_protocol`` -- VAL thr + frozen report orchestration
* ``lab_reject_calibration`` / ``lab_selective_sdc`` -- thr-reject vs ranking bake-off
* LOFO / W3 / teach / freeze -- multi-fire honesty report-only

Dual-product rails
------------------
* Lab ML rail only: mask IoU + conf reliability (**IoU != ROS**).
* field_ops fusion stays **OFF**; ``ml_product_go`` promoted true (human
  authorize 2026-08-05); never silent auto-flip.
* Thr tune / score-family select stay in protocol layer on **VAL only**;
  this module never fits thr or ECE post-hoc.
* Default frozen lab surface: ``iter1_reject_only`` (report metrics only here).
* Multi-fire honesty first-class: Tobarra hard / W3 external / LOFO are
  **report-only** consumers (never fit thr/ECE on those splits).

Dead thrash (not provided here)
-------------------------------
Same-holdout ECE retune, logistic refit promote hooks, Tobarra KEEP reopen of
KILL weights. ECE functions are for **report / scorecard**, not thrash loops.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final

import numpy as np

# Default coverage grid for risk-coverage / AURC (shared reject + selective-SDC).
DEFAULT_RANK_COVERAGES: Final[tuple[float, ...]] = (
    1.0,
    0.9,
    0.8,
    0.7,
    0.6,
    0.5,
    0.4,
)
DEFAULT_SELECTIVE_COVERAGE: Final[float] = 0.8

# Protocol surface labels (metrics are lab-only; no field promote).
PROTOCOL_SURFACE: Final[str] = "iter1_reject_only"
PROTOCOL_ID: Final[str] = "head_a_rank_reject_v1"


def ece_patch_conf(
    confidences: Sequence[float] | np.ndarray,
    labels: Sequence[int | float | bool] | np.ndarray,
    *,
    n_bins: int = 15,
) -> float:
    """Expected Calibration Error for patch-level confidences vs binary labels.

    Head A (patch): ECE on confidence vs y = 1{IoU >= tau}.
    Report-only on TEST / LOFO / external; never a same-holdout retune target.
    """
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    y = np.asarray(labels, dtype=np.float64).ravel()
    if conf.size == 0 or conf.size != y.size:
        return float("nan")
    conf = np.clip(conf, 0.0, 1.0)
    y = (y >= 0.5).astype(np.float64)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = float(conf.size)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (conf >= lo) & (conf <= hi) if i == n_bins - 1 else (conf >= lo) & (conf < hi)
        if not np.any(mask):
            continue
        acc = float(y[mask].mean())
        avg_conf = float(conf[mask].mean())
        ece += (mask.sum() / n) * abs(acc - avg_conf)
    return float(ece)


def ece_pixel_prob(
    probs: np.ndarray,
    targets: np.ndarray,
    *,
    n_bins: int = 15,
    max_pixels: int = 200_000,
    rng: np.random.Generator | None = None,
) -> float:
    """Pixel-level ECE; optional subsample for large maps.

    Head B (pixel): ECE on probability vs binary fire label (scorecard only).
    """
    p = np.asarray(probs, dtype=np.float64).ravel()
    t = np.asarray(targets, dtype=np.float64).ravel()
    if p.size == 0 or p.size != t.size:
        return float("nan")
    if p.size > max_pixels:
        gen = rng or np.random.default_rng(0)
        idx = gen.choice(p.size, size=max_pixels, replace=False)
        p, t = p[idx], t[idx]
    return ece_patch_conf(p, (t >= 0.5).astype(np.float64), n_bins=n_bins)


def selective_iou_at_coverage(
    ious: Sequence[float] | np.ndarray,
    confidences: Sequence[float] | np.ndarray,
    *,
    coverage: float = DEFAULT_SELECTIVE_COVERAGE,
) -> dict[str, float]:
    """Mean IoU on top ``coverage`` fraction by confidence (selective prediction).

    Shared by thr-reject scorecards and selective-SDC ranking bake-offs.
    Higher score/confidence is kept first. Does **not** select thr.
    """
    iou = np.asarray(ious, dtype=np.float64).ravel()
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    if iou.size == 0 or iou.size != conf.size:
        return {"selective_iou": float("nan"), "coverage_actual": 0.0, "n_keep": 0}
    cov = float(coverage)
    if cov <= 0.0:
        return {"selective_iou": float("nan"), "coverage_actual": 0.0, "n_keep": 0}
    n_keep = int(iou.size) if cov >= 1.0 else max(1, int(np.ceil(cov * iou.size)))
    order = np.argsort(-conf)
    keep = order[:n_keep]
    return {
        "selective_iou": float(iou[keep].mean()),
        "coverage_actual": float(n_keep / iou.size),
        "n_keep": int(n_keep),
    }


def risk_coverage_curve(
    scores: Sequence[float] | np.ndarray,
    ious: Sequence[float] | np.ndarray,
    *,
    coverages: Sequence[float] | None = None,
) -> list[dict[str, float]]:
    """Selective prediction curve: mean IoU on top-coverage fraction by score.

    Pure ranking evaluation for both reject conf and selective-SDC score
    families. Coverage 1.0 = full-set mean IoU. Does **not** tune thresholds.
    """
    score = np.asarray(scores, dtype=np.float64).ravel()
    iou = np.asarray(ious, dtype=np.float64).ravel()
    if score.size == 0 or score.size != iou.size:
        return []
    covs = list(coverages) if coverages is not None else list(DEFAULT_RANK_COVERAGES)
    rows: list[dict[str, float]] = []
    full_mean = float(iou.mean())
    for cov in covs:
        c = float(cov)
        if c <= 0.0:
            continue
        sel = selective_iou_at_coverage(iou, score, coverage=min(c, 1.0))
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


def aurc_from_curve(rows: Sequence[dict[str, float]] | list[dict[str, float]]) -> float:
    """Trapezoid AURC using risk = 1 - selective_iou over coverage_target grid.

    Lower is better. Shared primitive for selective-SDC bake-off and reject
    ranking quality. Requires at least one finite risk point.
    """
    if not rows:
        return float("nan")
    pts = sorted(
        (
            float(r["coverage_target"]),
            1.0 - float(r["selective_iou"])
            if np.isfinite(r.get("selective_iou", float("nan")))
            else float("nan"),
        )
        for r in rows
    )
    pts = [(c, r) for c, r in pts if np.isfinite(r)]
    if len(pts) < 2:
        return float(pts[0][1]) if pts else float("nan")
    area = 0.0
    for i in range(len(pts) - 1):
        c0, r0 = pts[i]
        c1, r1 = pts[i + 1]
        area += 0.5 * (r0 + r1) * (c1 - c0)
    return float(area)


def score_ranking(
    score: Sequence[float] | np.ndarray,
    ious: Sequence[float] | np.ndarray,
    *,
    coverages: Sequence[float] | None = None,
) -> dict[str, Any]:
    """Shared ranking quality metrics (selective@0.8 + AURC). Not a thr tune.

    Canonical rank-side of the unified rank/reject protocol API. Used by
    selective-SDC bake-off and reject risk-curve reporting on the same formulas.
    """
    s = np.asarray(score, dtype=np.float64).ravel()
    iou = np.asarray(ious, dtype=np.float64).ravel()
    covs = list(coverages) if coverages is not None else list(DEFAULT_RANK_COVERAGES)
    curve = risk_coverage_curve(s, iou, coverages=covs)
    sel80 = selective_iou_at_coverage(iou, s, coverage=DEFAULT_SELECTIVE_COVERAGE)
    full = float(np.mean(iou)) if iou.size else float("nan")
    return {
        "selective_iou_at_80": float(sel80["selective_iou"]),
        "coverage_actual_80": float(sel80["coverage_actual"]),
        "full_mean_iou": full,
        "lift_vs_full_at_80": float(sel80["selective_iou"]) - full
        if np.isfinite(sel80["selective_iou"]) and np.isfinite(full)
        else float("nan"),
        "aurc": aurc_from_curve(curve),
        "curve": curve,
        "protocol": PROTOCOL_ID,
        "surface_note": PROTOCOL_SURFACE,
    }


def reject_thr_metrics(
    confidences: Sequence[float] | np.ndarray,
    ious: Sequence[float] | np.ndarray,
    *,
    thr: float,
    labels: Sequence[int | float | bool] | np.ndarray | None = None,
    coverage_for_selective: float = DEFAULT_SELECTIVE_COVERAGE,
) -> dict[str, float]:
    """Shared abstain-side metrics at a frozen conf threshold.

    Rank/reject protocol apply path: conf >= thr keeps the patch. Does not
    select thr (VAL thr lives in protocol layer). Optional labels enable ECE
    on full and accepted sets for scorecards.
    """
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    iou = np.asarray(ious, dtype=np.float64).ravel()
    n = conf.size
    if n == 0 or n != iou.size:
        out: dict[str, float] = {
            "thr": float(thr),
            "n": 0.0,
            "n_keep": 0.0,
            "abstain_rate": float("nan"),
            "keep_rate": float("nan"),
            "mean_iou_accepted": float("nan"),
            "risk": float("nan"),
            "selective_iou_at_coverage": float("nan"),
            "ece_full": float("nan"),
            "ece_accepted": float("nan"),
        }
        return out
    keep = conf >= float(thr)
    n_keep = int(keep.sum())
    if n_keep == 0:
        iou_acc = float("nan")
        conf_acc = float("nan")
        risk = float("nan")
        ece_acc = float("nan")
    else:
        iou_acc = float(iou[keep].mean())
        conf_acc = float(conf[keep].mean())
        risk = float(1.0 - iou_acc)
        ece_acc = float("nan")
    ece_full = float("nan")
    if labels is not None:
        y = np.asarray(labels, dtype=np.float64).ravel()
        if y.size == n:
            ece_full = float(ece_patch_conf(conf, y))
            if n_keep > 0:
                ece_acc = float(ece_patch_conf(conf[keep], y[keep]))
    sel = selective_iou_at_coverage(iou, conf, coverage=coverage_for_selective)
    return {
        "thr": float(thr),
        "n": float(n),
        "n_keep": float(n_keep),
        "abstain_rate": float(1.0 - n_keep / n),
        "keep_rate": float(n_keep / n),
        "mean_iou_accepted": iou_acc,
        "mean_conf_accepted": conf_acc if n_keep > 0 else float("nan"),
        "risk": risk,
        "selective_iou_at_coverage": float(sel["selective_iou"]),
        "ece_full": ece_full,
        "ece_accepted": ece_acc,
        "threshold": float(thr),
    }


def rank_reject_metric_bundle(
    confidences: Sequence[float] | np.ndarray,
    ious: Sequence[float] | np.ndarray,
    *,
    thr: float,
    labels: Sequence[int | float | bool] | np.ndarray | None = None,
    coverages: Sequence[float] | None = None,
    selective_coverage: float = DEFAULT_SELECTIVE_COVERAGE,
) -> dict[str, Any]:
    """One protocol metric surface: ranking quality + frozen thr reject metrics.

    Backs the shared rank/reject API so reject and selective-SDC paths do not
    fork ECE / selective / AURC formulas. No thr selection; stamps rails only.
    """
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    iou = np.asarray(ious, dtype=np.float64).ravel()
    ranking = score_ranking(conf, iou, coverages=coverages)
    reject = reject_thr_metrics(
        conf,
        iou,
        thr=float(thr),
        labels=labels,
        coverage_for_selective=selective_coverage,
    )
    return {
        "protocol": PROTOCOL_ID,
        "recommended_lab_surface": PROTOCOL_SURFACE,
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "ranking": ranking,
        "reject": reject,
        "aurc": ranking.get("aurc"),
        "selective_iou_at_80": ranking.get("selective_iou_at_80"),
        "ece_full": reject.get("ece_full"),
        "ece_accepted": reject.get("ece_accepted"),
    }


def random_selective_baseline(
    ious: Sequence[float],
    *,
    coverage: float = DEFAULT_SELECTIVE_COVERAGE,
    n_trials: int = 50,
    seed: int = 0,
) -> dict[str, float]:
    """Mean IoU if keeping a random ``coverage`` subset (null for selective utility)."""
    iou = np.asarray(ious, dtype=np.float64).ravel()
    if iou.size == 0:
        return {"random_selective_iou_mean": float("nan"), "random_selective_iou_std": float("nan")}
    cov = float(coverage)
    if cov <= 0.0:
        return {
            "random_selective_iou_mean": float("nan"),
            "random_selective_iou_std": float("nan"),
            "n_trials": float(n_trials),
            "coverage": cov,
        }
    n_keep = int(iou.size) if cov >= 1.0 else max(1, int(np.ceil(cov * iou.size)))
    gen = np.random.default_rng(seed)
    scores = []
    for _ in range(n_trials):
        idx = gen.choice(iou.size, size=n_keep, replace=False)
        scores.append(float(iou[idx].mean()))
    arr = np.asarray(scores, dtype=np.float64)
    return {
        "random_selective_iou_mean": float(arr.mean()),
        "random_selective_iou_std": float(arr.std(ddof=0)),
        "n_trials": float(n_trials),
        "coverage": cov,
    }


def shuffle_conf_baseline(
    ious: Sequence[float],
    confidences: Sequence[float],
    *,
    coverage: float = DEFAULT_SELECTIVE_COVERAGE,
    n_trials: int = 50,
    seed: int = 0,
) -> dict[str, float]:
    """U1b null: selective@coverage using shuffled confidences (ranking null)."""
    iou = np.asarray(ious, dtype=np.float64).ravel()
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    if iou.size == 0 or iou.size != conf.size:
        return {
            "shuffle_selective_iou_mean": float("nan"),
            "shuffle_selective_iou_std": float("nan"),
        }
    gen = np.random.default_rng(seed)
    scores = []
    for _ in range(n_trials):
        shuffled = gen.permutation(conf)
        sel = selective_iou_at_coverage(iou, shuffled, coverage=coverage)
        scores.append(float(sel["selective_iou"]))
    arr = np.asarray(scores, dtype=np.float64)
    return {
        "shuffle_selective_iou_mean": float(np.nanmean(arr)),
        "shuffle_selective_iou_std": float(np.nanstd(arr)),
        "n_trials": float(n_trials),
        "coverage": float(coverage),
    }


def selective_beats_random(
    ious: Sequence[float],
    confidences: Sequence[float],
    *,
    coverage: float = DEFAULT_SELECTIVE_COVERAGE,
    n_trials: int = 50,
    seed: int = 0,
    margin: float = 0.01,
    use_shuffle_conf: bool = True,
) -> dict[str, Any]:
    """U1 helper: selective@coverage IoU must beat null baseline mean + margin (δ=0.01).

    Default null is **shuffled confidences** (U1b design). Set
    ``use_shuffle_conf=False`` for the random-subset IoU null.
    """
    sel = selective_iou_at_coverage(ious, confidences, coverage=coverage)
    s = sel["selective_iou"]
    if use_shuffle_conf:
        null = shuffle_conf_baseline(
            ious, confidences, coverage=coverage, n_trials=n_trials, seed=seed
        )
        r = null["shuffle_selective_iou_mean"]
        null_key = "shuffle_selective_iou_mean"
    else:
        null = random_selective_baseline(ious, coverage=coverage, n_trials=n_trials, seed=seed)
        r = null["random_selective_iou_mean"]
        null_key = "random_selective_iou_mean"
    ok = bool(np.isfinite(s) and np.isfinite(r) and s >= r + margin)
    return {
        **sel,
        **null,
        "beats_random": ok,
        "margin": margin,
        "null_kind": "shuffle_conf" if use_shuffle_conf else "random_subset",
        "null_key": null_key,
        "delta_vs_random": float(s - r) if np.isfinite(s) and np.isfinite(r) else float("nan"),
    }


def bootstrap_ci_mean(
    values: Sequence[float],
    *,
    n_boot: int = 200,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict[str, float]:
    x = np.asarray(values, dtype=np.float64).ravel()
    if x.size == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan")}
    gen = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        sample = gen.choice(x, size=x.size, replace=True)
        means.append(float(sample.mean()))
    arr = np.sort(np.asarray(means))
    lo_i = int(np.floor(alpha / 2 * n_boot))
    hi_i = int(np.ceil((1 - alpha / 2) * n_boot)) - 1
    lo_i = max(0, min(lo_i, n_boot - 1))
    hi_i = max(0, min(hi_i, n_boot - 1))
    return {
        "mean": float(x.mean()),
        "lo": float(arr[lo_i]),
        "hi": float(arr[hi_i]),
        "n_boot": float(n_boot),
    }


def overconfidence_gap(
    confidences: Sequence[float],
    labels: Sequence[int | float | bool],
) -> float:
    """mean(conf) - mean(accuracy); positive => overconfident."""
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    y = np.asarray(labels, dtype=np.float64).ravel()
    if conf.size == 0 or conf.size != y.size:
        return float("nan")
    acc = float((y >= 0.5).mean())
    return float(conf.mean() - acc)
