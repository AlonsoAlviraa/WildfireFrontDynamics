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
) -> float:
    """Pixel-level ECE; optional subsample for large maps."""
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
