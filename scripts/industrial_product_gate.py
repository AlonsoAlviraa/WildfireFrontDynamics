#!/usr/bin/env python3
"""T0 industrial product gate: flags, no-cite, holdout catalog, silent-GO contract.

Does not flip stamps. Exit 0 only when every check passes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPTS = str(ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from check_release_flags import evaluate as evaluate_flags  # noqa: E402

from wildfire_front.ml.product_catalog import list_holdout_only, list_products  # noqa: E402
from wildfire_front.product.confidence import Decision, build_decision_card  # noqa: E402
from wildfire_front.product.policy import get_policy  # noqa: E402


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True)


def main() -> int:
    checks: list[dict[str, Any]] = []
    hard_fail = False

    flags = evaluate_flags()
    flags_ok = flags.get("status") == "PASS" and int(flags.get("exit_code", 1)) == 0
    checks.append(
        {
            "id": "check_release_flags",
            "ok": flags_ok,
            "detail": flags.get("status"),
        }
    )
    hard_fail = hard_fail or not flags_ok

    refuse = ROOT / "scripts" / "refuse_promote_without_cite.py"
    ssot = _run([sys.executable, str(refuse)])
    ssot_ok = ssot.returncode == 0
    checks.append(
        {
            "id": "refuse_promote_ssot",
            "ok": ssot_ok,
            "detail": (ssot.stdout or ssot.stderr or "")[:200],
        }
    )
    hard_fail = hard_fail or not ssot_ok

    hellin = _run(
        [sys.executable, str(refuse), "--attempt-promote", "--fire-id", "hellin_2024"]
    )
    hellin_ok = hellin.returncode == 1
    checks.append(
        {
            "id": "refuse_promote_hellin",
            "ok": hellin_ok,
            "detail": f"exit={hellin.returncode} (want 1)",
        }
    )
    hard_fail = hard_fail or not hellin_ok

    products = {p["id"] for p in list_products()}
    holdout = list_holdout_only()
    holdout_ids = {row["id"] for row in holdout}
    holdout_ok = (
        {"rcda_net", "caldor_clean17_physical_v1"} <= holdout_ids
        and holdout_ids.isdisjoint(products)
        and all(row.get("ready") is False for row in holdout)
    )
    checks.append(
        {
            "id": "catalog_holdout_only",
            "ok": holdout_ok,
            "detail": f"holdout={sorted(holdout_ids)} products_overlap={sorted(holdout_ids & products)}",
        }
    )
    hard_fail = hard_fail or not holdout_ok

    field = get_policy("field_ops")
    cap_ok = (
        abs(float(field.ml_live_max_weight) - 0.20) < 1e-9
        and abs(float(field.ml_live_abstain_below) - 0.45) < 1e-9
    )
    checks.append(
        {
            "id": "field_ops_fusion_caps",
            "ok": cap_ok,
            "detail": (
                f"max_weight={field.ml_live_max_weight} "
                f"abstain_below={field.ml_live_abstain_below}"
            ),
        }
    )
    hard_fail = hard_fail or not cap_ok

    strong = {
        "ops_metrics": {
            "quality_grade": "A",
            "primary_ros_m_min": 6.0,
            "n_frames_staged": 20,
            "speed_vs_ref_ratio": 0.9,
            "area_ha_max": 50,
        },
        "open_metrics": {"max_area_ha": 2000, "n_timeline_steps": 5},
        "ml_metrics": {"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
    }
    unverified = build_decision_card("gate_field", policy_id="field_ops", **strong)
    silent_ok = (
        unverified.decision != Decision.GO
        and unverified.system_reliability_pass is False
        and any("fail_closed" in r for r in unverified.reasons)
    )
    checks.append(
        {
            "id": "field_ops_silent_go_blocked",
            "ok": silent_ok,
            "detail": f"decision={unverified.decision.value} pass={unverified.system_reliability_pass}",
        }
    )
    hard_fail = hard_fail or not silent_ok

    report = {
        "schema": "wfd_industrial_product_gate_v1",
        "status": "FAIL" if hard_fail else "PASS",
        "checks": checks,
        "not_claims": [
            "not GO_Q complete",
            "not GO_MES+",
            "not RCDA product",
            "not tactical dispatch",
        ],
    }
    print(json.dumps(report, indent=2))
    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
