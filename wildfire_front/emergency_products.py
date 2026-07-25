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


def ring_centroid(
    ring: list[tuple[float, float]] | tuple[tuple[float, float], ...],
) -> tuple[float, float]:
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
    sectors: dict[str, Any] = {
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
    head_ros_m_min: float | None = None,
    flank_ros_m_min: float | None = None,
    rear_ros_m_min: float | None = None,
) -> dict[str, Any]:
    """Extrude distance = ROS × time for emergency **guidance** only.

    When sector ROS is provided, each horizon includes **head / flank / rear**
    radii (and optional head bearing). Label is mandatory: not official dispatch.
    """
    base: dict[str, Any] = {
        "product": "short_horizon_envelope_v2_sector",
        "label_en": (
            "EXTRAPOLATED FRONT GUIDANCE from observed ROS (sector-aware) — "
            "NOT validated tactical dispatch, NOT official perimeter forecast"
        ),
        "label_es": (
            "GUÍA DE FRENTE EXTRAPOLADA desde ROS observada (por sector) — "
            "NO es despacho táctico validado ni perímetro oficial"
        ),
        "horizons_min": list(horizons_min),
        "quality_grade": quality_grade,
        "expansion_bearing_deg": expansion_bearing_deg,
        "sector_aware": True,
    }
    if primary_ros_m_min is None or not math.isfinite(primary_ros_m_min) or primary_ros_m_min < 0:
        base["status"] = "abstained"
        base["reason"] = "no_primary_ros"
        base["envelopes"] = []
        return base

    ros = min(float(primary_ros_m_min), _ENVELOPE_MAX_ROS_M_MIN)
    head = min(
        float(head_ros_m_min if head_ros_m_min is not None else ros), _ENVELOPE_MAX_ROS_M_MIN
    )
    flank = min(
        float(flank_ros_m_min if flank_ros_m_min is not None else ros), _ENVELOPE_MAX_ROS_M_MIN
    )
    rear = min(
        float(rear_ros_m_min if rear_ros_m_min is not None else ros * 0.55), _ENVELOPE_MAX_ROS_M_MIN
    )
    # Ensure head >= flank >= rear for guidance readability
    flank = min(flank, head)
    rear = min(rear, flank)

    envelopes = []
    for h in horizons_min:
        th = float(h)
        entry = {
            "horizon_min": int(h),
            "ros_m_min_used": round(ros, 4),
            "radius_m": round(ros * th, 2),
            "radius_km": round(ros * th / 1000.0, 4),
            "head_radius_m": round(head * th, 2),
            "flank_radius_m": round(flank * th, 2),
            "rear_radius_m": round(rear * th, 2),
            "head_ros_m_min": round(head, 4),
            "flank_ros_m_min": round(flank, 4),
            "rear_ros_m_min": round(rear, 4),
            "note": (
                "Sector-aware: head/flank/rear radii from observed ROS quartiles; "
                "isotropic radius_m kept for compatibility"
            ),
        }
        if expansion_bearing_deg is not None:
            entry["head_bearing_deg"] = round(float(expansion_bearing_deg) % 360.0, 2)
        envelopes.append(entry)
    base["status"] = "ok"
    base["envelopes"] = envelopes
    base["ros_m_min"] = round(ros, 4)
    base["sector_ros_m_min"] = {
        "head": round(head, 4),
        "flank": round(flank, 4),
        "rear": round(rear, 4),
    }
    base["capped"] = float(primary_ros_m_min) > _ENVELOPE_MAX_ROS_M_MIN
    return base


