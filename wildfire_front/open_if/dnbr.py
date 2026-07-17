"""dNBR / NBR math and USGS-style severity bins (no network)."""

from __future__ import annotations

from typing import Any

import numpy as np

# USGS-inspired dNBR thresholds (continuous RdNBR-like simplified for dNBR)
DNBR_BINS = (
    ("unburned", -1.0, 0.10),
    ("low", 0.10, 0.27),
    ("moderate_low", 0.27, 0.44),
    ("moderate_high", 0.44, 0.66),
    ("high", 0.66, 2.0),
)


def compute_nbr(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """NBR = (NIR - SWIR) / (NIR + SWIR). Returns float32; invalid → nan."""
    nir = np.asarray(nir, dtype=np.float64)
    swir = np.asarray(swir, dtype=np.float64)
    denom = nir + swir
    with np.errstate(divide="ignore", invalid="ignore"):
        nbr = (nir - swir) / denom
    nbr = nbr.astype(np.float32)
    nbr[~np.isfinite(nbr)] = np.nan
    nbr[denom == 0] = np.nan
    return nbr


def compute_dnbr(nbr_pre: np.ndarray, nbr_post: np.ndarray) -> np.ndarray:
    """dNBR = NBR_pre - NBR_post (positive → vegetation loss / burn signal)."""
    pre = np.asarray(nbr_pre, dtype=np.float32)
    post = np.asarray(nbr_post, dtype=np.float32)
    out = pre - post
    out[~(np.isfinite(pre) & np.isfinite(post))] = np.nan
    return out.astype(np.float32)


def classify_dnbr(dnbr: np.ndarray) -> np.ndarray:
    """Integer class 0..4 matching DNBR_BINS order; -1 = invalid."""
    d = np.asarray(dnbr, dtype=np.float32)
    cls = np.full(d.shape, -1, dtype=np.int8)
    valid = np.isfinite(d)
    for i, (_name, lo, hi) in enumerate(DNBR_BINS):
        if i == 0:
            m = valid & (d < hi)
        elif i == len(DNBR_BINS) - 1:
            m = valid & (d >= lo)
        else:
            m = valid & (d >= lo) & (d < hi)
        cls[m] = i
    return cls


def severity_fractions(dnbr: np.ndarray) -> dict[str, Any]:
    """Fraction of valid pixels per severity bin + summary stats."""
    d = np.asarray(dnbr, dtype=np.float32).ravel()
    valid = d[np.isfinite(d)]
    n = int(valid.size)
    if n == 0:
        return {
            "n_valid": 0,
            "mean": None,
            "p50": None,
            "p90": None,
            "fractions": {name: 0.0 for name, _, _ in DNBR_BINS},
            "burned_frac_ge_0.1": 0.0,
            "burned_frac_ge_0.27": 0.0,
        }
    cls = classify_dnbr(valid)
    fracs: dict[str, float] = {}
    for i, (name, _lo, _hi) in enumerate(DNBR_BINS):
        fracs[name] = float(np.mean(cls == i))
    return {
        "n_valid": n,
        "mean": float(np.mean(valid)),
        "p50": float(np.median(valid)),
        "p90": float(np.percentile(valid, 90)),
        "fractions": fracs,
        "burned_frac_ge_0.1": float(np.mean(valid >= 0.1)),
        "burned_frac_ge_0.27": float(np.mean(valid >= 0.27)),
    }


def scale_s2_reflectance(arr: np.ndarray, *, scale: float = 1e-4) -> np.ndarray:
    """Sentinel-2 L2A digital numbers → reflectance (Element84 often scale 0.0001)."""
    a = np.asarray(arr, dtype=np.float64) * float(scale)
    a[a <= 0] = np.nan
    # clip pathological values
    a = np.clip(a, 0.0, 1.0)
    return a.astype(np.float32)
