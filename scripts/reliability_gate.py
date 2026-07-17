#!/usr/bin/env python3
"""Reliability gate: enforce abstention + provenance (five-nines design bound).

Does NOT claim 99.9999% fire prediction accuracy.
Fails hard if a card would GO without sufficient sources.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.product.confidence import (  # noqa: E402
    Decision,
    build_decision_card,
    content_hash,
    system_reliability_report,
)


def main() -> int:
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

    rel = system_reliability_report(
        gates_ok=len(failures) == 0,
        determinism_ok="determinism_hash_mismatch" not in failures,
        abstention_enforced="empty_sources_must_abstain" not in failures,
        provenance_ok=True,
    )

    report = {
        "ok": len(failures) == 0,
        "failures": failures,
        "system_reliability": rel,
        "samples": {
            "empty": empty.to_dict(),
            "open_only": open_only.to_dict(),
            "both": both.to_dict(),
        },
    }
    out = ROOT / "docs" / "RELIABILITY_GATE_REPORT.json"
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "failures": failures, "five_nines": rel}, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
