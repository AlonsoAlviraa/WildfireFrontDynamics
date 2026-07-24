"""Mode A (area-fraction erode) and Mode B (buffer rings) PSB engines."""

from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from .geometry import (
    area_ha,
    area_m2,
    component_polygons,
    drop_micro_components,
    ensure_valid,
    erode,
    safe_homothety_center,
    scale_about,
)

# Polygon re-exported for empty stage recovery
from .schemas import FRACTION_EPS_ABS, FRACTION_EPS_REL, MIN_COMPONENT_AREA_HA_DEFAULT


def fraction_band_ok(f_actual: float, f_target: float) -> bool:
    eps = max(FRACTION_EPS_ABS, FRACTION_EPS_REL * abs(f_target))
    return abs(f_actual - f_target) <= eps + 1e-12


def _clean_stage(
    geom: BaseGeometry,
    final: BaseGeometry,
    *,
    min_component_area_ha: float,
) -> tuple[BaseGeometry, int]:
    if geom is None or geom.is_empty:
        return Polygon(), 0
    inter = geom.intersection(final)
    if inter is None or inter.is_empty:
        return Polygon(), 0
    g = ensure_valid(inter, allow_empty=True)
    if g.is_empty:
        return Polygon(), 0
    g2, dropped = drop_micro_components(g, min_area_ha=min_component_area_ha)
    if g2.is_empty:
        return Polygon(), dropped
    return ensure_valid(g2), dropped


def _binary_search_erode(
    final: BaseGeometry,
    target_area_m2: float,
    *,
    max_d: float | None = None,
    iters: int = 40,
) -> BaseGeometry:
    """Find erosion distance so area(erode(F,d)) ≈ target_area_m2."""
    a_f = area_m2(final)
    if target_area_m2 >= a_f * (1.0 - 1e-12):
        return ensure_valid(final)
    if target_area_m2 <= 0:
        return Polygon()

    # Max search distance: characteristic radius * 2
    r_char = math.sqrt(max(a_f, 1.0) / math.pi)
    hi = float(max_d) if max_d is not None else max(r_char * 2.5, 10.0)
    lo = 0.0

    # Expand hi until empty or area below target
    for _ in range(20):
        g = erode(final, hi)
        if g.is_empty or area_m2(g) <= target_area_m2:
            break
        hi *= 1.6

    best = erode(final, hi)
    best_err = abs(area_m2(best) - target_area_m2) if not best.is_empty else float("inf")

    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        g = erode(final, mid)
        a = area_m2(g) if not g.is_empty else 0.0
        err = abs(a - target_area_m2)
        if err < best_err:
            best, best_err = g, err
        if a > target_area_m2:
            lo = mid  # need more erosion
        else:
            hi = mid
    if best.is_empty:
        return best
    return ensure_valid(best)


def _per_component_homothety(
    final: BaseGeometry,
    f_target: float,
    *,
    min_component_area_ha: float,
) -> BaseGeometry:
    """KD13 M3: scale each component about its own representative point."""
    parts = component_polygons(final)
    a_f = area_m2(final)
    if a_f <= 0 or f_target <= 0:
        return Polygon()
    if f_target >= 1.0 - 1e-12:
        return ensure_valid(final)

    # Linear scale factor ~ sqrt(f) for area; then clip to F
    factor = math.sqrt(max(f_target, 1e-12))
    scaled: list[BaseGeometry] = []
    for p in parts:
        if area_ha(p) < min_component_area_ha and f_target < 0.95:
            continue  # micro deferred
        origin = safe_homothety_center(p)
        s = scale_about(p, factor, origin)
        s = ensure_valid(s.intersection(final))
        if not s.is_empty:
            scaled.append(s)
    if not scaled:
        # Last resort: scale largest only
        largest = max(parts, key=lambda p: p.area)
        origin = safe_homothety_center(largest)
        s = scale_about(largest, factor, origin).intersection(final)
        return ensure_valid(s) if not s.is_empty else Polygon()
    return ensure_valid(unary_union(scaled))


def area_fraction_stage(
    final: BaseGeometry,
    f_target: float,
    *,
    min_component_area_ha: float = MIN_COMPONENT_AREA_HA_DEFAULT,
) -> tuple[BaseGeometry, str, list[str]]:
    """Build one stage for Mode A. Returns (geom, method_used, partial_reasons)."""
    reasons: list[str] = []
    a_f = area_m2(final)
    if f_target >= 1.0 - 1e-12:
        return ensure_valid(final), "terminal_exact", reasons
    if f_target <= 0:
        return Polygon(), "empty", reasons

    target_a = f_target * a_f
    g = _binary_search_erode(final, target_a)
    g, dropped = _clean_stage(g, final, min_component_area_ha=min_component_area_ha)
    if dropped:
        reasons.append("micro_components_deferred")

    method = "area_fraction_erode"
    if g.is_empty or not fraction_band_ok(area_m2(g) / a_f if a_f else 0.0, f_target):
        g2 = _per_component_homothety(final, f_target, min_component_area_ha=min_component_area_ha)
        g2, dropped2 = _clean_stage(g2, final, min_component_area_ha=min_component_area_ha)
        if dropped2:
            reasons.append("micro_components_deferred")
        method = "area_fraction_homothety_fallback"
        g = g2

    if g.is_empty:
        reasons.append("stage_empty_after_fallback")
        return g, method, reasons

    f_act = area_m2(g) / a_f if a_f else 0.0
    if not fraction_band_ok(f_act, f_target):
        reasons.append("fraction_miss_after_nest_fix")
    return ensure_valid(g), method, reasons


