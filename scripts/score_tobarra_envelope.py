#!/usr/bin/env python3
"""F3.4 Tobarra envelope multi-window scorecard + optional F3.5 Decision Card attach.

Usage:
  python scripts/score_tobarra_envelope.py
  python scripts/score_tobarra_envelope.py --decision-card docs/FIRE_DECISION_CARD.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.envelope_scorecard import (  # noqa: E402
    build_tobarra_envelope_scorecard,
)


def _load_vp() -> float | None:
    p = ROOT / "data" / "infocam_anchors.json"
    if not p.is_file():
        return 7.0
    data = json.loads(p.read_text(encoding="utf-8"))
    a = (data.get("anchors") or {}).get("tobarra_20240802") or {}
    if a.get("status") == "confirmed" and a.get("vp_m_min") is not None:
        return float(a["vp_m_min"])
    return None


def _load_stack_slopes() -> tuple[float, float, str | None]:
    meta = ROOT / "outputs" / "fuel_stack" / "tobarra" / "fuel_terrain_stack.json"
    if not meta.is_file():
        return 3.3, 6.9, None
    d = json.loads(meta.read_text(encoding="utf-8"))
    ts = d.get("terrain_summary") or {}
    return (
        float(ts.get("slope_deg_mean") or 3.3),
        float(ts.get("slope_deg_p90") or 6.9),
        d.get("dem_source"),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Tobarra envelope F3.4 scorecard")
    ap.add_argument("--obs-ros", type=float, default=5.71)
    ap.add_argument("--decision-card", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--no-ensemble", action="store_true")
    ap.add_argument(
        "--weather",
        type=Path,
        default=None,
        help="WeatherScenario JSON (AEMET/observed/map); honesty-merged into windows",
    )
    args = ap.parse_args()

    slope_mean, slope_p90, dem_source = _load_stack_slopes()
    recipe = ROOT / "outputs" / "fuel_stack" / "tobarra" / "ros_calibration_recipe.json"
    stack_meta = ROOT / "outputs" / "fuel_stack" / "tobarra" / "fuel_terrain_stack.json"
    fuel_id = None
    if stack_meta.is_file():
        sm = json.loads(stack_meta.read_text(encoding="utf-8"))
        fuel_id = sm.get("fuel_id_dominant")
    card = None
    if args.decision_card and args.decision_card.is_file():
        card = json.loads(args.decision_card.read_text(encoding="utf-8"))
    elif args.decision_card is None:
        default_card = ROOT / "docs" / "FIRE_DECISION_CARD.json"
        if default_card.is_file():
            card = json.loads(default_card.read_text(encoding="utf-8"))

    pablo = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra" / "inventory.json"

    weather_doc = None
    weather_path = args.weather
    if weather_path is None:
        # Prefer stack AEMET/cached weather if present
        candidates = [
            ROOT / "data" / "fuel_stack" / "tobarra" / "weather_aemet_20240802.json",
            ROOT / "outputs" / "fuel_stack" / "tobarra" / "weather_scenario.json",
        ]
        for c in candidates:
            if c.is_file():
                weather_path = c
                break
    if weather_path is not None and weather_path.is_file():
        weather_doc = json.loads(weather_path.read_text(encoding="utf-8"))

    score = build_tobarra_envelope_scorecard(
        observed_ros_m_min=args.obs_ros,
        vp_m_min=_load_vp(),
        slope_mean=slope_mean,
        slope_p90=slope_p90,
        dem_source=dem_source or "copernicus_glo30",
        calibration_recipe=recipe if recipe.is_file() else None,
        weather_scenario=weather_doc,
        fuel_id=fuel_id,
        pablo_inventory=pablo if pablo.is_file() else None,
        decision_card=card,
        with_ensemble=not args.no_ensemble,
    )

    out = args.out or (
        ROOT / "outputs" / "fuel_stack" / "tobarra" / "envelope_scorecard_tobarra.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(score, indent=2, ensure_ascii=False), encoding="utf-8")

    if score.get("decision_card"):
        card_path = out.with_name("fire_decision_card_with_envelope.json")
        card_path.write_text(
            json.dumps(score["decision_card"], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {card_path}", file=sys.stderr)

    summary = {
        "verdict": score["verdict"],
        "counts": score["counts"],
        "primary_head_15_m": (score.get("windows_summary") or {})
        .get("w_slope_mean", {})
        .get("head_radius_15_m"),
        "failing": [c["id"] for c in score["checks"] if c["status"] == "fail"],
        "out": str(out),
    }
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out}", file=sys.stderr)
    return 0 if score["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
