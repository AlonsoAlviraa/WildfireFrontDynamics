"""ROS sector scale-factor calibration (Cell2Fire-style engineering).

Fits k factors so calibrated physics can match observed ROS / confirmed Vp.
Never overwrites official anchors. Raw metrics always retained for honesty.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from .rothermel_lite import PhysicsPriorResult

K_MIN = 0.05
K_MAX = 5.0
_ROS_CAP = 120.0


class CalibrationRefusedError(Exception):
    """Fit or apply refused. CLI maps to exit code 4."""

    def __init__(
        self,
        status: str,
        details: dict[str, Any] | None = None,
        message: str = "",
    ):
        self.status = status
        self.details = details or {}
        super().__init__(message or status)


@dataclass
class CalibrationRecipe:
    schema: str
    recipe_id: str
    version: int
    fire_id: str
    fuel_id: str
    mode: str
    dem_binding: dict[str, Any]
    weather_scenario: dict[str, Any]
    targets: dict[str, Any]
    raw_physics: dict[str, Any]
    factors: dict[str, float]
    calibrated_physics: dict[str, Any]
    metrics: dict[str, Any]
    product_claim: str
    no_tactical_dispatch: bool
    honesty_notes: list[str]
    literature_refs: list[str]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CalibrationRecipe:
        required = (
            "schema",
            "recipe_id",
            "fire_id",
            "fuel_id",
            "mode",
            "factors",
            "raw_physics",
        )
        for k in required:
            if k not in d:
                raise ValueError(f"recipe missing {k}")
        factors = {str(k): float(v) for k, v in (d.get("factors") or {}).items()}
        return cls(
            schema=str(d.get("schema", "ros_calibration_recipe_v1")),
            recipe_id=str(d["recipe_id"]),
            version=int(d.get("version", 1)),
            fire_id=str(d["fire_id"]),
            fuel_id=str(d["fuel_id"]),
            mode=str(d.get("mode", "uniform_from_head")),
            dem_binding=dict(d.get("dem_binding") or {}),
            weather_scenario=dict(d.get("weather_scenario") or {}),
            targets=dict(d.get("targets") or {}),
            raw_physics=dict(d["raw_physics"]),
            factors=factors,
            calibrated_physics=dict(d.get("calibrated_physics") or {}),
            metrics=dict(d.get("metrics") or {}),
            product_claim=str(d.get("product_claim", "physics_potential_calibrated")),
            no_tactical_dispatch=bool(d.get("no_tactical_dispatch", True)),
            honesty_notes=list(d.get("honesty_notes") or []),
            literature_refs=list(d.get("literature_refs") or []),
            created_at=str(d.get("created_at") or datetime.now(UTC).isoformat()),
        )


def residual_metrics(
    *,
    ros_head_raw: float,
    ros_head_cal: float | None,
    observed_ros_head_m_min: float | None,
    vp_anchor_m_min: float | None,
) -> dict[str, Any]:
    """Split raw vs cal residual metrics (honesty)."""
    out: dict[str, Any] = {
        "honesty": ("cal_err~0 after fit-to-obs is by construction; raw metrics are the model gap")
    }
    raw = float(ros_head_raw)
    if observed_ros_head_m_min is not None and observed_ros_head_m_min > 0:
        obs = float(observed_ros_head_m_min)
        out["raw_abs_err_head_vs_obs_m_min"] = round(abs(raw - obs), 4)
        out["raw_rel_err_head_vs_obs"] = round(abs(raw - obs) / obs, 4)
        out["ratio_raw_head_to_obs"] = round(raw / obs, 4)
        out["kpi_raw_rel_err_lt_0_5"] = bool(out["raw_rel_err_head_vs_obs"] < 0.5)
        if ros_head_cal is not None:
            cal = float(ros_head_cal)
            out["cal_abs_err_head_vs_obs_m_min"] = round(abs(cal - obs), 4)
            out["cal_rel_err_head_vs_obs"] = round(abs(cal - obs) / obs, 4)
            out["kpi_cal_engineering_ok"] = bool(out["cal_rel_err_head_vs_obs"] < 0.05)
    if vp_anchor_m_min is not None and vp_anchor_m_min > 0:
        vp = float(vp_anchor_m_min)
        out["raw_rel_err_head_vs_vp"] = round(abs(raw - vp) / vp, 4)
        out["ratio_raw_head_to_vp"] = round(raw / vp, 4)
        if ros_head_cal is not None:
            cal = float(ros_head_cal)
            out["cal_rel_err_head_vs_vp"] = round(abs(cal - vp) / vp, 4)
    return out


def _raw_dict_from_prior(raw: PhysicsPriorResult | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, PhysicsPriorResult):
        return {
            "method": raw.method,
            "status": raw.status,
            "fuel_id": raw.fuel_id,
            "ros_head_m_min": raw.ros_head_m_min,
            "ros_flank_m_min": raw.ros_flank_m_min,
            "ros_rear_m_min": raw.ros_rear_m_min,
            "ros_primary_m_min": raw.ros_primary_m_min,
        }
    return {
        "method": raw.get("method"),
        "status": raw.get("status"),
        "fuel_id": raw.get("fuel_id"),
        "ros_head_m_min": raw.get("ros_head_m_min"),
        "ros_flank_m_min": raw.get("ros_flank_m_min"),
        "ros_rear_m_min": raw.get("ros_rear_m_min"),
        "ros_primary_m_min": raw.get("ros_primary_m_min"),
    }


def _resolve_fit_target(
    *,
    observed_ros_head_m_min: float | None,
    vp_anchor_m_min: float | None,
    vp_status: str | None,
    fit_target: str,
    blend_w_obs: float,
) -> tuple[float, str]:
    ft = fit_target
    if ft == "observed_ros_head":
        if observed_ros_head_m_min is None or observed_ros_head_m_min <= 0:
            raise CalibrationRefusedError(
                "calibration_refused_missing_obs",
                message="fit_target=observed_ros_head requires positive observed ROS",
            )
        return float(observed_ros_head_m_min), "observed_ros_head"
    if ft == "vp_anchor":
        if vp_status != "confirmed" or vp_anchor_m_min is None or vp_anchor_m_min <= 0:
            raise CalibrationRefusedError(
                "calibration_refused_vp_not_confirmed",
                message="fit_target=vp_anchor requires confirmed positive Vp",
            )
        return float(vp_anchor_m_min), "vp_anchor"
    if ft == "blend":
        if (
            observed_ros_head_m_min is None
            or observed_ros_head_m_min <= 0
            or vp_status != "confirmed"
            or vp_anchor_m_min is None
            or vp_anchor_m_min <= 0
        ):
            raise CalibrationRefusedError(
                "calibration_refused_blend_inputs",
                message="blend requires obs and confirmed Vp",
            )
        w = float(np.clip(blend_w_obs, 0.0, 1.0))
        t = w * float(observed_ros_head_m_min) + (1.0 - w) * float(vp_anchor_m_min)
        return t, "blend"
    raise CalibrationRefusedError(
        "calibration_refused_unknown_fit_target",
        details={"fit_target": fit_target},
    )


def fit_sector_scale_factors(
    raw: PhysicsPriorResult | dict[str, Any],
    *,
    observed_ros_head_m_min: float | None,
    vp_anchor_m_min: float | None = None,
    vp_status: str | None = None,
    fit_target: str = "observed_ros_head",
    blend_w_obs: float = 0.7,
    mode: str = "uniform_from_head",
    fire_id: str = "tobarra_20240802",
    fuel_id: str | None = None,
    weather_scenario: dict[str, Any] | None = None,
    dem_binding: dict[str, Any] | None = None,
) -> CalibrationRecipe:
    """Compute k factors from raw physics prior."""
    rd = _raw_dict_from_prior(raw)
    head = rd.get("ros_head_m_min")
    if rd.get("status") == "abstained" or head is None or float(head) <= 0:
        raise CalibrationRefusedError(
            "calibration_refused_no_raw_head",
            details=rd,
            message="raw physics head missing or abstained",
        )
    head_f = float(head)
    target, target_label = _resolve_fit_target(
        observed_ros_head_m_min=observed_ros_head_m_min,
        vp_anchor_m_min=vp_anchor_m_min,
        vp_status=vp_status,
        fit_target=fit_target,
        blend_w_obs=blend_w_obs,
    )
    k = target / head_f
    if not (K_MIN <= k <= K_MAX):
        raise CalibrationRefusedError(
            "calibration_refused_extreme_k",
            details={"k_head": k, "raw_head": head_f, "target": target},
            message=f"k_head={k:.4f} outside [{K_MIN}, {K_MAX}]",
        )

    if mode not in {"uniform_from_head", "head_only", "per_sector"}:
        raise CalibrationRefusedError(
            "calibration_refused_unknown_mode",
            details={"mode": mode},
        )

    mode_effective = mode
    honesty_extra: list[str] = []
    if mode == "uniform_from_head":
        factors = {"k_head": round(k, 6), "k_flank": round(k, 6), "k_rear": round(k, 6)}
    elif mode == "head_only":
        factors = {"k_head": round(k, 6), "k_flank": 1.0, "k_rear": 1.0}
    else:
        # per_sector without flank/rear targets falls back to uniform (no silent mode)
        factors = {"k_head": round(k, 6), "k_flank": round(k, 6), "k_rear": round(k, 6)}
        mode_effective = "uniform_from_head"
        honesty_extra.append(
            "mode_effective=uniform_from_head (per_sector requested without "
            "flank/rear targets; same k applied to all sectors)"
        )

    flank = float(rd.get("ros_flank_m_min") or 0.0)
    rear = float(rd.get("ros_rear_m_min") or 0.0)
    cal_head = float(np.clip(factors["k_head"] * head_f, 0.0, _ROS_CAP))
    cal_flank = float(np.clip(factors["k_flank"] * flank, 0.0, _ROS_CAP))
    cal_rear = float(np.clip(factors["k_rear"] * rear, 0.0, _ROS_CAP))

    fid = fuel_id or str(rd.get("fuel_id") or "UNKNOWN")
    metrics = residual_metrics(
        ros_head_raw=head_f,
        ros_head_cal=cal_head,
        observed_ros_head_m_min=observed_ros_head_m_min,
        vp_anchor_m_min=vp_anchor_m_min if vp_status == "confirmed" else None,
    )
    if mode_effective != mode:
        metrics["mode_requested"] = mode
        metrics["mode_effective"] = mode_effective

    return CalibrationRecipe(
        schema="ros_calibration_recipe_v1",
        recipe_id=f"{fire_id}_{fid.lower()}_v1",
        version=1,
        fire_id=fire_id,
        fuel_id=fid,
        mode=mode_effective,
        dem_binding=dict(dem_binding or {}),
        weather_scenario=dict(weather_scenario or {}),
        targets={
            "observed_ros_head_m_min": observed_ros_head_m_min,
            "vp_anchor_m_min": vp_anchor_m_min,
            "vp_status": vp_status,
            "fit_target": target_label,
            "fit_target_value": target,
            "blend_w_obs": blend_w_obs if target_label == "blend" else None,
        },
        raw_physics={
            "method": rd.get("method"),
            "ros_head_m_min": head_f,
            "ros_flank_m_min": flank,
            "ros_rear_m_min": rear,
        },
        factors=factors,
        calibrated_physics={
            "ros_head_m_min": round(cal_head, 4),
            "ros_flank_m_min": round(cal_flank, 4),
            "ros_rear_m_min": round(cal_rear, 4),
        },
        metrics=metrics,
        product_claim="physics_potential_calibrated",
        no_tactical_dispatch=True,
        honesty_notes=[
            "Factors scale engineering physics potential only; do not overwrite INFOCAM Vp",
            "Single-scenario fit; not multi-IF LOFO validated",
            "Re-fit required after dem_source / DEM fingerprint or fuel_id change",
            "cal_rel_err_head_vs_obs ≈ 0 does not mean raw physics meets mega-plan KPI",
            "field_ops must not treat calibrated physics as dispatch GO",
            *honesty_extra,
        ],
        literature_refs=[
            "kim_2025_cell2fire / Cell2Fire HROS-BROS-FROS adjustment factors",
            "cardil_2023_ops_ros_bias protocol (report bias, do not silent-fix obs)",
        ],
        created_at=datetime.now(UTC).isoformat(),
    )


def apply_calibration(
    raw: PhysicsPriorResult,
    recipe: CalibrationRecipe | dict[str, Any],
    *,
    current_dem_source: str | None = None,
    force: bool = False,
) -> PhysicsPriorResult:
    """Scale sectors by recipe factors; preserve raw; label calibrated."""
    if isinstance(recipe, dict):
        recipe = CalibrationRecipe.from_dict(recipe)

    if raw.status == "abstained":
        return raw

    if not force:
        bound = (recipe.dem_binding or {}).get("dem_source")
        if bound is not None and current_dem_source is None:
            raise CalibrationRefusedError(
                "dem_source_unspecified",
                details={
                    "recipe_dem_source": bound,
                    "current_dem_source": None,
                },
                message=(
                    "recipe bound to dem_source but current_dem_source is None; "
                    "pass dem_source or force=True"
                ),
            )
        if (
            current_dem_source is not None
            and bound is not None
            and str(current_dem_source) != str(bound)
        ):
            raise CalibrationRefusedError(
                "dem_source_mismatch",
                details={
                    "recipe_dem_source": bound,
                    "current_dem_source": current_dem_source,
                },
            )
        if recipe.fuel_id and raw.fuel_id and recipe.fuel_id != raw.fuel_id:
            raise CalibrationRefusedError(
                "fuel_id_mismatch",
                details={"recipe_fuel": recipe.fuel_id, "raw_fuel": raw.fuel_id},
            )

    kh = float(recipe.factors.get("k_head", 1.0))
    kf = float(recipe.factors.get("k_flank", kh))
    kr = float(recipe.factors.get("k_rear", kh))

    def _sc(v: float | None, k: float) -> float | None:
        if v is None:
            return None
        return round(float(np.clip(float(v) * k, 0.0, _ROS_CAP)), 4)

    band = None
    if raw.band_p10_p90 and "head_m_min" in raw.band_p10_p90:
        lo, hi = raw.band_p10_p90["head_m_min"]
        band = {
            "head_m_min": [
                round(float(lo) * kh, 4),
                round(float(hi) * kh, 4),
            ]
        }

    return PhysicsPriorResult(
        status=raw.status,
        method=raw.method + "+calibrated",
        fuel_id=raw.fuel_id,
        ros_head_m_min=_sc(raw.ros_head_m_min, kh),
        ros_flank_m_min=_sc(raw.ros_flank_m_min, kf),
        ros_rear_m_min=_sc(raw.ros_rear_m_min, kr),
        ros_primary_m_min=_sc(raw.ros_primary_m_min, kh),
        band_p10_p90=band if band is not None else raw.band_p10_p90,
        drivers=dict(raw.drivers or {}),
        reasons=list(raw.reasons or []),
        product_claim="physics_potential_calibrated",
        no_tactical_dispatch=True,
        calibration_applied=True,
        calibration_recipe_id=recipe.recipe_id,
        k_factors={"k_head": kh, "k_flank": kf, "k_rear": kr},
        ros_head_raw_m_min=raw.ros_head_m_min,
        ros_flank_raw_m_min=raw.ros_flank_m_min,
        ros_rear_raw_m_min=raw.ros_rear_m_min,
    )


def load_recipe(path: Path | str) -> CalibrationRecipe:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return CalibrationRecipe.from_dict(data)


def save_recipe(recipe: CalibrationRecipe, path: Path | str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(recipe.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return p
