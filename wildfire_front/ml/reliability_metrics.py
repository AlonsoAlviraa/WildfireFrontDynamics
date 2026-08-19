"""Reliability / selective prediction metrics for ML product scorecards.

Head A (patch): ECE on confidence vs y = 1{IoU >= tau}
Head B (pixel): ECE on probability vs binary fire label (scorecard only)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np


def ece_patch_conf(
    confidences: Sequence[float] | np.ndarray,
    labels: Sequence[int | float | bool] | np.ndarray,
    *,
    n_bins: int = 15,
) -> float:
    """Expected Calibration Error for patch-level confidences vs binary labels."""
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
    eligible_mask: np.ndarray | None = None,
) -> float:
    """Pixel-level ECE; optional target-independent support and subsample."""
    p_full = np.asarray(probs, dtype=np.float64)
    t_full = np.asarray(targets, dtype=np.float64)
    if p_full.shape != t_full.shape or p_full.size == 0:
        return float("nan")
    eligible = np.ones(p_full.shape, dtype=bool)
    if eligible_mask is not None:
        candidate = np.asarray(eligible_mask) > 0.5
        if candidate.shape != p_full.shape:
            return float("nan")
        eligible &= candidate
    eligible &= np.isfinite(p_full) & np.isfinite(t_full)
    p = p_full[eligible].ravel()
    t = t_full[eligible].ravel()
    if p.size == 0:
        return float("nan")
    if p.size > max_pixels:
        gen = rng or np.random.default_rng(0)
        idx = gen.choice(p.size, size=max_pixels, replace=False)
        p, t = p[idx], t[idx]
    return ece_patch_conf(p, (t >= 0.5).astype(np.float64), n_bins=n_bins)


def pixel_selective_error_at_coverage(
    probs: np.ndarray,
    targets: np.ndarray,
    *,
    coverage: float = 0.8,
    eligible_mask: np.ndarray | None = None,
    threshold: float = 0.5,
) -> dict[str, float]:
    """Classification error after retaining the most confident pixels.

    Confidence is the distance from the binary decision boundary.  An
    ``eligible_mask`` may restrict evaluation only when it is derived without
    looking at the target (for example the FCER ring from ``t0``).
    """
    p_full = np.asarray(probs, dtype=np.float64)
    t_full = np.asarray(targets, dtype=np.float64)
    empty = {"selective_error": float("nan"), "coverage_actual": 0.0, "n_keep": 0.0}
    if p_full.shape != t_full.shape or p_full.size == 0:
        return empty
    eligible = np.ones(p_full.shape, dtype=bool)
    if eligible_mask is not None:
        candidate = np.asarray(eligible_mask) > 0.5
        if candidate.shape != p_full.shape:
            return empty
        eligible &= candidate
    eligible &= np.isfinite(p_full) & np.isfinite(t_full)
    p = np.clip(p_full[eligible].ravel(), 0.0, 1.0)
    target = t_full[eligible].ravel() >= threshold
    if p.size == 0 or coverage <= 0.0:
        return empty
    n_keep = p.size if coverage >= 1.0 else max(1, int(np.ceil(float(coverage) * p.size)))
    confidence = np.abs(p - threshold)
    keep = np.argsort(-confidence, kind="mergesort")[:n_keep]
    error = (p[keep] >= threshold) != target[keep]
    return {
        "selective_error": float(error.mean()),
        "coverage_actual": float(n_keep / p.size),
        "n_keep": float(n_keep),
    }


def pixel_risk_coverage_curve(
    probs: np.ndarray,
    targets: np.ndarray,
    *,
    coverages: Sequence[float] = (0.2, 0.4, 0.6, 0.8, 1.0),
    eligible_mask: np.ndarray | None = None,
    threshold: float = 0.5,
) -> dict[str, Any]:
    """Return a compact selective pixel-error curve and normalized AURC."""
    points = []
    for coverage in coverages:
        row = pixel_selective_error_at_coverage(
            probs,
            targets,
            coverage=float(coverage),
            eligible_mask=eligible_mask,
            threshold=threshold,
        )
        points.append({"coverage": float(coverage), **row})
    valid = [row for row in points if np.isfinite(row["selective_error"])]
    if len(valid) < 2:
        aurc = float("nan")
    else:
        x = np.asarray([row["coverage_actual"] for row in valid], dtype=np.float64)
        y = np.asarray([row["selective_error"] for row in valid], dtype=np.float64)
        order = np.argsort(x)
        width = float(x[order][-1] - x[order][0])
        aurc = float(np.trapezoid(y[order], x[order]) / width) if width > 0.0 else float(y.mean())
    return {
        "points": points,
        "aurc_normalized": aurc,
        "semantics": "pixel_classification_error_ranked_by_probability_margin",
    }


def selective_iou_at_coverage(
    ious: Sequence[float] | np.ndarray,
    confidences: Sequence[float] | np.ndarray,
    *,
    coverage: float = 0.8,
) -> dict[str, float]:
    """Mean IoU on top ``coverage`` fraction by confidence (selective prediction)."""
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


def random_selective_baseline(
    ious: Sequence[float],
    *,
    coverage: float = 0.8,
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
    coverage: float = 0.8,
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
    coverage: float = 0.8,
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


def patch_miss_rate_at_coverage(
    ious: Sequence[float] | np.ndarray,
    confidences: Sequence[float] | np.ndarray,
    *,
    coverage: float = 0.8,
    tau: float = 0.5,
) -> dict[str, float]:
    """Among top-``coverage`` patches by confidence, fraction with IoU < ``tau``.

    Patch-level called-set miss. **Not** pixel FNR and **not** a peer CRC claim
    (claim board L6 stays inventable-only until a dedicated scorecard).
    """
    iou = np.asarray(ious, dtype=np.float64).ravel()
    conf = np.asarray(confidences, dtype=np.float64).ravel()
    if iou.size == 0 or iou.size != conf.size:
        return {
            "miss_rate": float("nan"),
            "n_keep": 0.0,
            "n_miss": 0.0,
            "coverage_actual": 0.0,
            "tau": float(tau),
        }
    cov = float(coverage)
    if cov <= 0.0:
        return {
            "miss_rate": float("nan"),
            "n_keep": 0.0,
            "n_miss": 0.0,
            "coverage_actual": 0.0,
            "tau": float(tau),
        }
    n_keep = int(iou.size) if cov >= 1.0 else max(1, int(np.ceil(cov * iou.size)))
    keep = np.argsort(-conf)[:n_keep]
    miss = iou[keep] < float(tau)
    n_miss = int(miss.sum())
    return {
        "miss_rate": float(n_miss / n_keep),
        "n_keep": float(n_keep),
        "n_miss": float(n_miss),
        "coverage_actual": float(n_keep / iou.size),
        "tau": float(tau),
    }


def fnr_proxy_at_budget(
    ious: Sequence[float] | np.ndarray,
    confidences: Sequence[float] | np.ndarray,
    *,
    budget: float = 0.2,
    tau: float = 0.5,
) -> dict[str, float]:
    """Abstain lowest-confidence ``budget`` fraction; miss rate on the called set.

    ``budget`` = Decision Card ABSTAIN tail. ``coverage = 1 - budget`` is the
    GO/HOLD candidate set. Lab proxy only — not tactical dispatch, not L6.
    """
    b = float(budget)
    if b >= 1.0:
        return {
            "fnr_proxy": float("nan"),
            "miss_rate": float("nan"),
            "n_keep": 0.0,
            "n_miss": 0.0,
            "coverage_actual": 0.0,
            "budget": b,
            "coverage": 0.0,
            "tau": float(tau),
        }
    cov = max(0.0, 1.0 - b)
    miss = patch_miss_rate_at_coverage(ious, confidences, coverage=cov, tau=tau)
    return {
        **miss,
        "fnr_proxy": miss["miss_rate"],
        "budget": b,
        "coverage": cov,
    }
