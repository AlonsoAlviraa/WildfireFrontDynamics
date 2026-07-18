#!/usr/bin/env python3
"""One-command dual-product demo (ops + ML) for industrial smoke.

Usage:
  python scripts/demo_dual_product.py
  python scripts/demo_dual_product.py --skip-ml   # ops only (faster)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], timeout: int = 600) -> dict:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**dict(**dict(__import__("os").environ.items())), "PYTHONPATH": str(ROOT)},
    )
    return {
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout_tail": (p.stdout or "")[-2000:],
        "stderr_tail": (p.stderr or "")[-1000:],
        "ok": p.returncode == 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Dual product demo (ops + ML v34)")
    ap.add_argument("--skip-ml", action="store_true")
    ap.add_argument("--skip-ops", action="store_true")
    args = ap.parse_args()

    report: dict = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "product_ml": "clm_ensemble_v34",
        "product_ops": "incident_runtime_v1 / front_dynamics_v1",
        "steps": [],
        "ok": True,
    }

    # 0) list products
    r0 = _run([sys.executable, "scripts/predict_spread.py", "--list-products"], timeout=120)
    report["steps"].append({"name": "list_products", **r0})
    if not r0["ok"]:
        report["ok"] = False

    if not args.skip_ops:
        r1 = _run([sys.executable, "scripts/smoke_incident_runtime.py"], timeout=300)
        report["steps"].append({"name": "smoke_incident_synthetic", **r1})
        if not r1["ok"]:
            report["ok"] = False

    if not args.skip_ml:
        r2 = _run(
            [
                sys.executable,
                "scripts/smoke_production_products.py",
                "--products",
                "clm_v28,clm_ensemble_v34",
                "--max-patches",
                "12",
            ],
            timeout=600,
        )
        report["steps"].append({"name": "smoke_ml_v34", **r2})
        if not r2["ok"]:
            report["ok"] = False

    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    out = ROOT / "docs" / "DEMO_DUAL_PRODUCT_SNAPSHOT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "snapshot": str(out), "steps": [s["name"] for s in report["steps"]]}, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