def run_area_fraction_engine(
    final: BaseGeometry,
    fractions: list[float],
    *,
    min_component_area_ha: float = MIN_COMPONENT_AREA_HA_DEFAULT,
) -> tuple[list[BaseGeometry], list[str], list[list[str]]]:
    """Generate interior stages then exact terminal. Nested large→small enforce."""
    n = len(fractions)
    stages: list[BaseGeometry | None] = [None] * n
    methods: list[str] = [""] * n
    reasons_all: list[list[str]] = [[] for _ in range(n)]

    # Terminal exact
    stages[n - 1] = ensure_valid(final)
    methods[n - 1] = "terminal_exact"

    # Build from largest interior down to smallest for nesting
    for i in range(n - 2, -1, -1):
        f = fractions[i]
        parent = stages[i + 1]
        assert parent is not None
        # Area targets always vs full final
        g, method, reasons = area_fraction_stage(
            final, f, min_component_area_ha=min_component_area_ha
        )
        # Nest: S_i ⊆ S_{i+1}
        if g.is_empty:
            g_nested = Polygon()
        else:
            inter = g.intersection(parent)
            g_nested = ensure_valid(inter, allow_empty=True) if not inter.is_empty else Polygon()
        if g_nested.is_empty and not g.is_empty:
            reasons.append("fraction_miss_after_nest_fix")
        # If nest emptied, use parent slightly eroded as last resort
        if g_nested.is_empty and not parent.is_empty:
            g_nested = erode(parent, max(parent.area**0.5 * 0.01, 1.0))
            inter2 = g_nested.intersection(parent) if not g_nested.is_empty else Polygon()
            g_nested = ensure_valid(inter2, allow_empty=True) if not inter2.is_empty else Polygon()
            reasons.append("nest_recover_erode_parent")
            method = method + "+nest_recover"
        stages[i] = g_nested if not g_nested.is_empty else g
        methods[i] = method
        reasons_all[i] = reasons

        # Re-check fraction after nest
        a_f = area_m2(final)
        f_act = area_m2(stages[i]) / a_f if a_f and stages[i] is not None else 0.0
        if not fraction_band_ok(f_act, f) and "fraction_miss_after_nest_fix" not in reasons_all[i]:
            reasons_all[i].append("fraction_miss_after_nest_fix")

    # Forward pass: ensure area monotone by taking running max containment
    out: list[BaseGeometry] = []
    for s in stages:
        assert s is not None
        out.append(s if s.is_empty else ensure_valid(s))

    # Fix area non-decreasing: if A_i > A_{i+1}, set S_i = S_i ∩ S_{i+1}
    for i in range(n - 2, -1, -1):
        if area_m2(out[i]) > area_m2(out[i + 1]) + 1e-6:
            inter = out[i].intersection(out[i + 1])
            out[i] = ensure_valid(inter, allow_empty=True) if not inter.is_empty else Polygon()
            reasons_all[i].append("monotone_clip")

    return out, methods, reasons_all


def max_erode_distance(final: BaseGeometry, *, tol: float = 0.5) -> float:
    """Binary search max d where erode(F,d) still non-empty."""
    a_f = area_m2(final)
    r = math.sqrt(max(a_f, 1.0) / math.pi)
    lo, hi = 0.0, max(r * 2.0, 10.0)
    for _ in range(12):
        if not erode(final, hi).is_empty:
            hi *= 1.5
        else:
            break
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if erode(final, mid).is_empty:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    return max(lo, 0.0)


def run_buffer_rings_engine(
    final: BaseGeometry,
    n_stages: int,
    *,
    min_component_area_ha: float = MIN_COMPONENT_AREA_HA_DEFAULT,
) -> tuple[list[BaseGeometry], list[str], list[list[str]]]:
    """Mode B: inward shells; fractions induced."""
    d_max = max_erode_distance(final)
    if d_max <= 0:
        # Degenerate: all stages = final except empty early
        early = [ensure_valid(final) for _ in range(n_stages)]
        return early, ["buffer_rings"] * n_stages, [[] for _ in range(n_stages)]

    # distances: stage 0 most eroded, stage n-1 d=0
    distances = [d_max * (1.0 - (i + 1) / n_stages) for i in range(n_stages)]
    distances[-1] = 0.0

    stages: list[BaseGeometry] = []
    methods: list[str] = []
    reasons_all: list[list[str]] = []
    for i, d in enumerate(distances):
        reasons: list[str] = []
        if d <= 0:
            g = ensure_valid(final)
            method = "terminal_exact" if i == n_stages - 1 else "buffer_rings_zero"
        else:
            g = erode(final, d)
            g, dropped = _clean_stage(g, final, min_component_area_ha=min_component_area_ha)
            if dropped:
                reasons.append("micro_components_deferred")
            method = "buffer_rings"
            if g.is_empty:
                reasons.append("stage_empty_buffer_collapse")
                # recover: small disk about representative point
                from shapely.geometry import Point

                from .geometry import safe_homothety_center

                cx, cy = safe_homothety_center(final)
                g = ensure_valid(Point(cx, cy).buffer(max(d_max * 0.05, 5.0)).intersection(final))
                method = "buffer_rings_recover"
        stages.append(g)
        methods.append(method)
        reasons_all.append(reasons)

    # Nesting enforce small → large
    for i in range(n_stages - 2, -1, -1):
        if stages[i].is_empty:
            continue
        inter = stages[i].intersection(stages[i + 1])
        stages[i] = ensure_valid(inter, allow_empty=True) if not inter.is_empty else Polygon()

    stages[-1] = ensure_valid(final)
    methods[-1] = "terminal_exact"
    return stages, methods, reasons_all
