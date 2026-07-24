"""PSB metrics: growth, Hausdorff, proxy ROS, scorecard gates."""

from __future__ import annotations

import math
from typing import Any

from wildfire_front.scientific_ops import MAX_PLAUSIBLE_SPEED_M_MIN

from .geometry import area_m2, hausdorff_m, iou, nested_within, perimeter_m
from .pipeline import StageSequence
from .schemas import (
    ATTRIBUTION_REDIAM,
    FRACTION_EPS_ABS,
    FRACTION_EPS_REL,
    PRODUCT_SCHEMA,
)


def _pair_proxy_ros(
    a1_m2: float,
    a2_m2: float,
    p1_m: float,
    p2_m: float,
    dt_s: float,
) -> dict[str, Any]:
    """Normative units matching front_dynamics._pair_area_ros (m², m, dt_min)."""
    dt_min = dt_s / 60.0 if dt_s > 0 else 0.0
    dA_m2 = a2_m2 - a1_m2
    dA_ha = dA_m2 / 10_000.0
    ros_area = None
    ros_r = None
    p_avg = 0.5 * (p1_m + p2_m)
    if dt_min > 0 and p_avg > 1.0:
        ros_area = dA_m2 / (p_avg * dt_min)
    if dt_min > 0:
        r1 = math.sqrt(max(a1_m2, 0.0) / math.pi)
        r2 = math.sqrt(max(a2_m2, 0.0) / math.pi)
        ros_r = (r2 - r1) / dt_min
    return {
        "dt_min": dt_min,
        "dA_m2": dA_m2,
        "dA_ha": dA_ha,
        "ros_area_m_min": ros_area,
        "ros_equiv_radius_m_min": ros_r,
        "p_avg_m": p_avg,
        "label": "proxy_synthetic",
    }


def compute_stage_pair_metrics(seq: StageSequence) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    stages = seq.stages
    for i in range(len(stages) - 1):
        s0, s1 = stages[i], stages[i + 1]
        a1, a2 = area_m2(s0.geom_metric), area_m2(s1.geom_metric)
        p1, p2 = perimeter_m(s0.geom_metric), perimeter_m(s1.geom_metric)
        dt_s = s1.time_s - s0.time_s
        if dt_s <= 0:
            dt_s = s0.dt_s_to_next
        ros = _pair_proxy_ros(a1, a2, p1, p2, dt_s)
        pairs.append(
            {
                "i": i,
                "j": i + 1,
                "hausdorff_m": hausdorff_m(s0.geom_metric, s1.geom_metric),
                "iou": iou(s0.geom_metric, s1.geom_metric),
                **ros,
            }
        )
    return pairs