def enrich_ops_dict(
    ops: dict[str, Any],
    *,
    expansion_bearing_deg: float | None = None,
    cn_hybrid: bool = False,
    wind_from_deg: float | None = None,
) -> dict[str, Any]:
    """Attach sector_ros + short_horizon_envelope onto operational_metrics-like dict.

    ``cn_hybrid`` defaults **False** (no invented weather / hybrid ROS on the
    default operator path). When explicitly enabled, ``cn_hybrid_ros`` is only
    attached with numeric head/flank/rear ROS when ``wind_from_deg`` is provided;
    missing wind → ``status=inputs_assumed`` / ``abstained`` without an
    operational-looking numeric ROS (never invent 270° wind or fixed T/RH as ops).
    """
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
    secs = (sector.get("sectors") or {}) if sector else {}
    envelope = compute_short_horizon_envelope(
        float(primary) if primary is not None else None,
        expansion_bearing_deg=expansion_bearing_deg,
        quality_grade=str(grade) if grade else None,
        head_ros_m_min=secs.get("head_m_min"),
        flank_ros_m_min=secs.get("flank_m_min"),
        rear_ros_m_min=secs.get("rear_m_min"),
    )
    out = dict(ops)
    out["sector_ros"] = sector
    out["short_horizon_envelope"] = envelope
    out["emergency_product"] = "observed_front_dynamics_v1"
    out["not_a_product"] = "validated_tactical_dispatch"

    if cn_hybrid and primary is not None:
        # Never invent wind (270°) or expansion-proxy wind for operator-facing hybrid ROS.
        if wind_from_deg is None:
            out["cn_hybrid_ros"] = {
                "status": "inputs_assumed",
                "reason": "wind_from_deg_required",
                "model": "wang_mao_hybrid_obs_magnitude",
                "vp_tactical": None,
                "not_tactical": True,
                "note": (
                    "cn_hybrid requested but wind_from_deg missing; "
                    "refusing invented 270° wind / fixed weather as operational ROS."
                ),
            }
        else:
            try:
                from wildfire_front.cn_wang_zhengfei import hybrid_ros_prior

                hybrid = hybrid_ros_prior(
                    float(primary), wind_from_deg=float(wind_from_deg)
                )
                # Drop full polar from ops JSON bulk; keep summary + sample
                if hybrid.get("status") == "ok":
                    out["cn_hybrid_ros"] = {
                        "status": hybrid["status"],
                        "model": hybrid["model"],
                        "scale_factor": hybrid["scale_factor"],
                        "ros_head_m_min": hybrid["ros_head_m_min"],
                        "ros_flank_m_min": hybrid["ros_flank_m_min"],
                        "ros_rear_m_min": hybrid["ros_rear_m_min"],
                        "observed_ros_m_min": hybrid["observed_ros_m_min"],
                        "wind_from_deg": float(wind_from_deg),
                        "weather_defaults_used": True,
                        "not_tactical": True,
                        "polar_n": len(hybrid.get("polar_calibrated") or []),
                        "polar_sample": (hybrid.get("polar_calibrated") or [])[:6],
                        "label_es": hybrid.get("label_es"),
                    }
                else:
                    out["cn_hybrid_ros"] = hybrid
            except Exception as exc:  # pragma: no cover — defensive
                out["cn_hybrid_ros"] = {"status": "error", "reason": str(exc)}

    return out


