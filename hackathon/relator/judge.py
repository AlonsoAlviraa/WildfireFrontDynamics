"""Judge: sealed ``decide_from_request``. Not an LLM."""

from __future__ import annotations

from typing import Any

from .board import append_event, cell_status, cited_value, quorum


def _build_request(board: dict[str, Any], *, policy: str = "field_ops") -> dict[str, Any]:
    req: dict[str, Any] = {
        "event_id": board.get("incident_id") or "relator",
        "policy": policy,
        "require_ops_for_go": True,
        "channel": "relator_judge",
    }
    ros = cited_value(board, "ops_ros")
    if ros is not None and cell_status(board, "ops_thermal") in ("present", "cited"):
        req["ops_metrics"] = {
            "quality_grade": "A",
            "primary_ros_m_min": float(ros),
            "n_frames_staged": 2,
            "speed_vs_ref_ratio": 1.0,
        }
    ha = cited_value(board, "open_official_ha")
    if ha is not None:
        req["open_metrics"] = {"area_ha": float(ha), "source": "cited_document"}
    return req


def call_decide(board: dict[str, Any], *, policy: str = "field_ops") -> dict[str, Any]:
    from wildfire_front.product.decide_service import decide_from_request

    return decide_from_request(_build_request(board, policy=policy))


def seal_judgment(board: dict[str, Any], *, policy: str = "field_ops") -> dict[str, Any]:
    q = quorum(board)
    if not q["ready_for_judge"]:
        out = dict(board)
        out["decision"] = "ABSTAIN"
        out["decision_reason"] = (
            f"No thermal quorum ({q['n_present']}/{q['n_total']} present). "
            "FIRMS alone is not enough. Relator does not call the judge."
        )
        out["judge"] = {
            "called": False,
            "decision": "ABSTAIN",
            "engine": "relator_quorum",
            "policy": policy,
        }
        return append_event(
            out,
            {
                "type": "judge.skipped",
                "actor": "judge",
                "summary": out["decision_reason"],
            },
        )

    try:
        card = call_decide(board, policy=policy)
        engine = "decide_service"
    except Exception as exc:  # sealed judge unavailable → fail closed
        card = {
            "decision": "ABSTAIN",
            "reason": f"decide_service unavailable: {type(exc).__name__}",
            "system_reliability_pass": False,
        }
        engine = "decide_unavailable_fail_closed"

    dec = str(card.get("decision") or "ABSTAIN").upper()
    if dec not in ("GO", "HOLD", "ABSTAIN"):
        dec = "ABSTAIN"
    out = dict(board)
    out["decision"] = dec
    audit = card.get("audit") if isinstance(card.get("audit"), dict) else {}
    out["judge"] = {
        "called": True,
        "decision": dec,
        "engine": engine,
        "policy": policy,
        "confidence_pred": card.get("confidence_pred"),
        "output_hash": audit.get("output_hash") or card.get("output_hash"),
        "system_reliability_pass": bool(card.get("system_reliability_pass")),
        "not_tactical_dispatch": True,
        "go_q_met": False,
    }
    if dec == "ABSTAIN":
        out["decision_reason"] = "Sealed judge ABSTAIN (fail-closed). Not a model guess."
    elif dec == "HOLD":
        out["decision_reason"] = "Sealed judge HOLD. Wait / review. Not dispatch."
    else:
        out["decision_reason"] = (
            "Sealed judge GO under field_ops. Still not tactical dispatch. GO_Q partial."
        )
    return append_event(
        out,
        {"type": "judge.ruled", "actor": "judge", "summary": out["decision_reason"]},
    )
