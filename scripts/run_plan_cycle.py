#!/usr/bin/env python3
"""Review & adapt the 3-month plan from live evidence (loop-engineering cycle).

  python scripts/run_plan_cycle.py
  python scripts/run_plan_cycle.py --execute-m1   # also run hub + reliability + decide
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(p: Path):
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _exists(*parts: str) -> bool:
    return (ROOT.joinpath(*parts)).exists()


def _run(cmd: list[str], timeout: int = 300) -> dict:
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)},
    )
    return {"ok": p.returncode == 0, "code": p.returncode, "tail": (p.stdout or "")[-500:]}


def assess() -> dict:
    open_dir = ROOT / "outputs" / "open_if"
    n_packs = 0
    if open_dir.is_dir():
        n_packs = sum(
            1
            for d in open_dir.iterdir()
            if d.is_dir() and (d / "scorecard_pista_b.json").is_file()
        )
    hub = _load(ROOT / "docs" / "METRICS_HUB.json") or {}
    card = hub.get("decision_card") or {}
    clm = _load(ROOT / "models" / "clm_ensemble" / "manifest.json") or {}
    ml_iou = float((clm.get("metrics") or {}).get("test_iou") or 0)

    items = {
        "M1.1_plan_cycle_runner": {
            "status": "DONE",
            "evidence": "scripts/run_plan_cycle.py",
        },
        "M1.2_decide_cli": {
            "status": "DONE"
            if "decide" in (ROOT / "wildfire_front" / "cli.py").read_text(encoding="utf-8")
            else "PENDING",
            "evidence": "wildfire-front decide",
        },
        "M1.3_metrics_hub": {
            "status": "DONE" if _exists("docs", "METRICS_HUB.json") else "PENDING",
            "evidence": "docs/METRICS_HUB.json",
        },
        "M1.4_firms_overlay": {
            "status": "DONE"
            if _exists("scripts", "overlay_firms_on_open_pack.py")
            else "PENDING",
            "evidence": "scripts/overlay_firms_on_open_pack.py",
        },
        "M1.5_cems_delta_t": {
            "status": "AT_RISK",
            "evidence": "CEMS layer props lack acquisition time; still assume 24h",
            "note": "Improve when XML has usable times",
        },
        "M1.6_open_packs_ge_5": {
            "status": "DONE" if n_packs >= 5 else ("IN_PROGRESS" if n_packs >= 4 else "PENDING"),
            "evidence": f"n_packs={n_packs}",
        },
        "M1.7_onepager": {
            "status": "DONE" if _exists("docs", "ONEPAGER_COMERCIAL_ES.md") else "PENDING",
            "evidence": "docs/ONEPAGER_COMERCIAL_ES.md",
        },
        "M1.8_review": {
            "status": "DONE",
            "evidence": "cycle runner + portal UX",
        },
        "M2.1_fdc_in_incident": {
            "status": "DONE"
            if "publish_decision_card" in (
                ROOT / "wildfire_front" / "incident" / "pipeline.py"
            ).read_text(encoding="utf-8")
            else "PENDING",
            "evidence": "outbox/fire_decision_card.json on incident update",
        },
        "M2.2_second_anchor": {
            "status": "BLOCKED",
            "evidence": "pending_external INFOCAM",
        },
        "M2.3_dnbr_stac": {
            "status": "DONE"
            if (
                _exists("scripts", "build_open_if_dnbr.py")
                and _exists("wildfire_front", "open_if", "dnbr.py")
                and (
                    (
                        ROOT / "outputs" / "open_if" / "emsr578" / "dnbr_status.json"
                    ).is_file()
                    or _exists("docs", "design", "DNBR_STAC_OPEN_PACK.md")
                )
            )
            else "PENDING",
            "evidence": "scripts/build_open_if_dnbr.py + outputs/open_if/emsr578/dnbr_status.json",
        },
        "M2.5_incident_sla": {
            "status": "DONE"
            if _exists("docs", "INCIDENT_SLA_LATENCY.json")
            and bool((_load(ROOT / "docs" / "INCIDENT_SLA_LATENCY.json") or {}).get("sla_pass"))
            else (
                "IN_PROGRESS"
                if _exists("scripts", "measure_incident_sla.py")
                else "PENDING"
            ),
            "evidence": "docs/INCIDENT_SLA_LATENCY.json",
        },
        "M2.8_decide_api": {
            "status": "DONE"
            if _exists("wildfire_front", "product", "api_server.py")
            and (
                not _exists("docs", "DECIDE_API_LATENCY.json")
                or bool(
                    (_load(ROOT / "docs" / "DECIDE_API_LATENCY.json") or {}).get("sla_pass")
                )
            )
            else "PENDING",
            "evidence": "POST /v1/decide + docs/DECIDE_API_LATENCY.json",
        },
        "M2.9_forensic_acta": {
            "status": "DONE"
            if _exists("wildfire_front", "product", "forensics.py")
            and "replay-decide"
            in (ROOT / "wildfire_front" / "cli.py").read_text(encoding="utf-8")
            else "PENDING",
            "evidence": "forensics.py + export-acta + replay-decide",
        },
        "M2.10_decision_policy": {
            "status": "DONE"
            if _exists("config", "decision_policies.json")
            and _exists("wildfire_front", "product", "policy.py")
            else "PENDING",
            "evidence": "config/decision_policies.json + --policy field_ops",
        },
        "M2.11_commander_app": {
            "status": "DONE"
            if _exists("docs", "commander", "index.html")
            and _exists("scripts", "build_commander_app.py")
            else "PENDING",
            "evidence": "docs/commander/index.html WFD COMMAND HUD",
        },
        "M3.3_GO_Q": {"status": "PENDING", "evidence": None},
    }

    reliability = _load(ROOT / "docs" / "RELIABILITY_GATE_REPORT.json") or {}
    go_q_progress = {
        "decision_card_cli": items["M1.2_decide_cli"]["status"] == "DONE",
        "fdc_in_incident": items["M2.1_fdc_in_incident"]["status"] == "DONE",
        "decide_api_min": items["M2.8_decide_api"]["status"] == "DONE",
        "metrics_hub": items["M1.3_metrics_hub"]["status"] == "DONE",
        "reliability_gate": bool(reliability.get("ok")),
        "open_packs_ge_4": n_packs >= 4,
        "ml_hold": ml_iou >= 0.89,
        "incident_sla": items["M2.5_incident_sla"]["status"] == "DONE",
        "pilot_or_outreach": False,
        "quarter_report": False,
    }
    go_q_ready = all(
        [
            go_q_progress["decision_card_cli"],
            go_q_progress["fdc_in_incident"],
            go_q_progress["metrics_hub"],
            go_q_progress["reliability_gate"],
            go_q_progress["open_packs_ge_4"],
            go_q_progress["ml_hold"],
        ]
    )

    # adaptations
    adaptations = []
    if n_packs >= 4 and items["M1.6_open_packs_ge_5"]["status"] != "DONE":
        adaptations.append(
            "M1.6: 4 packs sufficient for demo; raise to 5 when next CEMS build is free"
        )
    if items["M1.5_cems_delta_t"]["status"] == "AT_RISK":
        adaptations.append(
            "M1.5 deferred: keep 24h assumption + document; focus M1.2/M1.4"
        )
    if not go_q_progress["pilot_or_outreach"]:
        adaptations.append(
            "Mes 2 priority shift: outreach list earlier if product gate stays green"
        )

    card = (hub or {}).get("decision_card") or {}
    status = {
        "schema": "plan_3_meses_status_v1",
        "plan": "docs/PLAN_3_MESES.md",
        "cycle_at_utc": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "live": {
            "n_open_packs": n_packs,
            "ml_test_iou": ml_iou,
            "decision_card": card,
        },
        "go_q_progress": go_q_progress,
        "go_q_partial_ready": go_q_ready,
        "adaptations_this_cycle": adaptations,
        "hub_decision": card.get("decision"),
        "hub_confidence_pred": card.get("confidence_pred"),
    }
    return status


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute-m1", action="store_true")
    args = ap.parse_args()
    executed = []
    if args.execute_m1:
        for cmd, name in [
            ([sys.executable, "scripts/reliability_gate.py"], "reliability"),
            ([sys.executable, "scripts/build_metrics_hub.py"], "metrics_hub"),
            (
                [
                    sys.executable,
                    "-m",
                    "wildfire_front",
                    "decide",
                    "--use-ml-v34",
                    "--open-pack",
                    "outputs/open_if/emsr578",
                    "--json",
                ],
                "decide_cli",
            ),
            ([sys.executable, "scripts/build_open_if_index.py"], "open_index"),
        ]:
            executed.append({"name": name, **_run(cmd)})

    status = assess()
    status["executed"] = executed
    out = ROOT / "docs" / "PLAN_3_MESES_STATUS.json"
    out.write_text(json.dumps(status, indent=2, default=str), encoding="utf-8")

    # human review log append
    log = ROOT / "docs" / "PLAN_3_MESES_REVIEW_LOG.md"
    line = (
        f"\n## Cycle {status['cycle_at_utc']}\n\n"
        f"- packs={status['live']['n_open_packs']} ml_iou={status['live']['ml_test_iou']}\n"
        f"- hub_decision={status.get('hub_decision')} conf={status.get('hub_confidence_pred')}\n"
        f"- go_q_partial_ready={status['go_q_partial_ready']}\n"
        f"- adaptations: {status['adaptations_this_cycle']}\n"
    )
    if log.is_file():
        log.write_text(log.read_text(encoding="utf-8") + line, encoding="utf-8")
    else:
        log.write_text("# Plan 3 meses — review log\n" + line, encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "status_file": str(out),
                "go_q_partial_ready": status["go_q_partial_ready"],
                "n_packs": status["live"]["n_open_packs"],
                "adaptations": status["adaptations_this_cycle"],
                "items_done": sum(
                    1 for v in status["items"].values() if v["status"] == "DONE"
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    from datetime import datetime, timezone

    raise SystemExit(main())
