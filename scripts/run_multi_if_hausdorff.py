#!/usr/bin/env python3
"""Batch temporal Hausdorff over outputs/observatorio/*/main_front.geojson."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    packs = ROOT / "outputs" / "observatorio"
    if len(sys.argv) > 1:
        packs = Path(sys.argv[1])
    script = ROOT / "scripts" / "eval_perimeter_hausdorff.py"
    results = []
    for mf in sorted(packs.glob("*/main_front.geojson")):
        out = mf.parent / "hausdorff_report.json"
        r = subprocess.run(
            [
                sys.executable,
                str(script),
                "--observed",
                str(mf),
                "--mode",
                "temporal",
                "--output",
                str(out),
            ],
            capture_output=True,
            text=True,
        )
        rep: dict = {}
        if out.is_file():
            rep = json.loads(out.read_text(encoding="utf-8"))
        results.append(
            {
                "fire": mf.parent.name,
                "status": rep.get("status"),
                "verdict": rep.get("verdict"),
                "summary": rep.get("summary"),
                "returncode": r.returncode,
            }
        )
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "temporal",
        "n_fires": len(results),
        "fires": results,
        "o2_official": False,
        "note": "Temporal proxy only. Official O2 needs --mode official + GeoJSON.",
    }
    out_path = packs / "hausdorff_multi_if.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print("Wrote", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
