"""Multi-horizon field_ops forecasts (1h / 3h / 5h / 12h / 24h).

Commercial / operational surface — **not** ML next-day mask IoU.

Industry sell (Technosylva, OroraTech, WIFIRE) requires multi-lead-time ROS /
envelope products. This module implements isotropic + anisotropic + hybrid
advance from ROS (m/min) over explicit lead times.

Rails (immutable here)
----------------------
* Product rail: **field_ops** (not lab ML).
* IoU ≠ ROS — never emit model_iou as primary ROS claim.
* field fusion stays **OFF**; lab ``ml_product_go`` is independent.
* Tobarra KEEP / ECE thrash are out of scope (not reopened).

Physics methods
---------------
* ``isotropic_ros_buffer_v1``: ``d = ros * h * 60`` circle/buffer
* ``anisotropic_ros_buffer_v1``: head/flank/rear sector radii
* ``hybrid_sector_envelope_v1``: obs × physics shape, commercial hours
* ``reinit_multipass_v1``: recompute from new IR perimeter / ROS

Never label model_iou as ROS.
"""

from __future__ import annotations

import contextlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Final

# Default commercial lead times (hours) for emergency SKU.
DEFAULT_LEAD_TIMES_H: Final[tuple[float, ...]] = (1.0, 3.0, 5.0, 12.0, 24.0)
PRODUCT_ID: Final = "front_dynamics_v1"
PRODUCT_RAIL: Final = "field_ops"
METHOD_ID: Final = "isotropic_ros_buffer_v1"
METHOD_ISOTROPIC: Final = "isotropic_ros_buffer_v1"
METHOD_ANISOTROPIC: Final = "anisotropic_ros_buffer_v1"
METHOD_HYBRID: Final = "hybrid_sector_envelope_v1"
METHOD_REINIT: Final = "reinit_multipass_v1"
SCHEMA: Final = "wfd_multihorizon_fieldops_v1"
SCHEMA_SCORECARD: Final = "wfd_multihorizon_multipass_scorecard_v1"
PIPELINE: Final = "ros→lead_times→envelope_geometry→scorecard"

# Obs-shape defaults when only primary ROS is known (matches fuel.envelope).
OBS_HEAD_FRAC: Final = 1.0
OBS_FLANK_FRAC: Final = 0.5
OBS_REAR_FRAC: Final = 0.3
ENVELOPE_CAP_ROS_M_MIN: Final = 40.0

# Wind boost (PR13) — mild directional tilt when weather present; never invent wind.
WIND_HEAD_BOOST: Final = 1.15
WIND_FLANK_SCALE: Final = 1.0
WIND_REAR_SCALE: Final = 0.9


class MultiHorizonError(ValueError):
    """Invalid ROS, lead times, or geometry for multi-horizon forecast."""


@dataclass(frozen=True)
class FieldOpsRails:
    """Honesty rails for multi-horizon field_ops (sell surface)."""

    product_id: str = PRODUCT_ID
    product_rail: str = PRODUCT_RAIL
    ops_rail: str = "field_ops"
    lab_ml_rail: str = "lab_ml"
    iou_is_not_ros: bool = True
    field_ops_allow_ml_live_in_fusion: bool = False
    field_ops_ml_live_fusion: str = "OFF"
    ml_next_day_is_not_tactical_1h: bool = True
    method: str = METHOD_ID
    pipeline: str = PIPELINE
    tobarra_keep_reopen: bool = False
    ece_thrash_reopen: bool = False
    banner: str = "field_ops multi-horizon · IoU ≠ ROS · not ML next-day · fusion OFF"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_RAILS: Final = FieldOpsRails()


def normalize_lead_times_h(
    lead_times_h: Sequence[float] | None = None,
) -> list[float]:
    """Return sorted unique positive lead times (hours)."""
    raw = list(DEFAULT_LEAD_TIMES_H) if lead_times_h is None else list(lead_times_h)
    out: list[float] = []
    seen: set[float] = set()
    for x in raw:
        h = float(x)
        if not math.isfinite(h) or h <= 0:
            raise MultiHorizonError(f"lead_time_h must be positive finite, got {x!r}")
        # round to avoid float key noise
        key = round(h, 6)
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
    if not out:
        raise MultiHorizonError("lead_times_h must be non-empty")
    return sorted(out)


def advance_distance_m(ros_m_min: float, lead_time_h: float) -> float:
    """Radial advance in metres: ROS [m/min] × minutes."""
    v = float(ros_m_min)
    h = float(lead_time_h)
    if not math.isfinite(v) or v < 0:
        raise MultiHorizonError(f"ros_m_min must be finite >= 0, got {ros_m_min!r}")
    if not math.isfinite(h) or h <= 0:
        raise MultiHorizonError(f"lead_time_h must be positive finite, got {lead_time_h!r}")
    return v * h * 60.0


def circle_area_ha(radius_m: float) -> float:
    r = float(radius_m)
    if r < 0 or not math.isfinite(r):
        return float("nan")
    return math.pi * r * r / 10_000.0


@dataclass(frozen=True)
class HorizonSlice:
    """One lead-time forecast slice."""

    lead_time_h: float
    lead_time_min: float
    advance_m: float
    ros_m_min: float
    area_ha_circle: float | None
    buffer_area_ha: float | None
    geometry_type: str  # point_circle | polygon_buffer | ros_only | anisotropic | hybrid
    notes: tuple[str, ...] = ()
    # Sector advances (PR5+); None for pure isotropic cards.
    head_advance_m: float | None = None
    flank_advance_m: float | None = None
    rear_advance_m: float | None = None
    head_ros_m_min: float | None = None
    flank_ros_m_min: float | None = None
    rear_ros_m_min: float | None = None

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["notes"] = list(self.notes)
        return d


@dataclass
class MultiHorizonForecast:
    """Full multi-horizon field_ops card."""

    schema: str = SCHEMA
    product_id: str = PRODUCT_ID
    method: str = METHOD_ID
    ros_m_min: float = 0.0
    ros_source: str = "user"
    lead_times_h: list[float] = field(default_factory=lambda: list(DEFAULT_LEAD_TIMES_H))
    horizons: list[HorizonSlice] = field(default_factory=list)
    rails: dict[str, Any] = field(default_factory=lambda: DEFAULT_RAILS.as_dict())
    origin: dict[str, Any] = field(default_factory=dict)
    honesty: dict[str, Any] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)
    sector_ros_m_min: dict[str, float] | None = None
    head_bearing_deg: float | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema": self.schema,
            "product_id": self.product_id,
            "method": self.method,
            "pipeline": PIPELINE,
            "ros_m_min": self.ros_m_min,
            "ros_source": self.ros_source,
            "lead_times_h": list(self.lead_times_h),
            "horizons": [h.as_dict() for h in self.horizons],
            "rails": dict(self.rails),
            "origin": dict(self.origin),
            "honesty": dict(self.honesty),
        }
        if self.sector_ros_m_min is not None:
            out["sector_ros_m_min"] = dict(self.sector_ros_m_min)
        if self.head_bearing_deg is not None:
            out["head_bearing_deg"] = float(self.head_bearing_deg)
        out.update(dict(self.extra))
        return out


