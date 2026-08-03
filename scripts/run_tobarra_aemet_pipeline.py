#!/usr/bin/env python3
"""End-to-end Tobarra fuel stack with AEMET weather + envelope + scorecard.

Usage:
  # Uses data/fuel_stack/tobarra/weather_aemet_20240802.json if present,
  # else fetches with AEMET_API_KEY from env / .env
  python scripts/run_tobarra_aemet_pipeline.py

  python scripts/run_tobarra_aemet_pipeline.py --refetch
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> int:
    print("+", " ".join(cmd), file=sys.stderr)
    return subprocess.call(cmd, cwd=str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser(description="Tobarra AEMET full physics pipeline")
    ap.add_argument("--refetch", action="store_true", help="Force live AEMET fetch")
    ap.add_argument("--date", default="2024-08-02")
    ap.add_argument("--station", default="8175")
    ap.add_argument("--no-envelope", action="store_true")
    ap.add_argument("--no-scorecard", action="store_true")
    args = ap.parse_args()

    wx = (
        ROOT
        / "data"
        / "fuel_stack"
        / "tobarra"
        / f"weather_aemet_{args.date.replace('-', '')}.json"
    )

    if args.refetch or not wx.is_file():
        rc = _run(
            [
                sys.executable,
                "scripts/build_aemet_weather_scenario.py",
                "--date",
                args.date,
                "--station",
                args.station,
                "--fire-id",
                "tobarra_20240802",
                "--out",
                str(wx),
            ]
        )
        if rc != 0:
            return rc
    else:
        print(f"Using cached weather {wx}", file=sys.stderr)

    stack_cmd = [
        sys.executable,
        "scripts/build_fuel_terrain_stack.py",
        "--fire",
        "tobarra",
        "--with-physics",
        "--weather",
        str(wx),
    ]
    if not args.no_envelope:
        stack_cmd.extend(["--with-envelope", "--with-ensemble"])
    rc = _run(stack_cmd)
    if rc != 0:
        return rc

    if not args.no_envelope:
        rc = _run(
            [
                sys.executable,
                "scripts/build_hybrid_envelope.py",
                "--preset",
                "tobarra_scenario",
                "--weather",
                str(wx),
                "--with-ensemble",
            ]
        )
        if rc != 0:
            return rc

    if not args.no_scorecard:
        rc = _run(
            [
                sys.executable,
                "scripts/score_tobarra_envelope.py",
                "--weather",
                str(wx),
            ]
        )
        if rc != 0:
            return rc

    # Compact summary
    phys = ROOT / "outputs" / "fuel_stack" / "tobarra" / "physics_prior_tobarra.json"
    score = ROOT / "outputs" / "fuel_stack" / "tobarra" / "envelope_scorecard_tobarra.json"
    summary: dict = {"weather": str(wx)}
    if phys.is_file():
        doc = json.loads(phys.read_text(encoding="utf-8"))
        p = doc.get("physics") or {}
        h = doc.get("hybrid") or {}
        summary["physics_head_m_min"] = p.get("ros_head_m_min")
        summary["hybrid_head_m_min"] = (h.get("sectors") or {}).get("head_m_min")
        summary["weather_source"] = (doc.get("weather_scenario") or {}).get("source")
        summary["weather_merge"] = doc.get("weather_drivers_merge")
    if score.is_file():
        sc = json.loads(score.read_text(encoding="utf-8"))
        summary["scorecard_verdict"] = sc.get("verdict")
        summary["scorecard_counts"] = sc.get("counts")
    out = ROOT / "outputs" / "fuel_stack" / "tobarra" / "aemet_pipeline_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nWrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
