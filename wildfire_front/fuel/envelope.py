"""Hybrid short-horizon envelope 15/30/60 (product v3).

Extrudes hybrid sector ROS into guidance radii. Never tactical dispatch.
Does not invent wind; repairs null hybrid sectors from obs when present.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ENVELOPE_MAX_ROS_M_MIN = 40.0
DEFAULT_HORIZONS_MIN: tuple[int, ...] = (15, 30, 60)
PRODUCT_V3 = "short_horizon_envelope_v3_hybrid"
OBS_FLANK_FRAC = 0.5
OBS_REAR_FRAC = 0.3

_LABEL_EN = (
    "EXTRAPOLATED hybrid short-horizon envelope (obs × physics shape) — "
    "NOT validated tactical dispatch, NOT official perimeter forecast"
)
_LABEL_ES = (
    "GUÍA DE FRENTE EXTRAPOLADA híbrida (obs × forma física) — "
    "NO es despacho táctico validado ni perímetro oficial"
)


def cap_ros(ros_m_min: float, cap: float = ENVELOPE_MAX_ROS_M_MIN) -> float:
    return min(max(0.0, float(ros_m_min)), float(cap))


def obs_only_sector_ros(observed_ros_m_min: float) -> dict[str, float]:
    """head=obs, flank=0.5*obs, rear=0.3*obs, primary=obs; clamp head≥flank≥rear."""
    obs = float(observed_ros_m_min)
    head = obs
    flank = obs * OBS_FLANK_FRAC
    rear = obs * OBS_REAR_FRAC
    flank = min(flank, head)
    rear = min(rear, flank)
    return {
        "head": head,
        "flank": flank,
        "rear": rear,
        "primary": obs,
    }


def _get_sector(sectors: Mapping[str, Any], name: str) -> float | None:
    for key in (f"{name}_m_min", name):
        if key in sectors and sectors[key] is not None:
            try:
                v = float(sectors[key])
            except (TypeError, ValueError):
                continue
            if math.isfinite(v) and v >= 0:
                return v
    return None


def extract_sector_ros(
    hybrid: Mapping[str, Any] | None,
    *,
    observed_ros_m_min: float | None = None,
) -> tuple[dict[str, float] | None, list[str]]:
    """Return ({head,flank,rear,primary}, reasons) or (None, reasons)."""
    reasons: list[str] = []
    sectors = (hybrid or {}).get("sectors") if hybrid else None
    if not isinstance(sectors, Mapping):
        sectors = {}

    head = _get_sector(sectors, "head")
    flank = _get_sector(sectors, "flank")
    rear = _get_sector(sectors, "rear")
    primary = _get_sector(sectors, "primary")

    if any(v is None for v in (head, flank, rear)):
        if observed_ros_m_min is not None and math.isfinite(float(observed_ros_m_min)) and float(observed_ros_m_min) > 0:
            reasons.append("hybrid_sectors_null_obs_only")
            return obs_only_sector_ros(float(observed_ros_m_min)), reasons
        reasons.append("no_usable_sectors")
        return None, reasons

    assert head is not None and flank is not None and rear is not None
    if primary is None:
        primary = float(np.median([head, flank, rear]))
    # order
    flank = min(flank, head)
    rear = min(rear, flank)
    return {
        "head": float(head),
        "flank": float(flank),
        "rear": float(rear),
        "primary": float(primary),
    }, reasons


def radii_from_sector_ros(
    head: float,
    flank: float,
    rear: float,
    *,
    primary: float | None = None,
    horizons_min: Sequence[int] = DEFAULT_HORIZONS_MIN,
    cap_m_min: float = ENVELOPE_MAX_ROS_M_MIN,
    head_bearing_deg: float | None = None,
) -> list[dict[str, Any]]:
    """Pure math: per-horizon radius entries."""
    h_ros = cap_ros(head, cap_m_min)
    f_ros = cap_ros(flank, cap_m_min)
    r_ros = cap_ros(rear, cap_m_min)
    f_ros = min(f_ros, h_ros)
    r_ros = min(r_ros, f_ros)
    p_ros = cap_ros(primary if primary is not None else f_ros, cap_m_min)

    out: list[dict[str, Any]] = []
    for h in horizons_min:
        th = float(h)
        entry: dict[str, Any] = {
            "horizon_min": int(h),
            "head_radius_m": round(h_ros * th, 2),
            "flank_radius_m": round(f_ros * th, 2),
            "rear_radius_m": round(r_ros * th, 2),
            "primary_radius_m": round(p_ros * th, 2),
            "radius_m": round(p_ros * th, 2),  # isotropic compat
            "head_ros_m_min": round(h_ros, 4),
            "flank_ros_m_min": round(f_ros, 4),
            "rear_ros_m_min": round(r_ros, 4),
            "primary_ros_m_min": round(p_ros, 4),
            "ros_m_min_used": round(p_ros, 4),  # v2 compat alias
        }
        if head_bearing_deg is not None:
            entry["head_bearing_deg"] = round(float(head_bearing_deg) % 360.0, 2)
        out.append(entry)
    return out


def radius_at_bearing(
    delta_deg: float, head: float, flank: float, rear: float
) -> float:
    """Normative polar radius at angle delta from head bearing (deg)."""
    d = math.radians(float(delta_deg))
    H = max(0.0, math.cos(d)) ** 2
    Rr = max(0.0, math.cos(d + math.pi)) ** 2
    s = H + Rr
    if s > 1.0:
        H, Rr = H / s, Rr / s
        F = 0.0
    else:
        F = 1.0 - s
    return float(head) * H + float(flank) * F + float(rear) * Rr


def ellipse_polar_ring(
    cx: float,
    cy: float,
    head_radius_m: float,
    flank_radius_m: float,
    rear_radius_m: float,
    head_bearing_deg: float,
    *,
    n: int = 72,
) -> list[list[float]]:
    """Closed ring via radius_at_bearing. Bearing 0=+y (N), 90=+x (E)."""
    coords: list[list[float]] = []
    for i in range(n):
        theta = 360.0 * i / n
        delta = ((theta - float(head_bearing_deg) + 180.0) % 360.0) - 180.0
        r = radius_at_bearing(delta, head_radius_m, flank_radius_m, rear_radius_m)
        br = math.radians(theta)
        x = float(cx) + r * math.sin(br)
        y = float(cy) + r * math.cos(br)
        coords.append([round(x, 3), round(y, 3)])
    if coords:
        coords.append(coords[0])
    return coords


def resolve_ensemble_weather(
    hybrid: Mapping[str, Any] | None,
    *,
    wind_10m_ms: float | None,
    wind_from_deg: float | None,
    dead_fmc_pct: float | None,
    fuel_id: str | None,
    slope_deg: float | None,
    observed_ros_m_min: float | None,
) -> dict[str, Any] | None:
    """Return complete weather dict or None. Never invent wind 270/4.4."""
    drivers: dict[str, Any] = {}
    if hybrid:
        phys = hybrid.get("physics") or {}
        if isinstance(phys, Mapping):
            drivers = dict(phys.get("drivers") or {})

    def _pick(key: str, explicit: Any, driver_keys: Sequence[str]) -> Any:
        if explicit is not None:
            return explicit
        for dk in driver_keys:
            if dk in drivers and drivers[dk] is not None:
                return drivers[dk]
        return None

    w = _pick("wind_10m_ms", wind_10m_ms, ("wind_10m_ms", "midflame_wind_ms"))
    # midflame is not 10m — only use wind_10m_ms from drivers
    if wind_10m_ms is None and "wind_10m_ms" in drivers:
        w = drivers["wind_10m_ms"]
    elif wind_10m_ms is not None:
        w = wind_10m_ms
    else:
        w = None

    wf = _pick("wind_from_deg", wind_from_deg, ("wind_from_deg",))
    fmc = _pick("dead_fmc_pct", dead_fmc_pct, ("dead_fmc_pct",))
    fid = fuel_id or drivers.get("fuel_id")
    sl = slope_deg if slope_deg is not None else drivers.get("slope_deg")

    needed = {
        "wind_10m_ms": w,
        "wind_from_deg": wf,
        "dead_fmc_pct": fmc,
        "fuel_id": fid,
        "slope_deg": sl,
    }
    for k, v in needed.items():
        if v is None:
            return None
        try:
            if k != "fuel_id" and not math.isfinite(float(v)):
                return None
        except (TypeError, ValueError):
            return None

    return {
        "wind_10m_ms": float(w),  # type: ignore[arg-type]
        "wind_from_deg": float(wf),  # type: ignore[arg-type]
        "dead_fmc_pct": float(fmc),  # type: ignore[arg-type]
        "fuel_id": str(fid),
        "slope_deg": float(sl),  # type: ignore[arg-type]
        "observed_ros_m_min": observed_ros_m_min,
    }


def ensemble_sector_ros_samples(
    *,
    observed_ros_m_min: float | None,
    fuel_id: str,
    wind_10m_ms: float,
    wind_from_deg: float,
    slope_deg: float,
    dead_fmc_pct: float,
    obs_age_minutes: float | None = 20.0,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    wind_factors: Sequence[float] = (0.8, 1.0, 1.2),
    fmc_deltas_pct: Sequence[float] = (-2.0, 0.0, 2.0),
) -> list[dict[str, float]]:
    from .hybrid import hybrid_ros_prior

    samples: list[dict[str, float]] = []
    for wf in wind_factors:
        for df in fmc_deltas_pct:
            h = hybrid_ros_prior(
                observed_ros_m_min,
                fuel_id=fuel_id,
                wind_10m_ms=float(wind_10m_ms) * float(wf),
                wind_from_deg=wind_from_deg,
                slope_deg=slope_deg,
                dead_fmc_pct=max(2.0, float(dead_fmc_pct) + float(df)),
                obs_age_minutes=obs_age_minutes,
                calibration_recipe=calibration_recipe,
                dem_source=dem_source,
            )
            sec, _ = extract_sector_ros(h, observed_ros_m_min=observed_ros_m_min)
            if sec:
                samples.append(sec)
    return samples


def physics_only_sector_ros_samples(
    *,
    fuel_id: str,
    wind_10m_ms: float,
    wind_from_deg: float,
    slope_deg: float,
    dead_fmc_pct: float,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    wind_factors: Sequence[float] = (0.8, 1.0, 1.2),
    fmc_deltas_pct: Sequence[float] = (-2.0, 0.0, 2.0),
) -> list[dict[str, float]]:
    from .calibration import apply_calibration, load_recipe, CalibrationRecipe
    from .rothermel_lite import estimate_sector_ros_physics

    recipe = calibration_recipe
    if isinstance(recipe, (str, Path)):
        recipe = load_recipe(recipe)
    elif isinstance(recipe, dict):
        recipe = CalibrationRecipe.from_dict(recipe)

    samples: list[dict[str, float]] = []
    for wf in wind_factors:
        for df in fmc_deltas_pct:
            raw = estimate_sector_ros_physics(
                fuel=fuel_id,
                wind_10m_ms=float(wind_10m_ms) * float(wf),
                wind_from_deg=wind_from_deg,
                slope_deg=slope_deg,
                dead_fmc_pct=max(2.0, float(dead_fmc_pct) + float(df)),
            )
            prior = raw
            if recipe is not None and raw.status == "estimated":
                try:
                    prior = apply_calibration(
                        raw, recipe, current_dem_source=dem_source, force=False
                    )
                except Exception:
                    prior = raw
            if prior.status != "estimated" or prior.ros_head_m_min is None:
                continue
            samples.append(
                {
                    "head": float(prior.ros_head_m_min),
                    "flank": float(prior.ros_flank_m_min or prior.ros_head_m_min * 0.45),
                    "rear": float(prior.ros_rear_m_min or prior.ros_head_m_min * 0.25),
                    "primary": float(prior.ros_primary_m_min or prior.ros_head_m_min),
                }
            )
    return samples


def _percentiles(vals: list[float]) -> dict[str, float]:
    arr = np.asarray(vals, dtype=float)
    return {
        "p10": round(float(np.percentile(arr, 10)), 2),
        "p50": round(float(np.percentile(arr, 50)), 2),
        "p90": round(float(np.percentile(arr, 90)), 2),
    }


def attach_ensemble_to_envelopes(
    envelopes: list[dict[str, Any]],
    hybrid_samples: list[dict[str, float]],
    physics_samples: list[dict[str, float]] | None,
    *,
    horizons_min: Sequence[int],
    cap_m_min: float = ENVELOPE_MAX_ROS_M_MIN,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach ensemble + ensemble_physics_only; set obs_locked_sectors."""
    locked: list[str] = []
    meta: dict[str, Any] = {
        "enabled": True,
        "n_hybrid_samples": len(hybrid_samples),
        "n_physics_samples": len(physics_samples or []),
        "grid": "wind_x{0.8,1.0,1.2}_fmc_pm2",
    }

    for env in envelopes:
        h = int(env["horizon_min"])
        hy: dict[str, Any] = {}
        for sector in ("head", "flank", "rear"):
            radii = [
                cap_ros(s[sector], cap_m_min) * h
                for s in hybrid_samples
                if sector in s
            ]
            if radii:
                pct = _percentiles(radii)
                hy[f"{sector}_radius_m"] = pct
                if abs(pct["p90"] - pct["p10"]) < 1e-6:
                    if sector not in locked:
                        locked.append(sector)
        env["ensemble"] = hy

        if physics_samples:
            ph: dict[str, Any] = {"not_product_p50": True}
            for sector in ("head", "flank", "rear"):
                radii = [
                    cap_ros(s[sector], cap_m_min) * h
                    for s in physics_samples
                    if sector in s
                ]
                if radii:
                    ph[f"{sector}_radius_m"] = _percentiles(radii)
            env["ensemble_physics_only"] = ph

    meta["obs_locked_sectors"] = locked
    meta["hybrid_ensemble"] = {
        "kind": "residual_under_alpha",
        "note_en": (
            "Hybrid 9-scenario band: residual shape sensitivity under α. "
            "With observed ROS, head is typically flat (p10=p50=p90). "
            "Not free weather uncertainty of unobserved fire."
        ),
        "note_es": (
            "Banda híbrida 9 escenarios: sensibilidad residual bajo α. "
            "Con ROS observada, la cabeza suele ser plana (p10=p50=p90)."
        ),
    }
    meta["physics_only_ensemble"] = {
        "kind": "weather_sensitivity_diagnostic",
        "required_when_with_ensemble": True,
        "not_product_p50": True,
        "note_en": "Physics-only band is diagnostic; not the hybrid p50 product radii.",
    }
    return envelopes, meta