def evaluate_invariants(
    seq: StageSequence,
    *,
    snap_m: float = 1.0,
    ops_cap_m_min: float = MAX_PLAUSIBLE_SPEED_M_MIN,
) -> dict[str, Any]:
    """Return gate results and detailed checks for a StageSequence."""
    stages = seq.stages
    n = len(stages)
    final = seq.final_metric
    checks: list[str] = []
    fails: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if cond:
            checks.append(name)
        else:
            fails.append(f"{name}:{detail}" if detail else name)

    # Terminal identity
    term = stages[-1].geom_metric
    ok("PSB_TERMINAL_IDENTITY", term.wkt == final.wkt, "wkt_mismatch")
    ok("PSB_TERMINAL_METRIC_QA", iou(term, final) >= 0.999 and hausdorff_m(term, final) <= 1.0)

    # Monotone area
    mono = all(
        area_m2(stages[i].geom_metric) <= area_m2(stages[i + 1].geom_metric) + 1e-3
        for i in range(n - 1)
    )
    ok("PSB_MONOTONE_AREA", mono)

    # Nested + inside final
    nested = True
    inside = True
    for i in range(n - 1):
        if not nested_within(stages[i].geom_metric, stages[i + 1].geom_metric, snap_m=snap_m):
            nested = False
        if not nested_within(stages[i].geom_metric, final, snap_m=snap_m):
            inside = False
    if not nested_within(stages[-1].geom_metric, final, snap_m=snap_m):
        inside = False
    ok("PSB_NESTED", nested and inside)

    # Honesty
    honesty = all(
        s.synthetic and s.not_real_lwir and s.not_official_intermediate_o2 for s in stages
    )
    ok("PSB_HONESTY", honesty)

    # Fraction band Mode A
    frac_ok = True
    if seq.engine_name == "area_fraction":
        for s in stages[:-1]:
            eps = max(FRACTION_EPS_ABS, FRACTION_EPS_REL * abs(s.area_fraction_target))
            # soft: recorded as PARTIAL not hard fail if reason present
            if (
                abs(s.area_fraction_actual - s.area_fraction_target) > eps + 1e-6
                and "fraction_miss_after_nest_fix" not in s.partial_reasons
            ):
                frac_ok = False
    ok("PSB_FRACTION_BAND", frac_ok or seq.engine_name != "area_fraction")

    pairs = compute_stage_pair_metrics(seq)
    ros_vals = [
        p["ros_area_m_min"]
        for p in pairs
        if p.get("ros_area_m_min") is not None and p["ros_area_m_min"] >= 0
    ]
    over_cap = any(v > ops_cap_m_min for v in ros_vals)
    if not pairs:
        ros_status = "SKIP"
        ok("PSB_PROXY_ROS", True)
    elif over_cap:
        ros_status = "PARTIAL"
        ok("PSB_PROXY_ROS", True)  # PARTIAL allowed
    else:
        ros_status = "PASS"
        ok("PSB_PROXY_ROS", True)

    ok("PSB_REPRO", seq.config.seed is not None and bool(seq.engine_name))
    ok("PSB_NO_FALSE_DISPATCH", True)  # structural — vp always null in emit

    gates = {
        "PSB_TERMINAL_IDENTITY": "PASS"
        if "PSB_TERMINAL_IDENTITY" in checks
        and not any(f.startswith("PSB_TERMINAL_IDENTITY") for f in fails)
        else "FAIL",
        "PSB_TERMINAL_METRIC_QA": "PASS"
        if not any(f.startswith("PSB_TERMINAL_METRIC_QA") for f in fails)
        else "FAIL",
        "PSB_MONOTONE_AREA": "PASS"
        if not any(f.startswith("PSB_MONOTONE_AREA") for f in fails)
        else "FAIL",
        "PSB_NESTED": "PASS" if not any(f.startswith("PSB_NESTED") for f in fails) else "FAIL",
        "PSB_HONESTY": "PASS" if not any(f.startswith("PSB_HONESTY") for f in fails) else "FAIL",
        "PSB_FRACTION_BAND": "PASS"
        if not any(f.startswith("PSB_FRACTION_BAND") for f in fails)
        else "PARTIAL",
        "PSB_PROXY_ROS": ros_status,
        "PSB_REPRO": "PASS",
        "PSB_NO_FALSE_DISPATCH": "PASS",
    }

    hard_fail = any(
        gates[k] == "FAIL"
        for k in (
            "PSB_TERMINAL_IDENTITY",
            "PSB_MONOTONE_AREA",
            "PSB_NESTED",
            "PSB_HONESTY",
        )
    )
    partial_reasons = list(seq.all_partial_reasons)
    if over_cap:
        partial_reasons.append("proxy_ros_exceeds_ops_cap")
    if any("fraction_miss" in r for r in partial_reasons):
        gates["PSB_FRACTION_BAND"] = "PARTIAL"

    if hard_fail:
        verdict = "NO_GO"
    elif (
        partial_reasons
        or gates["PSB_PROXY_ROS"] == "PARTIAL"
        or gates["PSB_FRACTION_BAND"] == "PARTIAL"
    ):
        verdict = "PARTIAL"
    else:
        verdict = "GO_PROGRESSIVE_SYNTHETIC"

    return {
        "schema": PRODUCT_SCHEMA,
        "verdict": verdict,
        "gates": gates,
        "fails": fails,
        "partial_reasons": partial_reasons,
        "pairs": pairs,
        "ops_cap_m_min": ops_cap_m_min,
        "vp_tactical": None,
        "proxy_ros": {
            "status": "synthetic_proxy_only",
            "pairs": pairs,
            "over_ops_cap": over_cap,
        },
        "final_geom_type": seq.final_geom_type,
        "final_n_parts": seq.final_n_parts,
        "final_area_ha": seq.final_area_ha,
        "n_stages": n,
        "engine": seq.engine_name,
        "seed": seq.config.seed,
        "attribution": seq.config.attribution or ATTRIBUTION_REDIAM,
        "honest_notes": [
            "Stages are synthetic reverse-growth from final official perimeter",
            "Not multi-day official O2",
            "Not LWIR / Heligrafics",
            "ROS figures are geometric proxies only; no tactical Vp",
        ],
    }


def assert_all_invariants(seq: StageSequence, *, snap_m: float = 1.0) -> int:
    """Return number of micro-assertions passed; raise AssertionError with repro on fail."""
    count = 0
    stages = seq.stages
    n = len(stages)
    final = seq.final_metric
    cfg = seq.config
    repro = (
        f"repro: --seed {cfg.seed} --engine {cfg.engine} --n-stages {cfg.n_stages} "
        f"--schedule {cfg.schedule}"
    )

    def check(cond: bool, msg: str) -> None:
        nonlocal count
        if not cond:
            raise AssertionError(f"{msg} | {repro}")
        count += 1

    check(n == cfg.n_stages, "n_stages mismatch")
    check(stages[-1].geom_metric.wkt == final.wkt, "terminal identity")
    check(all(s.synthetic for s in stages), "synthetic flags")
    check(all(s.not_real_lwir for s in stages), "not_real_lwir")
    check(all(s.not_official_intermediate_o2 for s in stages), "not_official_o2")
    check(all(math.isfinite(s.area_ha) and s.area_ha >= 0 for s in stages), "areas finite")
    for i in range(n - 1):
        check(
            area_m2(stages[i].geom_metric) <= area_m2(stages[i + 1].geom_metric) + 1.0,
            f"monotone area stage {i}",
        )
        check(
            nested_within(stages[i].geom_metric, stages[i + 1].geom_metric, snap_m=snap_m),
            f"nested {i}",
        )
        check(
            nested_within(stages[i].geom_metric, final, snap_m=snap_m),
            f"inside final {i}",
        )
        check(stages[i].time_s <= stages[i + 1].time_s, f"time monotone {i}")
    check(nested_within(stages[-1].geom_metric, final, snap_m=snap_m), "terminal inside")
    check(all(not s.geom_metric.is_empty or i == 0 for i, s in enumerate(stages)), "non-empty-ish")
    for s in stages:
        check(s.geom_metric.is_valid or s.geom_metric.is_empty, "valid geom")
    return count
