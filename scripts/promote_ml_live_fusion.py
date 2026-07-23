#!/usr/bin/env python3
"""Human-gated promote for ML live fusion (research_open only by default).

Reads an honest TEST U1 scorecard and writes a promote record / scorecard snapshot.
Does **not** flip ``config/decision_policies.json`` unless ``--apply-policy`` is set.
Never enables ``field_ops.allow_ml_live_in_fusion``.

Usage::

  $env:PYTHONPATH = "."
  python scripts/promote_ml_live_fusion.py \\
    --scorecard outputs/ml_eval/scorecards/ml_scorecard_u1_test.json

  # After checklist, optional policy flip (research_open only):
  python scripts/promote_ml_live_fusion.py --scorecard ... --apply-policy
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DEFAULT_SCORECARD = (
    ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_scorecard_u1_test.json"
)
DEFAULT_PROMOTE_RECORD = ROOT / "docs" / "ML_U1_PROMOTE_RECORD.json"
DEFAULT_PRODUCT_SCORECARD = ROOT / "docs" / "ML_PRODUCT_SCORECARD.json"
POLICY_PATH = ROOT / "config" / "decision_policies.json"

CHECKLIST = [
    "Scorecard schema_validation.pass == true",
    "gates.u1_test_honest == true (U1 on TEST with frozen VAL-fit calibrator)",
    "allow_ml_live_in_fusion_recommended == true",
    "primary.model_iou is eval TEST mean (not unlabeled catalog 0.8963)",
    "calibrator_fit_split == val; never fit on TEST",
    "Dual product: not ROS, not Tobarra ops claim, not REDIAM O2 as ML IoU",
    "field_ops.allow_ml_live_in_fusion remains false",
    "Human owner reviewed fail_cases / ECE / selective curves",
]


def _load_scorecard(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scorecard must be a JSON object")
    return data


def validate_promote_eligibility(doc: dict[str, Any]) -> list[str]:
    """Return refusal reasons; empty = eligible for draft promote record."""
    fails: list[str] = []
    from wildfire_front.ml.scorecard_schema import validate_ml_scorecard

    schema_fails = validate_ml_scorecard(doc)
    if schema_fails:
        fails.append(f"schema_fail:{schema_fails}")
    if not (doc.get("schema_validation") or {}).get("pass", True) and schema_fails:
        fails.append("schema_validation_pass_false")

    gates = doc.get("gates") if isinstance(doc.get("gates"), dict) else {}
    if not gates.get("u1_test_honest"):
        fails.append("u1_test_honest_false")
    if not doc.get("allow_ml_live_in_fusion_recommended"):
        fails.append("allow_ml_live_in_fusion_recommended_false")
    if str(doc.get("u1_eval_split") or doc.get("split") or "").lower() != "test":
        fails.append("u1_eval_split_not_test")
    fit = str(
        doc.get("calibrator_fit_split")
        or (doc.get("provenance") or {}).get("calibrator_fit_split")
        or ""
    ).lower()
    if fit and fit != "val":
        fails.append(f"calibrator_fit_split_not_val:{fit}")
    if gates.get("ml_product_go") is True:
        # Scorecard should never auto-set this; refuse corrupted inputs.
        fails.append("ml_product_go_already_true_unexpected")
    return fails


def build_promote_record(
    doc: dict[str, Any],
    *,
    scorecard_path: Path,
    apply_policy: bool,
    policy_applied: bool,
) -> dict[str, Any]:
    from wildfire_front.ml.u1_eval import FIXED_HONESTY_NOTES

    gates = doc.get("gates") or {}
    return {
        "schema": "ml_u1_promote_record_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": doc.get("product_id"),
        "protocol": doc.get("protocol"),
        "scorecard_path": str(scorecard_path).replace("\\", "/"),
        "u1_eval_split": doc.get("u1_eval_split") or doc.get("split"),
        "calibrator_fit_split": doc.get("calibrator_fit_split")
        or (doc.get("provenance") or {}).get("calibrator_fit_split"),
        "gates_snapshot": {
            "u1_test_honest": bool(gates.get("u1_test_honest")),
            "u1_val_lab_pass": bool(gates.get("u1_val_lab_pass")),
            "u1_val_optimistic": bool(gates.get("u1_val_optimistic")),
            "U1a": bool(gates.get("U1a_selective_ge_full_minus_eps")),
            "U1b": bool(gates.get("U1b_selective_beats_random")
                        or gates.get("U1_selective_beats_random")),
            "allow_ml_live_in_fusion_recommended": bool(
                doc.get("allow_ml_live_in_fusion_recommended")
            ),
            "ml_product_go": False,  # never auto
        },
        "primary_eval": doc.get("primary"),
        "uncertainty": doc.get("uncertainty"),
        "human_checklist": CHECKLIST,
        "checklist_status": "pending_human_signoff",
        "policy": {
            "apply_policy_requested": bool(apply_policy),
            "policy_applied": bool(policy_applied),
            "profile_if_applied": "research_open",
            "field_ops_always_false": True,
            "note": (
                "Only research_open.allow_ml_live_in_fusion may be set true. "
                "field_ops stays false forever from this script."
            ),
        },
        "honesty_notes": list(FIXED_HONESTY_NOTES),
        "artifacts_local_only": [
            "models/**/*.pt (gitignored weights)",
            "models/clm_ensemble/uncertainty_calibration_v1.json (operator artifact; often gitignored)",
            "artifacts/clm_ndws_patches/** (holdout NPZ)",
            "outputs/ml_eval/scorecards/* (runtime scorecards)",
        ],
        "artifacts_in_git": [
            "scripts/eval_ml_uncertainty_u1.py",
            "scripts/promote_ml_live_fusion.py",
            "scripts/ml_scorecard.py",
            "wildfire_front/ml/u1_eval.py",
            "tests/fixtures/ml/uncertainty_calibrator_v1.json (CI only)",
            "config/decision_policies.json (policy flip only with --apply-policy)",
        ],
    }


def apply_research_open_policy(policy_path: Path | None = None) -> dict[str, Any]:
    """Set research_open.allow_ml_live_in_fusion=true only; never field_ops.

    ``policy_path`` defaults to module ``POLICY_PATH`` at call time (so tests can
    monkeypatch the constant).
    """
    path = policy_path if policy_path is not None else POLICY_PATH
    data = json.loads(path.read_text(encoding="utf-8"))
    policies = data.get("policies") or {}
    if "research_open" not in policies:
        raise KeyError("research_open policy missing")
    if "field_ops" in policies:
        policies["field_ops"]["allow_ml_live_in_fusion"] = False
    ro = policies["research_open"]
    ro["allow_ml_live_in_fusion"] = True
    ro["notes"] = (
        str(ro.get("notes") or "")
        + " | allow_ml_live_in_fusion enabled after U1 TEST honest promote "
        f"({datetime.now(timezone.utc).date().isoformat()})."
    ).strip(" |")
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "research_open.allow_ml_live_in_fusion": True,
        "field_ops.allow_ml_live_in_fusion": False,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Promote ML live fusion after honest TEST U1")
    p.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    p.add_argument("--promote-record", type=Path, default=DEFAULT_PROMOTE_RECORD)
    p.add_argument(
        "--product-scorecard",
        type=Path,
        default=DEFAULT_PRODUCT_SCORECARD,
        help="Snapshot path under docs/ (only written when eligible)",
    )
    p.add_argument(
        "--apply-policy",
        action="store_true",
        help="Also set research_open.allow_ml_live_in_fusion=true (never field_ops)",
    )
    p.add_argument(
        "--force-draft",
        action="store_true",
        help="Write draft promote record even if not eligible (status=refused)",
    )
    args = p.parse_args(argv)

    sc_path = Path(args.scorecard)
    if not sc_path.is_file():
        print(f"ERROR: scorecard not found: {sc_path}", file=sys.stderr)
        return 2

    doc = _load_scorecard(sc_path)
    fails = validate_promote_eligibility(doc)
    eligible = len(fails) == 0

    if not eligible and not args.force_draft:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reasons": fails,
                    "note": (
                        "Need gates.u1_test_honest and recommended true. "
                        "Run scripts/eval_ml_uncertainty_u1.py --split test first."
                    ),
                },
                indent=2,
            )
        )
        return 2

    policy_applied = False
    if eligible and args.apply_policy:
        try:
            apply_research_open_policy()
            policy_applied = True
        except Exception as exc:
            print(f"ERROR applying policy: {exc}", file=sys.stderr)
            return 2
    elif args.apply_policy and not eligible:
        print(
            "ERROR: --apply-policy refused because scorecard is not u1_test_honest eligible",
            file=sys.stderr,
        )
        return 2

    record = build_promote_record(
        doc,
        scorecard_path=sc_path,
        apply_policy=bool(args.apply_policy),
        policy_applied=policy_applied,
    )
    if not eligible:
        record["checklist_status"] = "refused"
        record["refusal_reasons"] = fails
    else:
        record["checklist_status"] = (
            "eligible_pending_human_signoff"
            if not policy_applied
            else "policy_applied_research_open_pending_signoff"
        )

    # Scorecard snapshot: keep ml_product_go false; annotate promote draft
    snapshot = dict(doc)
    gates = dict(snapshot.get("gates") or {})
    gates["ml_product_go"] = False
    gates["promote_draft"] = True
    gates["promote_eligible"] = eligible
    snapshot["gates"] = gates
    prov = dict(snapshot.get("provenance") or {})
    prov["promote_draft"] = True
    prov["promote_record"] = str(args.promote_record).replace("\\", "/")
    snapshot["provenance"] = prov

    out_rec = Path(args.promote_record)
    out_rec.parent.mkdir(parents=True, exist_ok=True)
    out_rec.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")

    if eligible:
        out_sc = Path(args.product_scorecard)
        out_sc.parent.mkdir(parents=True, exist_ok=True)
        out_sc.write_text(
            json.dumps(snapshot, indent=2, allow_nan=False), encoding="utf-8"
        )
    else:
        out_sc = None

    print(
        json.dumps(
            {
                "status": "ok" if eligible else "draft_refused",
                "eligible": eligible,
                "reasons": fails,
                "wrote_promote_record": str(out_rec),
                "wrote_product_scorecard": str(out_sc) if out_sc else None,
                "policy_applied": policy_applied,
                "ml_product_go": False,
                "note": (
                    "Promote record is a human checklist. "
                    "field_ops fusion stays false. "
                    "ml_product_go never auto-true."
                ),
            },
            indent=2,
        )
    )
    return 0 if eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
