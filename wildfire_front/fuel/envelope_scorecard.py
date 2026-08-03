"""Tobarra multi-window envelope scorecard (F3.4 lite).

Validates hybrid envelope v3 structural properties and multi-scenario consistency.
Does **not** claim tactical skill vs official perimeters; Pablo pair is context only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .envelope import (
    PRODUCT_V3,
    compute_hybrid_envelope,
    envelope_decision_reasons,
)

SCHEMA = "wfd_envelope_scorecard_v1"
DEFAULT_OBS = 5.71
DEFAULT_VP = 7.0


@dataclass
class CheckResult:
    id: str
    status: str  # pass | fail | skip | info
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _pass(cid: str, detail: str, **evidence: Any) -> CheckResult:
    return CheckResult(cid, "pass", detail, evidence)


def _fail(cid: str, detail: str, **evidence: Any) -> CheckResult:
    return CheckResult(cid, "fail", detail, evidence)


def _info(cid: str, detail: str, **evidence: Any) -> CheckResult:
    return CheckResult(cid, "info", detail, evidence)


def check_envelope_structure(env: Mapping[str, Any]) -> list[CheckResult]:
    """Structural checks on a single envelope product."""
    out: list[CheckResult] = []
    if env.get("product") != PRODUCT_V3:
        out.append(
            _fail(
                "product_id",
                f"expected {PRODUCT_V3}",
                product=env.get("product"),
            )
        )
    else:
        out.append(_pass("product_id", PRODUCT_V3))

    if not env.get("not_tactical_dispatch"):
        out.append(_fail("not_dispatch", "missing not_tactical_dispatch flag"))
    else:
        out.append(_pass("not_dispatch", "not_tactical_dispatch=true"))

    if env.get("status") == "abstained":
        out.append(_fail("status", "envelope abstained", reason=env.get("reason")))
        return out
    out.append(_pass("status", str(env.get("status"))))

    envs = list(env.get("envelopes") or [])
    horizons = [int(e.get("horizon_min") or 0) for e in envs]
    if horizons != [15, 30, 60]:
        out.append(_fail("horizons", "expected 15/30/60", horizons=horizons))
    else:
        out.append(_pass("horizons", "15/30/60 present"))

    heads = [float(e.get("head_radius_m") or 0) for e in envs]
    if len(heads) == 3 and heads[0] < heads[1] < heads[2]:
        out.append(
            _pass(
                "head_monotonic",
                "head radii strictly increase with horizon",
                head_radii_m=heads,
            )
        )
    else:
        out.append(_fail("head_monotonic", "head radii not monotonic", head_radii_m=heads))

    for e in envs:
        h, f, r = (
            float(e.get("head_radius_m") or 0),
            float(e.get("flank_radius_m") or 0),
            float(e.get("rear_radius_m") or 0),
        )
        if not (h + 1e-9 >= f >= r - 1e-9):
            out.append(
                _fail(
                    f"sector_order_h{e.get('horizon_min')}",
                    "expected head>=flank>=rear",
                    head=h,
                    flank=f,
                    rear=r,
                )
            )
            break
    else:
        if envs:
            out.append(_pass("sector_order", "head>=flank>=rear at all horizons"))

    return out


def check_ensemble_honesty(env: Mapping[str, Any]) -> list[CheckResult]:
    """Hybrid flat head + physics_only labeling when ensemble enabled."""
    out: list[CheckResult] = []
    meta = env.get("ensemble_meta") or {}
    if not meta.get("enabled"):
        out.append(
            _info(
                "ensemble",
                "ensemble disabled",
                reason=meta.get("reason"),
            )
        )
        return out

    out.append(_pass("ensemble_enabled", "ensemble enabled", n=meta.get("n_hybrid_samples")))
    envs = list(env.get("envelopes") or [])
    if not envs:
        out.append(_fail("ensemble_rows", "no envelopes for ensemble check"))
        return out

    e0 = envs[0]
    hy = (e0.get("ensemble") or {}).get("head_radius_m") or {}
    if hy:
        p10, p50, p90 = float(hy.get("p10", -1)), float(hy.get("p50", -1)), float(hy.get("p90", -1))
        flat = abs(p90 - p10) < 1e-6
        locked = "head" in (meta.get("obs_locked_sectors") or [])
        if flat and locked:
            out.append(
                _pass(
                    "hybrid_head_flat",
                    "hybrid head p10=p50=p90 (obs-locked)",
                    p10=p10,
                    p90=p90,
                )
            )
        elif flat:
            out.append(
                _pass(
                    "hybrid_head_flat",
                    "hybrid head flat (obs-locked flag missing but widths zero)",
                    p10=p10,
                    p90=p90,
                )
            )
        else:
            out.append(
                _info(
                    "hybrid_head_width",
                    "hybrid head has width (unexpected with strong obs lock)",
                    p10=p10,
                    p90=p90,
                )
            )

    epo = e0.get("ensemble_physics_only") or {}
    if epo.get("not_product_p50") is True and epo.get("head_radius_m"):
        ph = epo["head_radius_m"]
        out.append(
            _pass(
                "physics_only_labeled",
                "physics_only band present and not_product_p50",
                p10=ph.get("p10"),
                p90=ph.get("p90"),
            )
        )
        if float(ph.get("p90", 0)) + 1e-9 >= float(ph.get("p10", 0)):
            out.append(_pass("physics_only_ordered", "physics_only p90>=p10"))
    else:
        out.append(_fail("physics_only_labeled", "missing ensemble_physics_only band"))

    return out


def check_ros_vs_anchors(
    env: Mapping[str, Any],
    *,
    observed_ros_m_min: float = DEFAULT_OBS,
    vp_m_min: float | None = DEFAULT_VP,
) -> list[CheckResult]:
    """Document ratios; do not invent pass/fail on mega-plan science KPI here."""
    out: list[CheckResult] = []
    sec = env.get("sector_ros_m_min") or {}
    head = sec.get("head")
    if head is None:
        out.append(_fail("head_ros", "missing sector head"))
        return out
    head_f = float(head)
    if abs(head_f - float(observed_ros_m_min)) < 0.05:
        out.append(
            _pass(
                "head_matches_obs",
                "hybrid head ≈ observed ROS (obs-locked path)",
                head=head_f,
                obs=observed_ros_m_min,
            )
        )
    else:
        out.append(
            _info(
                "head_vs_obs",
                "hybrid head differs from default obs",
                head=head_f,
                obs=observed_ros_m_min,
            )
        )
    if vp_m_min is not None and vp_m_min > 0:
        ratio = head_f / float(vp_m_min)
        out.append(
            _info(
                "head_vs_vp_anchor",
                "ratio hybrid_head/Vp (engineering, not GO gate)",
                ratio=round(ratio, 4),
                head=head_f,
                vp=vp_m_min,
            )
        )
    return out


def _recipe_fuel_id(calibration_recipe: Any | None, fallback: str) -> str:
    """Prefer fuel_id stored in recipe so apply_calibration does not refuse."""
    if calibration_recipe is None:
        return fallback
    if isinstance(calibration_recipe, dict):
        return str(calibration_recipe.get("fuel_id") or fallback)
    path = Path(calibration_recipe) if not hasattr(calibration_recipe, "fuel_id") else None
    if path is not None and path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return str(data.get("fuel_id") or fallback)
        except (OSError, json.JSONDecodeError, TypeError):
            return fallback
    fid = getattr(calibration_recipe, "fuel_id", None)
    return str(fid or fallback)


def build_multi_window_envelopes(
    *,
    observed_ros_m_min: float = DEFAULT_OBS,
    fuel_id: str = "MED_MAQUIS_LOW",
    wind_10m_ms: float = 4.4,
    wind_from_deg: float = 270.0,
    dead_fmc_pct: float = 7.0,
    slope_mean: float = 3.3,
    slope_p90: float = 6.9,
    dem_source: str | None = "copernicus_glo30",
    calibration_recipe: Any | None = None,
    with_ensemble: bool = True,
    weather_scenario_assumed: bool = True,
    weather_source: str | None = None,
) -> dict[str, Any]:
    """Several Tobarra-class scenario windows for consistency scoring."""
    windows: dict[str, Any] = {}
    fuel_id = _recipe_fuel_id(calibration_recipe, fuel_id)

    common = dict(
        observed_ros_m_min=observed_ros_m_min,
        fuel_id=fuel_id,
        wind_10m_ms=wind_10m_ms,
        wind_from_deg=wind_from_deg,
        dead_fmc_pct=dead_fmc_pct,
        dem_source=dem_source,
        calibration_recipe=calibration_recipe,
        weather_scenario_assumed=bool(weather_scenario_assumed),
        head_bearing_deg=(float(wind_from_deg) + 180.0) % 360.0,
        fire_id="tobarra_20240802",
    )
    if weather_source:
        # stamp only for audit on primary window after compute
        pass

    windows["w_slope_mean"] = compute_hybrid_envelope(
        None, slope_deg=slope_mean, with_ensemble=with_ensemble, **common
    )
    windows["w_slope_p90"] = compute_hybrid_envelope(
        None, slope_deg=slope_p90, with_ensemble=False, **common
    )
    windows["w_obs_age_10"] = compute_hybrid_envelope(
        None,
        slope_deg=slope_mean,
        obs_age_minutes=10.0,
        with_ensemble=False,
        **common,
    )
    windows["w_obs_age_60"] = compute_hybrid_envelope(
        None,
        slope_deg=slope_mean,
        obs_age_minutes=60.0,
        with_ensemble=False,
        **common,
    )
    return windows


def check_multi_window_consistency(windows: Mapping[str, Mapping[str, Any]]) -> list[CheckResult]:
    """Heads should stay obs-locked across slope/age windows when obs present."""
    out: list[CheckResult] = []
    heads: dict[str, float] = {}
    for name, env in windows.items():
        sec = env.get("sector_ros_m_min") or {}
        if sec.get("head") is not None:
            heads[name] = float(sec["head"])

    if len(heads) < 2:
        out.append(_fail("multi_window", "need ≥2 windows with head ROS"))
        return out

    vals = list(heads.values())
    spread = max(vals) - min(vals)
    if spread < 0.05:
        out.append(
            _pass(
                "multi_window_head_stable",
                "hybrid head stable across windows (obs-locked)",
                heads=heads,
                spread=round(spread, 4),
            )
        )
    else:
        out.append(
            _info(
                "multi_window_head_spread",
                "hybrid head varies across windows",
                heads=heads,
                spread=round(spread, 4),
            )
        )

    # flank may vary slightly with slope/physics
    flanks = {
        n: float((e.get("sector_ros_m_min") or {}).get("flank") or 0)
        for n, e in windows.items()
        if (e.get("sector_ros_m_min") or {}).get("flank") is not None
    }
    if flanks:
        out.append(
            _info(
                "multi_window_flank",
                "flank ROS by window (shape residual)",
                flanks={k: round(v, 4) for k, v in flanks.items()},
            )
        )
    return out


def check_pablo_perimeter_context(
    inventory_path: Path | None = None,
    *,
    envelope: Mapping[str, Any] | None = None,
) -> list[CheckResult]:
    """Context from Pablo multi-hour KMZ — NOT ROS validation."""
    out: list[CheckResult] = []
    if inventory_path is None or not Path(inventory_path).is_file():
        out.append(_info("pablo_inventory", "inventory not found — skip perimeter context"))
        return out

    inv = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
    growth = inv.get("area_growth") or {}
    kmz = inv.get("kmz_perimeters") or []
    out.append(
        _info(
            "pablo_pair",
            "ops perimeter multi-hour context (ha growth ≠ front ROS)",
            n_kmz=len(kmz),
            delta_ha=growth.get("delta_ha"),
            delta_minutes=growth.get("delta_minutes"),
            mean_ha_per_hour=growth.get("mean_ha_per_hour"),
            o2_status=inv.get("o2_status"),
        )
    )
    if envelope and (envelope.get("envelopes") or []):
        h60 = float((envelope["envelopes"][2] if len(envelope["envelopes"]) > 2 else {}).get("head_radius_m") or 0)
        out.append(
            _info(
                "envelope_vs_pablo_window",
                "60 min head radius is engineering extrusion, not fitted to Pablo polygons",
                head_radius_60_m=h60,
                pablo_delta_minutes=growth.get("delta_minutes"),
                honesty="do_not_equate_area_growth_with_envelope_radius",
            )
        )
    return out


def summarize_checks(checks: Sequence[CheckResult]) -> dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "skip": 0, "info": 0}
    for c in checks:
        counts[c.status] = counts.get(c.status, 0) + 1
    verdict = "PASS" if counts["fail"] == 0 else "FAIL"
    return {"verdict": verdict, "counts": counts}


def attach_envelope_to_decision_card(
    card: Mapping[str, Any] | dict[str, Any],
    envelope: Mapping[str, Any],
    *,
    max_reasons: int = 12,
) -> dict[str, Any]:
    """Append envelope reasons/disclaimers to a Decision Card dict (F3.5 lite).

    Does **not** change decision GO/HOLD/ABSTAIN or fusion weights.
    ML fusion flags untouched.
    """
    out = dict(card)
    reasons = list(out.get("reasons") or [])
    added = 0
    for r in envelope_decision_reasons(envelope):
        tag = f"envelope_v3:{r}"
        if tag not in reasons and added < max_reasons:
            reasons.append(tag)
            added += 1
    out["reasons"] = reasons

    disclaimers = list(out.get("disclaimers") or [])
    for d in (
        "Hybrid envelope 15/30/60 is extrapolated guidance, not official perimeter.",
        "Envelope ensemble head may be obs-locked (flat); physics_only band is diagnostic only.",
    ):
        if d not in disclaimers:
            disclaimers.append(d)
    out["disclaimers"] = disclaimers

    metrics = dict(out.get("metrics") or {})
    metrics["envelope_v3_hybrid"] = {
        "product": envelope.get("product"),
        "status": envelope.get("status"),
        "sector_ros_m_min": envelope.get("sector_ros_m_min"),
        "head_radius_15_m": (envelope.get("envelopes") or [{}])[0].get("head_radius_m"),
        "alpha_obs": envelope.get("alpha_obs"),
        "ensemble_enabled": (envelope.get("ensemble_meta") or {}).get("enabled"),
        "obs_locked_sectors": (envelope.get("ensemble_meta") or {}).get("obs_locked_sectors"),
        "not_tactical_dispatch": True,
        "fusion_weight": 0.0,
        "note": "Attached for audit only; does not drive fused confidence",
    }
    out["metrics"] = metrics

    sources = list(out.get("sources") or [])
    if not any(s.get("id") == "envelope_v3_hybrid" for s in sources):
        sources.append(
            {
                "id": "envelope_v3_hybrid",
                "available": envelope.get("status") not in (None, "abstained"),
                "weight": 0.0,
                "confidence": 0.0,
                "actionable": False,
                "abstained": envelope.get("status") == "abstained",
                "role": "short_horizon_guidance_audit",
                "source_type": "engineering_extrapolation",
                "metrics": metrics["envelope_v3_hybrid"],
            }
        )
    out["sources"] = sources

    audit = dict(out.get("audit") or {})
    audit["envelope_v3_attached"] = True
    audit["envelope_v3_product"] = envelope.get("product")
    out["audit"] = audit
    return out


def build_tobarra_envelope_scorecard(
    *,
    observed_ros_m_min: float = DEFAULT_OBS,
    vp_m_min: float | None = DEFAULT_VP,
    slope_mean: float = 3.3,
    slope_p90: float = 6.9,
    dem_source: str | None = "copernicus_glo30",
    calibration_recipe: Any | None = None,
    fuel_id: str | None = None,
    pablo_inventory: Path | str | None = None,
    decision_card: Mapping[str, Any] | None = None,
    with_ensemble: bool = True,
    weather_scenario: Mapping[str, Any] | None = None,
    wind_10m_ms: float | None = None,
    wind_from_deg: float | None = None,
    dead_fmc_pct: float | None = None,
) -> dict[str, Any]:
    """Full F3.4 scorecard + optional F3.5 card attachment.

    When *weather_scenario* is provided (or explicit wind/FMC), drivers are
    honesty-merged via ``merge_weather_drivers`` so AEMET/observed sources do
    not silently claim library wind as station truth.
    """
    from .weather import (
        WeatherScenario,
        merge_weather_drivers,
    )

    fid = fuel_id or _recipe_fuel_id(calibration_recipe, "MED_GRASS")

    ws_obj: WeatherScenario | Mapping[str, Any] | None = None
    if weather_scenario is not None:
        if isinstance(weather_scenario, WeatherScenario):
            ws_obj = weather_scenario
        else:
            ws_obj = dict(weather_scenario)
    wx = merge_weather_drivers(
        ws_obj,
        wind_10m_ms=wind_10m_ms if wind_10m_ms is not None else 4.4,
        wind_from_deg=wind_from_deg if wind_from_deg is not None else 270.0,
        dead_fmc_pct=dead_fmc_pct if dead_fmc_pct is not None else 7.0,
        fill_library_when_missing=True,
    )
    use_wind = float(wx.wind_10m_ms) if wx.wind_10m_ms is not None else 4.4
    use_from = float(wx.wind_from_deg) if wx.wind_from_deg is not None else 270.0
    use_fmc = float(wx.dead_fmc_pct) if wx.dead_fmc_pct is not None else 7.0

    windows = build_multi_window_envelopes(
        observed_ros_m_min=observed_ros_m_min,
        fuel_id=fid,
        wind_10m_ms=use_wind,
        wind_from_deg=use_from,
        dead_fmc_pct=use_fmc,
        slope_mean=slope_mean,
        slope_p90=slope_p90,
        dem_source=dem_source,
        calibration_recipe=calibration_recipe,
        with_ensemble=with_ensemble,
        weather_scenario_assumed=bool(wx.weather_scenario_assumed),
        weather_source=wx.source,
    )
    primary = windows["w_slope_mean"]
    primary["weather_drivers_merge"] = wx.to_audit_dict()
    if weather_scenario is not None:
        if isinstance(weather_scenario, WeatherScenario):
            primary["weather_scenario"] = weather_scenario.to_dict()
        else:
            primary["weather_scenario"] = dict(weather_scenario)

    checks: list[CheckResult] = []
    checks.extend(check_envelope_structure(primary))
    checks.extend(check_ensemble_honesty(primary))
    checks.extend(
        check_ros_vs_anchors(
            primary, observed_ros_m_min=observed_ros_m_min, vp_m_min=vp_m_min
        )
    )
    checks.extend(check_multi_window_consistency(windows))
    inv = Path(pablo_inventory) if pablo_inventory else None
    checks.extend(check_pablo_perimeter_context(inv, envelope=primary))

    # Weather honesty stamp
    if weather_scenario is not None:
        src = wx.source
        if src in {"aemet", "observed"} and wx.weather_scenario_assumed and wx.fields_filled_from_defaults:
            checks.append(
                _info(
                    "weather_partial_station",
                    f"source={src} but library fill on {wx.fields_filled_from_defaults}",
                    merge=wx.to_audit_dict(),
                )
            )
        elif src in {"aemet", "observed"} and not wx.weather_scenario_assumed:
            checks.append(
                _pass(
                    "weather_station_clean",
                    f"source={src} without library fill",
                    wind_10m_ms=wx.wind_10m_ms,
                )
            )
        else:
            checks.append(
                _info(
                    "weather_source",
                    f"source={src} assumed={wx.weather_scenario_assumed}",
                    merge=wx.to_audit_dict(),
                )
            )
    else:
        checks.append(
            _info(
                "weather_default_assumed",
                "no weather_scenario; library/CLI drivers assumed",
                wind_10m_ms=use_wind,
            )
        )

    summary = summarize_checks(checks)
    card_out = None
    if decision_card is not None:
        card_out = attach_envelope_to_decision_card(decision_card, primary)

    return {
        "schema": SCHEMA,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fire_id": "tobarra_20240802",
        "product": PRODUCT_V3,
        "verdict": summary["verdict"],
        "counts": summary["counts"],
        "checks": [c.to_dict() for c in checks],
        "primary_window": "w_slope_mean",
        "weather_drivers_merge": wx.to_audit_dict(),
        "windows_summary": {
            name: {
                "status": env.get("status"),
                "sector_ros_m_min": env.get("sector_ros_m_min"),
                "head_radius_15_m": (env.get("envelopes") or [{}])[0].get("head_radius_m"),
                "alpha_obs": env.get("alpha_obs"),
                "ensemble_enabled": (env.get("ensemble_meta") or {}).get("enabled"),
            }
            for name, env in windows.items()
        },
        "primary_envelope_compact": {
            "status": primary.get("status"),
            "sector_ros_m_min": primary.get("sector_ros_m_min"),
            "envelopes": primary.get("envelopes"),
            "ensemble_meta": primary.get("ensemble_meta"),
            "not_tactical_dispatch": True,
            "weather_scenario_assumed": primary.get("weather_scenario_assumed"),
        },
        "decision_card_attached": card_out is not None,
        "decision_card": card_out,
        "honesty": [
            "Scorecard is engineering QA of envelope product, not tactical validation",
            "Pablo ha growth is not front ROS",
            "Decision Card attach uses weight=0 (audit only)",
            "field_ops ML fusion must remain OFF",
            "AEMET/observed weather uses merge_weather_drivers honesty rails",
        ],
    }
