"""Structural fire-front dynamics engine (observatory-grade).

This is a **level-up** over pairwise normal-ray speed alone:

1. **Main-front geometry** (already cleaned upstream).
2. **Residual coregistration** between consecutive frames (translation that
   maximises mask IoU) so georef drift does not fake 400 m/min ROS.
3. **Dual ROS estimators**
   - *normal_ray* — local outward advance (existing geometry_speed).
   - *area_isotropic* — dA / (P·dt) (standard fire-science bulk ROS).
   - *equiv_radius* — d(√(A/π)) / dt.
4. **Fusion + quality** — primary ROS for operators with explicit method.
5. **INFOCAM calibration report** — raw vs operational anchor, never silent.

References (methods, not code copy):
- Rothermel bulk rate concepts; equivalent-radius growth.
- Conservative normal-ray tracking already in geometry_speed.py.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from .geometry_speed import (
    component_centroid,
    estimate_geometry_speeds,
    signed_area,
    summarize_geometry_speeds,
)
from .models import FrontObservation, GeometrySpeedConfig, GeometrySpeedResult, Line, MultiLine
from .scientific_ops import (
    MAX_PLAUSIBLE_SPEED_M_MIN,
    MIN_PLAUSIBLE_DT_S,
    OperationalReference,
    build_operational_metrics,
    component_area_m2,
    observation_area_ha,
    observation_area_m2,
)


def perimeter_m(component: Line) -> float:
    pts = np.asarray(component, dtype=float)
    if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    if len(pts) < 2:
        return 0.0
    closed = np.vstack((pts, pts[0]))
    return float(np.sum(np.linalg.norm(np.diff(closed, axis=0), axis=1)))


def total_perimeter_m(obs: FrontObservation) -> float:
    return float(sum(perimeter_m(c) for c in obs.components))


def _shift_component(component: Line, dx: float, dy: float) -> Line:
    return tuple((float(x + dx), float(y + dy)) for x, y in component)


def _shift_observation(obs: FrontObservation, dx: float, dy: float) -> FrontObservation:
    comps = tuple(_shift_component(c, dx, dy) for c in obs.components)
    return FrontObservation(
        observation_id=obs.observation_id,
        event_id=obs.event_id,
        sensor_id=obs.sensor_id,
        time_s=obs.time_s,
        observed_at=obs.observed_at,
        components=comps,
        estimated_error_m=obs.estimated_error_m,
        status=obs.status,
        truth_components=obs.truth_components,
        crs=obs.crs,
        coordinate_system=obs.coordinate_system,
        resolution_m=obs.resolution_m,
        source_uri=obs.source_uri,
        source_sha256=obs.source_sha256,
        method=obs.method + "+coreg_shift",
        limitations=obs.limitations + ("coregistration_translation_applied",),
    )


def _rasterize_main(
    obs: FrontObservation,
    origin: tuple[float, float],
    resolution: float,
    shape: tuple[int, int],
) -> np.ndarray:
    """Coarse raster of main component(s) for correlation (point-in-grid)."""
    h, w = shape
    grid = np.zeros((h, w), dtype=np.uint8)
    ox, oy = origin
    # Fill bounding boxes of components as approximation (fast structural coreg)
    for comp in obs.components:
        pts = np.asarray(comp, dtype=float)
        if len(pts) < 3:
            continue
        min_x, min_y = pts.min(axis=0)
        max_x, max_y = pts.max(axis=0)
        c0 = int(math.floor((min_x - ox) / resolution))
        c1 = int(math.ceil((max_x - ox) / resolution))
        r0 = int(math.floor((min_y - oy) / resolution))
        r1 = int(math.ceil((max_y - oy) / resolution))
        c0, c1 = max(0, c0), min(w, c1)
        r0, r1 = max(0, r0), min(h, r1)
        if c1 > c0 and r1 > r0:
            # denser: stamp polygon via edge samples
            for x, y in pts:
                cc = int((x - ox) / resolution)
                rr = int((y - oy) / resolution)
                if 0 <= rr < h and 0 <= cc < w:
                    grid[rr, cc] = 1
            grid[r0:r1, c0:c1] = np.maximum(
                grid[r0:r1, c0:c1],
                0,  # keep points; fill bbox lightly
            )
            # soft bbox fill at 0.3 for area mass
            sub = grid[r0:r1, c0:c1]
            # mark centroid neighborhood
            cx, cy = component_centroid(comp)
            cc = int((cx - ox) / resolution)
            rr = int((cy - oy) / resolution)
            for dr in range(-3, 4):
                for dc in range(-3, 4):
                    r2, c2 = rr + dr, cc + dc
                    if 0 <= r2 < h and 0 <= c2 < w:
                        grid[r2, c2] = 1
    return grid


def estimate_coreg_translation(
    previous: FrontObservation,
    current: FrontObservation,
    *,
    resolution_m: float = 4.0,
    max_shift_m: float = 60.0,
) -> dict[str, float]:
    """Estimate translation (dx, dy) to apply to *current* to align with previous.

    Maximises coarse IoU of rasterised fronts. Structural fix for residual
    georeferencing drift between consecutive drone orthos.
    """
    all_pts = []
    for obs in (previous, current):
        for c in obs.components:
            all_pts.append(np.asarray(c, dtype=float))
    if not all_pts:
        return {"dx_m": 0.0, "dy_m": 0.0, "peak_iou": 0.0, "applied": 0.0}
    stack = np.vstack(all_pts)
    pad = max_shift_m + resolution_m * 2
    min_x, min_y = stack.min(axis=0) - pad
    max_x, max_y = stack.max(axis=0) + pad
    w = max(8, int(math.ceil((max_x - min_x) / resolution_m)))
    h = max(8, int(math.ceil((max_y - min_y) / resolution_m)))
    # Cap grid size for speed
    while w * h > 250_000 and resolution_m < 32:
        resolution_m *= 2
        w = max(8, int(math.ceil((max_x - min_x) / resolution_m)))
        h = max(8, int(math.ceil((max_y - min_y) / resolution_m)))

    origin = (float(min_x), float(min_y))
    a = _rasterize_main(previous, origin, resolution_m, (h, w))
    b = _rasterize_main(current, origin, resolution_m, (h, w))
    if a.sum() == 0 or b.sum() == 0:
        return {"dx_m": 0.0, "dy_m": 0.0, "peak_iou": 0.0, "applied": 0.0, "iou0": 0.0}

    def _iou_at(dx: int, dy: int) -> float:
        shifted = np.roll(np.roll(b, dy, axis=0), dx, axis=1)
        if dy > 0:
            shifted[:dy, :] = 0
        elif dy < 0:
            shifted[dy:, :] = 0
        if dx > 0:
            shifted[:, :dx] = 0
        elif dx < 0:
            shifted[:, dx:] = 0
        inter = np.logical_and(a, shifted).sum()
        union = np.logical_or(a, shifted).sum()
        return float(inter) / float(union) if union else 0.0

    iou0 = _iou_at(0, 0)
    max_pix = int(math.ceil(max_shift_m / resolution_m))
    best_iou = iou0
    best = (0, 0)
    # Coarse search every 2 pixels then refine
    step = 2 if max_pix > 6 else 1
    for dy in range(-max_pix, max_pix + 1, step):
        for dx in range(-max_pix, max_pix + 1, step):
            iou = _iou_at(dx, dy)
            if iou > best_iou:
                best_iou = iou
                best = (dx, dy)

    # Local refine
    cx, cy = best
    for dy in range(cy - step, cy + step + 1):
        for dx in range(cx - step, cx + step + 1):
            if abs(dx) > max_pix or abs(dy) > max_pix:
                continue
            iou = _iou_at(dx, dy)
            if iou > best_iou:
                best_iou = iou
                best = (dx, dy)

    dx_m = best[0] * resolution_m
    dy_m = best[1] * resolution_m
    # Apply only if IoU improves materially over identity (avoid spurious max-shift).
    improves = best_iou >= iou0 + 0.05 and best_iou >= 0.15
    nontrivial = abs(dx_m) >= resolution_m * 0.5 or abs(dy_m) >= resolution_m * 0.5
    apply = 1.0 if (improves and nontrivial) else 0.0
    if apply < 1.0:
        dx_m, dy_m = 0.0, 0.0
        best_iou = iou0
    return {
        "dx_m": float(dx_m),
        "dy_m": float(dy_m),
        "peak_iou": float(best_iou),
        "iou0": float(iou0),
        "resolution_m": float(resolution_m),
        "applied": apply,
    }


@dataclass
class PairDynamics:
    time_start_s: float
    time_end_s: float
    dt_min: float
    area_ha_prev: float
    area_ha_curr: float
    perimeter_m_prev: float
    perimeter_m_curr: float
    ros_area_m_min: float | None
    ros_equiv_radius_m_min: float | None
    ros_normal_median_m_min: float | None
    ros_normal_n: int
    coreg_dx_m: float
    coreg_dy_m: float
    coreg_iou: float
    coreg_applied: bool
    primary_ros_m_min: float | None
    primary_method: str
    pair_quality: str


@dataclass
class FrontDynamicsResult:
    pairs: list[PairDynamics] = field(default_factory=list)
    speed_result: GeometrySpeedResult | None = None
    aligned_observations: list[FrontObservation] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _pair_area_ros(
    prev: FrontObservation,
    curr: FrontObservation,
    dt_min: float,
) -> tuple[float | None, float | None, float, float, float, float]:
    a1 = observation_area_m2(prev)
    a2 = observation_area_m2(curr)
    p1 = total_perimeter_m(prev)
    p2 = total_perimeter_m(curr)
    ha1, ha2 = a1 / 10_000.0, a2 / 10_000.0
    if dt_min <= 0:
        return None, None, ha1, ha2, p1, p2
    ros_area = None
    p_avg = 0.5 * (p1 + p2)
    if p_avg > 1.0:
        # Isotropic bulk ROS (m/min)
        ros_area = (a2 - a1) / (p_avg * dt_min)
    r1 = math.sqrt(max(a1, 0.0) / math.pi)
    r2 = math.sqrt(max(a2, 0.0) / math.pi)
    ros_r = (r2 - r1) / dt_min
    return ros_area, ros_r, ha1, ha2, p1, p2


def _filter_normal_speeds(
    estimates: list,
    t0: float,
    t1: float,
) -> list[float]:
    out: list[float] = []
    for e in estimates:
        if not e.observable or e.speed_m_min is None:
            continue
        if abs(e.time_start_s - t0) > 1e-6 or abs(e.time_end_s - t1) > 1e-6:
            continue
        if e.quality_score is not None and e.quality_score < 0.2:
            continue
        spd = float(e.speed_m_min)
        dt_s = float(e.time_end_s - e.time_start_s)
        if dt_s < MIN_PLAUSIBLE_DT_S:
            continue
        if spd > MAX_PLAUSIBLE_SPEED_M_MIN or spd < 0:
            continue
        out.append(spd)
    return out


def _fuse_ros(
    ros_area: float | None,
    ros_radius: float | None,
    ros_normal_med: float | None,
    coreg_shift_m: float,
) -> tuple[float | None, str, str]:
    """Choose primary ROS for operators.

    Prefer area/radius when coreg shift is large (normals contaminated by georef).
    Prefer normals when registration is stable and enough samples exist.
    """
    candidates: list[tuple[str, float]] = []
    if ros_normal_med is not None and 0 <= ros_normal_med <= MAX_PLAUSIBLE_SPEED_M_MIN:
        candidates.append(("normal_ray", ros_normal_med))
    if ros_area is not None and 0 <= ros_area <= MAX_PLAUSIBLE_SPEED_M_MIN:
        candidates.append(("area_isotropic", ros_area))
    if ros_radius is not None and 0 <= ros_radius <= MAX_PLAUSIBLE_SPEED_M_MIN:
        candidates.append(("equiv_radius", ros_radius))

    if not candidates:
        # allow mild negative area (shrink) as abstain
        return None, "abstained", "C"

    if coreg_shift_m > 15.0:
        # Prefer bulk estimators
        for name in ("area_isotropic", "equiv_radius", "normal_ray"):
            for n, v in candidates:
                if n == name:
                    return v, n, "B" if name != "normal_ray" else "C"
    # Stable georef: median of available positive estimators (robust fusion)
    vals = [v for _, v in candidates if v >= 0]
    if not vals:
        return None, "abstained", "C"
    fused = float(np.median(vals))
    # High disagreement → conservative (lower quartile of candidates)
    # Avoids early-window mask inflation dominating the headline ROS.
    if len(vals) >= 2 and max(vals) > max(min(vals), 1e-6) * 2.5:
        fused = float(np.percentile(vals, 35))
        method = min(candidates, key=lambda t: abs(t[1] - fused))[0]
        return fused, f"fused_conservative:{method}", "B"
    # Method label = closest candidate
    method = min(candidates, key=lambda t: abs(t[1] - fused))[0]
    grade = "A" if coreg_shift_m < 8 and len(candidates) >= 2 else "B"
    return fused, f"fused:{method}", grade


def run_front_dynamics(
    observations: list[FrontObservation],
    speed_config: GeometrySpeedConfig | None = None,
    *,
    enable_coreg: bool = True,
    max_coreg_shift_m: float = 60.0,
) -> FrontDynamicsResult:
    """Run structural multi-estimator front dynamics on a cleaned sequence."""
    if len(observations) < 2:
        return FrontDynamicsResult(
            summary={"error": "need_at_least_2_observations", "n": len(observations)}
        )

    observations = sorted(observations, key=lambda o: o.time_s)
    speed_config = speed_config or GeometrySpeedConfig(
        sample_spacing_m=10.0,
        max_normal_distance_m=100.0,
        min_component_area_m2=200.0,
        min_valid_fraction=0.2,
        max_component_centroid_distance_m=350.0,
    )

    # Build coreg-aligned sequence (absolute cascade of pairwise shifts)
    aligned: list[FrontObservation] = [observations[0]]
    pair_coreg: list[dict[str, float]] = []
    cum_dx, cum_dy = 0.0, 0.0
    for i in range(1, len(observations)):
        prev = observations[i - 1]
        curr = observations[i]
        if enable_coreg:
            coreg = estimate_coreg_translation(
                prev, curr, max_shift_m=max_coreg_shift_m
            )
        else:
            coreg = {"dx_m": 0.0, "dy_m": 0.0, "peak_iou": 0.0, "applied": 0.0}
        pair_coreg.append(coreg)
        if coreg.get("applied", 0) > 0:
            # Align current to previous local frame, then accumulate to first frame
            cum_dx += float(coreg["dx_m"])
            cum_dy += float(coreg["dy_m"])
            aligned.append(_shift_observation(curr, cum_dx, cum_dy))
        else:
            aligned.append(_shift_observation(curr, cum_dx, cum_dy) if (cum_dx or cum_dy) else curr)

    speed_result = estimate_geometry_speeds(aligned, speed_config)
    estimates = list(speed_result.estimates)

    pairs: list[PairDynamics] = []
    primary_values: list[float] = []
    methods: list[str] = []

    for i in range(1, len(aligned)):
        prev, curr = aligned[i - 1], aligned[i]
        dt_min = (curr.time_s - prev.time_s) / 60.0
        if dt_min <= 0:
            continue
        ros_area, ros_r, ha1, ha2, p1, p2 = _pair_area_ros(prev, curr, dt_min)
        normals = _filter_normal_speeds(estimates, prev.time_s, curr.time_s)
        n_med = float(np.median(normals)) if normals else None
        coreg = pair_coreg[i - 1] if i - 1 < len(pair_coreg) else {}
        shift = math.hypot(float(coreg.get("dx_m", 0)), float(coreg.get("dy_m", 0)))
        primary, method, pquality = _fuse_ros(ros_area, ros_r, n_med, shift)
        # Reject bulk ROS if dt too small
        if dt_min * 60 < MIN_PLAUSIBLE_DT_S:
            primary, method, pquality = None, "abstained_dt", "C"
        if primary is not None:
            primary_values.append(primary)
            methods.append(method.split(":")[-1] if ":" in method else method)
        pairs.append(
            PairDynamics(
                time_start_s=prev.time_s,
                time_end_s=curr.time_s,
                dt_min=dt_min,
                area_ha_prev=ha1,
                area_ha_curr=ha2,
                perimeter_m_prev=p1,
                perimeter_m_curr=p2,
                ros_area_m_min=ros_area if ros_area is not None and ros_area >= 0 else None,
                ros_equiv_radius_m_min=ros_r if ros_r is not None and ros_r >= 0 else None,
                ros_normal_median_m_min=n_med,
                ros_normal_n=len(normals),
                coreg_dx_m=float(coreg.get("dx_m", 0)),
                coreg_dy_m=float(coreg.get("dy_m", 0)),
                coreg_iou=float(coreg.get("peak_iou", 0)),
                coreg_applied=bool(coreg.get("applied", 0)),
                primary_ros_m_min=primary,
                primary_method=method,
                pair_quality=pquality,
            )
        )

    primary_arr = np.asarray(primary_values, dtype=float) if primary_values else np.array([])
    area_vals = [
        p.ros_area_m_min
        for p in pairs
        if p.ros_area_m_min is not None and 0 <= p.ros_area_m_min <= MAX_PLAUSIBLE_SPEED_M_MIN
    ]
    radius_vals = [
        p.ros_equiv_radius_m_min
        for p in pairs
        if p.ros_equiv_radius_m_min is not None
        and 0 <= p.ros_equiv_radius_m_min <= MAX_PLAUSIBLE_SPEED_M_MIN
    ]
    normal_vals = [
        p.ros_normal_median_m_min
        for p in pairs
        if p.ros_normal_median_m_min is not None
    ]

    def _stats(vals: list[float]) -> dict[str, float | int | None]:
        a = np.asarray(vals, dtype=float)
        if a.size == 0:
            return {"n": 0, "median": None, "p25": None, "p75": None, "mean": None}
        return {
            "n": int(a.size),
            "median": float(np.median(a)),
            "p25": float(np.percentile(a, 25)),
            "p75": float(np.percentile(a, 75)),
            "mean": float(np.mean(a)),
        }

    # Structural grade
    n_primary = int(primary_arr.size)
    med_primary = float(np.median(primary_arr)) if n_primary else None
    mean_shift = float(
        np.mean([math.hypot(p.coreg_dx_m, p.coreg_dy_m) for p in pairs])
    ) if pairs else 0.0
    methods_used = sorted(set(methods))

    multi = len(methods_used) >= 2
    if (
        n_primary >= 3
        and med_primary is not None
        and 0.3 <= med_primary <= 25
        and (multi or mean_shift < 15)
    ):
        struct_grade = "A"
        struct_label = "dinámica multi-estimador defendible"
    elif n_primary >= 2 and med_primary is not None and med_primary <= 40:
        struct_grade = "B"
        struct_label = "orientativo — señal parcial o un solo estimador"
    elif n_primary >= 1 and med_primary is not None:
        struct_grade = "B"
        struct_label = "orientativo — muestra corta"
    else:
        struct_grade = "C"
        struct_label = "sin ROS defendible — abstención estructural"

    summary: dict[str, Any] = {
        "engine": "front_dynamics_v1",
        "n_pairs": len(pairs),
        "primary_ros_m_min": med_primary,
        "primary_ros_p25_m_min": float(np.percentile(primary_arr, 25)) if n_primary else None,
        "primary_ros_p75_m_min": float(np.percentile(primary_arr, 75)) if n_primary else None,
        "primary_ros_n": n_primary,
        "primary_methods_used": methods_used,
        "ros_area": _stats([v for v in area_vals if v is not None]),  # type: ignore[misc]
        "ros_equiv_radius": _stats([v for v in radius_vals if v is not None]),  # type: ignore[misc]
        "ros_normal": _stats([v for v in normal_vals if v is not None]),  # type: ignore[misc]
        "mean_coreg_shift_m": mean_shift,
        "structural_grade": struct_grade,
        "structural_label_es": struct_label,
        "geometry_speed": summarize_geometry_speeds(speed_result),
        "pairs": [asdict(p) for p in pairs],
    }

    return FrontDynamicsResult(
        pairs=pairs,
        speed_result=speed_result,
        aligned_observations=aligned,
        summary=summary,
    )


def attach_reference_calibration(
    summary: dict[str, Any],
    ref: OperationalReference | None,
) -> dict[str, Any]:
    """Add INFOCAM-style calibration block (report-only, not silent rescale)."""
    if ref is None or ref.vp_m_min is None or ref.vp_m_min <= 0:
        summary["calibration"] = {"has_reference": False}
        return summary
    raw = summary.get("primary_ros_m_min")
    out: dict[str, Any] = {
        "has_reference": True,
        "reference_name": ref.name,
        "reference_vp_m_min": ref.vp_m_min,
        "reference_area_ha": ref.area_ha,
        "raw_primary_ros_m_min": raw,
    }
    if isinstance(raw, (int, float)):
        ratio = float(raw) / float(ref.vp_m_min)
        out["raw_vs_ref_ratio"] = ratio
        out["scale_to_match_ref"] = float(ref.vp_m_min) / float(raw) if raw > 1e-6 else None
        if 0.5 <= ratio <= 2.0:
            out["grade"] = "compatible_order_of_magnitude"
            out["interpretation_es"] = (
                f"ROS primaria {raw:.2f} m/min vs ancla {ref.vp_m_min:.1f} m/min "
                f"(ratio {ratio:.2f}): mismo orden de magnitud. "
                "No se reescala en silencio; se reporta crudo."
            )
        elif ratio < 0.5:
            out["grade"] = "underestimate"
            out["interpretation_es"] = (
                f"ROS primaria {raw:.2f} << ancla {ref.vp_m_min:.1f}. "
                "Posible sub-segmentación o abstención de avance real."
            )
        else:
            out["grade"] = "overestimate"
            out["interpretation_es"] = (
                f"ROS primaria {raw:.2f} >> ancla {ref.vp_m_min:.1f}. "
                "Posible residual de georreferenciación o expansión de máscara."
            )
    summary["calibration"] = out
    return summary


def build_structural_operational_bundle(
    observations: list[FrontObservation],
    base_ingest_summary: dict[str, Any],
    *,
    speed_config: GeometrySpeedConfig | None = None,
    ref: OperationalReference | None = None,
) -> dict[str, Any]:
    """Full structural product for observatory packs."""
    dyn = run_front_dynamics(observations, speed_config=speed_config)
    summary = attach_reference_calibration(dict(dyn.summary), ref)

    # Merge legacy operational metrics on aligned obs for continuity
    if dyn.speed_result is not None:
        ops = build_operational_metrics(
            dyn.aligned_observations or observations,
            dyn.speed_result,
            base_ingest_summary,
            ref=ref,
        )
    else:
        ops = dict(base_ingest_summary)

    # Override headline speeds with structural primary ROS
    ops["structural"] = summary
    ops["speed_median_m_min"] = summary.get("primary_ros_m_min")
    ops["speed_p25_m_min"] = summary.get("primary_ros_p25_m_min")
    ops["speed_p75_m_min"] = summary.get("primary_ros_p75_m_min")
    ops["speed_n_observable"] = summary.get("primary_ros_n")
    ops["speed_status"] = (
        "estimated" if summary.get("primary_ros_m_min") is not None else "abstained"
    )
    ops["speed_defendable"] = bool((summary.get("primary_ros_n") or 0) >= 2)
    ops["quality_grade"] = summary.get("structural_grade")
    ops["quality_label_es"] = summary.get("structural_label_es")
    ops["primary_methods_used"] = summary.get("primary_methods_used")
    ops["mean_coreg_shift_m"] = summary.get("mean_coreg_shift_m")
    if summary.get("calibration", {}).get("has_reference"):
        ops["speed_vs_ref_ratio"] = summary["calibration"].get("raw_vs_ref_ratio")
        ops["speed_vs_ref_grade"] = summary["calibration"].get("grade")
        ops["speed_vs_ref_interpretation_es"] = summary["calibration"].get(
            "interpretation_es"
        )
        ops["has_reference"] = True
        ops["reference_name"] = summary["calibration"].get("reference_name")
        ops["reference_vp_m_min"] = summary["calibration"].get("reference_vp_m_min")
        ops["reference_area_ha"] = summary["calibration"].get("reference_area_ha")

    # Area evolution still useful
    ops["area_ha_series"] = [
        {
            "time_s": o.time_s,
            "observed_at": o.observed_at,
            "area_ha": observation_area_ha(o),
            "n_components": len(o.components),
        }
        for o in (dyn.aligned_observations or observations)
    ]
    areas = [s["area_ha"] for s in ops["area_ha_series"]]
    if areas:
        ops["area_ha_first"] = areas[0]
        ops["area_ha_last"] = areas[-1]
        ops["area_ha_max"] = max(areas)
        ops["area_ha_min"] = min(areas)

    ops["engine"] = "front_dynamics_v1"
    ops["product"] = "structural_observed_front_dynamics"
    return ops