def _optional_polygon_buffer_area_ha(
    polygon_xy_m: Sequence[Sequence[float]] | None,
    distance_m: float,
) -> tuple[float | None, str]:
    """Buffer a closed ring in metres; return area_ha or None."""
    if polygon_xy_m is None:
        return None, "point_circle"
    try:
        from shapely.geometry import Polygon
    except ImportError:
        return None, "point_circle_no_shapely"
    coords = [(float(p[0]), float(p[1])) for p in polygon_xy_m]
    if len(coords) < 3:
        return None, "point_circle"
    if coords[0] != coords[-1]:
        coords = coords + [coords[0]]
    poly = Polygon(coords)
    if not poly.is_valid or poly.is_empty:
        return None, "point_circle_invalid_poly"
    buf = poly.buffer(float(distance_m))
    if buf.is_empty:
        return 0.0, "polygon_buffer"
    return float(buf.area / 10_000.0), "polygon_buffer"


def build_multihorizon_forecast(
    ros_m_min: float,
    *,
    lead_times_h: Sequence[float] | None = None,
    ros_source: str = "user",
    origin_xy_m: tuple[float, float] | None = None,
    polygon_xy_m: Sequence[Sequence[float]] | None = None,
    rails: FieldOpsRails | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Build multi-horizon field_ops forecast from scalar ROS.

    Parameters
    ----------
    ros_m_min:
        Rate of spread [m/min] (geometry / ops), **not** mask IoU.
    lead_times_h:
        Hours ahead (default 1, 3, 5, 12, 24).
    origin_xy_m:
        Optional point ignition in a local metric frame (for provenance only).
    polygon_xy_m:
        Optional closed perimeter ring in metric coords for buffer area.
    """
    v = float(ros_m_min)
    if not math.isfinite(v) or v < 0:
        raise MultiHorizonError(f"ros_m_min must be finite >= 0, got {ros_m_min!r}")
    leads = normalize_lead_times_h(lead_times_h)
    r = rails or DEFAULT_RAILS
    if r.product_rail != "field_ops":
        raise MultiHorizonError("multihorizon product_rail must be field_ops")
    if not r.iou_is_not_ros:
        raise MultiHorizonError("iou_is_not_ros rail must be true")
    if r.field_ops_allow_ml_live_in_fusion:
        raise MultiHorizonError("field fusion must stay OFF on multihorizon path")

    horizons: list[HorizonSlice] = []
    for h in leads:
        d = advance_distance_m(v, h)
        area_circ = circle_area_ha(d) if v > 0 else 0.0
        buf_ha, geom_type = _optional_polygon_buffer_area_ha(polygon_xy_m, d)
        notes: list[str] = []
        if v == 0:
            notes.append("ros_zero_no_advance")
        if geom_type.startswith("point_circle") and polygon_xy_m is not None:
            notes.append("polygon_buffer_unavailable_fallback_circle")
        horizons.append(
            HorizonSlice(
                lead_time_h=h,
                lead_time_min=h * 60.0,
                advance_m=d,
                ros_m_min=v,
                area_ha_circle=area_circ,
                buffer_area_ha=buf_ha,
                geometry_type=geom_type if polygon_xy_m is not None else "point_circle",
                notes=tuple(notes),
            )
        )

    origin: dict[str, Any] = {}
    if origin_xy_m is not None:
        origin["xy_m"] = [float(origin_xy_m[0]), float(origin_xy_m[1])]
        origin["kind"] = "point"
    if polygon_xy_m is not None:
        origin["kind"] = origin.get("kind", "polygon")
        origin["n_vertices"] = len(polygon_xy_m)

    honesty = {
        "iou_is_not_ros": True,
        "ml_next_day_is_not_tactical_1h": True,
        "method_is_isotropic_v1": True,
        "not_cfm_physics": True,
        "not_wrf_sfire": True,
        "guidance_not_tactical": True,
        "reinit_with_new_perimeter": (
            "Re-run with updated ROS / perimeter when multipass IR arrives; "
            "do not roll out ML next-day masks as 1h truth."
        ),
        "sell_sku": "field_ops multi-horizon envelopes",
        "lab_sku": "clm_ensemble_v34 next-day mask (separate product rail)",
    }

    return MultiHorizonForecast(
        method=METHOD_ISOTROPIC,
        ros_m_min=v,
        ros_source=str(ros_source),
        lead_times_h=leads,
        horizons=horizons,
        rails=r.as_dict(),
        origin=origin,
        honesty=honesty,
        extra=dict(extra or {}),
    )


def _assert_field_ops_rails(rails: FieldOpsRails | None = None) -> FieldOpsRails:
    r = rails or DEFAULT_RAILS
    if r.product_rail != "field_ops":
        raise MultiHorizonError("multihorizon product_rail must be field_ops")
    if not r.iou_is_not_ros:
        raise MultiHorizonError("iou_is_not_ros rail must be true")
    if r.field_ops_allow_ml_live_in_fusion:
        raise MultiHorizonError("field fusion must stay OFF on multihorizon path")
    return r


def _cap_ros(v: float, cap: float = ENVELOPE_CAP_ROS_M_MIN) -> float:
    return min(max(0.0, float(v)), float(cap))


def sector_ros_from_primary(
    primary_m_min: float,
    *,
    head_frac: float = OBS_HEAD_FRAC,
    flank_frac: float = OBS_FLANK_FRAC,
    rear_frac: float = OBS_REAR_FRAC,
    sectors_override: Mapping[str, Any] | None = None,
    head_bearing_deg: float | None = None,
    cap_m_min: float = ENVELOPE_CAP_ROS_M_MIN,
) -> dict[str, Any]:
    """Build head/flank/rear ROS with ordering head ≥ flank ≥ rear.

    When ``sectors_override`` supplies head/flank/rear (or *_m_min keys), those
    values are used (still ordered). Otherwise obs-shape fractions of primary.
    """
    primary = _cap_ros(float(primary_m_min), cap_m_min)
    if not math.isfinite(primary) or primary < 0:
        raise MultiHorizonError(f"primary_m_min must be finite >= 0, got {primary_m_min!r}")

    head = flank = rear = None
    if sectors_override:
        for name, _holder in (
            ("head", "head"),
            ("flank", "flank"),
            ("rear", "rear"),
        ):
            for key in (f"{name}_m_min", name):
                if key in sectors_override and sectors_override[key] is not None:
                    try:
                        val = float(sectors_override[key])
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(val) and val >= 0:
                        if name == "head":
                            head = val
                        elif name == "flank":
                            flank = val
                        else:
                            rear = val
                        break
        if "primary_m_min" in sectors_override and sectors_override["primary_m_min"] is not None:
            with contextlib.suppress(TypeError, ValueError):
                primary = _cap_ros(float(sectors_override["primary_m_min"]), cap_m_min)
        elif "primary" in sectors_override and sectors_override["primary"] is not None:
            with contextlib.suppress(TypeError, ValueError):
                primary = _cap_ros(float(sectors_override["primary"]), cap_m_min)

    if head is None:
        head = primary * float(head_frac)
    if flank is None:
        flank = primary * float(flank_frac)
    if rear is None:
        rear = primary * float(rear_frac)

    head = _cap_ros(head, cap_m_min)
    flank = _cap_ros(flank, cap_m_min)
    rear = _cap_ros(rear, cap_m_min)
    # Enforce guidance ordering head ≥ flank ≥ rear
    flank = min(flank, head)
    rear = min(rear, flank)

    out: dict[str, Any] = {
        "head": head,
        "flank": flank,
        "rear": rear,
        "primary": primary,
        "head_m_min": head,
        "flank_m_min": flank,
        "rear_m_min": rear,
        "primary_m_min": primary,
    }
    if head_bearing_deg is not None and math.isfinite(float(head_bearing_deg)):
        out["head_bearing_deg"] = float(head_bearing_deg) % 360.0
    return out


def apply_wind_sector_boost(
    sector_ros: Mapping[str, Any],
    *,
    weather: Mapping[str, Any] | None = None,
    wind_from_deg: float | None = None,
    wind_10m_ms: float | None = None,
    head_boost: float = WIND_HEAD_BOOST,
    flank_scale: float = WIND_FLANK_SCALE,
    rear_scale: float = WIND_REAR_SCALE,
    cap_m_min: float = ENVELOPE_CAP_ROS_M_MIN,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Optional wind-aligned sector tilt (PR13).

    If weather / wind is missing → returns sector_ros unchanged with
    ``weather_used=False`` (fallback to PR5/PR7 obs shape).

    Wind *from* direction implies head bearing = from + 180° (downwind).
    """
    base = sector_ros_from_primary(
        float(sector_ros.get("primary", sector_ros.get("primary_m_min", 0.0))),
        sectors_override=sector_ros,
        head_bearing_deg=sector_ros.get("head_bearing_deg"),
        cap_m_min=cap_m_min,
    )
    provenance: dict[str, Any] = {
        "weather_used": False,
        "method": "no_wind_fallback",
        "fallback": "obs_sector_shape",
    }

    w_ms = wind_10m_ms
    w_from = wind_from_deg
    src = None
    if weather is not None:
        if w_ms is None:
            for k in ("wind_10m_ms", "midflame_wind_ms", "wind_speed_ms"):
                if weather.get(k) is not None:
                    try:
                        w_ms = float(weather[k])
                        src = weather.get("source") or "weather_json"
                        break
                    except (TypeError, ValueError):
                        pass
        if w_from is None and weather.get("wind_from_deg") is not None:
            try:
                w_from = float(weather["wind_from_deg"])
                src = src or weather.get("source") or "weather_json"
            except (TypeError, ValueError):
                pass

    if w_ms is None or not math.isfinite(float(w_ms)) or float(w_ms) < 0:
        return base, provenance
    if w_from is None or not math.isfinite(float(w_from)):
        return base, provenance

    # Mild boost only; do not invent extreme winds.
    # Zero / calm wind is an identity fallback (no sector reshape, weather_used=False).
    w_ms_f = float(w_ms)
    _CALM_EPS = 1e-9
    if w_ms_f <= _CALM_EPS:
        provenance = {
            "weather_used": False,
            "method": "no_wind_fallback",
            "fallback": "obs_sector_shape",
            "reason": "calm_or_zero_wind",
            "wind_10m_ms": w_ms_f,
            "wind_from_deg": float(w_from) % 360.0,
            "source": src or "explicit",
            "note": (
                "Calm/zero wind does not reshape sectors; obs sector shape retained. "
                "Not WRF-SFIRE; not tactical dispatch."
            ),
        }
        return base, provenance

    # Near-calm (0 < w < 1 m/s): taper head/flank/rear scales toward 1.0 together
    # so calm weather never fully applies rear_scale=0.9 while head stays flat.
    boost = float(head_boost)
    f_scale = float(flank_scale)
    r_scale = float(rear_scale)
    if w_ms_f < 1.0:
        t = w_ms_f  # 0→1 linear blend from identity to full scales
        boost = 1.0 + (boost - 1.0) * t
        f_scale = 1.0 + (f_scale - 1.0) * t
        r_scale = 1.0 + (r_scale - 1.0) * t
    head = _cap_ros(base["head"] * boost, cap_m_min)
    flank = _cap_ros(base["flank"] * f_scale, cap_m_min)
    rear = _cap_ros(base["rear"] * r_scale, cap_m_min)
    flank = min(flank, head)
    rear = min(rear, flank)
    head_bearing = (float(w_from) + 180.0) % 360.0

    boosted = {
        "head": head,
        "flank": flank,
        "rear": rear,
        "primary": base["primary"],
        "head_m_min": head,
        "flank_m_min": flank,
        "rear_m_min": rear,
        "primary_m_min": base["primary"],
        "head_bearing_deg": head_bearing,
    }
    provenance = {
        "weather_used": True,
        "method": "wind_aligned_sector_boost_v1",
        "wind_10m_ms": w_ms_f,
        "wind_from_deg": float(w_from) % 360.0,
        "head_bearing_deg": head_bearing,
        "head_boost": boost,
        "flank_scale": f_scale,
        "rear_scale": r_scale,
        "source": src or "explicit",
        "note": (
            "Optional mild wind tilt; missing/calm weather falls back to obs sector shape. "
            "Not WRF-SFIRE; not tactical dispatch."
        ),
    }
    return boosted, provenance


def build_anisotropic_multihorizon(
    ros_m_min: float,
    *,
    lead_times_h: Sequence[float] | None = None,
    ros_source: str = "user",
    sector_ros: Mapping[str, Any] | None = None,
    head_bearing_deg: float | None = None,
    weather: Mapping[str, Any] | None = None,
    wind_from_deg: float | None = None,
    wind_10m_ms: float | None = None,
    apply_wind: bool = True,
    rails: FieldOpsRails | None = None,
    origin_xy_m: tuple[float, float] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Sector anisotropic multihorizon (PR5). Method ``anisotropic_ros_buffer_v1``.

    For same primary, head advance ≥ flank ≥ rear. Optional wind boost (PR13)
    when weather JSON / wind args present; otherwise obs-shape fallback.
    """
    r = _assert_field_ops_rails(rails)
    v = float(ros_m_min)
    if not math.isfinite(v) or v < 0:
        raise MultiHorizonError(f"ros_m_min must be finite >= 0, got {ros_m_min!r}")
    leads = normalize_lead_times_h(lead_times_h)

    base_sectors = sector_ros_from_primary(
        v,
        sectors_override=sector_ros,
        head_bearing_deg=head_bearing_deg
        if head_bearing_deg is not None
        else (sector_ros or {}).get("head_bearing_deg")
        if sector_ros
        else None,
    )
    wind_prov: dict[str, Any] = {"weather_used": False, "method": "no_wind_fallback"}
    if apply_wind:
        base_sectors, wind_prov = apply_wind_sector_boost(
            base_sectors,
            weather=weather,
            wind_from_deg=wind_from_deg,
            wind_10m_ms=wind_10m_ms,
        )

    head = float(base_sectors["head"])
    flank = float(base_sectors["flank"])
    rear = float(base_sectors["rear"])
    bearing = base_sectors.get("head_bearing_deg")
    if bearing is None and head_bearing_deg is not None:
        bearing = float(head_bearing_deg) % 360.0

    horizons: list[HorizonSlice] = []
    for h in leads:
        d_head = advance_distance_m(head, h)
        d_flank = advance_distance_m(flank, h)
        d_rear = advance_distance_m(rear, h)
        # advance_m is primary-isotropic (primary_ros × h × 60); sector advances
        # are head_advance_m / flank_advance_m / rear_advance_m.
        d_primary = advance_distance_m(v, h)
        notes: list[str] = []
        if v == 0:
            notes.append("ros_zero_no_advance")
        if wind_prov.get("weather_used"):
            notes.append("wind_boost_applied")
        else:
            notes.append("obs_sector_shape")
        horizons.append(
            HorizonSlice(
                lead_time_h=h,
                lead_time_min=h * 60.0,
                advance_m=d_primary,
                ros_m_min=v,
                area_ha_circle=circle_area_ha(d_primary) if v > 0 else 0.0,
                buffer_area_ha=None,
                geometry_type="anisotropic",
                notes=tuple(notes),
                head_advance_m=d_head,
                flank_advance_m=d_flank,
                rear_advance_m=d_rear,
                head_ros_m_min=head,
                flank_ros_m_min=flank,
                rear_ros_m_min=rear,
            )
        )

    origin: dict[str, Any] = {"kind": "anisotropic_sectors"}
    if origin_xy_m is not None:
        origin["xy_m"] = [float(origin_xy_m[0]), float(origin_xy_m[1])]

    honesty = {
        "iou_is_not_ros": True,
        "ml_next_day_is_not_tactical_1h": True,
        "method_is_isotropic_v1": False,
        "method_is_anisotropic_v1": True,
        "guidance_not_tactical": True,
        "not_cfm_physics": True,
        "not_wrf_sfire": True,
        "head_ge_flank_ge_rear": True,
        "reinit_with_new_perimeter": (
            "Re-run with updated ROS / perimeter when multipass IR arrives; "
            "do not roll out ML next-day masks as 1h truth."
        ),
        "sell_sku": "field_ops multi-horizon anisotropic envelopes",
        "lab_sku": "clm_ensemble_v34 next-day mask (separate product rail)",
    }
    meta = {
        "wind": wind_prov,
        "sector_shape": "obs_or_override" if not wind_prov.get("weather_used") else "wind_boosted",
    }
    if extra:
        meta.update(dict(extra))

    return MultiHorizonForecast(
        method=METHOD_ANISOTROPIC,
        ros_m_min=v,
        ros_source=str(ros_source),
        lead_times_h=leads,
        horizons=horizons,
        rails=r.as_dict(),
        origin=origin,
        honesty=honesty,
        sector_ros_m_min={
            "head": head,
            "flank": flank,
            "rear": rear,
            "primary": v,
        },
        head_bearing_deg=float(bearing) if bearing is not None else None,
        extra=meta,
    )


def build_hybrid_multihorizon(
    observed_ros_m_min: float,
    *,
    lead_times_h: Sequence[float] | None = None,
    ros_source: str = "obs_hybrid",
    hybrid: Mapping[str, Any] | None = None,
    sector_ros: Mapping[str, Any] | None = None,
    head_bearing_deg: float | None = None,
    weather: Mapping[str, Any] | None = None,
    wind_from_deg: float | None = None,
    wind_10m_ms: float | None = None,
    fuel_id: str = "MED_MAQUIS_LOW",
    apply_wind: bool = True,
    rails: FieldOpsRails | None = None,
    origin_xy_m: tuple[float, float] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Hybrid multihorizon 1–24 h (PR7). Method ``hybrid_sector_envelope_v1``.

    Uses ``fuel.envelope`` sector extraction when hybrid/physics present;
    otherwise obs sector shape. Honesty: guidance not tactical.
    """
    r = _assert_field_ops_rails(rails)
    v = float(observed_ros_m_min)
    if not math.isfinite(v) or v < 0:
        raise MultiHorizonError(
            f"observed_ros_m_min must be finite >= 0, got {observed_ros_m_min!r}"
        )
    leads = normalize_lead_times_h(lead_times_h)

    # Prefer fuel.envelope extraction when hybrid doc provided
    sectors_dict: dict[str, float] | None = None
    extract_reasons: list[str] = []
    if hybrid is not None:
        try:
            from wildfire_front.fuel.envelope import extract_sector_ros

            sectors_dict, extract_reasons = extract_sector_ros(hybrid, observed_ros_m_min=v)
        except Exception as exc:  # pragma: no cover — defensive
            extract_reasons = [f"envelope_extract_failed:{exc}"]
            sectors_dict = None

    if sectors_dict is None and sector_ros is not None:
        sec = sector_ros_from_primary(v, sectors_override=sector_ros)
        sectors_dict = {
            "head": sec["head"],
            "flank": sec["flank"],
            "rear": sec["rear"],
            "primary": sec["primary"],
        }
        extract_reasons.append("sector_ros_override")
    if sectors_dict is None:
        sec = sector_ros_from_primary(v)
        sectors_dict = {
            "head": sec["head"],
            "flank": sec["flank"],
            "rear": sec["rear"],
            "primary": sec["primary"],
        }
        extract_reasons.append("obs_only_sector_shape")

    # Optional wind boost on hybrid sectors
    wind_prov: dict[str, Any] = {"weather_used": False, "method": "no_wind_fallback"}
    bearing = head_bearing_deg
    if bearing is None and hybrid is not None:
        drivers = (hybrid.get("physics") or {}).get("drivers") or {}
        if "head_bearing_deg" in drivers:
            with contextlib.suppress(TypeError, ValueError):
                bearing = float(drivers["head_bearing_deg"])
        elif "wind_from_deg" in drivers:
            with contextlib.suppress(TypeError, ValueError):
                bearing = (float(drivers["wind_from_deg"]) + 180.0) % 360.0
    boosted_in = {**sectors_dict, "head_bearing_deg": bearing}
    if apply_wind:
        boosted_in, wind_prov = apply_wind_sector_boost(
            boosted_in,
            weather=weather,
            wind_from_deg=wind_from_deg,
            wind_10m_ms=wind_10m_ms,
        )
        sectors_dict = {
            "head": float(boosted_in["head"]),
            "flank": float(boosted_in["flank"]),
            "rear": float(boosted_in["rear"]),
            "primary": float(boosted_in.get("primary", v)),
        }
        if boosted_in.get("head_bearing_deg") is not None:
            bearing = float(boosted_in["head_bearing_deg"])

    # Commercial hours via envelope radii (minutes)
    horizons_min = [int(round(h * 60.0)) for h in leads]
    try:
        from wildfire_front.fuel.envelope import radii_from_sector_ros

        radii = radii_from_sector_ros(
            sectors_dict["head"],
            sectors_dict["flank"],
            sectors_dict["rear"],
            primary=sectors_dict.get("primary", v),
            horizons_min=horizons_min,
            head_bearing_deg=bearing,
        )
    except Exception:
        radii = []

    horizons: list[HorizonSlice] = []
    for i, h in enumerate(leads):
        head_r = advance_distance_m(sectors_dict["head"], h)
        flank_r = advance_distance_m(sectors_dict["flank"], h)
        rear_r = advance_distance_m(sectors_dict["rear"], h)
        d_primary = advance_distance_m(v, h)
        if i < len(radii):
            head_r = float(radii[i].get("head_radius_m", head_r))
            flank_r = float(radii[i].get("flank_radius_m", flank_r))
            rear_r = float(radii[i].get("rear_radius_m", rear_r))
        notes = ["hybrid_sector_envelope", "guidance_not_tactical"]
        if wind_prov.get("weather_used"):
            notes.append("wind_boost_applied")
        horizons.append(
            HorizonSlice(
                lead_time_h=h,
                lead_time_min=h * 60.0,
                advance_m=d_primary,
                ros_m_min=v,
                area_ha_circle=circle_area_ha(d_primary) if v > 0 else 0.0,
                buffer_area_ha=None,
                geometry_type="hybrid",
                notes=tuple(notes),
                head_advance_m=head_r,
                flank_advance_m=flank_r,
                rear_advance_m=rear_r,
                head_ros_m_min=float(sectors_dict["head"]),
                flank_ros_m_min=float(sectors_dict["flank"]),
                rear_ros_m_min=float(sectors_dict["rear"]),
            )
        )

    origin: dict[str, Any] = {"kind": "hybrid_sector", "fuel_id": fuel_id}
    if origin_xy_m is not None:
        origin["xy_m"] = [float(origin_xy_m[0]), float(origin_xy_m[1])]

    honesty = {
        "iou_is_not_ros": True,
        "ml_next_day_is_not_tactical_1h": True,
        "method_is_isotropic_v1": False,
        "method_is_hybrid_sector_envelope_v1": True,
        "guidance_not_tactical": True,
        "not_tactical_dispatch": True,
        "not_official_perimeter": True,
        "not_cfm_physics": True,
        "not_wrf_sfire": True,
        "head_ge_flank_ge_rear": True,
        "reinit_with_new_perimeter": (
            "Re-run with updated ROS / perimeter when multipass IR arrives; "
            "do not roll ML next-day masks as 1h truth."
        ),
        "sell_sku": "field_ops hybrid multi-horizon guidance (1–24 h)",
        "lab_sku": "clm_ensemble_v34 next-day mask (separate product rail)",
        "honesty_banner": (
            "EXTRAPOLATED hybrid multi-horizon envelope — "
            "guidance not tactical dispatch; not official perimeter"
        ),
    }
    meta: dict[str, Any] = {
        "wind": wind_prov,
        "extract_reasons": extract_reasons,
        "fuel_id": fuel_id,
        "hybrid_status": (hybrid or {}).get("status") if hybrid else None,
        "envelope_radii": radii,
    }
    if extra:
        meta.update(dict(extra))

    return MultiHorizonForecast(
        method=METHOD_HYBRID,
        ros_m_min=v,
        ros_source=str(ros_source),
        lead_times_h=leads,
        horizons=horizons,
        rails=r.as_dict(),
        origin=origin,
        honesty=honesty,
        sector_ros_m_min={
            "head": float(sectors_dict["head"]),
            "flank": float(sectors_dict["flank"]),
            "rear": float(sectors_dict["rear"]),
            "primary": float(sectors_dict.get("primary", v)),
        },
        head_bearing_deg=float(bearing) % 360.0 if bearing is not None else None,
        extra=meta,
    )


def reinit_multihorizon_from_frame(
    ros_m_min: float,
    *,
    frame_id: str,
    frame_timestamp_utc: str | None = None,
    method: str = METHOD_ANISOTROPIC,
    previous_card: Mapping[str, Any] | MultiHorizonForecast | None = None,
    lead_times_h: Sequence[float] | None = None,
    ros_source: str = "reinit_multipass",
    sector_ros: Mapping[str, Any] | None = None,
    head_bearing_deg: float | None = None,
    weather: Mapping[str, Any] | None = None,
    rails: FieldOpsRails | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Re-init multihorizon from a new IR / multipass frame (PR9).

    Stamps ``reinit_from_frame``. Never rolls ML next-day mask as 1h truth.
    Method label becomes ``reinit_multipass_v1`` with parent method provenance.
    """
    if not frame_id or not str(frame_id).strip():
        raise MultiHorizonError("frame_id is required for reinit")

    prev_dict: dict[str, Any] | None = None
    if previous_card is not None:
        prev_dict = (
            previous_card.as_dict()
            if isinstance(previous_card, MultiHorizonForecast)
            else dict(previous_card)
        )

    meta: dict[str, Any] = {
        "reinit_from_frame": str(frame_id),
        "frame_timestamp_utc": frame_timestamp_utc,
        "parent_method": method,
        "never_ml_mask_as_1h_truth": True,
        "previous_ros_m_min": (prev_dict or {}).get("ros_m_min"),
        "previous_method": (prev_dict or {}).get("method"),
    }
    if extra:
        meta.update(dict(extra))

    m = str(method)
    if m == METHOD_HYBRID:
        card = build_hybrid_multihorizon(
            float(ros_m_min),
            lead_times_h=lead_times_h,
            ros_source=ros_source,
            sector_ros=sector_ros,
            head_bearing_deg=head_bearing_deg,
            weather=weather,
            rails=rails,
            extra=meta,
        )
    elif m == METHOD_ISOTROPIC:
        card = build_multihorizon_forecast(
            float(ros_m_min),
            lead_times_h=lead_times_h,
            ros_source=ros_source,
            rails=rails,
            extra=meta,
        )
    else:
        card = build_anisotropic_multihorizon(
            float(ros_m_min),
            lead_times_h=lead_times_h,
            ros_source=ros_source,
            sector_ros=sector_ros,
            head_bearing_deg=head_bearing_deg,
            weather=weather,
            rails=rails,
            extra=meta,
        )

    card.method = METHOD_REINIT
    card.honesty = {
        **card.honesty,
        "reinit_multipass_v1": True,
        "reinit_from_frame": str(frame_id),
        "never_ml_mask_as_1h_truth": True,
        "ml_next_day_is_not_tactical_1h": True,
    }
    # Ensure reinit stamp also in extra top-level via as_dict merge
    card.extra = {**card.extra, "reinit_from_frame": str(frame_id)}
    return card


def multihorizon_to_geojson(
    card: MultiHorizonForecast | Mapping[str, Any],
    *,
    center_xy: tuple[float, float] | None = (0.0, 0.0),
    head_bearing_deg: float | None = None,
    n_ring: int = 72,
) -> dict[str, Any]:
    """GeoJSON FeatureCollection of horizon rings with honesty properties (PR10)."""
    d = card.as_dict() if isinstance(card, MultiHorizonForecast) else dict(card)
    honesty_props = {
        "product_id": d.get("product_id") or PRODUCT_ID,
        "product_rail": "field_ops",
        "method": d.get("method"),
        "ros_m_min": d.get("ros_m_min"),
        "ros_source": d.get("ros_source"),
        "iou_is_not_ros": True,
        "guidance_not_tactical": True,
        "not_official_perimeter": True,
        "not_tactical_dispatch": True,
        "ml_next_day_is_not_tactical_1h": True,
        "field_ops_ml_live_fusion": "OFF",
        "schema": d.get("schema") or SCHEMA,
    }
    if center_xy is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "properties": {**honesty_props, "status": "abstained", "reason": "no_center"},
        }
    cx, cy = float(center_xy[0]), float(center_xy[1])
    bearing = head_bearing_deg
    if bearing is None:
        bearing = d.get("head_bearing_deg")
    if bearing is None:
        bearing = 0.0
    bearing = float(bearing) % 360.0

    sector = d.get("sector_ros_m_min") or {}
    features: list[dict[str, Any]] = []

    for h in d.get("horizons") or []:
        lead_h = float(h.get("lead_time_h") or 0)
        lead_min = float(h.get("lead_time_min") or lead_h * 60.0)
        head_r = h.get("head_advance_m")
        flank_r = h.get("flank_advance_m")
        rear_r = h.get("rear_advance_m")
        primary_r = float(h.get("advance_m") or 0.0)
        if head_r is None:
            head_r = primary_r
        if flank_r is None:
            flank_r = primary_r * OBS_FLANK_FRAC if primary_r else 0.0
        if rear_r is None:
            rear_r = primary_r * OBS_REAR_FRAC if primary_r else 0.0
        head_r = float(head_r)
        flank_r = float(flank_r)
        rear_r = float(rear_r)

        # Prefer polar anisotropic ring when sector advances differ
        if abs(head_r - flank_r) > 1e-6 or abs(flank_r - rear_r) > 1e-6:
            try:
                from wildfire_front.fuel.envelope import ellipse_polar_ring

                ring = ellipse_polar_ring(cx, cy, head_r, flank_r, rear_r, bearing, n=n_ring)
            except Exception:
                ring = _circle_ring_xy(cx, cy, primary_r, n=n_ring)
            geom_kind = "anisotropic_polar"
        else:
            ring = _circle_ring_xy(cx, cy, primary_r, n=n_ring)
            geom_kind = "isotropic_circle"

        features.append(
            {
                "type": "Feature",
                "properties": {
                    **honesty_props,
                    "lead_time_h": lead_h,
                    "lead_time_min": lead_min,
                    "advance_m": primary_r,
                    "head_advance_m": head_r,
                    "flank_advance_m": flank_r,
                    "rear_advance_m": rear_r,
                    "head_bearing_deg": bearing,
                    "geometry_kind": geom_kind,
                    "sector_ros_m_min": sector or None,
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            **honesty_props,
            "n_horizons": len(features),
            "center_xy_m": [cx, cy],
            "head_bearing_deg": bearing,
        },
    }


def _circle_ring_xy(cx: float, cy: float, radius_m: float, *, n: int = 72) -> list[list[float]]:
    coords: list[list[float]] = []
    r = max(0.0, float(radius_m))
    for i in range(n):
        th = 2.0 * math.pi * i / n
        coords.append([round(cx + r * math.sin(th), 3), round(cy + r * math.cos(th), 3)])
    if coords:
        coords.append(coords[0])
    return coords


def multipass_envelope_scorecard(
    forecast: MultiHorizonForecast | Mapping[str, Any],
    *,
    lead_time_h: float,
    observed_advance_m: float | None = None,
    observed_head_advance_m: float | None = None,
    observed_area_ha: float | None = None,
    predicted_area_ha: float | None = None,
    multipass_span_s: float | None = None,
    min_span_s_for_full: float = 3600.0,
    advance_rel_err_pass: float = 0.5,
    fire_id: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Ops multipass validation scorecard (PR8) — **not** ML IoU.

    Compares envelope advance @ lead τ vs observed multipass progression.
    Metrics labeled as envelope/ops geometry skill, never model_iou / ML IoU.
    PARTIAL allowed when multipass span is shorter than lead time.
    """
    d = forecast.as_dict() if isinstance(forecast, MultiHorizonForecast) else dict(forecast)
    lead = float(lead_time_h)
    # Find matching horizon (nearest)
    horizons = list(d.get("horizons") or [])
    chosen = None
    best_dh = float("inf")
    for h in horizons:
        dh = abs(float(h.get("lead_time_h", 0)) - lead)
        if dh < best_dh:
            best_dh = dh
            chosen = h
    if chosen is None:
        return {
            "schema": SCHEMA_SCORECARD,
            "status": "ABSTAIN",
            "reason": "no_horizons_in_forecast",
            "product_rail": "field_ops",
            "metrics_are_not_ml_iou": True,
        }

    pred_advance = float(chosen.get("advance_m") or 0.0)
    pred_head = chosen.get("head_advance_m")
    pred_head = float(pred_head) if pred_head is not None else pred_advance

    # Span honesty
    span_s = multipass_span_s
    span_partial = False
    if span_s is not None and float(span_s) < min_span_s_for_full:
        span_partial = True
    if span_s is not None and float(span_s) < lead * 3600.0:
        span_partial = True

    metrics: dict[str, Any] = {
        "lead_time_h": lead,
        "predicted_advance_m": pred_advance,
        "predicted_head_advance_m": pred_head,
        "observed_advance_m": observed_advance_m,
        "observed_head_advance_m": observed_head_advance_m,
        "predicted_area_ha": predicted_area_ha or chosen.get("area_ha_circle"),
        "observed_area_ha": observed_area_ha,
        "multipass_span_s": span_s,
        # Explicit non-ML labels
        "envelope_advance_error_m": None,
        "envelope_advance_rel_error": None,
        "envelope_head_error_m": None,
        "envelope_area_ratio": None,
        "ops_hausdorff_proxy_m": None,
    }
    # Never call these ML IoU
    metrics["ml_iou"] = None
    metrics["model_iou"] = None
    metrics["label_note"] = "Ops envelope skill only — not lab model_iou / not ML next-day IoU"

    obs_adv = observed_advance_m
    if obs_adv is not None and math.isfinite(float(obs_adv)):
        err = pred_advance - float(obs_adv)
        metrics["envelope_advance_error_m"] = err
        if abs(float(obs_adv)) > 1e-6:
            metrics["envelope_advance_rel_error"] = err / float(obs_adv)
        metrics["ops_hausdorff_proxy_m"] = abs(err)

    obs_head = observed_head_advance_m
    if obs_head is not None and pred_head is not None and math.isfinite(float(obs_head)):
        metrics["envelope_head_error_m"] = pred_head - float(obs_head)

    if (
        observed_area_ha is not None
        and metrics["predicted_area_ha"] is not None
        and float(observed_area_ha) > 0
    ):
        metrics["envelope_area_ratio"] = float(metrics["predicted_area_ha"]) / float(
            observed_area_ha
        )

    # Pass / fail / partial
    status = "PASS"
    reasons: list[str] = []
    if obs_adv is None and observed_area_ha is None:
        status = "PARTIAL" if span_partial else "ABSTAIN"
        reasons.append("no_observed_geometry_for_score")
    elif span_partial:
        status = "PARTIAL"
        reasons.append("multipass_span_shorter_than_full_validation_window")
    else:
        rel = metrics.get("envelope_advance_rel_error")
        if rel is not None and abs(float(rel)) > advance_rel_err_pass:
            status = "FAIL"
            reasons.append(f"envelope_advance_rel_error={rel:.3f} exceeds {advance_rel_err_pass}")
        elif rel is not None:
            reasons.append("envelope_advance_within_threshold")

    out: dict[str, Any] = {
        "schema": SCHEMA_SCORECARD,
        "status": status,
        "product_rail": "field_ops",
        "product_id": PRODUCT_ID,
        "forecast_method": d.get("method"),
        "forecast_ros_m_min": d.get("ros_m_min"),
        "forecast_ros_source": d.get("ros_source"),
        "fire_id": fire_id,
        "metrics_are_not_ml_iou": True,
        "metrics_not_labeled_ml_iou": True,
        "iou_is_not_ros": True,
        "field_ops_ml_live_fusion": "OFF",
        "metrics": metrics,
        "reasons": reasons,
        "thresholds": {
            "advance_rel_err_pass": advance_rel_err_pass,
            "min_span_s_for_full": min_span_s_for_full,
        },
        "honesty": {
            "not_ml_iou": True,
            "not_lab_scorecard": True,
            "ops_envelope_validation_only": True,
            "partial_ok_for_short_multipass": True,
        },
    }
    if extra:
        out["extra"] = dict(extra)
    return out


def attach_multihorizon_for_ops(
    ops_metrics: Mapping[str, Any] | None,
    *,
    method: str = METHOD_ANISOTROPIC,
    lead_times_h: Sequence[float] | None = None,
    weather: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Build multihorizon card dict when ops ROS present (PR12 decide surface).

    Returns None (caller ABSTAINs / omits field) when no finite ops ROS.
    Fusion stays OFF; never uses ML mask IoU as ROS.
    """
    if not ops_metrics:
        return None
    ros = None
    source_key = None
    for k in (
        "primary_ros_m_min",
        "speed_median_m_min",
        "ros_median_m_min",
        "ros_m_min",
        "geometry_primary_ros_m_min",
    ):
        v = ops_metrics.get(k)
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(fv) and fv >= 0:
                ros = fv
                source_key = k
                break
    if ros is None:
        return None

    # Refuse ML IoU masquerading as ROS
    if "model_iou" in (source_key or "") or (source_key or "").lower() == "iou":
        return None

    sector = None
    if isinstance(ops_metrics.get("sector_ros_m_min"), Mapping):
        sector = ops_metrics["sector_ros_m_min"]
    elif isinstance(ops_metrics.get("sectors"), Mapping):
        sector = ops_metrics["sectors"]

    bearing = ops_metrics.get("expansion_bearing_deg") or ops_metrics.get("head_bearing_deg")
    m = str(method)
    if m == METHOD_HYBRID:
        card = build_hybrid_multihorizon(
            ros,
            lead_times_h=lead_times_h,
            ros_source=f"ops:{source_key}",
            sector_ros=sector,
            head_bearing_deg=float(bearing) if bearing is not None else None,
            weather=weather,
            extra={"attached_for": "decide_operator_surface"},
        )
    elif m == METHOD_ISOTROPIC:
        card = build_multihorizon_forecast(
            ros,
            lead_times_h=lead_times_h,
            ros_source=f"ops:{source_key}",
            extra={"attached_for": "decide_operator_surface"},
        )
    else:
        card = build_anisotropic_multihorizon(
            ros,
            lead_times_h=lead_times_h,
            ros_source=f"ops:{source_key}",
            sector_ros=sector,
            head_bearing_deg=float(bearing) if bearing is not None else None,
            weather=weather,
            extra={"attached_for": "decide_operator_surface"},
        )
    payload = card.as_dict()
    payload["status"] = "ok"
    return payload


def from_arrival_ros_result(
    arrival_ros: Mapping[str, Any],
    *,
    lead_times_h: Sequence[float] | None = None,
    prefer_key: str = "ros_median_m_min",
    fallback_ros_m_min: float | None = None,
    ros_source: str = "arrival_ros",
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Build multi-horizon card from ``arrival_gradient_ros_m_min``-style dict."""
    ros = arrival_ros.get(prefer_key)
    if ros is None:
        for k in ("ros_mean_m_min", "ros_p75_m_min", "ros_m_min", "primary_ros_m_min"):
            if arrival_ros.get(k) is not None:
                ros = arrival_ros[k]
                prefer_key = k
                break
    if ros is None:
        if fallback_ros_m_min is None:
            raise MultiHorizonError("arrival_ros has no ros_* key and no fallback_ros_m_min")
        ros = fallback_ros_m_min
        prefer_key = "fallback"
    meta = {
        "arrival_ros_method": arrival_ros.get("method"),
        "arrival_ros_key": prefer_key,
        "n_ros_cells": arrival_ros.get("n_ros_cells"),
        "n_arrival_cells": arrival_ros.get("n_arrival_cells"),
        "status": arrival_ros.get("status"),
    }
    if extra:
        meta.update(dict(extra))
    return build_multihorizon_forecast(
        float(ros),
        lead_times_h=lead_times_h,
        ros_source=f"{ros_source}:{prefer_key}",
        extra={"arrival_ros": meta},
    )


def equivalent_ros_from_area_duration(
    final_area_ha: float,
    total_duration_s: float,
) -> float:
    """Isotropic equivalent ROS [m/min] from final area and assumed duration.

    ``r = sqrt(A/π)`` then ``ROS = r / minutes``. Honest synthetic proxy only —
    not multipass LWIR ROS and not ML IoU.
    """
    a_ha = float(final_area_ha)
    t_s = float(total_duration_s)
    if not math.isfinite(a_ha) or a_ha < 0:
        raise MultiHorizonError(f"final_area_ha must be finite >= 0, got {final_area_ha!r}")
    if not math.isfinite(t_s) or t_s <= 0:
        raise MultiHorizonError(
            f"total_duration_s must be positive finite, got {total_duration_s!r}"
        )
    if a_ha == 0:
        return 0.0
    area_m2 = a_ha * 10_000.0
    radius_m = math.sqrt(area_m2 / math.pi)
    minutes = t_s / 60.0
    return radius_m / minutes


def from_psb_duration(
    total_duration_s: float,
    final_area_ha: float,
    *,
    lead_times_h: Sequence[float] | None = None,
    ros_source: str = "psb_equiv_isotropic",
    engine: str | None = None,
    n_stages: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast:
    """Multi-horizon from Progressive Synthetic Burn duration + final area.

    Stages are synthetic (not real LWIR). Equivalent ROS is isotropic radius /
    assumed duration only. Stamps honesty accordingly.
    """
    ros = equivalent_ros_from_area_duration(final_area_ha, total_duration_s)
    meta: dict[str, Any] = {
        "psb_total_duration_s": float(total_duration_s),
        "psb_final_area_ha": float(final_area_ha),
        "psb_equiv_ros_m_min": ros,
        "psb_engine": engine,
        "psb_n_stages": n_stages,
        "honesty_psb": (
            "PSB stages are synthetic reverse-growth under final perimeter; "
            "not multipass IR, not official intermediate O2, not tactical Vp."
        ),
    }
    if extra:
        meta.update(dict(extra))
    card = build_multihorizon_forecast(
        ros,
        lead_times_h=lead_times_h,
        ros_source=ros_source,
        extra={"psb": meta},
    )
    # Augment honesty with PSB-specific stamps
    card.honesty = {
        **card.honesty,
        "psb_synthetic_not_lwir": True,
        "psb_not_official_intermediate_o2": True,
        "psb_time_is_assumed": True,
        "ros_is_equiv_isotropic_from_area_duration": True,
    }
    return card


def from_s4_board_sources(
    *,
    geometry_ros: Mapping[str, Any] | None = None,
    arrival_oneill: Mapping[str, Any] | None = None,
    fallback_ros_m_min: float | None = None,
    lead_times_h: Sequence[float] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> MultiHorizonForecast | None:
    """Pick best available ROS from S4 board inputs; return multihorizon or None.

    Preference: geometry primary_ros → O'Neill median → explicit fallback.
    Returns None when no finite ROS is available (caller may omit the field).
    """
    candidates: list[tuple[str, float]] = []
    if geometry_ros:
        for k in ("primary_ros_m_min", "ros_median_m_min", "speed_median_m_min"):
            v = geometry_ros.get(k)
            if v is not None and math.isfinite(float(v)) and float(v) >= 0:
                candidates.append((f"geometry_ros:{k}", float(v)))
                break
    if arrival_oneill and arrival_oneill.get("status") != "skipped":
        for k in ("ros_median_m_min", "ros_mean_m_min", "ros_p75_m_min"):
            v = arrival_oneill.get(k)
            if v is not None and math.isfinite(float(v)) and float(v) >= 0:
                candidates.append((f"arrival_oneill:{k}", float(v)))
                break
    if not candidates and fallback_ros_m_min is not None:
        v = float(fallback_ros_m_min)
        if math.isfinite(v) and v >= 0:
            candidates.append(("fallback", v))
    if not candidates:
        return None
    source, ros = candidates[0]
    meta: dict[str, Any] = {
        "s4_ros_source": source,
        "s4_candidate_count": len(candidates),
        "all_candidates": [{"source": s, "ros_m_min": r} for s, r in candidates],
    }
    if extra:
        meta.update(dict(extra))
    return build_multihorizon_forecast(
        ros,
        lead_times_h=lead_times_h,
        ros_source=source,
        extra={"s4_attach": meta},
    )


def format_multihorizon_human(card: MultiHorizonForecast | Mapping[str, Any]) -> str:
    """Human table for CLI."""
    d = card.as_dict() if isinstance(card, MultiHorizonForecast) else dict(card)
    lines = [
        "Multi-horizon field_ops forecast (not ML next-day IoU)",
        f"  product:   {d.get('product_id')}",
        f"  method:    {d.get('method')}",
        f"  ros_m_min: {d.get('ros_m_min')}  source={d.get('ros_source')}",
        f"  rails:     fusion={(d.get('rails') or {}).get('field_ops_ml_live_fusion')}  "
        f"iou_is_not_ros={(d.get('rails') or {}).get('iou_is_not_ros')}",
    ]
    sec = d.get("sector_ros_m_min")
    if sec:
        lines.append(
            f"  sectors:   head={sec.get('head')}  flank={sec.get('flank')}  "
            f"rear={sec.get('rear')}  bearing={d.get('head_bearing_deg')}"
        )
    lines += [
        "",
        f"{'h':>6}  {'min':>8}  {'advance_m':>12}  {'head_m':>10}  "
        f"{'flank_m':>10}  {'rear_m':>10}  geom",
        "-" * 78,
    ]
    for h in d.get("horizons") or []:
        head_a = h.get("head_advance_m")
        flank_a = h.get("flank_advance_m")
        rear_a = h.get("rear_advance_m")
        lines.append(
            f"{float(h['lead_time_h']):6.1f}  "
            f"{float(h['lead_time_min']):8.1f}  "
            f"{float(h['advance_m']):12.1f}  "
            f"{float(head_a) if head_a is not None else float('nan'):10.1f}  "
            f"{float(flank_a) if flank_a is not None else float('nan'):10.1f}  "
            f"{float(rear_a) if rear_a is not None else float('nan'):10.1f}  "
            f"{h.get('geometry_type')}"
        )
    lines.append("")
    lines.append(
        "honesty: re-init with new perimeter/ROS; guidance not tactical; "
        "do not sell ML next-day as 1h tactical."
    )
    if d.get("reinit_from_frame") or (d.get("honesty") or {}).get("reinit_from_frame"):
        rid = d.get("reinit_from_frame") or (d.get("honesty") or {}).get("reinit_from_frame")
        lines.append(f"reinit_from_frame: {rid}")
    return "\n".join(lines)


def load_weather_json(path: str | Any) -> dict[str, Any] | None:
    """Load optional weather JSON for PR13 wind path; None if missing/invalid."""
    from pathlib import Path as _Path

    p = _Path(path)
    if not p.is_file():
        return None
    try:
        import json as _json

        data = _json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    # Nested weather common shapes
    for key in ("weather", "scenario", "aemet", "drivers"):
        nested = data.get(key)
        if isinstance(nested, dict) and (
            nested.get("wind_10m_ms") is not None or nested.get("wind_from_deg") is not None
        ):
            out = dict(nested)
            out.setdefault("source", data.get("source") or key)
            return out
    return data


__all__ = [
    "DEFAULT_LEAD_TIMES_H",
    "DEFAULT_RAILS",
    "ENVELOPE_CAP_ROS_M_MIN",
    "FieldOpsRails",
    "HorizonSlice",
    "METHOD_ANISOTROPIC",
    "METHOD_HYBRID",
    "METHOD_ID",
    "METHOD_ISOTROPIC",
    "METHOD_REINIT",
    "MultiHorizonError",
    "MultiHorizonForecast",
    "PRODUCT_ID",
    "SCHEMA",
    "SCHEMA_SCORECARD",
    "advance_distance_m",
    "apply_wind_sector_boost",
    "attach_multihorizon_for_ops",
    "build_anisotropic_multihorizon",
    "build_hybrid_multihorizon",
    "build_multihorizon_forecast",
    "circle_area_ha",
    "equivalent_ros_from_area_duration",
    "format_multihorizon_human",
    "from_arrival_ros_result",
    "from_psb_duration",
    "from_s4_board_sources",
    "load_weather_json",
    "multihorizon_to_geojson",
    "multipass_envelope_scorecard",
    "normalize_lead_times_h",
    "reinit_multihorizon_from_frame",
    "sector_ros_from_primary",
]