def compute_hybrid_envelope(
    hybrid: Mapping[str, Any] | None = None,
    *,
    observed_ros_m_min: float | None = None,
    fuel_id: str = "MED_MAQUIS_LOW",
    wind_10m_ms: float | None = None,
    wind_from_deg: float | None = None,
    slope_deg: float = 5.0,
    dead_fmc_pct: float | None = None,
    obs_age_minutes: float | None = 20.0,
    calibration_recipe: Any | None = None,
    dem_source: str | None = None,
    horizons_min: Sequence[int] = DEFAULT_HORIZONS_MIN,
    head_bearing_deg: float | None = None,
    origin_xy: tuple[float, float] | None = None,
    origin_source: str = "none",
    fire_id: str = "",
    with_ensemble: bool = False,
    weather_scenario_assumed: bool = False,
) -> dict[str, Any]:
    """Build short_horizon_envelope_v3_hybrid document."""
    from .hybrid import hybrid_ros_prior

    base: dict[str, Any] = {
        "product": PRODUCT_V3,
        "label_en": _LABEL_EN,
        "label_es": _LABEL_ES,
        "horizons_min": list(horizons_min),
        "not_tactical_dispatch": True,
        "not_dispatch": True,
        "not_official_perimeter": True,
        "fire_id": fire_id or None,
        "sector_aware": True,
        "cap_ros_m_min": ENVELOPE_MAX_ROS_M_MIN,
        "weather_scenario_assumed": bool(weather_scenario_assumed),
        "origin": {
            "source": origin_source,
            "xy": list(origin_xy) if origin_xy else None,
        },
    }

    hybrid_doc: Mapping[str, Any] | None = hybrid
    if hybrid_doc is None:
        hybrid_doc = hybrid_ros_prior(
            observed_ros_m_min,
            fuel_id=fuel_id,
            wind_10m_ms=wind_10m_ms,
            wind_from_deg=wind_from_deg if wind_from_deg is not None else 0.0,
            # wind_from only used for physics shape; if no wind_10m, hybrid may obs-only
            slope_deg=slope_deg,
            dead_fmc_pct=dead_fmc_pct if dead_fmc_pct is not None else 7.0,
            obs_age_minutes=obs_age_minutes,
            calibration_recipe=calibration_recipe,
            dem_source=dem_source,
        )
        # If wind missing and we forced defaults for internal call, mark assumed only when
        # weather_scenario_assumed or we used placeholder — prefer re-call with None wind
        if wind_10m_ms is None:
            hybrid_doc = hybrid_ros_prior(
                observed_ros_m_min,
                fuel_id=fuel_id,
                wind_10m_ms=None,
                wind_from_deg=wind_from_deg if wind_from_deg is not None else 0.0,
                slope_deg=slope_deg,
                dead_fmc_pct=dead_fmc_pct if dead_fmc_pct is not None else 7.0,
                obs_age_minutes=obs_age_minutes,
                calibration_recipe=calibration_recipe,
                dem_source=dem_source,
            )

    if hybrid_doc.get("status") == "abstained":
        base["status"] = "abstained"
        base["reason"] = hybrid_doc.get("reason") or "hybrid_abstained"
        base["envelopes"] = []
        base["hybrid_status"] = hybrid_doc.get("status")
        base["alpha_obs"] = hybrid_doc.get("alpha_obs")
        return base

    obs = observed_ros_m_min
    if obs is None and hybrid_doc.get("sectors"):
        # try primary from hybrid after extract
        pass
    if obs is None:
        # recover obs from nested if present
        pr = (hybrid_doc.get("physics_report_calibration") or {}).get("observed_ros_m_min")
        if pr is not None:
            obs = float(pr)

    sectors, reasons = extract_sector_ros(hybrid_doc, observed_ros_m_min=obs)
    if sectors is None:
        base["status"] = "abstained"
        base["reason"] = "no_usable_sectors"
        base["reasons"] = reasons
        base["envelopes"] = []
        base["hybrid_status"] = hybrid_doc.get("status")
        return base

    bearing = head_bearing_deg
    if bearing is None:
        drivers = ((hybrid_doc.get("physics") or {}).get("drivers") or {})
        if "head_bearing_deg" in drivers:
            bearing = float(drivers["head_bearing_deg"])
        elif "wind_from_deg" in drivers:
            bearing = (float(drivers["wind_from_deg"]) + 180.0) % 360.0

    envelopes = radii_from_sector_ros(
        sectors["head"],
        sectors["flank"],
        sectors["rear"],
        primary=sectors["primary"],
        horizons_min=horizons_min,
        head_bearing_deg=bearing,
    )

    status = "ok"
    if weather_scenario_assumed:
        status = "inputs_assumed"
    if hybrid_doc.get("status") == "estimated_obs_only" or "hybrid_sectors_null_obs_only" in reasons:
        status = "inputs_assumed" if weather_scenario_assumed else "ok"
        reasons = list(reasons) + ["hybrid_obs_only_path"]

    ensemble_meta: dict[str, Any] = {"enabled": False}
    if with_ensemble:
        weather = resolve_ensemble_weather(
            hybrid_doc,
            wind_10m_ms=wind_10m_ms,
            wind_from_deg=wind_from_deg,
            dead_fmc_pct=dead_fmc_pct,
            fuel_id=fuel_id,
            slope_deg=slope_deg,
            observed_ros_m_min=obs,
        )
        if weather is None:
            ensemble_meta = {
                "enabled": False,
                "reason": "ensemble_missing_weather_inputs",
            }
        else:
            hy_samples = ensemble_sector_ros_samples(
                observed_ros_m_min=weather.get("observed_ros_m_min") or obs,
                fuel_id=str(weather["fuel_id"]),
                wind_10m_ms=float(weather["wind_10m_ms"]),
                wind_from_deg=float(weather["wind_from_deg"]),
                slope_deg=float(weather["slope_deg"]),
                dead_fmc_pct=float(weather["dead_fmc_pct"]),
                obs_age_minutes=obs_age_minutes,
                calibration_recipe=calibration_recipe,
                dem_source=dem_source,
            )
            ph_samples = physics_only_sector_ros_samples(
                fuel_id=str(weather["fuel_id"]),
                wind_10m_ms=float(weather["wind_10m_ms"]),
                wind_from_deg=float(weather["wind_from_deg"]),
                slope_deg=float(weather["slope_deg"]),
                dead_fmc_pct=float(weather["dead_fmc_pct"]),
                calibration_recipe=calibration_recipe,
                dem_source=dem_source,
            )
            if hy_samples:
                envelopes, ensemble_meta = attach_ensemble_to_envelopes(
                    envelopes, hy_samples, ph_samples or None, horizons_min=horizons_min
                )
            else:
                ensemble_meta = {
                    "enabled": False,
                    "reason": "ensemble_no_hybrid_samples",
                }

    base.update(
        {
            "status": status,
            "envelopes": envelopes,
            "sector_ros_m_min": {
                "head": round(sectors["head"], 4),
                "flank": round(sectors["flank"], 4),
                "rear": round(sectors["rear"], 4),
                "primary": round(sectors["primary"], 4),
            },
            "ros_m_min": round(sectors["primary"], 4),
            "expansion_bearing_deg": (
                round(float(bearing) % 360.0, 2) if bearing is not None else None
            ),
            "alpha_obs": hybrid_doc.get("alpha_obs"),
            "hybrid_status": hybrid_doc.get("status"),
            "hybrid_method": hybrid_doc.get("method"),
            "reasons": reasons,
            "ensemble_meta": ensemble_meta,
            "physics_product_claim": hybrid_doc.get("physics_product_claim"),
            "disclaimer": (
                "Engineering short-horizon guidance only; "
                "not official perimeter; not tactical dispatch"
            ),
        }
    )
    return base


