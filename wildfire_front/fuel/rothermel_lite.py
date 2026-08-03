"""Rothermel-lite surface ROS for ops product (physics potential).

This is an **engineering prior**, not a full BehavePlus port. It uses
fuel-model parameters from ``fuel.models`` with a simplified Rothermel form
compatible with the existing ``ml.physics.rothermel_ros`` numerical path,
extended with fuel-specific load/depth/SAV and midflame wind reduction.

Product rules:
- ABSTAIN if fuel UNKNOWN or wind missing (when required)
- Label outputs as ``physics_potential`` never ``tactical_dispatch``
- Cap ROS at literature extreme (120 m/min)
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .models import FUEL_CATALOG, FuelModel, get_fuel
from .terrain import slope_factor_phi_s, upslope_alignment

_ROS_CAP = 120.0
_MIN_ROS = 0.01


@dataclass
class PhysicsPriorResult:
    status: str  # estimated | abstained
    method: str
    fuel_id: str
    ros_head_m_min: float | None
    ros_flank_m_min: float | None
    ros_rear_m_min: float | None
    ros_primary_m_min: float | None
    band_p10_p90: dict[str, list[float]] | None
    drivers: dict[str, Any]
    reasons: list[str] = field(default_factory=list)
    product_claim: str = "physics_potential_orientation_only"
    no_tactical_dispatch: bool = True
    calibration_applied: bool = False
    calibration_recipe_id: str | None = None
    k_factors: dict[str, float] | None = None
    ros_head_raw_m_min: float | None = None
    ros_flank_raw_m_min: float | None = None
    ros_rear_raw_m_min: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def midflame_wind_ms(
    wind_10m_ms: float,
    fuel: FuelModel | str,
    *,
    wind_reduction: float | None = None,
) -> float:
    """Convert 10 m wind to midflame wind using fuel WAF."""
    f = get_fuel(fuel) if isinstance(fuel, str) else fuel
    waf = float(wind_reduction) if wind_reduction is not None else float(f.wind_reduction)
    return max(0.0, float(wind_10m_ms) * waf)


def _packing_ratio(fuel: FuelModel) -> float:
    if fuel.fuel_depth <= 0 or fuel.fuel_density <= 0:
        return 0.05
    # β = load / (depth * particle_density)
    return float(np.clip(fuel.fuel_load / (fuel.fuel_depth * fuel.fuel_density), 1e-4, 0.2))


def _reaction_intensity(fuel: FuelModel, moisture_pct: float) -> float:
    """Simplified reaction intensity (kW/m² proxy → scaled for ROS)."""
    mx = max(1.0, float(fuel.moisture_extinction_pct))
    m = max(0.0, float(moisture_pct))
    if m >= mx:
        return 0.0
    # moisture damping η_M ≈ 1 − 2.59(M/Mx) + 5.11(M/Mx)² − 3.52(M/Mx)³ (Rothermel-ish)
    r = m / mx
    eta_m = 1.0 - 2.59 * r + 5.11 * r * r - 3.52 * r * r * r
    eta_m = max(0.0, eta_m)
    # SA/V boost for fine fuels
    sav_factor = float(np.clip(fuel.fuel_sav / 5000.0, 0.4, 1.6))
    depth_factor = float(np.clip(math.sqrt(max(fuel.fuel_depth, 0.05)), 0.2, 2.0))
    ir = fuel.fuel_load * fuel.fuel_heat * 0.001 * eta_m * sav_factor * depth_factor
    return float(max(0.0, ir))


def _phi_w(midflame_ms: float, fuel: FuelModel) -> float:
    """Wind factor Φ_w (simplified Rothermel-like)."""
    u = max(0.0, float(midflame_ms))
    if u <= 0:
        return 0.0
    # SA/V modulates wind sensitivity
    b = 1.4 + 0.2 * (fuel.fuel_sav / 5000.0)
    c = 4.5 * (fuel.fuel_sav / 5000.0) ** 0.3
    return float(c * (u**b) * 0.35)


def ros_potential_m_min(
    *,
    fuel: FuelModel | str,
    wind_10m_ms: float | None,
    slope_deg: float,
    dead_fmc_pct: float,
    wind_to_spread_deg: float = 0.0,
    aspect_deg: float | None = None,
    require_wind: bool = True,
    upslope: bool | None = None,
) -> dict[str, Any]:
    """Directional surface ROS potential (m/min).

    ``wind_to_spread_deg``: angle between wind vector (to) and spread direction
    (0 = wind aligned with spread / head).
    """
    f = get_fuel(fuel) if isinstance(fuel, str) else fuel
    reasons: list[str] = []

    if f.id == "UNKNOWN" or f.fuel_load <= 0:
        return {
            "status": "abstained",
            "ros_m_min": None,
            "reason": "unknown_or_empty_fuel",
            "fuel_id": f.id,
        }

    if require_wind and (wind_10m_ms is None or not math.isfinite(float(wind_10m_ms))):
        return {
            "status": "abstained",
            "ros_m_min": None,
            "reason": "missing_wind",
            "fuel_id": f.id,
        }

    w10 = 0.0 if wind_10m_ms is None else float(wind_10m_ms)
    mf = midflame_wind_ms(w10, f)
    # wind component along spread
    th = math.radians(float(wind_to_spread_deg))
    # only positive wind contribution along spread (head); rear gets small residual
    u_eff = mf * max(0.0, math.cos(th))

    ir = _reaction_intensity(f, dead_fmc_pct)
    if ir <= 0:
        return {
            "status": "estimated",
            "ros_m_min": 0.0,
            "reason": "moisture_at_or_above_extinction",
            "fuel_id": f.id,
            "midflame_wind_ms": mf,
        }

    beta = _packing_ratio(f)
    if upslope is None:
        up = upslope_alignment(0.0 if wind_to_spread_deg == 0 else 0.0, aspect_deg)
        # better: upslope if spread is upslope — use spread as 0 relative when head
        up = True if aspect_deg is None else upslope_alignment(0.0, aspect_deg)
    else:
        up = bool(upslope)

    phi_s = slope_factor_phi_s(slope_deg, packing_ratio=beta)
    if not up:
        phi_s = -0.5 * phi_s  # downslope penalty (lite)

    phi_w = _phi_w(u_eff, f)
    # base ROS scale: maps IR·(1+Φ) into m/min order of magnitude for Med fuels
    base = ir * (1.0 + phi_w + max(-0.9, phi_s))
    # normalize so moderate shrub ~ few–tens m/min
    ros = base * 0.85
    ros = float(np.clip(ros, 0.0, _ROS_CAP))
    if ros < _MIN_ROS and ir > 0:
        ros = _MIN_ROS

    return {
        "status": "estimated",
        "ros_m_min": round(ros, 4),
        "fuel_id": f.id,
        "midflame_wind_ms": round(mf, 4),
        "phi_w": round(phi_w, 4),
        "phi_s": round(phi_s, 4),
        "reaction_intensity_proxy": round(ir, 4),
        "dead_fmc_pct": float(dead_fmc_pct),
        "slope_deg": float(slope_deg),
        "wind_10m_ms": w10,
        "wind_to_spread_deg": float(wind_to_spread_deg),
        "reasons": reasons,
    }


def _angle_abs(a: float, b: float) -> float:
    return abs((float(a) - float(b) + 180.0) % 360.0 - 180.0)


def _ros_for_fuel(
    fuel: FuelModel | str,
    *,
    wind_10m_ms: float | None,
    slope_deg: float,
    dead_fmc_pct: float,
    wind_to: float,
    spread_bearing: float,
    aspect_deg: float | None,
    require_wind: bool,
    upslope: bool,
) -> float:
    wind_to_spread = _angle_abs(wind_to, spread_bearing)
    r = ros_potential_m_min(
        fuel=fuel,
        wind_10m_ms=wind_10m_ms,
        slope_deg=slope_deg,
        dead_fmc_pct=dead_fmc_pct,
        wind_to_spread_deg=wind_to_spread,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=upslope,
    )
    if r["status"] != "estimated" or r.get("ros_m_min") is None:
        return 0.0
    return float(r["ros_m_min"])


def estimate_sector_ros_physics(
    *,
    fuel: FuelModel | str,
    wind_10m_ms: float | None,
    slope_deg: float,
    dead_fmc_pct: float,
    wind_from_deg: float = 270.0,
    head_bearing_deg: float | None = None,
    aspect_deg: float | None = None,
    require_wind: bool = True,
) -> PhysicsPriorResult:
    """Head / flank / rear physics ROS for a single fuel+terrain scenario.

    Wind **from** convention (met): wind blows from wind_from_deg.
    Head defaults to downwind direction (wind_from + 180).
    """
    f = get_fuel(fuel) if isinstance(fuel, str) else fuel
    if f.id == "UNKNOWN":
        return PhysicsPriorResult(
            status="abstained",
            method="rothermel_lite_sectors_v1",
            fuel_id=f.id,
            ros_head_m_min=None,
            ros_flank_m_min=None,
            ros_rear_m_min=None,
            ros_primary_m_min=None,
            band_p10_p90=None,
            drivers={},
            reasons=["unknown_fuel_class"],
        )
    if require_wind and wind_10m_ms is None:
        return PhysicsPriorResult(
            status="abstained",
            method="rothermel_lite_sectors_v1",
            fuel_id=f.id,
            ros_head_m_min=None,
            ros_flank_m_min=None,
            ros_rear_m_min=None,
            ros_primary_m_min=None,
            band_p10_p90=None,
            drivers={},
            reasons=["missing_wind"],
        )

    wind_to = (float(wind_from_deg) + 180.0) % 360.0
    head_b = float(head_bearing_deg) if head_bearing_deg is not None else wind_to

    head = _ros_for_fuel(
        f,
        wind_10m_ms=wind_10m_ms,
        slope_deg=slope_deg,
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=head_b,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=True,
    )
    rear = _ros_for_fuel(
        f,
        wind_10m_ms=wind_10m_ms,
        slope_deg=slope_deg,
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=(head_b + 180.0) % 360.0,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=False,
    )
    flank = _ros_for_fuel(
        f,
        wind_10m_ms=wind_10m_ms,
        slope_deg=slope_deg,
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=(head_b + 90.0) % 360.0,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=True,
    )
    # Single-fuel path: soft intermediate flank shape (legacy product stability)
    flank = float(np.median([flank, head * 0.45, max(rear, head * 0.2)]))
    if head < rear:
        head, rear = rear, head

    primary = float(np.median([head, flank, rear]))

    # Uncertainty band from FMC ±2% and wind ±20% ensemble (lite)
    w0 = 0.0 if wind_10m_ms is None else float(wind_10m_ms)
    samples_h: list[float] = []
    for dw in (0.8, 1.0, 1.2):
        for dm in (-2.0, 0.0, 2.0):
            rr = ros_potential_m_min(
                fuel=f,
                wind_10m_ms=w0 * dw,
                slope_deg=slope_deg,
                dead_fmc_pct=max(2.0, dead_fmc_pct + dm),
                wind_to_spread_deg=0.0,
                require_wind=False,
                upslope=True,
            )
            if rr.get("ros_m_min") is not None:
                samples_h.append(float(rr["ros_m_min"]))
    if samples_h:
        arr = np.asarray(samples_h, dtype=float)
        p10, p90 = float(np.percentile(arr, 10)), float(np.percentile(arr, 90))
    else:
        p10, p90 = head * 0.6, head * 1.4

    return PhysicsPriorResult(
        status="estimated",
        method="rothermel_lite_sectors_v1",
        fuel_id=f.id,
        ros_head_m_min=round(head, 4),
        ros_flank_m_min=round(flank, 4),
        ros_rear_m_min=round(rear, 4),
        ros_primary_m_min=round(primary, 4),
        band_p10_p90={
            "head_m_min": [round(p10, 4), round(p90, 4)],
        },
        drivers={
            "fuel_id": f.id,
            "fuel_family": f.family,
            "fuel_height_m": f.height_m,
            "fuel_depth_m": f.fuel_depth,
            "slope_deg": slope_deg,
            "wind_10m_ms": w0,
            "wind_from_deg": wind_from_deg,
            "head_bearing_deg": head_b,
            "dead_fmc_pct": dead_fmc_pct,
            "midflame_wind_ms": midflame_wind_ms(w0, f),
            "provenance": f.provenance,
            "sector_fuel_mode": "single_dominant",
        },
        reasons=[],
    )


def estimate_sector_ros_from_fuel_map(
    fuel_map: Any | None = None,
    *,
    wind_10m_ms: float | None,
    slope_deg: float,
    dead_fmc_pct: float,
    wind_from_deg: float = 270.0,
    head_bearing_deg: float | None = None,
    aspect_deg: float | None = None,
    require_wind: bool = True,
    sector_fuels: Any | None = None,
    fallback_fuel_id: str | None = None,
    fuel_id_grid: Any | None = None,
    slope_deg_grid: Any | None = None,
    sector_slopes: Any | None = None,
) -> PhysicsPriorResult:
    """Head / flank / rear physics using **sector-majority fuels** from a map.

    When ``sector_fuels`` or a fuel map / grid is provided:
    - head ROS uses head-wedge majority fuel
    - flank ROS uses flank-wedge majority fuel (not only head model) — improves
      crude single-fuel flank shape
    - rear ROS uses rear-wedge majority fuel

    Falls back to ``estimate_sector_ros_physics`` with dominant/fallback fuel when
    spatial mix is unavailable. Sector assignment is persisted in ``drivers``.

    Honesty:
    - All-UNKNOWN spatial mix → **ABSTAIN** (even if ``fallback_fuel_id`` is set).
      Use non-spatial ``estimate_sector_ros_physics(fallback)`` intentionally for
      dominant-only priors — do not label spatial ROS with a real fuel while
      computing from UNKNOWN cells.
    - Head UNKNOWN with burnable flank/rear → substitute head fuel for ROS
      (fallback → flank → rear) and record ``head_fuel_substituted_*``; fuel–ROS
      pairing stays fixed (no head/rear value swap that desyncs audit ids).
    """
    from .sector_fuels import (
        SectorFuelSummary,
        SectorTerrainSummary,
        canonicalize_fuel_id,
        sector_fuel_summary_from_grid,
        sector_fuel_summary_from_product,
        sector_slope_summary_from_grid,
    )

    wind_to = (float(wind_from_deg) + 180.0) % 360.0
    head_b = float(head_bearing_deg) if head_bearing_deg is not None else wind_to

    # Per-sector slopes from DEM (optional)
    terr: SectorTerrainSummary | None = None
    if isinstance(sector_slopes, SectorTerrainSummary):
        terr = sector_slopes
    elif isinstance(sector_slopes, dict) and sector_slopes.get("head_slope_deg") is not None:
        terr = SectorTerrainSummary(
            head_slope_deg=float(sector_slopes["head_slope_deg"]),
            flank_slope_deg=float(
                sector_slopes.get("flank_slope_deg", sector_slopes["head_slope_deg"])
            ),
            rear_slope_deg=float(
                sector_slopes.get("rear_slope_deg", sector_slopes["head_slope_deg"])
            ),
            head_bearing_deg=float(sector_slopes.get("head_bearing_deg", head_b)),
            n_cells=dict(sector_slopes.get("n_cells") or {}),
            method=str(sector_slopes.get("method") or "caller_dict"),
            global_mean_slope_deg=sector_slopes.get("global_mean_slope_deg"),
            notes=list(sector_slopes.get("notes") or ["from_dict"]),
        )
    elif slope_deg_grid is not None:
        try:
            terr = sector_slope_summary_from_grid(
                np.asarray(slope_deg_grid, dtype=float),
                head_bearing_deg=head_b,
                fallback_slope_deg=float(slope_deg),
            )
        except Exception:
            terr = None

    def _slope(sector: str) -> float:
        if terr is not None:
            return terr.slope_for(sector)
        return float(slope_deg)

    summary: SectorFuelSummary | None = None
    if isinstance(sector_fuels, SectorFuelSummary):
        summary = sector_fuels
    elif isinstance(sector_fuels, dict):
        summary = SectorFuelSummary(
            head_fuel_id=canonicalize_fuel_id(
                sector_fuels.get("head_fuel_id") or fallback_fuel_id or "UNKNOWN"
            ),
            flank_fuel_id=canonicalize_fuel_id(
                sector_fuels.get("flank_fuel_id")
                or sector_fuels.get("head_fuel_id")
                or "UNKNOWN"
            ),
            rear_fuel_id=canonicalize_fuel_id(
                sector_fuels.get("rear_fuel_id")
                or sector_fuels.get("head_fuel_id")
                or "UNKNOWN"
            ),
            head_mix=dict(sector_fuels.get("head_mix") or {}),
            flank_mix=dict(sector_fuels.get("flank_mix") or {}),
            rear_mix=dict(sector_fuels.get("rear_mix") or {}),
            head_bearing_deg=float(sector_fuels.get("head_bearing_deg", head_b)),
            n_cells=dict(sector_fuels.get("n_cells") or {}),
            method=str(sector_fuels.get("method") or "caller_dict"),
            notes=list(sector_fuels.get("notes") or ["from_dict"]),
            dominant_fallback=fallback_fuel_id,
        )
    elif fuel_map is not None:
        try:
            summary = sector_fuel_summary_from_product(
                fuel_map, head_bearing_deg=head_b
            )
        except Exception:
            summary = None
    elif fuel_id_grid is not None:
        summary = sector_fuel_summary_from_grid(
            np.asarray(fuel_id_grid),
            head_bearing_deg=head_b,
            dominant_fallback=fallback_fuel_id,
        )

    if summary is None:
        fb = fallback_fuel_id or "MED_MAQUIS_LOW"
        if fuel_map is not None and getattr(fuel_map, "fuel_id_dominant", None):
            fb = str(fuel_map.fuel_id_dominant)
        return estimate_sector_ros_physics(
            fuel=fb,
            wind_10m_ms=wind_10m_ms,
            slope_deg=slope_deg,
            dead_fmc_pct=dead_fmc_pct,
            wind_from_deg=wind_from_deg,
            head_bearing_deg=head_b,
            aspect_deg=aspect_deg,
            require_wind=require_wind,
        )

    head_fid = canonicalize_fuel_id(summary.head_fuel_id)
    flank_fid = canonicalize_fuel_id(summary.flank_fuel_id)
    rear_fid = canonicalize_fuel_id(summary.rear_fuel_id)
    map_head_fid = head_fid  # pre-substitution audit
    head_sub_note: str | None = None

    # Issue 1: all-UNKNOWN spatial mix → ABSTAIN (never estimated with fallback label + 0 ROS)
    if head_fid == "UNKNOWN" and flank_fid == "UNKNOWN" and rear_fid == "UNKNOWN":
        return PhysicsPriorResult(
            status="abstained",
            method="rothermel_lite_sectors_spatial_v1",
            fuel_id="UNKNOWN",
            ros_head_m_min=None,
            ros_flank_m_min=None,
            ros_rear_m_min=None,
            ros_primary_m_min=None,
            band_p10_p90=None,
            drivers={
                "sector_fuels": summary.to_dict(),
                "sector_fuel_ids": {
                    "head": head_fid,
                    "flank": flank_fid,
                    "rear": rear_fid,
                },
                "sector_fuel_mode": "spatial_all_unknown",
                "fallback_fuel_id_ignored": fallback_fuel_id,
                "note": (
                    "spatial map all UNKNOWN — abstain; do not apply fallback_fuel_id "
                    "as estimated product (use non-spatial path for dominant-only)"
                ),
            },
            reasons=["unknown_fuel_class", "spatial_all_unknown"],
        )

    # Issue 2: head UNKNOWN but other sectors burnable → substitute head fuel for ROS
    # (keep fuel–ROS pairing; never soft-swap ROS across sectors without updating ids)
    if head_fid == "UNKNOWN":
        fb_can = canonicalize_fuel_id(fallback_fuel_id) if fallback_fuel_id else "UNKNOWN"
        if fb_can != "UNKNOWN":
            head_fid = fb_can
            head_sub_note = f"head_fuel_substituted_from_fallback:{fb_can}"
        elif flank_fid != "UNKNOWN":
            head_fid = flank_fid
            head_sub_note = f"head_fuel_substituted_from_flank:{flank_fid}"
        elif rear_fid != "UNKNOWN":
            head_fid = rear_fid
            head_sub_note = f"head_fuel_substituted_from_rear:{rear_fid}"
        else:
            return PhysicsPriorResult(
                status="abstained",
                method="rothermel_lite_sectors_spatial_v1",
                fuel_id="UNKNOWN",
                ros_head_m_min=None,
                ros_flank_m_min=None,
                ros_rear_m_min=None,
                ros_primary_m_min=None,
                band_p10_p90=None,
                drivers={"sector_fuels": summary.to_dict()},
                reasons=["unknown_fuel_class", "spatial_head_unknown"],
            )

    primary_fid = head_fid

    if require_wind and wind_10m_ms is None:
        return PhysicsPriorResult(
            status="abstained",
            method="rothermel_lite_sectors_spatial_v1",
            fuel_id=primary_fid,
            ros_head_m_min=None,
            ros_flank_m_min=None,
            ros_rear_m_min=None,
            ros_primary_m_min=None,
            band_p10_p90=None,
            drivers={
                "sector_fuels": summary.to_dict(),
                "sector_fuel_ids": {
                    "head": head_fid,
                    "flank": flank_fid,
                    "rear": rear_fid,
                    "map_head": map_head_fid,
                },
            },
            reasons=["missing_wind"],
        )

    head = _ros_for_fuel(
        head_fid,
        wind_10m_ms=wind_10m_ms,
        slope_deg=_slope("head"),
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=head_b,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=True,
    )
    # Flank: fuel-map derived majority (not head-only model) at ±90° from head
    flank_use = flank_fid if flank_fid != "UNKNOWN" else head_fid
    rear_use = rear_fid if rear_fid != "UNKNOWN" else head_fid
    flank = _ros_for_fuel(
        flank_use,
        wind_10m_ms=wind_10m_ms,
        slope_deg=_slope("flank"),
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=(head_b + 90.0) % 360.0,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=True,
    )
    rear = _ros_for_fuel(
        rear_use,
        wind_10m_ms=wind_10m_ms,
        slope_deg=_slope("rear"),
        dead_fmc_pct=dead_fmc_pct,
        wind_to=wind_to,
        spread_bearing=(head_b + 180.0) % 360.0,
        aspect_deg=aspect_deg,
        require_wind=require_wind,
        upslope=False,
    )

    # Soft product order: clamp only — never swap multi-fuel ROS (keeps fuel–ROS audit)
    order_notes: list[str] = []
    if head > 0 and flank > head:
        flank = float(head)
        order_notes.append("flank_clamped_le_head")
    if head > 0 and rear > head:
        rear = float(head)
        order_notes.append("rear_clamped_le_head")
    if flank > 0 and rear > flank:
        rear = float(flank)
        order_notes.append("rear_clamped_le_flank")
    if flank <= 0 and head > 0:
        flank = head * 0.45
        order_notes.append("flank_filled_from_head_frac")
    if rear <= 0 and flank > 0:
        rear = min(flank, head * 0.25 if head > 0 else flank)
        order_notes.append("rear_filled_from_flank_or_head_frac")
    if order_notes:
        order_notes.append("ros_order_enforced_head_ge_flank_ge_rear_clamp_only")

    primary = float(np.median([head, flank, rear]))
    w0 = 0.0 if wind_10m_ms is None else float(wind_10m_ms)

    f_head = get_fuel(head_fid)
    samples_h: list[float] = []
    for dw in (0.8, 1.0, 1.2):
        for dm in (-2.0, 0.0, 2.0):
            rr = ros_potential_m_min(
                fuel=f_head,
                wind_10m_ms=w0 * dw,
                slope_deg=_slope("head"),
                dead_fmc_pct=max(2.0, dead_fmc_pct + dm),
                wind_to_spread_deg=0.0,
                require_wind=False,
                upslope=True,
            )
            if rr.get("ros_m_min") is not None:
                samples_h.append(float(rr["ros_m_min"]))
    if samples_h:
        arr = np.asarray(samples_h, dtype=float)
        p10, p90 = float(np.percentile(arr, 10)), float(np.percentile(arr, 90))
    else:
        p10, p90 = head * 0.6, head * 1.4

    reasons = [
        "spatial_sector_fuels",
        "flank_fuel_map_derived",
    ]
    if head_fid != flank_use or head_fid != rear_use:
        reasons.append("sector_fuels_differ")
    if head_sub_note:
        reasons.append("head_fuel_substituted")
        reasons.append(head_sub_note)
    if terr is not None:
        reasons.append("sector_slopes_from_dem")

    sector_fuel_ids = {
        "head": head_fid,
        "flank": flank_use,
        "rear": rear_use,
        "map_head": map_head_fid,
        "map_flank": flank_fid,
        "map_rear": rear_fid,
    }

    return PhysicsPriorResult(
        status="estimated",
        method="rothermel_lite_sectors_spatial_v1",
        fuel_id=primary_fid,
        ros_head_m_min=round(head, 4),
        ros_flank_m_min=round(flank, 4),
        ros_rear_m_min=round(rear, 4),
        ros_primary_m_min=round(primary, 4),
        band_p10_p90={
            "head_m_min": [round(p10, 4), round(p90, 4)],
        },
        drivers={
            "fuel_id": primary_fid,
            "fuel_family": f_head.family,
            "fuel_height_m": f_head.height_m,
            "fuel_depth_m": f_head.fuel_depth,
            "slope_deg": slope_deg,
            "sector_slopes_deg": {
                "head": _slope("head"),
                "flank": _slope("flank"),
                "rear": _slope("rear"),
            },
            "sector_terrain": terr.to_dict() if terr is not None else None,
            "wind_10m_ms": w0,
            "wind_from_deg": wind_from_deg,
            "head_bearing_deg": head_b,
            "dead_fmc_pct": dead_fmc_pct,
            "midflame_wind_ms": midflame_wind_ms(w0, f_head),
            "provenance": f_head.provenance,
            "sector_fuel_mode": "spatial_wedge_majority",
            "sector_fuels": summary.to_dict(),
            "sector_fuel_ids": sector_fuel_ids,
            "head_fuel_substitution": head_sub_note,
            "ros_order_notes": order_notes,
            "flank_note": (
                "flank ROS from flank-wedge majority fuel on fuel map "
                "(not single dominant / head-only model)"
            ),
        },
        reasons=reasons,
    )


# Library engineering defaults (assumed scenario — not station observations).
# Prefer passing WeatherScenario or explicit wind from CLI; these remain for
# back-compat of pure unit calls. Stamped in drivers when used without scenario.
_LIBRARY_DEFAULT_WIND_MS = 4.4
_LIBRARY_DEFAULT_WIND_FROM_DEG = 270.0


def physics_prior_report(
    *,
    fuel_id: str = "MED_MAQUIS_LOW",
    wind_10m_ms: float | None = _LIBRARY_DEFAULT_WIND_MS,
    slope_deg: float = 5.0,
    dead_fmc_pct: float = 7.0,
    wind_from_deg: float = _LIBRARY_DEFAULT_WIND_FROM_DEG,
    head_bearing_deg: float | None = None,
    observed_ros_m_min: float | None = None,
    vp_anchor_m_min: float | None = None,
    vp_status: str | None = None,
    calibration_recipe: Any | None = None,
    fit_calibration: bool = False,
    dem_source: str | None = None,
    dem_binding: dict[str, Any] | None = None,
    fire_id: str = "tobarra_20240802",
    force_recipe: bool = False,
    fuel_map: Any | None = None,
    sector_fuels: Any | None = None,
    slope_deg_grid: Any | None = None,
    weather_scenario: Any | None = None,
    prior_raw: PhysicsPriorResult | None = None,
) -> dict[str, Any]:
    """Full JSON-serializable physics prior report (Tobarra-ready defaults).

    Key ``calibration`` always holds **raw (pre-k)** ratios vs obs/Vp for honesty.
    Optional ``calibration_recipe`` applies k factors to product sectors.

    When ``fuel_map`` or ``sector_fuels`` is set, sectors use spatial majority
    fuels (``estimate_sector_ros_from_fuel_map``); otherwise single ``fuel_id``.
    Optional ``slope_deg_grid`` enables per-wedge DEM slopes.
    Optional ``weather_scenario`` is audited into drivers (does not invent wind).

    ``prior_raw``: optional precomputed ``PhysicsPriorResult`` to avoid double
    physics evaluation (e.g. from ``hybrid_ros_prior``). When set, fuel_map /
    sector_fuels are not re-run for the raw prior.

    Wind defaults (4.4 m/s, 270°) are **library engineering assumed** values,
    not observed weather — stamped when no weather_scenario is supplied.
    Incomplete ``observed``/``aemet`` scenarios never keep library wind while
    ``weather_scenario_assumed=False`` (see ``merge_weather_drivers``).
    """
    from .weather import merge_weather_drivers

    weather_merge = merge_weather_drivers(
        weather_scenario,
        wind_10m_ms=wind_10m_ms,
        wind_from_deg=wind_from_deg,
        dead_fmc_pct=dead_fmc_pct,
    )
    wind_10m_ms = weather_merge.wind_10m_ms
    wind_from_deg = weather_merge.wind_from_deg
    dead_fmc_pct = weather_merge.dead_fmc_pct

    if prior_raw is None:
        use_spatial = fuel_map is not None or sector_fuels is not None
        fmc_use = dead_fmc_pct if dead_fmc_pct is not None else 7.0
        from_use = wind_from_deg if wind_from_deg is not None else 0.0
        if use_spatial:
            prior_raw = estimate_sector_ros_from_fuel_map(
                fuel_map,
                wind_10m_ms=wind_10m_ms,
                slope_deg=slope_deg,
                dead_fmc_pct=fmc_use,
                wind_from_deg=from_use,
                head_bearing_deg=head_bearing_deg,
                sector_fuels=sector_fuels,
                fallback_fuel_id=fuel_id,
                slope_deg_grid=slope_deg_grid,
            )
        else:
            prior_raw = estimate_sector_ros_physics(
                fuel=fuel_id,
                wind_10m_ms=wind_10m_ms,
                slope_deg=slope_deg,
                dead_fmc_pct=fmc_use,
                wind_from_deg=from_use,
                head_bearing_deg=head_bearing_deg,
            )
    # Always raw ratios first
    raw_ratio_block: dict[str, Any] | None = None
    if prior_raw.status == "estimated" and prior_raw.ros_head_m_min:
        cal: dict[str, Any] = {}
        raw_head = float(prior_raw.ros_head_m_min)
        if observed_ros_m_min is not None and observed_ros_m_min > 0:
            cal["ratio_physics_head_to_obs"] = round(raw_head / float(observed_ros_m_min), 4)
            cal["abs_err_head_m_min"] = round(abs(raw_head - float(observed_ros_m_min)), 4)
            cal["rel_err_head"] = round(
                abs(raw_head - float(observed_ros_m_min)) / float(observed_ros_m_min), 4
            )
            cal["observed_ros_m_min"] = float(observed_ros_m_min)
            cal["basis"] = "raw_pre_k"
        if vp_anchor_m_min is not None and vp_anchor_m_min > 0:
            cal["ratio_physics_head_to_vp"] = round(raw_head / float(vp_anchor_m_min), 4)
            cal["vp_anchor_m_min"] = float(vp_anchor_m_min)
            # Do not invent "confirmed" — only stamp confirmed source when caller says so
            if vp_status == "confirmed":
                cal["vp_source"] = "infocam_anchors.confirmed_only"
            elif vp_status:
                cal["vp_source"] = f"caller_vp_status:{vp_status}"
            else:
                cal["vp_source"] = "caller_vp_unspecified"
            cal["vp_status"] = vp_status
            cal["basis"] = "raw_pre_k"
        raw_ratio_block = cal or None

    prior = prior_raw
    recipe_dict: dict[str, Any] | None = None

    if fit_calibration or calibration_recipe is not None:
        from .calibration import (  # local import avoids cycles at module load
            CalibrationRecipe,
            apply_calibration,
            fit_sector_scale_factors,
            load_recipe,
        )

        recipe_obj: CalibrationRecipe | None = None
        if fit_calibration:
            weather = {
                "wind_10m_ms": wind_10m_ms,
                "wind_from_deg": wind_from_deg,
                "dead_fmc_pct": dead_fmc_pct,
                "slope_deg_used": slope_deg,
                "slope_source": "caller",
            }
            binding = dict(dem_binding or {})
            if dem_source and "dem_source" not in binding:
                binding["dem_source"] = dem_source
            recipe_obj = fit_sector_scale_factors(
                prior_raw,
                observed_ros_head_m_min=observed_ros_m_min,
                vp_anchor_m_min=vp_anchor_m_min,
                vp_status=vp_status,
                fire_id=fire_id,
                fuel_id=prior_raw.fuel_id or fuel_id,
                weather_scenario=weather,
                dem_binding=binding,
            )
        elif calibration_recipe is not None:
            if isinstance(calibration_recipe, (str, Path)):
                recipe_obj = load_recipe(calibration_recipe)
            elif isinstance(calibration_recipe, CalibrationRecipe):
                recipe_obj = calibration_recipe
            elif isinstance(calibration_recipe, dict):
                recipe_obj = CalibrationRecipe.from_dict(calibration_recipe)
            else:
                raise TypeError("calibration_recipe must be path, dict, or CalibrationRecipe")

        if recipe_obj is not None:
            prior = apply_calibration(
                prior_raw,
                recipe_obj,
                current_dem_source=dem_source,
                force=force_recipe,
            )
            recipe_dict = recipe_obj.to_dict()

    out = prior.to_dict()
    report_fuel_id = prior.fuel_id or fuel_id
    try:
        out["fuel"] = get_fuel(report_fuel_id).to_dict()
    except Exception:
        out["fuel"] = get_fuel(fuel_id).to_dict()
    out["calibration"] = raw_ratio_block  # always raw pre-k
    out["calibration_recipe"] = recipe_dict
    if recipe_dict is not None:
        out["physics_raw"] = prior_raw.to_dict()
    # Persist sector fuel assignment for audit (spatial or single)
    drivers = dict(out.get("drivers") or {})
    drivers["weather_drivers_merge"] = weather_merge.to_audit_dict()
    if weather_scenario is not None:
        if hasattr(weather_scenario, "to_dict"):
            wdict = weather_scenario.to_dict()
        elif isinstance(weather_scenario, dict):
            wdict = dict(weather_scenario)
        else:
            wdict = {"repr": str(weather_scenario)}
        drivers["weather_scenario"] = wdict
        out["weather_scenario"] = wdict
        # Honesty: merge flag wins (partial fills under observed → assumed True)
        out["weather_scenario_assumed"] = bool(weather_merge.weather_scenario_assumed)
        if weather_merge.weather_partially_filled_from_defaults:
            drivers["weather_partially_filled_from_defaults"] = True
            drivers["weather_fields_filled_from_defaults"] = list(
                weather_merge.fields_filled_from_defaults
            )
        if weather_merge.fields_missing_cleared:
            drivers["weather_fields_missing_cleared"] = list(
                weather_merge.fields_missing_cleared
            )
    else:
        # No WeatherScenario: library/caller wind is not station-observed
        drivers["library_wind_defaults_note"] = (
            "wind_10m_ms/wind_from_deg are caller or library engineering defaults "
            f"(library default {_LIBRARY_DEFAULT_WIND_MS} m/s / "
            f"{_LIBRARY_DEFAULT_WIND_FROM_DEG}°) — not AEMET/station observed "
            "unless caller documented otherwise"
        )
        drivers["weather_scenario_assumed"] = True
        out["weather_scenario_assumed"] = True
        out["weather_defaults_source"] = "library_or_caller_no_scenario"
    # Ensure top-level matches merge when scenario present
    if weather_scenario is not None:
        out["weather_scenario_assumed"] = bool(weather_merge.weather_scenario_assumed)
    out["drivers"] = drivers
    if "sector_fuels" in drivers:
        out["sector_fuels"] = drivers["sector_fuels"]
    out["disclaimer"] = (
        "physics_potential only — not a dispatch order; ABSTAIN if fuel/wind unknown; "
        "field_ops fusion must not treat this as GO without observed ROS gates; "
        "calibration ratios in key 'calibration' are always raw (pre-k)"
    )
    return out
