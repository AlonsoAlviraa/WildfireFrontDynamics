#!/usr/bin/env python3
"""Human-gated promote for ML live fusion (research_open only by default).

Reads an honest TEST U1 scorecard and writes a promote record / scorecard snapshot.
Does **not** flip ``config/decision_policies.json`` unless ``--apply-policy`` is set.
Never enables ``field_ops.allow_ml_live_in_fusion``.

Offline / synthetic scorecards are **refused** for public docs scorecard and
``--apply-policy`` unless ``--allow-lab-synthetic`` (CI lab only).

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
import re
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
MIN_REAL_PATCHES = 50

CHECKLIST = [
    "Scorecard schema_validation.pass == true",
    "gates.u1_test_honest == true (U1 on TEST with frozen VAL-fit calibrator)",
    "allow_ml_live_in_fusion_recommended == true",
    "Scorecard is real holdout eval (not offline/synthetic) unless --allow-lab-synthetic",
    "primary.model_iou is eval TEST mean (not unlabeled catalog 0.8963)",
    "calibrator_fit_split == val; never fit on TEST",
    "Dual product: not ROS, not Tobarra ops claim, not REDIAM O2 as ML IoU",
    "field_ops.allow_ml_live_in_fusion remains false",
    "research_open live fusion is experimental (lab claim surface, not tactical)",
    "Human owner reviewed fail_cases / ECE / selective curves / nested_cv if present",
]

RESEARCH_OPEN_EXPERIMENTAL_NOTE = (
    "research_open.allow_ml_live_in_fusion is experimental lab fusion only — "
    "not field_ops, not tactical dispatch, not ROS. Dual-product honesty applies."
)

_PROMOTE_ENABLE_CLAUSE_RE = re.compile(
    r"allow_ml_live_in_fusion enabled after U1 TEST honest promote \(\d{4}-\d{2}-\d{2}\)\.?"
)
_EXPERIMENTAL_CLAUSE = (
    "EXPERIMENTAL research_open live fusion only — not field_ops, not tactical."
)


def _load_scorecard(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("scorecard must be a JSON object")
    return data


def _is_offline_or_synthetic(doc: dict[str, Any]) -> bool:
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    if bool(prov.get("offline")):
        return True
    syn = prov.get("synthetic_mode")
    if syn is not None and str(syn).strip() != "" and str(syn).lower() != "none":
        return True
    if bool(doc.get("offline")):
        return True
    if doc.get("synthetic_mode") not in (None, "", "none"):
        return True
    return False


def _n_patches(doc: dict[str, Any]) -> int:
    primary = doc.get("primary") if isinstance(doc.get("primary"), dict) else {}
    unc = doc.get("uncertainty") if isinstance(doc.get("uncertainty"), dict) else {}
    for src in (primary, unc, doc):
        n = src.get("n_patches")
        if n is not None:
            try:
                return int(n)
            except (TypeError, ValueError):
                pass
    return 0


def _has_real_eval_path(doc: dict[str, Any]) -> bool:
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    eval_dir = str(prov.get("eval_dir") or doc.get("eval_dir") or "").strip()
    if not eval_dir:
        return False
    parts = [p.lower() for p in Path(eval_dir).parts]
    if "test" not in parts:
        return False
    # Refuse LOFO / train as promote eval path
    for part in parts:
        base = part.split(".")[0]
        if base == "train" or base == "lofo" or base.startswith("lofo"):
            return False
    return True


def validate_promote_eligibility(
    doc: dict[str, Any],
    *,
    allow_lab_synthetic: bool = False,
) -> list[str]:
    """Return refusal reasons; empty = eligible for promote / policy / docs scorecard.

    Real promote (default) requires:
    * schema + u1_test_honest + recommended + TEST eval + VAL-fit calibrator
    * not offline / not synthetic (unless allow_lab_synthetic)
    * n_patches >= 50 **or** provenance.eval_dir looks like a real holdout test path
    """
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
        fails.append("ml_product_go_already_true_unexpected")

    # Real-data rails (Issue 2): refuse offline/synthetic unless explicit lab override
    if not allow_lab_synthetic:
        if _is_offline_or_synthetic(doc):
            fails.append("offline_or_synthetic_scorecard")
        n = _n_patches(doc)
        real_path = _has_real_eval_path(doc)
        if n < MIN_REAL_PATCHES and not real_path:
            fails.append(
                f"insufficient_real_patches:n={n}<{MIN_REAL_PATCHES}_and_no_real_eval_dir"
            )
        prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
        if prov.get("identity_calibrator") is True:
            fails.append("identity_calibrator")
        if prov.get("frozen_calibrator") is False:
            fails.append("calibrator_not_frozen")

    return fails


def build_public_product_scorecard(
    doc: dict[str, Any],
    *,
    eligible: bool,
    promote_record_path: Path | None,
) -> dict[str, Any]:
    """Lab claim surface for docs/ML_PRODUCT_SCORECARD.json (no ROS, dual honesty)."""
    from wildfire_front.ml.u1_eval import FIXED_HONESTY_NOTES, catalog_holdout_test_reference

    snapshot = dict(doc)
    gates = dict(snapshot.get("gates") or {})
    gates["ml_product_go"] = False
    gates["promote_draft"] = True
    gates["promote_eligible"] = bool(eligible)
    snapshot["gates"] = gates
    prov = dict(snapshot.get("provenance") or {})
    prov["promote_draft"] = True
    if promote_record_path is not None:
        prov["promote_record"] = str(promote_record_path).replace("\\", "/")
    if "catalog_holdout_test_reference" not in prov:
        prov["catalog_holdout_test_reference"] = catalog_holdout_test_reference()
    if "nested_cv" not in prov and isinstance(doc.get("nested_cv"), dict):
        prov["nested_cv"] = doc["nested_cv"]
    honesty = list(prov.get("honesty_notes") or FIXED_HONESTY_NOTES)
    if RESEARCH_OPEN_EXPERIMENTAL_NOTE not in honesty:
        honesty.append(RESEARCH_OPEN_EXPERIMENTAL_NOTE)
    prov["honesty_notes"] = honesty
    prov["lab_claim_surface"] = True
    prov["not_tactical"] = True
    prov["not_ros"] = True
    prov["research_open_live_fusion"] = "experimental"
    snapshot["provenance"] = prov
    snapshot["claim_surface"] = {
        "kind": "lab_ml_product_scorecard",
        "not_tactical": True,
        "not_field_ops": True,
        "not_ros": True,
        "research_open_live_fusion": "experimental",
        "primary_is_test_eval_mean": True,
        "catalog_reference_separate": True,
    }
    primary = snapshot.get("primary") if isinstance(snapshot.get("primary"), dict) else {}
    for bad in (
        "primary_ros_m_min",
        "ros_area_m_min",
        "ros_equiv_radius_m_min",
        "vp_tactical",
        "ros_m_min",
    ):
        primary.pop(bad, None)
    snapshot["primary"] = primary
    return snapshot


def build_promote_record(
    doc: dict[str, Any],
    *,
    scorecard_path: Path,
    apply_policy: bool,
    policy_applied: bool,
    allow_lab_synthetic: bool = False,
) -> dict[str, Any]:
    from wildfire_front.ml.u1_eval import FIXED_HONESTY_NOTES

    gates = doc.get("gates") or {}
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    nested = prov.get("nested_cv") or doc.get("nested_cv")
    honesty = list(FIXED_HONESTY_NOTES) + [RESEARCH_OPEN_EXPERIMENTAL_NOTE]
    return {
        "schema": "ml_u1_promote_record_v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "product_id": doc.get("product_id"),
        "protocol": doc.get("protocol"),
        "scorecard_path": str(scorecard_path).replace("\\", "/"),
        "u1_eval_split": doc.get("u1_eval_split") or doc.get("split"),
        "calibrator_fit_split": doc.get("calibrator_fit_split")
        or prov.get("calibrator_fit_split"),
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
            "ml_product_go": False,
        },
        "primary_eval": doc.get("primary"),
        "uncertainty": doc.get("uncertainty"),
        "nested_cv": nested,
        "human_checklist": CHECKLIST,
        "checklist_status": "pending_human_signoff",
        "allow_lab_synthetic": bool(allow_lab_synthetic),
        "policy": {
            "apply_policy_requested": bool(apply_policy),
            "policy_applied": bool(policy_applied),
            "profile_if_applied": "research_open",
            "field_ops_always_false": True,
            "research_open_experimental": True,
            "note": (
                "Only research_open.allow_ml_live_in_fusion may be set true "
                "(experimental lab fusion). field_ops stays false forever from this script."
            ),
        },
        "honesty_notes": honesty,
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
            "scripts/fit_ml_uncertainty_calibration.py",
            "wildfire_front/ml/u1_eval.py",
            "wildfire_front/ml/nested_cv.py",
            "docs/ML_PRODUCT_SCORECARD.json (lab claim surface after eligible promote)",
            "docs/ML_U1_PROMOTE_RECORD.json",
            "tests/fixtures/ml/uncertainty_calibrator_v1.json (CI only)",
            "config/decision_policies.json (policy flip only with --apply-policy)",
        ],
    }


def _normalize_research_open_notes(existing: str, *, today: str) -> str:
    """Rebuild notes without duplicate promote clauses."""
    base = str(existing or "")
    # Strip prior enable/experimental clauses; keep other note content
    cleaned = _PROMOTE_ENABLE_CLAUSE_RE.sub("", base)
    cleaned = cleaned.replace(_EXPERIMENTAL_CLAUSE, "")
    # Collapse separators
    parts = [p.strip() for p in re.split(r"\s*\|\s*", cleaned) if p.strip()]
    parts.append(
        f"allow_ml_live_in_fusion enabled after U1 TEST honest promote ({today})."
    )
    parts.append(_EXPERIMENTAL_CLAUSE)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return " | ".join(out)


def apply_research_open_policy(policy_path: Path | None = None) -> dict[str, Any]:
    """Set research_open.allow_ml_live_in_fusion=true only; never field_ops.

    ``policy_path`` defaults to module ``POLICY_PATH`` at call time (so tests can
    monkeypatch the constant). Notes are normalized (no duplicate promote lines).
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
    today = datetime.now(timezone.utc).date().isoformat()
    ro["notes"] = _normalize_research_open_notes(str(ro.get("notes") or ""), today=today)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    if policies.get("field_ops", {}).get("allow_ml_live_in_fusion") is True:
        policies["field_ops"]["allow_ml_live_in_fusion"] = False
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "research_open.allow_ml_live_in_fusion": True,
        "field_ops.allow_ml_live_in_fusion": False,
        "research_open_experimental": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Promote ML live fusion after honest TEST U1")
    p.add_argument("--scorecard", type=Path, default=DEFAULT_SCORECARD)
    p.add_argument("--promote-record", type=Path, default=DEFAULT_PROMOTE_RECORD)
    p.add_argument(
        "--product-scorecard",
        type=Path,
        default=DEFAULT_PRODUCT_SCORECARD,
        help="Snapshot path under docs/ (written when eligible)",
    )
    p.add_argument(
        "--write-docs-scorecard",
        action="store_true",
        help=(
            "Write docs product scorecard when eligible. "
            "Without this flag, eligible promote still writes the product-scorecard "
            "path (default docs/ML_PRODUCT_SCORECARD.json) for operator promote; "
            "this flag is explicit intent logging only when eligible."
        ),
    )
    p.add_argument(
        "--no-write-product-scorecard",
        action="store_true",
        help="Do not write product/docs scorecard even when eligible",
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
    p.add_argument(
        "--allow-lab-synthetic",
        action="store_true",
        help=(
            "CI/lab only: allow offline/synthetic scorecards that set u1_test_honest. "
            "Default false — public docs scorecard and --apply-policy require real TEST eval."
        ),
    )
    args = p.parse_args(argv)

    sc_path = Path(args.scorecard)
    if not sc_path.is_file():
        print(f"ERROR: scorecard not found: {sc_path}", file=sys.stderr)
        return 2

    doc = _load_scorecard(sc_path)
    fails = validate_promote_eligibility(
        doc, allow_lab_synthetic=bool(args.allow_lab_synthetic)
    )
    eligible = len(fails) == 0

    if not eligible and not args.force_draft:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reasons": fails,
                    "note": (
                        "Need gates.u1_test_honest, recommended true, and real "
                        "(non-offline/synthetic) TEST scorecard. "
                        "Run scripts/eval_ml_uncertainty_u1.py --split test first. "
                        "Lab synthetic only with --allow-lab-synthetic."
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
            "ERROR: --apply-policy refused because scorecard is not u1_test_honest eligible "
            f"(reasons={fails})",
            file=sys.stderr,
        )
        return 2

    record = build_promote_record(
        doc,
        scorecard_path=sc_path,
        apply_policy=bool(args.apply_policy),
        policy_applied=policy_applied,
        allow_lab_synthetic=bool(args.allow_lab_synthetic),
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

    out_rec = Path(args.promote_record)
    out_rec.parent.mkdir(parents=True, exist_ok=True)
    out_rec.write_text(json.dumps(record, indent=2, allow_nan=False), encoding="utf-8")

    # Write public/docs product scorecard when eligible unless suppressed.
    # --write-docs-scorecard documents explicit intent; eligible still writes by default.
    write_docs = bool(eligible) and not bool(args.no_write_product_scorecard)
    if args.write_docs_scorecard and not eligible:
        print(
            "NOTE: --write-docs-scorecard ignored (not eligible / u1_test_honest false "
            "or offline/synthetic without --allow-lab-synthetic)",
            file=sys.stderr,
        )

    out_sc = None
    if write_docs:
        snapshot = build_public_product_scorecard(
            doc, eligible=eligible, promote_record_path=out_rec
        )
        out_sc = Path(args.product_scorecard)
        out_sc.parent.mkdir(parents=True, exist_ok=True)
        out_sc.write_text(
            json.dumps(snapshot, indent=2, allow_nan=False), encoding="utf-8"
        )

    print(
        json.dumps(
            {
                "status": "ok" if eligible else "draft_refused",
                "eligible": eligible,
                "reasons": fails,
                "wrote_promote_record": str(out_rec),
                "wrote_product_scorecard": str(out_sc) if out_sc else None,
                "write_docs_scorecard": bool(args.write_docs_scorecard),
                "allow_lab_synthetic": bool(args.allow_lab_synthetic),
                "policy_applied": policy_applied,
                "ml_product_go": False,
                "research_open_experimental": True,
                "field_ops_allow_ml_live_in_fusion": False,
                "note": (
                    "Promote record is a human checklist. "
                    "docs/ML_PRODUCT_SCORECARD.json is lab claim surface (not tactical). "
                    "field_ops fusion stays false. "
                    "ml_product_go never auto-true. "
                    "Offline/synthetic refused unless --allow-lab-synthetic."
                ),
            },
            indent=2,
        )
    )
    return 0 if eligible else 2


if __name__ == "__main__":
    raise SystemExit(main())