def hybrid_envelope_to_geojson(
    envelope: Mapping[str, Any],
    *,
    center_xy: tuple[float, float] | None = None,
    include_wedges: bool = True,
    include_polar: bool = True,
    include_ensemble_rings: bool = False,
    include_physics_only_rings: bool = False,
    fire_id: str = "",
) -> dict[str, Any]:
    """FeatureCollection of guidance rings (projected meters)."""
    from wildfire_front.emergency_products import _circle_ring, _sector_wedge_ring

    label = {
        "guidance": "extrapolated_hybrid_ros",
        "not_official_perimeter": True,
        "not_tactical_dispatch": True,
        "not_dispatch": True,
        "label_en": envelope.get("label_en"),
        "label_es": envelope.get("label_es"),
        "fire_id": fire_id or envelope.get("fire_id"),
        "product": envelope.get("product") or PRODUCT_V3,
    }
    origin = envelope.get("origin") or {}
    if center_xy is None and origin.get("xy"):
        center_xy = (float(origin["xy"][0]), float(origin["xy"][1]))

    if center_xy is None:
        return {
            "type": "FeatureCollection",
            "features": [],
            "properties": {**label, "status": "abstained", "reason": "no_center"},
        }

    cx, cy = float(center_xy[0]), float(center_xy[1])
    bearing = envelope.get("expansion_bearing_deg")
    features: list[dict[str, Any]] = []

    for e in envelope.get("envelopes") or []:
        h = int(e.get("horizon_min") or 0)
        r_flank = float(e.get("flank_radius_m") or e.get("radius_m") or 0)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    **label,
                    "horizon_min": h,
                    "sector": "flank_isotropic",
                    "radius_m": r_flank,
                    "ros_m_min": e.get("flank_ros_m_min"),
                    "not_product_p50": False,
                },
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [_circle_ring(cx, cy, r_flank)],
                },
            }
        )
        r_head = float(e.get("head_radius_m") or r_flank)
        r_rear = float(e.get("rear_radius_m") or 0)
        if include_wedges and bearing is not None:
            if r_head > 0:
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
                            "coordinates": [
                                _sector_wedge_ring(cx, cy, r_head, float(bearing), 45.0)
                            ],
                        },
                    }
                )
            if r_rear > 0:
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
        if include_polar and bearing is not None and r_head > 0:
            ring = ellipse_polar_ring(
                cx, cy, r_head, r_flank, r_rear, float(bearing)
            )
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        **label,
                        "horizon_min": h,
                        "sector": "polar_p50",
                        "radius_m": r_head,
                        "ros_m_min": e.get("head_ros_m_min"),
                    },
                    "geometry": {"type": "Polygon", "coordinates": [ring]},
                }
            )

        if include_ensemble_rings and e.get("ensemble"):
            ens = e["ensemble"]
            head_band = ens.get("head_radius_m") or {}
            for key, sector_name in (("p10", "polar_p10"), ("p90", "polar_p90")):
                if key in head_band and bearing is not None:
                    rh = float(head_band[key])
                    rf = float((ens.get("flank_radius_m") or {}).get(key, r_flank))
                    rr = float((ens.get("rear_radius_m") or {}).get(key, r_rear))
                    features.append(
                        {
                            "type": "Feature",
                            "properties": {
                                **label,
                                "horizon_min": h,
                                "sector": sector_name,
                                "percentile": key,
                                "radius_m": rh,
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    ellipse_polar_ring(cx, cy, rh, rf, rr, float(bearing))
                                ],
                            },
                        }
                    )

        if include_physics_only_rings and e.get("ensemble_physics_only"):
            epo = e["ensemble_physics_only"]
            head_band = epo.get("head_radius_m") or {}
            for key in ("p10", "p90"):
                if key in head_band and bearing is not None:
                    rh = float(head_band[key])
                    rf = float((epo.get("flank_radius_m") or {}).get(key, r_flank))
                    rr = float((epo.get("rear_radius_m") or {}).get(key, r_rear))
                    features.append(
                        {
                            "type": "Feature",
                            "properties": {
                                **label,
                                "horizon_min": h,
                                "sector": f"physics_only_polar_{key}",
                                "percentile": key,
                                "radius_m": rh,
                                "not_product_p50": True,
                            },
                            "geometry": {
                                "type": "Polygon",
                                "coordinates": [
                                    ellipse_polar_ring(cx, cy, rh, rf, rr, float(bearing))
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
            "ensemble_meta": envelope.get("ensemble_meta"),
        },
    }


def write_hybrid_envelope_json(envelope: Mapping[str, Any], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False), encoding="utf-8")


def write_hybrid_envelope_geojson(
    envelope: Mapping[str, Any],
    path: Path,
    *,
    center_xy: tuple[float, float] | None = None,
    write_wgs84: bool = True,
    fire_id: str = "",
    **geo_kwargs: Any,
) -> dict[str, Any]:
    """Write envelope GeoJSON; optional WGS84 primary + UTM sibling."""
    from wildfire_front.geo_crs import geojson_to_wgs84, looks_projected_meters

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    gj = hybrid_envelope_to_geojson(
        envelope, center_xy=center_xy, fire_id=fire_id, **geo_kwargs
    )

    is_utm = False
    if center_xy is not None:
        is_utm = looks_projected_meters(float(center_xy[0]), float(center_xy[1]))

    if write_wgs84 and is_utm:
        utm_path = path.with_name(path.stem + "_utm.geojson")
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


def envelope_decision_reasons(envelope: Mapping[str, Any]) -> list[str]:
    """Honest reasons for Decision Card / briefing (F3.5 lite)."""
    reasons: list[str] = [
        "envelope_is_extrapolated_guidance",
        "not_official_perimeter",
        "not_tactical_dispatch",
    ]
    st = envelope.get("status")
    if st == "abstained":
        reasons.append(f"envelope_abstained:{envelope.get('reason')}")
    if st == "inputs_assumed":
        reasons.append("weather_scenario_assumed")
    if envelope.get("ensemble_meta", {}).get("obs_locked_sectors"):
        reasons.append(
            "hybrid_ensemble_head_obs_locked:"
            + ",".join(envelope["ensemble_meta"]["obs_locked_sectors"])
        )
    if envelope.get("alpha_obs") is not None:
        reasons.append(f"hybrid_alpha_obs={envelope['alpha_obs']}")
    return reasons


def bbox_center_utm(
    bbox_wgs84: Sequence[float],
    *,
    target_crs: str = "EPSG:32630",
) -> tuple[float, float]:
    """Mean lon/lat of bbox → projected meters."""
    from pyproj import Transformer

    w, s, e, n = (float(x) for x in bbox_wgs84)
    lon = 0.5 * (w + e)
    lat = 0.5 * (s + n)
    tr = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
    x, y = tr.transform(lon, lat)
    return float(x), float(y)
