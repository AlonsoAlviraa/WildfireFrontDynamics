"""Arrival-time ROS helpers (deep research S4 / O'Neill-style geometry).

ROS is the **geometry of progression**, not mask IoU. Lampman multi-pass TIR
MAE is a method cite only — never a Tobarra SLA.

Primary formula (arrival field T in seconds, spacing in metres)::

    |∇T|  [s/m]
    ROS   [m/min] = 60 / |∇T|

This matches the physical inverse of the arrival-time surface slope (O'Neill
et al., IJWF 2024 narrative: steeper time surface in distance–time space ⇒
faster spread when time is the dependent axis inverted).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

# Tobarra INFOCAM anchor (confirmed in data/infocam_anchors.json) — cite only.
TOBARRA_VP_M_MIN = 7.0
TOBARRA_AREA_HA = 39.0
TOBARRA_FIRE_ID = "tobarra_20240802"

_TS_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})[_T](\d{2})-(\d{2})-(\d{2})(?:-(\d+))?")


@dataclass(frozen=True)
class MultipassFrame:
    """One geo-referenced LWIR / mask pair with parseable timestamp."""

    image_path: Path
    mask_path: Path | None
    timestamp_utc: str | None
    sort_key: float
    stem: str


def parse_timestamp_from_name(name: str) -> tuple[str | None, float | None]:
    """Parse YYYY-MM-DD_HH-MM-SS[-ms] from IF filenames.

    Returns (iso-ish string, unix timestamp for sort) or (None, None).
    """
    m = _TS_RE.search(name)
    if not m:
        return None, None
    date_s, hh, mm, ss = m.group(1), m.group(2), m.group(3), m.group(4)
    ms = m.group(5) or "0"
    try:
        base = datetime.strptime(f"{date_s} {hh}:{mm}:{ss}", "%Y-%m-%d %H:%M:%S")
        key = base.timestamp() + int(ms) / 1000.0
        iso = (
            f"{date_s}T{hh}:{mm}:{ss}.{int(ms):03d}Z" if m.group(5) else f"{date_s}T{hh}:{mm}:{ss}Z"
        )
        return iso, key
    except ValueError:
        return None, None


def _list_tifs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files = list(directory.glob("*.tif")) + list(directory.glob("*.tiff"))
    return sorted(set(files), key=lambda p: p.name)


def discover_multipass_chain(
    images_dir: Path,
    masks_dir: Path | None = None,
    *,
    min_frames: int = 2,
    require_mask: bool = True,
) -> dict[str, Any]:
    """Discover ≥2 geo-referenced LWIR frames with timestamps on disk.

    Does **not** invent frames. Returns a machine-readable inventory dict.
    """
    images = _list_tifs(images_dir)
    mask_by_stem: dict[str, Path] = {}
    if masks_dir is not None and masks_dir.is_dir():
        for mpath in _list_tifs(masks_dir):
            stem = mpath.stem
            if stem.endswith("_mask"):
                stem = stem[: -len("_mask")]
            mask_by_stem[stem] = mpath

    frames: list[MultipassFrame] = []
    for img in images:
        stem = img.stem
        mask = mask_by_stem.get(stem)
        if mask is None and masks_dir is not None:
            cand = masks_dir / f"{stem}_mask.tif"
            if cand.is_file():
                mask = cand
        if require_mask and mask is None:
            continue
        iso, key = parse_timestamp_from_name(img.name)
        if key is None:
            # Keep frame with lexical sort key if no timestamp — still geo TIF.
            key = float(len(frames))
        frames.append(
            MultipassFrame(
                image_path=img,
                mask_path=mask,
                timestamp_utc=iso,
                sort_key=float(key),
                stem=stem,
            )
        )

    frames.sort(key=lambda f: (f.sort_key, f.stem))
    n = len(frames)
    timestamps = [f.timestamp_utc for f in frames if f.timestamp_utc]
    dt_s: list[float] = []
    for i in range(1, len(frames)):
        dt_s.append(frames[i].sort_key - frames[i - 1].sort_key)

    ok = n >= min_frames
    status = "OK" if ok else "BLOCKED_MULTI_PASS_EXPORT"
    reason = None
    if not ok:
        if n == 0:
            reason = "no_paired_georeferenced_frames_on_disk"
        elif n == 1:
            reason = "single_frame_only_need_ge_2"
        else:
            reason = f"need_ge_{min_frames}_frames_got_{n}"

    return {
        "status": status,
        "blocked_reason": reason,
        "n_frames": n,
        "n_with_timestamp": len(timestamps),
        "min_frames_required": min_frames,
        "images_dir": str(images_dir),
        "masks_dir": str(masks_dir) if masks_dir else None,
        "first_timestamp_utc": timestamps[0] if timestamps else None,
        "last_timestamp_utc": timestamps[-1] if timestamps else None,
        "span_s": (frames[-1].sort_key - frames[0].sort_key) if n >= 2 else None,
        "median_dt_s": float(np.median(dt_s)) if dt_s else None,
        "frames": [
            {
                "stem": f.stem,
                "image": str(f.image_path),
                "mask": str(f.mask_path) if f.mask_path else None,
                "timestamp_utc": f.timestamp_utc,
            }
            for f in frames
        ],
        "frame_objects": frames,  # for in-process use; stripped on JSON export
    }


def strip_frame_objects(inventory: dict[str, Any]) -> dict[str, Any]:
    """Drop non-JSON frame_objects before serialisation."""
    out = dict(inventory)
    out.pop("frame_objects", None)
    return out


def arrival_gradient_ros_m_min(
    arrival_s: np.ndarray,
    resolution_m: float,
    *,
    max_plausible_m_min: float = 120.0,
    min_plausible_m_min: float = 0.05,
) -> dict[str, Any]:
    """O'Neill-style ROS from first-arrival raster (seconds).

    Parameters
    ----------
    arrival_s:
        2D array; NaN = unobserved / unburned.
    resolution_m:
        Cell size in metres (isotropic).
    """
    if resolution_m <= 0 or not math.isfinite(resolution_m):
        raise ValueError("resolution_m must be positive and finite")
    arr = np.asarray(arrival_s, dtype=float)
    if arr.ndim != 2:
        raise ValueError("arrival_s must be 2D")
    finite = np.isfinite(arr)
    n_obs = int(finite.sum())
    if n_obs < 4:
        return {
            "status": "skipped",
            "reason": "too_few_arrival_cells",
            "n_arrival_cells": n_obs,
            "n_ros_cells": 0,
            "ros_median_m_min": None,
            "ros_p25_m_min": None,
            "ros_p75_m_min": None,
            "ros_mean_m_min": None,
            "method": "oneill_arrival_gradient_v1",
            "formula": "ROS_m_min = 60 / |grad T_s|",
        }

    # Fill NaN with a large sentinel for gradient edges, then mask.
    filled = np.where(finite, arr, np.nan)
    # Use nan-aware finite differences on a copy with nan-padded edges.
    gy, gx = np.gradient(np.nan_to_num(filled, nan=np.nanmean(arr[finite])), resolution_m)
    # Invalidate gradient where any of the central cell or 4-neighbours lack data.
    valid = finite.copy()
    valid[1:, :] &= finite[:-1, :]
    valid[:-1, :] &= finite[1:, :]
    valid[:, 1:] &= finite[:, :-1]
    valid[:, :-1] &= finite[:, 1:]
    # Interior only (np.gradient uses edge differences).
    valid[0, :] = False
    valid[-1, :] = False
    valid[:, 0] = False
    valid[:, -1] = False

    mag = np.hypot(gx, gy)  # s/m
    with np.errstate(divide="ignore", invalid="ignore"):
        ros = np.where((mag > 1e-12) & valid, 60.0 / mag, np.nan)
    ros = np.where(
        (ros >= min_plausible_m_min) & (ros <= max_plausible_m_min),
        ros,
        np.nan,
    )
    vals = ros[np.isfinite(ros)]
    if vals.size == 0:
        return {
            "status": "skipped",
            "reason": "no_finite_ros_after_gates",
            "n_arrival_cells": n_obs,
            "n_ros_cells": 0,
            "ros_median_m_min": None,
            "ros_p25_m_min": None,
            "ros_p75_m_min": None,
            "ros_mean_m_min": None,
            "method": "oneill_arrival_gradient_v1",
            "formula": "ROS_m_min = 60 / |grad T_s|",
            "resolution_m": resolution_m,
            "max_plausible_m_min": max_plausible_m_min,
        }
    return {
        "status": "ok",
        "reason": None,
        "n_arrival_cells": n_obs,
        "n_ros_cells": int(vals.size),
        "ros_median_m_min": float(np.median(vals)),
        "ros_p25_m_min": float(np.percentile(vals, 25)),
        "ros_p75_m_min": float(np.percentile(vals, 75)),
        "ros_mean_m_min": float(np.mean(vals)),
        "ros_p95_m_min": float(np.percentile(vals, 95)),
        "method": "oneill_arrival_gradient_v1",
        "formula": "ROS_m_min = 60 / |grad T_s|",
        "resolution_m": resolution_m,
        "max_plausible_m_min": max_plausible_m_min,
        "honesty": "Arrival-time gradient ROS is geometry of progression, not ML mask IoU",
    }


def compare_ros_to_anchor(
    ros_m_min: float | None,
    vp_m_min: float | None = TOBARRA_VP_M_MIN,
    *,
    compatible_lo: float = 0.4,
    compatible_hi: float = 2.5,
) -> dict[str, Any]:
    """Honest order-of-magnitude compare vs operational Vp (no silent rescaling)."""
    if ros_m_min is None or not math.isfinite(float(ros_m_min)):
        return {
            "has_ros": False,
            "has_anchor": vp_m_min is not None,
            "reference_vp_m_min": vp_m_min,
            "ros_m_min": None,
            "ratio": None,
            "grade": "no_ros",
            "interpretation_es": "Sin ROS geométrico defendible para comparar con Vp.",
        }
    if vp_m_min is None or not math.isfinite(float(vp_m_min)) or float(vp_m_min) <= 0:
        return {
            "has_ros": True,
            "has_anchor": False,
            "reference_vp_m_min": None,
            "ros_m_min": float(ros_m_min),
            "ratio": None,
            "grade": "no_anchor",
            "interpretation_es": "ROS reportado sin ancla Vp (no inventar Vp).",
        }
    ratio = float(ros_m_min) / float(vp_m_min)
    if compatible_lo <= ratio <= compatible_hi:
        grade = "compatible_order_of_magnitude"
        interp = (
            f"ROS {ros_m_min:.2f} m/min vs Vp {vp_m_min:.1f} m/min "
            f"(ratio {ratio:.2f}): mismo orden de magnitud. Sin reescalado silencioso."
        )
    elif ratio < compatible_lo:
        grade = "underestimate"
        interp = (
            f"ROS {ros_m_min:.2f} m/min << Vp {vp_m_min:.1f} (ratio {ratio:.2f}). "
            "Reportar crudo; no forzar match."
        )
    else:
        grade = "overestimate"
        interp = (
            f"ROS {ros_m_min:.2f} m/min >> Vp {vp_m_min:.1f} (ratio {ratio:.2f}). "
            "Reportar crudo; posible multi-pass / FOV / mask instability."
        )
    return {
        "has_ros": True,
        "has_anchor": True,
        "reference_vp_m_min": float(vp_m_min),
        "ros_m_min": float(ros_m_min),
        "ratio": ratio,
        "grade": grade,
        "interpretation_es": interp,
    }


def s4_rails() -> dict[str, Any]:
    return {
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "lampman_mae_not_sla": True,
        "never_invent_vp": True,
    }


def build_s4_board(
    *,
    status: str,
    inventory: dict[str, Any],
    geometry_ros: dict[str, Any] | None = None,
    arrival_oneill: dict[str, Any] | None = None,
    front_dynamics: dict[str, Any] | None = None,
    anchor_compare: dict[str, Any] | None = None,
    hybrid_refs: list[str] | None = None,
    artifacts: dict[str, str] | None = None,
    blocked_reason: str | None = None,
    mode: str = "ops_geometry",
    created_utc: str | None = None,
    multihorizon: dict[str, Any] | None = None,
    attach_multihorizon: bool = True,
    multihorizon_fallback_ros_m_min: float | None = None,
    multihorizon_lead_times_h: list[float] | None = None,
) -> dict[str, Any]:
    """Machine JSON board schema for multipass S4 export.

    When ``attach_multihorizon`` is True (default), attaches a field_ops
    multi-horizon card from geometry / O'Neill ROS when available. Pass an
    explicit ``multihorizon`` dict to override auto-build.
    """
    from datetime import UTC
    from datetime import datetime as dt

    inv = strip_frame_objects(inventory)
    board: dict[str, Any] = {
        "schema": "wfd_tobarra_multipass_s4_v1",
        "created_utc": created_utc or dt.now(UTC).isoformat(),
        "strategy": "S4_arrival_time_ros_geometry",
        "fire_id": TOBARRA_FIRE_ID,
        "status": status,
        "verdict": status,
        "blocked_reason": blocked_reason,
        "mode": mode,
        "multipass_inventory": inv,
        "geometry_ros": geometry_ros,
        "arrival_oneill_ros": arrival_oneill,
        "front_dynamics_summary": front_dynamics,
        "anchor_compare": anchor_compare
        or compare_ros_to_anchor(
            (geometry_ros or {}).get("primary_ros_m_min")
            if geometry_ros
            else (arrival_oneill or {}).get("ros_median_m_min")
        ),
        "hybrid_refs": hybrid_refs or [],
        "artifacts": artifacts or {},
        "rails": s4_rails(),
        "honesty": [
            "Arrival-time ROS is geometry of progression, not mask IoU",
            "ml_product_go true (lab); field_ops ML fusion OFF",
            "Lampman multi-pass TIR MAE is method cite only — not Tobarra SLA",
            "Thermal mask ≠ official fire perimeter",
            "Vp 7 m/min is INFOCAM anchor cite — not invented and not rescaled onto ROS",
            "Multi-horizon envelopes are field_ops isotropic ROS buffers — not ML next-day IoU",
        ],
        "literature": {
            "oneill_ijwf_2024": "arrival-time raster → ROS from surface slope / inverse gradient",
            "lampman_ijwf_2026": "multi-pass TIR method anchor only",
        },
    }

    if multihorizon is not None:
        board["multihorizon_fieldops"] = multihorizon
    elif attach_multihorizon:
        try:
            from .multihorizon_fieldops import from_s4_board_sources

            card = from_s4_board_sources(
                geometry_ros=geometry_ros,
                arrival_oneill=arrival_oneill,
                fallback_ros_m_min=multihorizon_fallback_ros_m_min,
                lead_times_h=multihorizon_lead_times_h,
                extra={"attached_from": "build_s4_board"},
            )
            if card is not None:
                board["multihorizon_fieldops"] = card.as_dict()
            else:
                board["multihorizon_fieldops"] = {
                    "status": "skipped",
                    "reason": "no_finite_ros_for_multihorizon",
                    "product_rail": "field_ops",
                }
        except Exception as exc:  # pragma: no cover — defensive attach
            board["multihorizon_fieldops"] = {
                "status": "error",
                "reason": str(exc),
                "product_rail": "field_ops",
            }
    return board
