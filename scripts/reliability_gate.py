#!/usr/bin/env python3
"""Reliability gate: enforce abstention + provenance (five-nines design bound).

Does NOT claim 99.9999% fire prediction accuracy.
Fails hard if a card would GO without sufficient sources.

Output
------
Writes a **run-local** report under ``outputs/reliability_gate_report.json``
by default. Optionally updates ``docs/RELIABILITY_GATE_REPORT.json`` as a
**suite-only sample** (``suite_only=true``, ``field_unlock=false``, checks
cleared) so it cannot unlock field_ops GO. Operators must not copy the docs
sample into an incident outbox as a production unlock key.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.product.confidence import (  # noqa: E402
    Decision,
    build_decision_card,
    content_hash,
    system_reliability_report,
)


def _measure_provenance_ok(samples: dict[str, Any]) -> bool:
    """R4: sample cards must carry schema + input/output content hashes."""
    if not samples:
        return False
    for name, card in samples.items():
        if not isinstance(card, dict):
            return False
        audit = card.get("audit")
        if not isinstance(audit, dict):
            return False
        if audit.get("schema") != "fire_decision_card_v1":
            return False
        ih = audit.get("input_hash")
        oh = audit.get("output_hash")
        if not isinstance(ih, str) or len(ih) < 16:
            return False
        if not isinstance(oh, str) or len(oh) < 16:
            return False
        # Hashes must look like hex digests
        try:
            int(ih, 16)
            int(oh, 16)
        except (TypeError, ValueError):
            return False
        _ = name
    return True


def build_suite_report() -> dict[str, Any]:
    failures: list[str] = []

    # 1) empty → ABSTAIN
    empty = build_decision_card("test_empty")
    if empty.decision != Decision.ABSTAIN:
        failures.append("empty_sources_must_abstain")

    # 2) open-only → not GO (HOLD or ABSTAIN)
    open_only = build_decision_card(
        "test_open",
        open_metrics={
            "max_area_ha": 2500,
            "n_timeline_steps": 5,
            "activation": "EMSR578",
            "O2_cems_delineation": "GO",
        },
        require_ops_for_go=True,
    )
    if open_only.decision == Decision.GO:
        failures.append("open_only_must_not_go_when_ops_required")

    # 3) ops A + open → may GO
    both = build_decision_card(
        "test_both",
        ops_metrics={
            "quality_grade": "A",
            "primary_ros_m_min": 5.7,
            "n_frames_staged": 20,
            "area_ha_max": 39,
            "speed_vs_ref_ratio": 0.81,
        },
        open_metrics={
            "max_area_ha": 2500,
            "n_timeline_steps": 4,
            "activation": "EMSR578",
        },
        ml_metrics={
            "test_iou": 0.8963,
            "improvement_vs_copy_iou": 0.2545,
            "model_iou_growth": 0.9071,
        },
    )
    if both.decision == Decision.ABSTAIN:
        failures.append("strong_ops_open_should_not_abstain")

    # 4) determinism: same input → same output hash
    a = build_decision_card(
        "det",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
    )
    b = build_decision_card(
        "det",
        ml_metrics={"test_iou": 0.9, "improvement_vs_copy_iou": 0.25},
    )
    # confidence path deterministic; timestamps differ — hash payload without utc
    ha = content_hash(
        {
            "d": a.decision.value,
            "c": a.confidence_pred,
            "s": a.sources,
            "r": a.reasons,
        }
    )
    hb = content_hash(
        {
            "d": b.decision.value,
            "c": b.confidence_pred,
            "s": b.sources,
            "r": b.reasons,
        }
    )
    if ha != hb:
        failures.append("determinism_hash_mismatch")

    samples = {
        "empty": empty.to_dict(),
        "open_only": open_only.to_dict(),
        "both": both.to_dict(),
    }
    provenance_ok = _measure_provenance_ok(samples)

    rel = system_reliability_report(
        gates_ok=len(failures) == 0,
        determinism_ok="determinism_hash_mismatch" not in failures,
        abstention_enforced="empty_sources_must_abstain" not in failures,
        provenance_ok=provenance_ok,
    )

    return {
        "ok": len(failures) == 0 and provenance_ok,
        "failures": failures + ([] if provenance_ok else ["provenance_hashes_missing"]),
        "suite_only": False,
        "field_unlock": True,
        "provenance": {
            "kind": "suite_run",
            "note": (
                "This-run suite report from reliability_gate.py. "
                "Not a per-incident field unlock unless event_id/hashes match."
            ),
            "sample_input_hashes": {
                k: (v.get("audit") or {}).get("input_hash") for k, v in samples.items()
            },
        },
        "system_reliability": rel,
        "samples": samples,
    }


def suite_sample_for_docs(live: dict[str, Any]) -> dict[str, Any]:
    """Neutralize a live suite report for committed docs/ (not a field key)."""
    return {
        "ok": live.get("ok"),
        "failures": live.get("failures") or [],
        "suite_only": True,
        "field_unlock": False,
        "provenance": {
            "kind": "suite_sample",
            "note": (
                "SUITE-ONLY SAMPLE — NOT a field unlock key. "
                "Consumers must reject suite_only/field_unlock=false for field_ops GO. "
                "Regenerate a this-run report via scripts/reliability_gate.py "
                "(outputs/) or the incident pipeline outbox/reliability_gate_report.json."
            ),
        },
        "system_reliability": {
            "system_reliability_pass": False,
            "status": "unknown",
            "checks": {
                "R1_determinism": None,
                "R2_gates": None,
                "R3_abstention_enforced": None,
                "R4_provenance": None,
            },
            "residual_silent_go_risk_bound": 1.0,
            "five_nines_claim": (
                "UNKNOWN: docs sample is not measured field reliability. "
                "Does NOT unlock field_ops GO."
            ),
            "fire_prediction_accuracy_claim": "NOT_CLAIMED",
        },
        "samples": live.get("samples") or {},
        "measured_suite_ok": live.get("ok"),
        "measured_suite_reliability": live.get("system_reliability"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "outputs" / "reliability_gate_report.json",
        help="Run-local report path (default: outputs/reliability_gate_report.json)",
    )
    parser.add_argument(
        "--write-docs-sample",
        action="store_true",
        help="Also write neutralized suite-only sample under docs/",
    )
    args = parser.parse_args(argv)

    report = build_suite_report()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    if args.write_docs_sample:
        docs_path = ROOT / "docs" / "RELIABILITY_GATE_REPORT.json"
        docs_path.write_text(
            json.dumps(suite_sample_for_docs(report), indent=2, default=str),
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "ok": report["ok"],
                "failures": report["failures"],
                "out": str(out),
                "five_nines": report["system_reliability"],
                "note": "docs sample is suite-only; not a field unlock key",
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
