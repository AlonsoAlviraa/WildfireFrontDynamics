"""Emergency-facing products: sector ROS, uncertainty, short-horizon envelope.

Geometry-first. Numbers are **observed or extrapolated from observed ROS**,
never marketed as validated tactical dispatch without independent anchors.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

# Safe operational caps (m/min) for envelope extrusion only.
_ENVELOPE_MAX_ROS_M_MIN = 40.0
_HORIZONS_MIN = (15, 30, 60)


def expansion_bearing_deg_from_centroids(
    centroids: list[tuple[float, float]],
) -> float | None:
    """Bearing of net centroid travel (deg clockwise from north, 0–360)."""
    if len(centroids) < 2:
        return None
    x0, y0 = centroids[0]
    x1, y1 = centroids[-1]
    dx, dy = x1 - x0, y1 - y0
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return None
    # math.atan2(dx, dy): 0 = north, 90 = east
    ang = math.degrees(math.atan2(dx, dy)) % 360.0
    return float(ang)


def ring_centroid(ring: list[tuple[float, float]] | tuple[tuple[float, float], ...]) -> tuple[float, float]:
    pts = np.asarray(ring, dtype=float)
    if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    if len(pts) == 0:
        return 0.0, 0.0
    return float(pts[:, 0].mean()), float(pts[:, 1].mean())


def load_main_front_centroids(geojson_path: Path) -> list[tuple[float, float]]:
    """Centroids of successive rings in main_front.geojson (feature order = time)."""
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    out: list[tuple[float, float]] = []
    for feat in data.get("features") or []:
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and coords:
            out.append(ring_centroid([(float(x), float(y)) for x, y in coords[0]]))
        elif gtype == "LineString" and coords:
            out.append(ring_centroid([(float(x), float(y)) for x, y in coords]))
    return out


def compute_sector_ros(
    primary_ros_m_min: float | None,
    p25_m_min: float | None = None,
    p75_m_min: float | None = None,
    *,
    expansion_bearing_deg: float | None = None,
    n_estimates: int = 0,
) -> dict[str, Any]:
    """Split primary ROS into head / flank / rear guidance sectors.

    When only bulk ROS is available, head uses upper quartile (or 1.15×),
    flank uses primary, rear uses lower quartile (or 0.55×). Bearing is
    optional metadata for GIS arrows — not a wind-calibrated model.
    """
    if primary_ros_m_min is None or not math.isfinite(primary_ros_m_min) or primary_ros_m_min < 0:
        return {
            "status": "abstained",
            "reason": "no_primary_ros",
            "sectors": None,
            "uncertainty_m_min": None,
            "expansion_bearing_deg": expansion_bearing_deg,
        }

    p = float(primary_ros_m_min)
    lo = float(p25_m_min) if p25_m_min is not None and math.isfinite(p25_m_min) else p * 0.55
    hi = float(p75_m_min) if p75_m_min is not None and math.isfinite(p75_m_min) else p * 1.15
    lo = max(0.0, min(lo, p))
    hi = max(p, hi)

    head = min(hi, _ENVELOPE_MAX_ROS_M_MIN)
    flank = min(p, _ENVELOPE_MAX_ROS_M_MIN)
    rear = min(lo, flank)

    unc = abs(hi - lo)
    sectors = {
        "head_m_min": round(head, 4),
        "flank_m_min": round(flank, 4),
        "rear_m_min": round(rear, 4),
        "primary_m_min": round(p, 4),
    }
    if expansion_bearing_deg is not None:
        b = float(expansion_bearing_deg) % 360.0
        sectors["head_bearing_deg"] = round(b, 2)
        sectors["head_sector_deg"] = [round((b - 45) % 360, 2), round((b + 45) % 360, 2)]
        sectors["rear_bearing_deg"] = round((b + 180) % 360, 2)

    return {
        "status": "estimated" if n_estimates >= 1 else "estimated_low_n",
        "sectors": sectors,
        "uncertainty_m_min": {
            "p25": round(lo, 4),
            "p75": round(hi, 4),
            "half_iqr": round(0.5 * unc, 4),
            "n": int(n_estimates),
        },
        "expansion_bearing_deg": expansion_bearing_deg,
        "method": "bulk_ros_quartile_split",
        "label_es": (
            "ROS por sector (orientativo): cabeza≈P75, flanco≈primaria, cola≈P25. "
            "No es despacho táctico validado."
        ),
    }


def compute_short_horizon_envelope(
    primary_ros_m_min: float | None,
    *,
    horizons_min: tuple[int, ...] = _HORIZONS_MIN,
    expansion_bearing_deg: float | None = None,
    quality_grade: str | None = None,
) -> dict[str, Any]:
    """Extrude distance = ROS × time for emergency **guidance** only.

    Label is mandatory: not official dispatch, not ML next-day mask.
    """
    base = {
        "product": "short_horizon_envelope_v1",
        "label_en": (
            "EXTRAPOLATED FRONT GUIDANCE from observed ROS — "
            "NOT validated tactical dispatch, NOT official perimeter forecast"
        ),
        "label_es": (
            "GUÍA DE FRENTE EXTRAPOLADA desde ROS observada — "
            "NO es despacho táctico validado ni perímetro oficial"
        ),
        "horizons_min": list(horizons_min),
        "quality_grade": quality_grade,
        "expansion_bearing_deg": expansion_bearing_deg,
    }
    if primary_ros_m_min is None or not math.isfinite(primary_ros_m_min) or primary_ros_m_min < 0:
        base["status"] = "abstained"
        base["reason"] = "no_primary_ros"
        base["envelopes"] = []
        return base

    ros = min(float(primary_ros_m_min), _ENVELOPE_MAX_ROS_M_MIN)
    envelopes = []
    for h in horizons_min:
        dist_m = ros * float(h)
        envelopes.append(
            {
                "horizon_min": int(h),
                "ros_m_min_used": round(ros, 4),
                "radius_m": round(dist_m, 2),
                "radius_km": round(dist_m / 1000.0, 4),
                "note": "isotropic radius from last observed front if no sector bias applied",
            }
        )
    base["status"] = "ok"
    base["envelopes"] = envelopes
    base["ros_m_min"] = round(ros, 4)
    base["capped"] = float(primary_ros_m_min) > _ENVELOPE_MAX_ROS_M_MIN
    return base


def enrich_ops_dict(
    ops: dict[str, Any],
    *,
    expansion_bearing_deg: float | None = None,
) -> dict[str, Any]:
    """Attach sector_ros + short_horizon_envelope onto operational_metrics-like dict."""
    primary = ops.get("speed_median_m_min")
    if primary is None:
        primary = ops.get("primary_ros_m_min")
    p25 = ops.get("speed_p25_m_min")
    p75 = ops.get("speed_p75_m_min")
    n = int(ops.get("speed_n_observable") or ops.get("primary_ros_n") or 0)
    grade = ops.get("quality_grade")

    sector = compute_sector_ros(
        float(primary) if primary is not None else None,
        float(p25) if p25 is not None else None,
        float(p75) if p75 is not None else None,
        expansion_bearing_deg=expansion_bearing_deg,
        n_estimates=n,
    )
    envelope = compute_short_horizon_envelope(
        float(primary) if primary is not None else None,
        expansion_bearing_deg=expansion_bearing_deg,
        quality_grade=str(grade) if grade else None,
    )
    out = dict(ops)
    out["sector_ros"] = sector
    out["short_horizon_envelope"] = envelope
    out["emergency_product"] = "observed_front_dynamics_v1"
    out["not_a_product"] = "validated_tactical_dispatch"
    return out


def write_emergency_envelope_file(envelope: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")