def write_emergency_envelope_file(envelope: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")


def _circle_ring(
    cx: float,
    cy: float,
    radius_m: float,
    *,
    n: int = 48,
) -> list[list[float]]:
    """Closed ring in projected meters (x east, y north)."""
    if radius_m <= 0:
        return [[cx, cy], [cx, cy]]
    pts: list[list[float]] = []
    for i in range(n):
        ang = 2.0 * math.pi * i / n
        # ang 0 = east; convert so 0 bearing north is +y
        # For isotropic circle direction does not matter.
        x = cx + radius_m * math.sin(ang)
        y = cy + radius_m * math.cos(ang)
        pts.append([round(x, 3), round(y, 3)])
    pts.append(pts[0])
    return pts


def _sector_wedge_ring(
    cx: float,
    cy: float,
    radius_m: float,
    bearing_deg: float,
    half_width_deg: float = 45.0,
    *,
    n: int = 24,
) -> list[list[float]]:
    """Wedge ring centered on bearing (deg from north, clockwise)."""
    if radius_m <= 0:
        return [[cx, cy], [cx, cy]]
    # Walk clockwise across the wedge (start bearing + span in degrees)
    start = (bearing_deg - half_width_deg) % 360.0
    span = (2.0 * half_width_deg) % 360.0
    if span <= 0:
        span = 90.0
    pts: list[list[float]] = [[cx, cy]]
    for i in range(n + 1):
        brg = math.radians((start + span * i / n) % 360.0)
        # bearing 0 = +y (north), 90 = +x (east)
        x = cx + radius_m * math.sin(brg)
        y = cy + radius_m * math.cos(brg)
        pts.append([round(x, 3), round(y, 3)])
    pts.append([cx, cy])
    return pts


def envelope_to_geojson(
    envelope: dict[str, Any],
    *,
    center_xy: tuple[float, float] | None,
    fire_id: str = "",
    expansion_bearing_deg: float | None = None,
) -> dict[str, Any]:
    """Build FeatureCollection of guidance rings from emergency envelope numbers.

    Coordinates are in the same projected CRS as the pack (typically UTM meters).
    Properties always state extrapolated / non-official guidance.
    """
    features: list[dict[str, Any]] = []
    label = {
        "guidance": "extrapolated_from_observed_ros",
        "not_official_perimeter": True,
        "not_tactical_dispatch": True,
        "label_en": envelope.get("label_en"),
        "label_es": envelope.get("label_es"),
        "fire_id": fire_id,
        "product": envelope.get("product") or "short_horizon_envelope_v2_sector",
    }
    if center_xy is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "properties": {**label, "status": "abstained", "reason": "no_center"},
        }
    cx, cy = float(center_xy[0]), float(center_xy[1])
    bearing = expansion_bearing_deg
    if bearing is None:
        bearing = envelope.get("expansion_bearing_deg")

    for e in envelope.get("envelopes") or []:
        h = int(e.get("horizon_min") or 0)
        # Flank isotropic circle (primary guidance)
        r_flank = float(e.get("flank_radius_m") or e.get("radius_m") or 0)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    **label,
                    "horizon_min": h,
                    "sector": "flank_isotropic",
                    "radius_m": r_flank,
                    "ros_m_min": e.get("flank_ros_m_min") or e.get("ros_m_min_used"),
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_circle_ring(cx, cy, r_flank)],
                },
            }
        )
        r_head = float(e.get("head_radius_m") or r_flank)
        if bearing is not None and r_head > 0:
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        **label,
                        "horizon_min": h,
                        "sector": "head",
                        "radius_m": r_head,
                        "bearing_deg": bearing,
                        "ros_m_min": e.get("head_ros_m_min"),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [_sector_wedge_ring(cx, cy, r_head, float(bearing), 45.0)],
                    },
                }
            )
        r_rear = float(e.get("rear_radius_m") or 0)
        if bearing is not None and r_rear > 0:
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        **label,
                        "horizon_min": h,
                        "sector": "rear",
                        "radius_m": r_rear,
                        "bearing_deg": (float(bearing) + 180.0) % 360.0,
                        "ros_m_min": e.get("rear_ros_m_min"),
                    },
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            _sector_wedge_ring(
                                cx, cy, r_rear, (float(bearing) + 180.0) % 360.0, 45.0
                            )
                        ],
                    },
                }
            )

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            **label,
            "status": envelope.get("status") or "ok",
            "n_features": len(features),
            "center_xy": [cx, cy],
        },
    }


def write_envelope_geojson(
    envelope: dict[str, Any],
    path: Path,
    *,
    center_xy: tuple[float, float] | None,
    fire_id: str = "",
    expansion_bearing_deg: float | None = None,
    write_wgs84: bool = True,
) -> dict[str, Any]:
    """Write envelope GeoJSON. Default output is WGS84 for geojson.io/Leaflet.

    Also writes ``*_utm.geojson`` next to path when coordinates were projected.
    """
    from .geo_crs import geojson_to_wgs84, looks_projected_meters

    gj = envelope_to_geojson(
        envelope,
        center_xy=center_xy,
        fire_id=fire_id,
        expansion_bearing_deg=expansion_bearing_deg,
    )
    path.parent.mkdir(parents=True, exist_ok=True)

    # Detect if center is UTM-style
    is_utm = False
    if center_xy is not None:
        is_utm = looks_projected_meters(float(center_xy[0]), float(center_xy[1]))

    if write_wgs84 and is_utm:
        utm_path = path.with_name(path.stem + "_utm.geojson")
        # store projected version for QGIS with local CRS
        utm_doc = dict(gj)
        utm_doc["crs"] = {
            "type": "name",
            "properties": {"name": "EPSG:32630"},
        }
        utm_path.write_text(json.dumps(utm_doc, indent=2), encoding="utf-8")
        gj_wgs = geojson_to_wgs84(gj, zone=30, northern=True)
        path.write_text(json.dumps(gj_wgs, indent=2), encoding="utf-8")
        return gj_wgs

    path.write_text(json.dumps(gj, indent=2), encoding="utf-8")
    return gj
