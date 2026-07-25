"""Convert StageSequence → FrontObservation list + optional front_dynamics smoke."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from wildfire_front.front_dynamics import run_front_dynamics
from wildfire_front.models import FrontObservation
from wildfire_front.scientific_ops import MAX_PLAUSIBLE_SPEED_M_MIN

from .geometry import exterior_rings
from .pipeline import StageSequence
from .schemas import HONESTY_LIMITATIONS, OPS_METHOD


def stages_to_observations(
    seq: StageSequence,
    *,
    event_id: str = "psb_synthetic",
    sensor_id: str = "psb_engine",
    resolution_m: float = 10.0,
    main_front_only: bool = False,
    base_time: datetime | None = None,
) -> list[FrontObservation]:
    """KD13 M5: emit all retained exteriors as components unless main_front_only."""
    base = base_time or datetime(2024, 6, 6, tzinfo=UTC)
    out: list[FrontObservation] = []
    for s in seq.stages:
        rings = exterior_rings(s.geom_metric, min_points=8)
        if not rings:
            continue
        if main_front_only:
            rings = [max(rings, key=lambda r: _ring_area_proxy(r))]
        components = tuple(tuple((float(x), float(y)) for x, y in ring) for ring in rings)
        # Ensure ≥4 points each
        components = tuple(c for c in components if len(c) >= 4)
        if not components:
            continue
        obs = FrontObservation(
            observation_id=f"psb_stage_{s.stage_index:03d}",
            event_id=event_id,
            sensor_id=sensor_id,
            time_s=float(s.time_s),
            observed_at=(base + timedelta(seconds=float(s.time_s))).isoformat(),
            components=components,
            estimated_error_m=max(resolution_m, 5.0),
            status="observed",
            crs=seq.config.metric_crs,
            coordinate_system="projected_metric",
            resolution_m=float(resolution_m),
            method="synthetic_progressive_burn",
            limitations=HONESTY_LIMITATIONS + ("dt_assumed",),
        )
        obs.validate()
        out.append(obs)
    return out


def _ring_area_proxy(ring: list[tuple[float, float]]) -> float:
    # shoelace absolute
    if len(ring) < 3:
        return 0.0
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def run_psb_front_dynamics(
    seq: StageSequence,
    *,
    resolution_m: float = 10.0,
    event_id: str = "psb_synthetic",
) -> dict[str, Any]:
    """Adapter contract (ISS-004 / design):

    - projected_metric EPSG:6933, resolution_m set
    - enable_coreg=False
    - force primary_method ∈ {area_isotropic, equiv_radius}
    - quality grade ≤ B / synthetic_research
    """
    observations = stages_to_observations(seq, event_id=event_id, resolution_m=resolution_m)
    if len(observations) < 2:
        return {
            "status": "SKIP",
            "reason": "need_at_least_2_observations",
            "ops_method": OPS_METHOD,
            "vp_tactical": None,
            "pairs": [],
        }

    result = run_front_dynamics(observations, enable_coreg=False)
    pairs_out: list[dict[str, Any]] = []
    for p in result.pairs:
        # Prefer bulk estimators only (force off normal_ray primary)
        primary = "abstained"
        ros = None
        if p.ros_area_m_min is not None and 0 <= p.ros_area_m_min <= MAX_PLAUSIBLE_SPEED_M_MIN:
            primary = "area_isotropic"
            ros = p.ros_area_m_min
        elif (
            p.ros_equiv_radius_m_min is not None
            and 0 <= p.ros_equiv_radius_m_min <= MAX_PLAUSIBLE_SPEED_M_MIN
        ):
            primary = "equiv_radius"
            ros = p.ros_equiv_radius_m_min

        grade = p.pair_quality or "C"
        # Cap quality: never operational A on synthetic
        if grade == "A":
            grade = "B"
        pairs_out.append(
            {
                "time_start_s": p.time_start_s,
                "time_end_s": p.time_end_s,
                "ros_area_m_min": p.ros_area_m_min,
                "ros_equiv_radius_m_min": p.ros_equiv_radius_m_min,
                "ros_primary_m_min": ros,
                "primary_method": primary,
                "pair_quality": grade,
                "structural_grade": "synthetic_research",
                "label": "proxy_synthetic",
            }
        )

    return {
        "status": "synthetic_proxy_only",
        "ops_method": OPS_METHOD,
        "enable_coreg": False,
        "vp_tactical": None,
        "not_real_lwir": True,
        "proxy_synthetic": True,
        "n_observations": len(observations),
        "pairs": pairs_out,
        # Never embed raw FD summary as operational (no unfiltered primary_ros as ops).
        "summary": _sanitize_psb_fd_summary(result.summary if result.summary else {}),
        "limitations": list(HONESTY_LIMITATIONS),
    }


def _sanitize_psb_fd_summary(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Strip/rewrite FD summary so PSB never exposes ops-looking primary_ros.

    - ``vp_tactical`` always null
    - grade capped (A → B)
    - ROS only under explicit proxy_* keys
    - synthetic / not_ops flags always set
    """
    raw = raw or {}
    grade = raw.get("structural_grade")
    if grade == "A":
        grade = "B"
    if grade is None:
        grade = "synthetic_research"
    proxy_ros = raw.get("primary_ros_m_min")
    return {
        "status": "synthetic_proxy_only",
        "vp_tactical": None,
        "proxy_synthetic": True,
        "not_ops": True,
        "not_real_lwir": True,
        "not_tactical_dispatch": True,
        "n_pairs": raw.get("n_pairs"),
        "structural_grade_capped": grade,
        "structural_label_es": "proxy sintético — no operativo",
        "primary_methods_used": raw.get("primary_methods_used"),
        "primary_ros_n": raw.get("primary_ros_n"),
        # Explicit proxy naming — never primary_ros_m_min as ops field
        "proxy_ros_m_min": proxy_ros,
        "proxy_ros_p25_m_min": raw.get("primary_ros_p25_m_min"),
        "proxy_ros_p75_m_min": raw.get("primary_ros_p75_m_min"),
        "label": "proxy_synthetic",
        "note": (
            "PSB sanitized FD summary: geometric proxy only; "
            "not operational ROS; not tactical Vp; not dispatch."
        ),
    }


def wrap_sector_ros_synthetic(sector: dict[str, Any]) -> dict[str, Any]:
    """ISS-011: override method string + synthetic flag."""
    out = dict(sector)
    out["method"] = "bulk_ros_quartile_split_synthetic"
    out["synthetic"] = True
    out["not_official_perimeter"] = True
    return out
