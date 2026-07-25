#!/usr/bin/env python3
"""Sprint 1 demo: ML live prediction JSON → Decision Card.

Pipeline (dual-product honest):
  pack / NPZ / offline  →  ml_prediction.json (ml_live_metrics_v1)
                      →  build_decision_card (research_open by default)
                      →  outputs under out-dir

Modes
-----
* ``offline`` (default, CI-friendly): synthetic / fixture live metrics, no weights.
* ``live``: run ensemble ``predict_with_uncertainty`` when product weights exist.
* ``from-json``: reuse an existing ml_prediction / ml_live_metrics JSON.

Never invents ops ROS / tactical Vp. Never enables field_ops fusion.
Catalog holdout IoU 0.8963 is provenance only — live Card uses patch confidence.

Examples
--------
  python scripts/run_ml_live_card_demo.py --help
  python scripts/run_ml_live_card_demo.py --mode offline --scenario hold
  python scripts/run_ml_live_card_demo.py --mode offline --scenario abstain
  python scripts/run_ml_live_card_demo.py --mode live --npz artifacts/clm_ndws_patches/holdout_v1/test --max-patches 1
  python scripts/run_ml_live_card_demo.py --mode from-json --ml-prediction path/ml_prediction.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_PRODUCT = "clm_ensemble_v34"
DEFAULT_POLICY = "research_open"
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "ml_live_card_demo"
FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "ml"
SCORECARD_PATH = PROJECT_ROOT / "docs" / "ML_PRODUCT_SCORECARD.json"
PROMOTE_PATH = PROJECT_ROOT / "docs" / "ML_U1_PROMOTE_RECORD.json"
CALIBRATOR_PRODUCT = (
    PROJECT_ROOT / "models" / "clm_ensemble" / "uncertainty_calibration_v1.json"
)

# U1 numeric fallbacks for demo banners only when scorecard is missing.
# Gates default False: never claim honest TEST / fusion-recommended without a real scorecard.
_U1_FALLBACK: dict[str, Any] = {
    "mean_iou_eval": 0.8569,
    "selective_iou_at_80": 0.9034,
    "ece_patch_conf": 0.1528,
    "catalog_holdout_iou_provenance": 0.8963,
    "u1_test_honest": False,
    "allow_ml_live_in_fusion_recommended": False,
    "field_ops_fusion": False,
    "note": (
        "U1 TEST honest metrics from scorecard when present. "
        "Fallback gates are False (not inventing u1_test_honest). "
        "Catalog 0.8963 is holdout research quality under provenance only — "
        "not live fire certainty, not ops ROS."
    ),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_u1_honesty_snapshot(
    scorecard_path: Path | None = None,
    promote_path: Path | None = None,
) -> dict[str, Any]:
    """Pull U1 TEST honest numbers for banners / demo notes (no retrain)."""
    sc = _load_json(scorecard_path or SCORECARD_PATH) or {}
    prom = _load_json(promote_path or PROMOTE_PATH) or {}
    primary = sc.get("primary") or prom.get("primary_eval") or {}
    unc = sc.get("uncertainty") or prom.get("uncertainty") or {}
    gates = sc.get("gates") or prom.get("gates_snapshot") or {}
    prov = sc.get("provenance") or {}
    cat = prov.get("catalog_holdout_test_reference") or {}

    mean_iou = primary.get("model_iou")
    if mean_iou is None:
        mean_iou = _U1_FALLBACK["mean_iou_eval"]
    sel = unc.get("selective_iou_at_80pct_coverage")
    if sel is None:
        sel = _U1_FALLBACK["selective_iou_at_80"]
    ece = unc.get("ece_patch_conf")
    if ece is None:
        ece = _U1_FALLBACK["ece_patch_conf"]
    cat_iou = cat.get("test_iou")
    if cat_iou is None:
        cat_iou = _U1_FALLBACK["catalog_holdout_iou_provenance"]

    # u1_source: scorecard when primary metrics came from ML_PRODUCT_SCORECARD
    used_scorecard = bool(sc) and (
        (isinstance(primary, dict) and primary.get("model_iou") is not None)
        or (isinstance(unc, dict) and unc.get("ece_patch_conf") is not None)
    )
    return {
        "mean_iou_eval": float(mean_iou),
        "selective_iou_at_80": float(sel),
        "ece_patch_conf": float(ece),
        "catalog_holdout_iou_provenance": float(cat_iou),
        "u1_test_honest": bool(gates.get("u1_test_honest", _U1_FALLBACK["u1_test_honest"])),
        "allow_ml_live_in_fusion_recommended": bool(
            sc.get(
                "allow_ml_live_in_fusion_recommended",
                gates.get(
                    "allow_ml_live_in_fusion_recommended",
                    _U1_FALLBACK["allow_ml_live_in_fusion_recommended"],
                ),
            )
        ),
        "field_ops_fusion": False,
        "u1_source": "scorecard" if used_scorecard else "fallback",
        "scorecard_path": str(scorecard_path or SCORECARD_PATH),
        "promote_record_path": str(promote_path or PROMOTE_PATH),
        "note": _U1_FALLBACK["note"],
    }


def build_offline_ml_prediction(
    *,
    scenario: str = "hold",
    product_id: str = DEFAULT_PRODUCT,
    event_id: str = "ml_live_card_demo",
) -> dict[str, Any]:
    """Synthetic ml_prediction_v1 compatible with decide_service / build_decision_card.

    Scenarios
    ---------
    hold:
        Actionable live confidence above research_open hold floor → ML-only HOLD.
    abstain:
        Low conf / explicit abstain (simulates identity calibrator force-abstain).
    identity:
        Neutral conf=0.5 with calibrator_id=identity and abstain=true (product path).
    """
    scenario = (scenario or "hold").strip().lower()
    if scenario not in {"hold", "abstain", "identity"}:
        raise ValueError(f"unknown offline scenario: {scenario!r}")

    if scenario == "hold":
        conf = 0.72
        abstain = False
        cal_id = "fixture_hold_v1"
        diags = {
            "mean_entropy": 0.18,
            "member_disagreement": 0.05,
            "mean_margin": 0.32,
            "n_members": 3,
        }
        note = (
            "Offline fixture: high patch confidence (not holdout IoU). "
            "Expect ML-only HOLD under research_open when trusted + not abstained."
        )
    elif scenario == "identity":
        conf = 0.5
        abstain = True
        cal_id = "identity"
        diags = {
            "mean_entropy": 0.40,
            "member_disagreement": 0.15,
            "mean_margin": 0.20,
            "n_members": 3,
        }
        note = (
            "Offline fixture: identity calibrator forces abstain on product path "
            "(conf=0.5 is not a reliability claim). Decision Card → ABSTAIN."
        )
    else:  # abstain
        conf = 0.18
        abstain = True
        cal_id = "fixture_abstain_v1"
        diags = {
            "mean_entropy": 0.65,
            "member_disagreement": 0.28,
            "mean_margin": 0.08,
            "n_members": 3,
        }
        note = (
            "Offline fixture: low patch confidence / explicit abstain. "
            "Unreliable conf → Decision Card ABSTAIN (never invent ROS)."
        )

    live = {
        "schema": "ml_live_metrics_v1",
        "product_id": product_id,
        "confidence": float(conf),
        "abstain": bool(abstain),
        "mean_entropy": float(diags["mean_entropy"]),
        "member_disagreement": float(diags["member_disagreement"]),
        "mean_margin": float(diags["mean_margin"]),
        "calibrator_id": cal_id,
        "n_members": int(diags["n_members"]),
    }
    return {
        "schema": "ml_prediction_v1",
        "product_id": product_id,
        "event_id": event_id,
        "abstain": bool(abstain),
        "confidence": float(conf),
        "diagnostics": diags,
        "ml_live_metrics": live,
        "calibrator_id": cal_id,
        "protocol": "clm_holdout_test_seed42_v1",
        "offline_fixture": True,
        "scenario": scenario,
        "honesty_note": note,
        "mask_summary": {
            "mean_prob": 0.42 if not abstain else 0.35,
            "fire_frac": 0.22 if not abstain else 0.15,
            "shape": [64, 64],
            "synthetic": True,
        },
    }


def load_fixture_ml_prediction(
    scenario: str = "hold",
    *,
    product_id: str = DEFAULT_PRODUCT,
    event_id: str = "ml_live_card_demo",
) -> dict[str, Any]:
    """Prefer on-disk fixture JSON; fall back to in-code builder."""
    name = {
        "hold": "ml_prediction_hold.json",
        "abstain": "ml_prediction_abstain.json",
        "identity": "ml_prediction_identity.json",
    }.get((scenario or "hold").strip().lower())
    if name:
        path = FIXTURE_DIR / name
        data = _load_json(path)
        if data is not None:
            data = dict(data)
            data.setdefault("product_id", product_id)
            data.setdefault("event_id", event_id)
            live = data.get("ml_live_metrics")
            if isinstance(live, dict):
                live = dict(live)
                live.setdefault("product_id", product_id)
                data["ml_live_metrics"] = live
            return data
    return build_offline_ml_prediction(
        scenario=scenario, product_id=product_id, event_id=event_id
    )


def weights_available_for_product(product_id: str = DEFAULT_PRODUCT) -> bool:
    """True when catalog product weights exist on disk (not loaded)."""
    try:
        from wildfire_front.ml.product_catalog import get_product

        spec = get_product(product_id)
        ok, _msg = spec.resolve_existing()
        return bool(ok)
    except Exception:
        ens = PROJECT_ROOT / "models" / "clm_ensemble"
        return any(ens.glob("weights_*.pt")) if ens.is_dir() else False


def _resolve_calibrator(explicit: str | None):
    from wildfire_front.ml.uncertainty import LogisticCalibrator, load_calibrator

    if explicit:
        p = Path(explicit)
        if not p.is_file():
            raise FileNotFoundError(f"--calibrator not found: {p}")
        return load_calibrator(p)
    if CALIBRATOR_PRODUCT.is_file():
        return load_calibrator(CALIBRATOR_PRODUCT)
    return LogisticCalibrator.identity()


def predict_live_ml_document(
    npz: Path,
    *,
    product_id: str = DEFAULT_PRODUCT,
    calibrator_path: str | None = None,
    abstain_below: float | None = None,
    max_patches: int = 1,
) -> dict[str, Any]:
    """Run ensemble uncertainty on NPZ (requires weights). Reuses product APIs."""
    import numpy as np

    from wildfire_front.ml.product_catalog import load_predictor_for_product
    from wildfire_front.ml.uncertainty import build_ml_prediction_document

    paths = sorted(npz.glob("*.npz")) if npz.is_dir() else [npz]
    if max_patches and max_patches > 0:
        paths = paths[: int(max_patches)]
    if not paths:
        raise FileNotFoundError(f"No NPZ under {npz}")

    predictor = load_predictor_for_product(product_id)
    if not hasattr(predictor, "predict_with_uncertainty"):
        raise TypeError(
            f"product {product_id} predictor has no predict_with_uncertainty "
            "(need ensemble for live Head A path)"
        )
    cal = _resolve_calibrator(calibrator_path)
    path = paths[0]
    with np.load(path) as data:
        seq = data["sequence"]
        current_fire = data["current_fire"]

    thr = predictor.manifest.threshold
    unc_kwargs: dict[str, Any] = {
        "threshold": thr,
        "calibrator": cal,
        "product_id": product_id,
    }
    if abstain_below is not None:
        unc_kwargs["abstain_below"] = float(abstain_below)
    unc = predictor.predict_with_uncertainty(seq, current_fire, **unc_kwargs)
    mask_summary = {
        "mean_prob": float(np.mean(unc.prob)),
        "fire_frac": float(np.mean(unc.binary)),
        "shape": list(unc.prob.shape),
        "npz_path": str(path),
        "synthetic": False,
    }
    doc = build_ml_prediction_document(unc, mask_summary=mask_summary)
    doc["offline_fixture"] = False
    doc["identity_calibrator"] = bool(getattr(cal, "is_identity", False))
    if getattr(cal, "is_identity", False):
        doc["honesty_note"] = (
            "Identity calibrator (no VAL-fit product artifact loaded) → "
            "force abstain on product path. Card must not treat conf=0.5 as certainty."
        )
    else:
        doc["honesty_note"] = (
            "Live ensemble patch confidence (Head A). Not catalog holdout IoU 0.8963; "
            "not ops ROS. HOLD/ABSTAIN from reliability, never invent tactical Vp."
        )
    return doc


def extract_ml_live_metrics(doc: dict[str, Any]) -> dict[str, Any]:
    """Normalize ml_prediction_v1 or flat ml_live_metrics_v1 for the Card."""
    from wildfire_front.product.decide_service import load_ml_live_metrics

    live = load_ml_live_metrics(doc)
    if live is None:
        raise ValueError("could not extract ml_live_metrics from document")
    return live


def build_card_from_ml_doc(
    ml_doc: dict[str, Any],
    *,
    event_id: str = "ml_live_card_demo",
    policy_id: str = DEFAULT_POLICY,
    open_metrics: dict[str, Any] | None = None,
    ops_metrics: dict[str, Any] | None = None,
    ml_metrics: dict[str, Any] | None = None,
    allow_ml_live_in_fusion: bool | None = None,
    ml_live_trusted: bool = True,
) -> dict[str, Any]:
    """Build Decision Card dict via product APIs (research_open default)."""
    from wildfire_front.product.confidence import build_decision_card
    from wildfire_front.product.policy import get_policy

    live = extract_ml_live_metrics(ml_doc)
    policy = get_policy(policy_id)
    # research_open already has allow_ml_live_in_fusion=true after U1 promote;
    # never force field_ops fusion ON from this demo.
    if str(getattr(policy, "id", "")) == "field_ops":
        fusion = False
    elif allow_ml_live_in_fusion is None:
        fusion = bool(getattr(policy, "allow_ml_live_in_fusion", False))
    else:
        fusion = bool(allow_ml_live_in_fusion)

    card = build_decision_card(
        event_id,
        ml_metrics=ml_metrics,
        ml_live_metrics=live,
        open_metrics=open_metrics,
        ops_metrics=ops_metrics,
        policy_id=policy_id,
        allow_ml_live_in_fusion=fusion,
        ml_live_trusted=ml_live_trusted,
        require_ops_for_go=bool(getattr(policy, "require_ops_for_go", False)),
        # reliability_gate intentionally omitted (pilot field_ops contrast honesty)
    )
    return card.to_dict()


def _policy_ml_live_abstain_below(policy_id: str | None) -> float:
    """Active policy floor for live conf; default matches DEFAULT_ABSTAIN_THRESHOLD."""
    try:
        from wildfire_front.product.policy import get_policy

        pol = get_policy(policy_id or DEFAULT_POLICY)
        return float(getattr(pol, "ml_live_abstain_below", 0.35))
    except Exception:
        return 0.35


def build_abstain_ece_note(
    ml_doc: dict[str, Any],
    card: dict[str, Any],
    u1: dict[str, Any],
    *,
    policy_id: str | None = None,
) -> dict[str, Any]:
    """Short metric note for S1-3: when conf is unreliable / identity → abstain."""
    live = ml_doc.get("ml_live_metrics") if isinstance(ml_doc.get("ml_live_metrics"), dict) else {}
    conf = float(
        ml_doc.get("confidence")
        if ml_doc.get("confidence") is not None
        else live.get("confidence") or 0.0
    )
    abstain_flag = bool(ml_doc.get("abstain") if "abstain" in ml_doc else live.get("abstain"))
    cal_id = str(ml_doc.get("calibrator_id") or live.get("calibrator_id") or "")
    identity = bool(ml_doc.get("identity_calibrator")) or cal_id.lower() == "identity"
    decision = str(card.get("decision") or "")
    ece = float(u1.get("ece_patch_conf") or 0.0)
    floor = _policy_ml_live_abstain_below(policy_id)
    conf_below_floor = conf < floor

    reasons: list[str] = []
    if identity:
        reasons.append(
            "Identity calibrator (unfitted) forces product-path abstain; "
            "conf=0.5 is not calibrated reliability."
        )
    if abstain_flag:
        reasons.append(
            f"Explicit live abstain=true (payload). confidence={conf:.3f}."
        )
    if conf_below_floor and not abstain_flag:
        # Only when conf alone trips the floor without an explicit abstain flag.
        reasons.append(
            f"Live patch confidence={conf:.3f} below policy "
            f"ml_live_abstain_below={floor:.3f} (policy={policy_id or DEFAULT_POLICY})."
        )
    elif conf_below_floor and abstain_flag:
        # Both true: keep a separate threshold reason for audit clarity.
        reasons.append(
            f"Live patch confidence={conf:.3f} also below policy "
            f"ml_live_abstain_below={floor:.3f} (policy={policy_id or DEFAULT_POLICY})."
        )

    # Lab ECE is always context; "prefer ABSTAIN" only when the card is refusing
    # or conf is marginal relative to the active policy floor.
    lab_context: dict[str, Any] = {
        "u1_ece_patch_conf": ece,
        "u1_mean_iou_eval": u1.get("mean_iou_eval"),
        "u1_selective_iou_at_80": u1.get("selective_iou_at_80"),
        "catalog_holdout_iou_provenance_only": u1.get("catalog_holdout_iou_provenance"),
        "note": (
            f"Lab ECE patch conf ≈ {ece:.3f} on TEST (U1 residual). "
            "Catalog holdout 0.8963 is provenance only — not live certainty."
        ),
    }
    marginal = conf_below_floor or conf < (floor + 0.10)
    if ece >= 0.12 and (decision == "ABSTAIN" or marginal):
        reasons.append(
            f"Lab ECE patch conf ≈ {ece:.3f} on TEST (U1). "
            "When calibration is weak, prefer ABSTAIN over overconfident HOLD/GO."
        )

    if decision == "ABSTAIN":
        summary = (
            "Card ABSTAIN is the honest outcome when live reliability is weak, "
            "identity calibrator is used, or conf is below policy threshold."
        )
    elif decision == "HOLD":
        summary = (
            "Card HOLD: usable monitoring signal from live ML reliability "
            f"(policy={policy_id or DEFAULT_POLICY}). "
            "Not a tactical dispatch order; not ops ROS."
        )
    else:
        summary = (
            f"Card decision={decision}. GO from ML-only without ops is not the "
            "intended demo claim surface; re-check policy and sources."
        )

    return {
        "schema": "ml_live_abstain_ece_note_v1",
        "decision": decision,
        "live_confidence": conf,
        "live_abstain": abstain_flag,
        "identity_calibrator": identity,
        "calibrator_id": cal_id,
        "policy_id": policy_id or DEFAULT_POLICY,
        "ml_live_abstain_below": floor,
        "conf_below_policy_floor": conf_below_floor,
        "u1_ece_patch_conf": ece,
        "u1_mean_iou_eval": u1.get("mean_iou_eval"),
        "u1_selective_iou_at_80": u1.get("selective_iou_at_80"),
        "catalog_holdout_iou_provenance_only": u1.get("catalog_holdout_iou_provenance"),
        "field_ops_allow_ml_live_in_fusion": False,
        "lab_context": lab_context,
        "reasons": reasons,
        "summary": summary,
        "refs": {
            "scorecard": u1.get("scorecard_path"),
            "promote_record": u1.get("promote_record_path"),
            "design": "docs/design/ML_FOCUS_PRODUCT_V1.md",
            "note_doc": "docs/ML_LIVE_ABSTAIN_ECE_NOTE.md",
        },
    }


def run_demo(
    *,
    mode: str = "offline",
    scenario: str = "hold",
    product_id: str = DEFAULT_PRODUCT,
    policy_id: str = DEFAULT_POLICY,
    event_id: str = "ml_live_card_demo",
    out_dir: Path | None = None,
    npz: Path | None = None,
    ml_prediction_path: Path | None = None,
    open_pack: Path | None = None,
    work_dir: Path | None = None,
    ops_metrics: dict[str, Any] | None = None,
    calibrator: str | None = None,
    max_patches: int = 1,
    include_catalog_ml_metrics: bool = False,
    allow_missing_open_pack: bool = False,
) -> dict[str, Any]:
    """End-to-end: ML prediction doc → Decision Card → write artifacts."""
    out = Path(out_dir) if out_dir else DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    u1 = load_u1_honesty_snapshot()
    mode = (mode or "offline").strip().lower()

    if mode == "from-json":
        if ml_prediction_path is None or not Path(ml_prediction_path).is_file():
            raise FileNotFoundError("--ml-prediction required for mode=from-json")
        ml_doc = _load_json(Path(ml_prediction_path))
        if not ml_doc:
            raise ValueError(f"invalid ml prediction JSON: {ml_prediction_path}")
        ml_doc = dict(ml_doc)
        ml_doc.setdefault("offline_fixture", False)
    elif mode == "live":
        if npz is None:
            raise ValueError("--npz required for mode=live")
        if not weights_available_for_product(product_id):
            raise FileNotFoundError(
                f"weights for {product_id} not available; use --mode offline "
                "or install product weights under models/"
            )
        ml_doc = predict_live_ml_document(
            Path(npz),
            product_id=product_id,
            calibrator_path=calibrator,
            max_patches=max_patches,
        )
        ml_doc["event_id"] = event_id
    else:
        # offline
        ml_doc = load_fixture_ml_prediction(
            scenario, product_id=product_id, event_id=event_id
        )

    open_metrics = None
    if open_pack is not None:
        from wildfire_front.product.decide_service import load_open_metrics_from_pack

        open_metrics = load_open_metrics_from_pack(
            open_pack, base=PROJECT_ROOT, include_repo_root=True
        )
        if open_metrics is None and not allow_missing_open_pack:
            pack_p = Path(open_pack)
            raise FileNotFoundError(
                f"--open-pack did not yield open metrics: path={pack_p} "
                "(missing pack dir or unresolved scorecard: "
                "scorecard_pista_b.json / scorecard_and_industrial.json / "
                "scorecard_ext_industrial.json / scorecard_*_industrial.json). "
                "Pass --allow-missing-open-pack to continue as ML-only."
            )

    resolved_ops = ops_metrics
    if resolved_ops is None and work_dir is not None:
        from wildfire_front.product.decide_service import load_ops_metrics_from_work_dir

        resolved_ops = load_ops_metrics_from_work_dir(
            work_dir, base=PROJECT_ROOT, include_repo_root=True
        )

    ml_metrics = None
    if include_catalog_ml_metrics:
        # Catalog holdout as research metadata only (weight 0 / holdout_quality).
        ml_metrics = {
            "test_iou": float(u1["catalog_holdout_iou_provenance"]),
            "improvement_vs_copy_iou": 0.2545,
            "product_id": product_id,
            "role": "holdout_quality",
            "note": "Catalog provenance only — not live certainty.",
        }

    card = build_card_from_ml_doc(
        ml_doc,
        event_id=event_id,
        policy_id=policy_id,
        open_metrics=open_metrics,
        ops_metrics=resolved_ops,
        ml_metrics=ml_metrics,
    )
    note = build_abstain_ece_note(ml_doc, card, u1, policy_id=policy_id)

    pred_path = out / "ml_prediction.json"
    card_path = out / "decision_card.json"
    note_path = out / "abstain_ece_note.json"
    summary_path = out / "demo_summary.json"
    readme_path = out / "README.md"

    pred_path.write_text(json.dumps(ml_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    card_path.write_text(json.dumps(card, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    note_path.write_text(json.dumps(note, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = {
        "schema": "ml_live_card_demo_summary_v1",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "mode": mode,
        "scenario": scenario if mode == "offline" else None,
        "product_id": product_id,
        "policy_id": policy_id,
        "event_id": event_id,
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "confidence_pred_label": card.get("confidence_pred_label"),
        "reasons": card.get("reasons"),
        "disclaimers": card.get("disclaimers"),
        "live_ok": (card.get("metrics") or {}).get("live_ok"),
        "live_available": (card.get("metrics") or {}).get("live_available"),
        "allow_ml_live_in_fusion": (card.get("metrics") or {}).get("allow_ml_live_in_fusion"),
        "field_ops_fusion_always_false": True,
        "u1_honest": u1,
        "abstain_ece_note": note,
        "outputs": {
            "ml_prediction": str(pred_path.relative_to(PROJECT_ROOT))
            if pred_path.is_relative_to(PROJECT_ROOT)
            else str(pred_path),
            "decision_card": str(card_path.relative_to(PROJECT_ROOT))
            if card_path.is_relative_to(PROJECT_ROOT)
            else str(card_path),
            "abstain_ece_note": str(note_path.relative_to(PROJECT_ROOT))
            if note_path.is_relative_to(PROJECT_ROOT)
            else str(note_path),
        },
        "honesty": [
            "Ops ≠ ML; fuse only at Decision Card; never train on fused labels.",
            "No tactical Vp/ROS invented from open packs or ML masks.",
            "Catalog holdout IoU 0.8963 is provenance only — not live fire certainty.",
            f"U1 TEST honest: mean IoU eval ≈ {u1['mean_iou_eval']:.3f}, "
            f"selective@80 ≈ {u1['selective_iou_at_80']:.3f}, "
            f"ECE ≈ {u1['ece_patch_conf']:.3f}.",
            "research_open live fusion is experimental lab surface; field_ops fusion OFF.",
        ],
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    readme = "\n".join(
        [
            "# ML live → Decision Card demo",
            "",
            f"- **Decision:** `{card.get('decision')}`",
            f"- **confidence_pred:** {card.get('confidence_pred')}",
            f"- **policy:** `{policy_id}`",
            f"- **mode:** `{mode}`",
            "",
            "## U1 TEST honest (lab claim surface)",
            f"- mean IoU eval ≈ **{u1['mean_iou_eval']:.3f}**",
            f"- selective@80 ≈ **{u1['selective_iou_at_80']:.3f}**",
            f"- ECE patch conf ≈ **{u1['ece_patch_conf']:.3f}**",
            f"- catalog holdout IoU **{u1['catalog_holdout_iou_provenance']:.4f}** = provenance only",
            "",
            "## Outputs",
            "- `ml_prediction.json`",
            "- `decision_card.json`",
            "- `abstain_ece_note.json`",
            "- `demo_summary.json`",
            "",
            "## Constraints",
            "- Not a tactical dispatch order.",
            "- field_ops.allow_ml_live_in_fusion remains false.",
            "- Dual product: ML mask confidence ≠ ops ROS.",
            "",
        ]
    )
    readme_path.write_text(readme, encoding="utf-8")

    summary["_paths"] = {
        "out_dir": str(out),
        "ml_prediction": str(pred_path),
        "decision_card": str(card_path),
        "abstain_ece_note": str(note_path),
        "demo_summary": str(summary_path),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Demo: ML live prediction → Decision Card (research_open). "
            "Offline fixture by default (no weights)."
        )
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "live", "from-json"),
        default="offline",
        help="offline=fixture (CI), live=ensemble+weights, from-json=existing prediction",
    )
    parser.add_argument(
        "--scenario",
        choices=("hold", "abstain", "identity"),
        default="hold",
        help="Offline fixture scenario (default: hold)",
    )
    parser.add_argument("--product", default=DEFAULT_PRODUCT, help="Catalog product id")
    parser.add_argument(
        "--policy",
        default=DEFAULT_POLICY,
        help="Decision policy id (default: research_open; never use field_ops for fusion ON)",
    )
    parser.add_argument("--event-id", default="ml_live_card_demo")
    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT),
        help="Output directory (default: outputs/ml_live_card_demo)",
    )
    parser.add_argument(
        "--npz",
        type=str,
        default=None,
        help="NPZ file or directory for mode=live",
    )
    parser.add_argument(
        "--ml-prediction",
        type=str,
        default=None,
        help="Existing ml_prediction.json for mode=from-json",
    )
    parser.add_argument(
        "--open-pack",
        type=str,
        default=None,
        help="Optional open industrial pack for multi-source Card (no invented Vp)",
    )
    parser.add_argument(
        "--allow-missing-open-pack",
        action="store_true",
        help=(
            "If --open-pack is set but pack/scorecard is missing, continue as ML-only "
            "(default: error)"
        ),
    )
    parser.add_argument("--calibrator", type=str, default=None, help="Override calibrator JSON")
    parser.add_argument("--max-patches", type=int, default=1)
    parser.add_argument(
        "--include-catalog-ml",
        action="store_true",
        help="Also attach catalog holdout IoU as research metadata (weight 0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print demo_summary JSON only",
    )
    args = parser.parse_args(argv)

    try:
        summary = run_demo(
            mode=args.mode,
            scenario=args.scenario,
            product_id=args.product,
            policy_id=args.policy,
            event_id=args.event_id,
            out_dir=Path(args.out_dir),
            npz=Path(args.npz) if args.npz else None,
            ml_prediction_path=Path(args.ml_prediction) if args.ml_prediction else None,
            open_pack=Path(args.open_pack) if args.open_pack else None,
            calibrator=args.calibrator,
            max_patches=int(args.max_patches),
            include_catalog_ml_metrics=bool(args.include_catalog_ml),
            allow_missing_open_pack=bool(args.allow_missing_open_pack),
        )
    except (FileNotFoundError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({k: v for k, v in summary.items() if not k.startswith("_")}, indent=2))
    else:
        u1 = summary.get("u1_honest") or {}
        print("=== ML live → Decision Card demo ===")
        print(f"mode={summary.get('mode')}  policy={summary.get('policy_id')}")
        conf_v = summary.get("confidence_pred")
        conf_s = f"{float(conf_v):.3f}" if conf_v is not None else "n/a"
        print(f"decision={summary.get('decision')}  conf={conf_s}")
        print(
            f"U1 TEST honest: mean_IoU≈{float(u1.get('mean_iou_eval', 0)):.3f}  "
            f"sel@80≈{float(u1.get('selective_iou_at_80', 0)):.3f}  "
            f"ECE≈{float(u1.get('ece_patch_conf', 0)):.3f}"
        )
        print(
            f"catalog holdout IoU {float(u1.get('catalog_holdout_iou_provenance', 0.8963)):.4f} "
            "= provenance only (not live certainty)"
        )
        note = summary.get("abstain_ece_note") or {}
        print(f"note: {note.get('summary')}")
        paths = summary.get("_paths") or {}
        print(f"wrote: {paths.get('out_dir')}")
        for key in ("ml_prediction", "decision_card", "abstain_ece_note", "demo_summary"):
            if paths.get(key):
                print(f"  - {paths[key]}")
        for h in summary.get("honesty") or []:
            print(f"  · {h}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
