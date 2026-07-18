#!/usr/bin/env python3
"""One-command sellable dual-product demo (open CEMS + CLM readiness).

  python scripts/demo_sellable_product.py
  python scripts/demo_sellable_product.py --skip-build   # only index + report
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], timeout: int = 600) -> dict:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    return {
        "cmd": cmd,
        "ok": p.returncode == 0,
        "code": p.returncode,
        "tail": ((p.stdout or "") + (p.stderr or ""))[-1500:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true", help="Do not re-download CEMS")
    ap.add_argument(
        "--activations",
        default="EMSR578,EMSR583,EMSR581",
        help="Comma list of CEMS activations to ensure",
    )
    args = ap.parse_args()

    report: dict = {
        "started_at_utc": datetime.now(UTC).isoformat(),
        "steps": [],
        "ok": True,
    }

    acts = [a.strip().upper() for a in args.activations.split(",") if a.strip()]
    if not args.skip_build:
        for act in acts:
            sc = ROOT / "outputs" / "open_if" / act.lower() / "scorecard_pista_b.json"
            if sc.is_file():
                report["steps"].append({"name": f"pack_{act}", "ok": True, "skipped": True})
                continue
            r = run(
                [sys.executable, "scripts/build_open_if_pack.py", "--activation", act],
                timeout=900,
            )
            report["steps"].append({"name": f"pack_{act}", **r})
            if not r["ok"]:
                report["ok"] = False

    r_idx = run([sys.executable, "scripts/build_open_if_index.py"], timeout=120)
    report["steps"].append({"name": "index_compare", **r_idx})
    if not r_idx["ok"]:
        report["ok"] = False

    # list products (CLM ready)
    r_list = run([sys.executable, "scripts/predict_spread.py", "--list-products"], timeout=120)
    report["steps"].append({"name": "list_products", **r_list})
    if not r_list["ok"]:
        report["ok"] = False

    # ops synthetic smoke
    r_ops = run([sys.executable, "scripts/smoke_incident_runtime.py"], timeout=300)
    report["steps"].append({"name": "ops_smoke", **r_ops})
    if not r_ops["ok"]:
        report["ok"] = False

    cmp_path = ROOT / "docs" / "COMPARE_CLM_VS_OPEN_SCORECARD.json"
    if cmp_path.is_file():
        cmp = json.loads(cmp_path.read_text(encoding="utf-8"))
        report["comparison"] = {
            "score_dual": cmp.get("score_dual_weighted"),
            "score_clm_only": cmp.get("score_clm_only_weighted"),
            "VENTA_GO": cmp.get("VENTA_GO"),
            "axes_win": cmp.get("axes_where_dual_wins"),
            "n_packs": len(cmp.get("open_packs") or []),
        }
        if not cmp.get("VENTA_GO"):
            # still ok engineering-wise; venta_go may need 3 packs
            report["venta_go"] = False
        else:
            report["venta_go"] = True
    else:
        report["venta_go"] = False
        report["ok"] = False

    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    report["artifacts"] = {
        "compare_md": "docs/COMPARE_CLM_VS_OPEN.md",
        "compare_json": "docs/COMPARE_CLM_VS_OPEN_SCORECARD.json",
        "onepager": "docs/ONEPAGER_COMERCIAL_ES.md",
        "plan": "docs/PLAN_COMERCIAL_SUPERA_CLM.md",
        "index_html": "outputs/open_if/index.html",
    }
    out = ROOT / "docs" / "DEMO_SELLABLE_SNAPSHOT.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "venta_go": report.get("venta_go"),
                "comparison": report.get("comparison"),
                "snapshot": str(out),
            },
            indent=2,
        )
    )
    # exit 0 if engineering ok even if venta_go false; exit 2 if broken
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
