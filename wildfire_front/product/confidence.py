"""Confidence + abstention engine (honest; no fake fire accuracy).

Prediction confidence is 0..1 from available quality signals.
System reliability is separate: gates that prevent silent GO failures.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any


class Decision(StrEnum):
    GO = "GO"  # emit operational recommendation (with disclaimers)
    HOLD = "HOLD"  # usable for monitoring only
    ABSTAIN = "ABSTAIN"  # do not recommend action from this product


@dataclass
class DecisionCard:
    event_id: str
    decision: Decision
    confidence_pred: float
    confidence_pred_label: str
    system_reliability_pass: bool
    sources: list[dict[str, Any]] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    disclaimers: list[str] = field(default_factory=list)
    audit: dict[str, Any] = field(default_factory=dict)
    built_at_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["decision"] = self.decision.value
        return d


DEFAULT_DISCLAIMERS = [
    "Not a tactical dispatch order.",
    "Fire-phenomenon confidence is NOT 99.9999% — that figure only applies to "
    "automated gate enforcement under test (no silent GO without sources).",
    "ML IoU is not front ROS; CEMS perimeter is not national cadastre.",
    "ABSTAIN means the product refuses to recommend action.",
]


def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _label(c: float) -> str:
    if c >= 0.75:
        return "HIGH"
    if c >= 0.45:
        return "MEDIUM"
    if c >= 0.20:
        return "LOW"
    return "VERY_LOW"


def content_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def score_ml_source(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    """Score static catalog / holdout ML metrics as research metadata.

    Catalog IoU is **not** live fire-spread confidence. Weight is 0 so fusion
    does not treat holdout quality as a phenomenon signal on field incidents.
    ``confidence`` / ``holdout_quality`` remain available for research display
    and ml-only HOLD policies.
    """
    if not metrics:
        return {
            "id": "ml",
            "available": False,
            "weight": 0.0,
            "confidence": 0.0,
            "role": "holdout_quality",
            "source_type": "research_metadata",
        }
    iou = float(metrics.get("test_iou") or metrics.get("model_iou") or 0.0)
    delta = float(
        metrics.get("improvement_vs_copy_iou") or metrics.get("improvement_vs_copy") or 0.0
    )
    # Holdout quality 0..1 (research metadata; not probability of next fire)
    conf = _clip01(0.35 * (iou / 0.9) + 0.45 * (delta / 0.25) + 0.2)
    return {
        "id": "ml_clm_ensemble",
        "available": True,
        # Never fuse static holdout IoU as live phenomenon confidence.
        "weight": 0.0,
        "confidence": conf,
        "holdout_quality": conf,
        "role": "holdout_quality",
        "source_type": "research_metadata",
        "metrics": {
            "test_iou": iou,
            "improvement_vs_copy_iou": delta,
            "model_iou_growth": metrics.get("model_iou_growth"),
            "holdout_quality": conf,
        },
    }


def score_ops_source(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {"id": "ops", "available": False, "weight": 0.0, "confidence": 0.0}
    grade = str(metrics.get("quality_grade") or metrics.get("grade") or "")
    grade_map = {"A": 0.85, "B": 0.55, "C": 0.30, "D": 0.12}
    conf = grade_map.get(grade.upper(), 0.2)
    ros = metrics.get("primary_ros_m_min")
    n = int(metrics.get("n_frames_staged") or metrics.get("n_frames") or 0)
    if n >= 5:
        conf = _clip01(conf + 0.05)
    if metrics.get("speed_vs_ref_ratio") is not None:
        try:
            r = float(metrics["speed_vs_ref_ratio"])
            conf = _clip01(conf + 0.08) if 0.5 <= r <= 2.0 else _clip01(conf - 0.15)
        except (TypeError, ValueError):
            pass
    return {
        "id": "ops_thermal_front",
        "available": True,
        "weight": 0.40,
        "confidence": conf,
        "metrics": {
            "quality_grade": grade,
            "primary_ros_m_min": ros,
            "n_frames": n,
            "area_ha_max": metrics.get("area_ha_max") or metrics.get("area_ha"),
            "speed_vs_ref_ratio": metrics.get("speed_vs_ref_ratio"),
        },
    }


def score_open_cems_source(metrics: Mapping[str, Any] | None) -> dict[str, Any]:
    if not metrics:
        return {"id": "open_cems", "available": False, "weight": 0.0, "confidence": 0.0}
    steps = int(metrics.get("n_timeline_steps") or 0)
    area = float(metrics.get("max_area_ha") or 0.0)
    conf = 0.25
    if steps >= 3:
        conf += 0.25
    if steps >= 5:
        conf += 0.10
    if area >= 500:
        conf += 0.15
    if area >= 2000:
        conf += 0.10
    # CEMS is satellite emergency mapping — cap confidence for action
    conf = min(conf, 0.72)
    return {
        "id": "open_cems_perimeter",
        "available": True,
        "weight": 0.35,
        "confidence": _clip01(conf),
        "metrics": {
            "max_area_ha": area,
            "n_timeline_steps": steps,
            "activation": metrics.get("activation"),
            "O2_cems_delineation": metrics.get("O2_cems_delineation") or metrics.get("O2_cems"),
        },
    }


def fuse_confidence(sources: Sequence[Mapping[str, Any]]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    num = 0.0
    den = 0.0
    for s in sources:
        if not s.get("available"):
            reasons.append(f"missing:{s.get('id')}")
            continue
        c = float(s.get("confidence") or 0.0)
        # Research holdout metadata is display-only — never fused as live fire quality.
        if s.get("role") == "holdout_quality" or s.get("source_type") == "research_metadata":
            reasons.append(f"{s.get('id')}:holdout_quality={c:.3f}:not_fused")
            continue
        w = float(s.get("weight") or 0.0)
        num += w * c
        den += w
        reasons.append(f"{s.get('id')}:conf={c:.3f}:w={w:.2f}")
    if den <= 0:
        return 0.0, reasons + ["no_sources"]
    return _clip01(num / den), reasons


def decide(
    confidence_pred: float,
    sources: Sequence[Mapping[str, Any]],
    *,
    require_ops_for_go: bool = False,
    policy: Any | None = None,
) -> tuple[Decision, list[str]]:
    """Apply GO/HOLD/ABSTAIN rules.

    If ``policy`` is a DecisionPolicy, its thresholds win.
    ``require_ops_for_go`` overrides policy when True (CLI flag still works).
    """
    from .policy import LEGACY_DEFAULT, DecisionPolicy

    pol: DecisionPolicy = policy if isinstance(policy, DecisionPolicy) else LEGACY_DEFAULT
    # CLI/API may force ops requirement without switching full profile
    req_ops = bool(require_ops_for_go) or bool(pol.require_ops_for_go)

    reasons: list[str] = [f"policy:{pol.id}"]
    available = [s for s in sources if s.get("available")]
    if len(available) < int(pol.min_available_sources):
        return Decision.ABSTAIN, reasons + ["no_available_sources"]

    ops_ok = any(s.get("id") == "ops_thermal_front" and s.get("available") for s in sources)
    open_ok = any(s.get("id") == "open_cems_perimeter" and s.get("available") for s in sources)
    ml_ok = any(s.get("id") == "ml_clm_ensemble" and s.get("available") for s in sources)

    if confidence_pred < float(pol.abstain_below):
        return Decision.ABSTAIN, reasons + [f"confidence_pred<{pol.abstain_below}"]
    if req_ops and not ops_ok:
        if open_ok and pol.allow_open_only_hold and confidence_pred >= float(pol.hold_open_min):
            return Decision.HOLD, reasons + ["open_only_monitoring"]
        return Decision.ABSTAIN, reasons + ["ops_required_for_go"]

    # GO only if we have thermal ops with decent grade OR multi-source strong
    if ops_ok and confidence_pred >= float(pol.go_ops_min):
        return Decision.GO, reasons + ["ops_confidence_ok"]
    if ops_ok and open_ok and confidence_pred >= float(pol.go_ops_open_min):
        return Decision.GO, reasons + ["ops+open_fusion"]
    if open_ok and pol.allow_open_only_hold and confidence_pred >= float(pol.hold_open_min):
        return Decision.HOLD, reasons + ["open_cems_monitoring_only"]
    if (
        ml_ok
        and not ops_ok
        and pol.allow_ml_only_hold
        and confidence_pred >= float(pol.hold_ml_only_min)
    ):
        return Decision.HOLD, reasons + ["ml_only_not_field_ros"]
    if ml_ok and not ops_ok and not pol.allow_ml_only_hold:
        return Decision.ABSTAIN, reasons + ["ml_only_blocked_by_policy"]
    return Decision.ABSTAIN, reasons + ["below_action_threshold"]


def _tri_state(value: bool | None) -> bool | None:
    """Normalize gate flags: only True/False/None are meaningful."""
    if value is None:
        return None
    return bool(value)


def system_reliability_report(
    *,
    gates_ok: bool | None = None,
    determinism_ok: bool | None = None,
    abstention_enforced: bool | None = None,
    provenance_ok: bool | None = None,
) -> dict[str, Any]:
    """R1–R4 system reliability (NOT fire prediction accuracy).

    Each check may be True / False / None (not measured).
    PASS and residual risk 1e-6 are claimed only when every check is
    explicitly True — never by default.
    """
    checks: dict[str, bool | None] = {
        "R1_determinism": _tri_state(determinism_ok),
        "R2_gates": _tri_state(gates_ok),
        "R3_abstention_enforced": _tri_state(abstention_enforced),
        "R4_provenance": _tri_state(provenance_ok),
    }
    values = list(checks.values())
    any_unknown = any(v is None for v in values)
    any_fail = any(v is False for v in values)
    # Fail-closed: unmeasured checks are not a pass.
    passed = (not any_unknown) and (not any_fail) and all(v is True for v in values)
    # Design target: silent GO without gates should be impossible under test.
    # Residual 1e-6 only when all checks are explicitly verified True.
    residual_silent_go_risk = 1e-6 if passed else 1.0
    if passed:
        claim = (
            "PASS: residual risk of silent GO without gates under automated "
            "enforcement bound at 1e-6 (design+tests). "
            "DOES NOT mean 99.9999% fire-spread prediction accuracy."
        )
        status = "pass"
    elif any_unknown and not any_fail:
        claim = (
            "UNKNOWN: system reliability checks not measured for this card. "
            "Does NOT claim residual 1e-6 or five-nines gate enforcement."
        )
        status = "unknown"
    else:
        claim = "FAIL: system reliability checks incomplete or failed"
        status = "fail"
    return {
        "system_reliability_pass": passed,
        "status": status,
        "checks": checks,
        "residual_silent_go_risk_bound": residual_silent_go_risk,
        "five_nines_claim": claim,
        "fire_prediction_accuracy_claim": "NOT_CLAIMED",
    }


def _load_reliability_gate_report(
    source: Mapping[str, Any] | Path | str | None,
) -> dict[str, Any] | None:
    """Load a reliability_gate.py JSON report (mapping or path)."""
    if source is None:
        return None
    if isinstance(source, Mapping):
        return dict(source)
    path = Path(source)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


# Provenance kinds that are never valid field unlock keys (suite / docs / CI).
_FIELD_REJECT_PROVENANCE_KINDS = frozenset(
    {
        "suite_sample",
        "docs_sample",
        "synthetic_suite",
        "suite_run",
    }
)


def _report_rejected_for_field(
    report: Mapping[str, Any],
    *,
    event_id: str | None = None,
) -> str | None:
    """Return rejection reason if report must not unlock field_ops, else None.

    Field unlock requires a this-run (or other non-suite) report with an
    explicit ``event_id`` that matches the card event when one is supplied.
    """
    if report.get("suite_only") is True or report.get("field_unlock") is False:
        return "suite_only_or_field_unlock_false"
    prov = report.get("provenance")
    prov_map = prov if isinstance(prov, Mapping) else {}
    kind = str(prov_map.get("kind") or report.get("kind") or "")
    if kind in _FIELD_REJECT_PROVENANCE_KINDS:
        return f"provenance_kind:{kind}"
    # Field-unlock reports must carry event_id; missing id is not a wildcard match.
    report_event = report.get("event_id")
    if report_event is None:
        report_event = prov_map.get("event_id")
    if event_id is not None:
        if report_event is None:
            return "missing_event_id"
        if str(report_event) != str(event_id):
            return "event_id_mismatch"
    return None


def _gate_flags_from_report(
    report: Mapping[str, Any] | None,
    *,
    event_id: str | None = None,
) -> dict[str, bool | None]:
    """Extract R1–R4 flags from a reliability gate report if present.

    Only explicit ``system_reliability.checks`` keys count. Top-level
    ``ok`` is advisory metadata and must NOT grant R1–R4 PASS by itself.
    Suite-only / docs sample reports and event_id mismatches yield unknowns.
    """
    empty: dict[str, bool | None] = {
        "gates_ok": None,
        "determinism_ok": None,
        "abstention_enforced": None,
        "provenance_ok": None,
    }
    if not report:
        return empty
    if _report_rejected_for_field(report, event_id=event_id):
        return empty
    sys_rel = report.get("system_reliability")
    checks: Mapping[str, Any] = {}
    if isinstance(sys_rel, Mapping):
        raw = sys_rel.get("checks")
        if isinstance(raw, Mapping):
            checks = raw

    def _c(key: str) -> bool | None:
        if key not in checks:
            return None
        v = checks[key]
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        # Non-bool check values are untrusted / unmeasured
        return None

    return {
        "determinism_ok": _c("R1_determinism"),
        "gates_ok": _c("R2_gates"),
        "abstention_enforced": _c("R3_abstention_enforced"),
        "provenance_ok": _c("R4_provenance"),
    }


def _derive_abstention_enforced(
    decision: Decision,
    confidence_pred: float,
    sources: Sequence[Mapping[str, Any]],
    policy: Any,
) -> bool:
    """Honest R3: abstention applied when conf/policy requires it.

    Not ``conf >= 0.0`` (always true). When policy requires ABSTAIN,
    the decision must be ABSTAIN. Otherwise the engine ran decide()
    so abstention rules were applied for this card.
    """
    min_src = int(getattr(policy, "min_available_sources", 1) or 1)
    abstain_below = float(getattr(policy, "abstain_below", 0.20))
    available = [s for s in sources if s.get("available")]
    must_abstain = confidence_pred < abstain_below or len(available) < min_src
    if must_abstain:
        return decision == Decision.ABSTAIN
    # Policy path ran; GO/HOLD only when sources satisfied thresholds.
    return True


def build_decision_card(
    event_id: str,
    *,
    ml_metrics: Mapping[str, Any] | None = None,
    ops_metrics: Mapping[str, Any] | None = None,
    open_metrics: Mapping[str, Any] | None = None,
    extra_metrics: Mapping[str, Any] | None = None,
    require_ops_for_go: bool = False,
    git_commit: str | None = None,
    policy: Any | None = None,
    policy_id: str | None = None,
    gates_ok: bool | None = None,
    determinism_ok: bool | None = None,
    abstention_enforced: bool | None = None,
    provenance_ok: bool | None = None,
    reliability_gate: Mapping[str, Any] | Path | str | None = None,
) -> DecisionCard:
    """Build a Fire Decision Card.

    System reliability flags default to unknown/not measured. Pass explicit
    gate results or a ``reliability_gate`` report (from reliability_gate.py)
    to claim PASS / residual 1e-6. field_ops fails closed: GO → ABSTAIN when
    reliability is not fully verified.
    """
    from .policy import DecisionPolicy, get_policy

    if policy is None:
        policy = get_policy(policy_id)
    elif not isinstance(policy, DecisionPolicy):
        policy = get_policy(policy_id or "default")

    sources = [
        score_ml_source(ml_metrics),
        score_ops_source(ops_metrics),
        score_open_cems_source(open_metrics),
    ]
    conf, fuse_reasons = fuse_confidence(sources)
    # ML-only cards: surface holdout quality for research/monitoring display
    # without claiming live phenomenon confidence from multi-source fusion.
    if (
        conf <= 0.0
        and sources[0].get("available")
        and not sources[1].get("available")
        and not sources[2].get("available")
    ):
        conf = float(sources[0].get("holdout_quality") or sources[0].get("confidence") or 0.0)
        fuse_reasons = list(fuse_reasons) + ["ml_holdout_quality_display"]
    decision, dec_reasons = decide(
        conf,
        sources,
        require_ops_for_go=require_ops_for_go,
        policy=policy,
    )

    # Merge optional external gate report; explicit kwargs win when not None.
    # R3/R4 stay None unless report/kwargs supply them (do not auto-claim verified).
    loaded_gate = _load_reliability_gate_report(reliability_gate)
    from_report = _gate_flags_from_report(loaded_gate, event_id=event_id)
    g_ok = from_report["gates_ok"] if gates_ok is None else gates_ok
    d_ok = from_report["determinism_ok"] if determinism_ok is None else determinism_ok
    p_ok = from_report["provenance_ok"] if provenance_ok is None else provenance_ok
    a_ok = (
        from_report["abstention_enforced"] if abstention_enforced is None else abstention_enforced
    )
    abstention_heuristic_ok = _derive_abstention_enforced(decision, conf, sources, policy)

    sys_rep = system_reliability_report(
        gates_ok=g_ok,
        determinism_ok=d_ok,
        abstention_enforced=a_ok,
        provenance_ok=p_ok,
    )

    # field_ops fail-closed: do not emit GO without verified system reliability.
    if (
        str(getattr(policy, "id", "") or "") == "field_ops"
        and decision == Decision.GO
        and not bool(sys_rep["system_reliability_pass"])
    ):
        decision = Decision.ABSTAIN
        dec_reasons = list(dec_reasons) + ["field_ops_fail_closed_reliability_unverified"]
        abstention_heuristic_ok = _derive_abstention_enforced(decision, conf, sources, policy)

    metrics: dict[str, Any] = {
        "ml": sources[0].get("metrics"),
        "ops": sources[1].get("metrics"),
        "open_cems": sources[2].get("metrics"),
        "fused_confidence_pred": conf,
        "policy_id": policy.id,
    }
    if extra_metrics:
        metrics["extra"] = dict(extra_metrics)

    # output_hash must ignore channel/extra so forensic replay is stable
    # policy_id is part of the decision contract → included
    hash_payload = {
        "event_id": event_id,
        "sources": sources,
        "metrics": {
            "ml": metrics["ml"],
            "ops": metrics["ops"],
            "open_cems": metrics["open_cems"],
            "fused_confidence_pred": conf,
            "policy_id": policy.id,
        },
        "decision": decision.value,
        "policy_id": policy.id,
    }
    audit = {
        "input_hash": content_hash(
            {
                "ml": ml_metrics,
                "ops": ops_metrics,
                "open": open_metrics,
                "policy_id": policy.id,
            }
        ),
        "output_hash": content_hash(hash_payload),
        "git_commit": git_commit,
        "schema": "fire_decision_card_v1",
        "policy_id": policy.id,
        "policy_label": policy.label,
        "policy_snapshot": {
            "require_ops_for_go": policy.require_ops_for_go,
            "abstain_below": policy.abstain_below,
            "go_ops_min": policy.go_ops_min,
            "go_ops_open_min": policy.go_ops_open_min,
            "hold_open_min": policy.hold_open_min,
            "hold_ml_only_min": policy.hold_ml_only_min,
            "allow_ml_only_hold": policy.allow_ml_only_hold,
            "allow_open_only_hold": policy.allow_open_only_hold,
        },
        # Heuristic only — not a gate-verified R3/R4 claim
        "abstention_heuristic_ok": abstention_heuristic_ok,
        "provenance_hashes_attached": True,
    }

    disclaimers = list(DEFAULT_DISCLAIMERS)
    if not bool(sys_rep["system_reliability_pass"]):
        disclaimers.append(
            "System reliability gates not verified for this card "
            "(no residual 1e-6 claim; status="
            f"{sys_rep.get('status', 'unknown')})."
        )

    return DecisionCard(
        event_id=event_id,
        decision=decision,
        confidence_pred=conf,
        confidence_pred_label=_label(conf),
        system_reliability_pass=bool(sys_rep["system_reliability_pass"]),
        sources=[dict(s) for s in sources],
        metrics=metrics,
        reasons=fuse_reasons + dec_reasons,
        disclaimers=disclaimers,
        audit={**audit, "system_reliability": sys_rep},
        built_at_utc=datetime.now(UTC).isoformat(),
    )
