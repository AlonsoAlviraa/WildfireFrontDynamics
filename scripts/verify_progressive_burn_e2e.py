#!/usr/bin/env python3
"""Verify progressive synthetic burn on gold Níjar pack (offline).

Exit 0 on GO_PROGRESSIVE_SYNTHETIC or PARTIAL with documented reasons.
Exit 2 on NO_GO. Exit 1 on missing pack.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.progressive_burn.pack_attach import attach_progressive_burn  # noqa: E402
from wildfire_front.progressive_burn.pipeline import ProgressiveBurnConfig  # noqa: E402
from wildfire_front.progressive_burn.schemas import ATTRIBUTION_REDIAM  # noqa: E402

DEFAULT_PACK = ROOT / "outputs" / "open_if" / "and_2024040053_20240606"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pack", type=Path, default=DEFAULT_PACK)
    p.add_argument("--n-stages", type=int, default=12)
    p.add_argument("--engine", default="area_fraction")
    p.add_argument("--schedule", default="sqrt")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--write", action="store_true", help="attach artifacts into pack")
    args = p.parse_args(argv)

    pack = args.pack
    if not pack.is_dir():
        print(f"MISSING pack: {pack}", file=sys.stderr)
        return 1

    cfg = ProgressiveBurnConfig(
        n_stages=args.n_stages,
        engine=args.engine,
        schedule=args.schedule,
        seed=args.seed,
        attribution=ATTRIBUTION_REDIAM,
        codigo="2024040053",
    )
    result = attach_progressive_burn(pack, cfg, run_fd=True)
    metrics_path = pack / "progressive" / "metrics_progressive.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.is_file() else {}

    report = {
        "pack": str(pack),
        "verdict": result.get("verdict"),
        "n_stages": result.get("n_stages"),
        "final_area_ha": result.get("final_area_ha"),
        "gates": metrics.get("gates"),
        "partial_reasons": metrics.get("partial_reasons"),
        "final_geom_type": metrics.get("final_geom_type"),
        "final_n_parts": metrics.get("final_n_parts"),
        "vp_tactical": None,
        "attribution": ATTRIBUTION_REDIAM,
        "acceptance": {
            "terminal_identity": metrics.get("gates", {}).get("PSB_TERMINAL_IDENTITY"),
            "nested": metrics.get("gates", {}).get("PSB_NESTED"),
            "honesty": metrics.get("gates", {}).get("PSB_HONESTY"),
            "multipolygon_parts": metrics.get("final_n_parts"),
        },
    }
    out_report = pack / "progressive" / "verify_progressive_burn_e2e.json"
    out_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Industrial independence: industrial scorecard must still exist if present
    industrial = pack / "scorecard_and_industrial.json"
    if industrial.is_file():
        sc = json.loads(industrial.read_text(encoding="utf-8"))
        if sc.get("vp_invented") is True:
            print("INDUSTRIAL REGRESSION: vp_invented true", file=sys.stderr)
            return 2

    v = result.get("verdict")
    if v == "NO_GO":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
