"""SPA honesty UI helpers: uncertainty bar, H1, SR, decision-log, V&V, weakness board.

Pure payload builders — never invent GO_Q=true, never invent backend ACK.
Uncertainty bar is conf-only (existing confidence_pred) — never ROS / never invented scores.
Weakness board is read-only JSON — never invent counts / Vp/ha / 2nd grade-A.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

_H1_SESSION_REL = Path("docs") / "H1_DEMO_SESSION_READY.json"


def _fusion_rail() -> str:
    from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

    return field_ops_ml_live_fusion_rail()

# Mes2 PR1-A fixed honesty strings (tests pin exact phrases)
UNCERTAINTY_BAR_NOTE = (
    "no es ROS · IoU ≠ ROS · banda de calidad existente, sin inventar scores"
)
UNCERTAINTY_BAR_LABEL = "Conf. predicción (no es ROS)"

# Support / recommendation ladder (eng UI only — not field GO sell)
SR_LADDER_LEVELS: tuple[dict[str, str], ...] = (
    {
        "id": "S0",
        "label": "Observar / ABSTAIN",
        "why": "Datos insuficientes o rails field_ops — callarse es feature",
    },
    {
        "id": "S1",
        "label": "HOLD / soporte limitado",
        "why": "Señales parciales; no recomendación de acción táctica",
    },
    {
        "id": "S2",
        "label": "Revisar con ops",
        "why": "Apoyo a lectura conjunta con evidencia ops — no despacho",
    },
    {
        "id": "S3",
        "label": "Soporte con evidencia",
        "why": "Ops + decision card trazable; sigue sin ser GO de campo vendible",
    },
)

SR_NON_CLAIMS: tuple[str, ...] = (
    "No es despacho táctico",
    "No vende field GO / fusion ON",
    "IoU ≠ ROS · conf ML ≠ conf ROS",
    "GO_Q partial hasta acta tercero humana",
    "Claims Guardian: no outbound marketing sin clear",
)


def build_uncertainty_bar_view(
    *,
    confidence_pred: float | int | None = None,
    confidence_label: str | None = None,
) -> dict[str, Any]:
    """Mes2 PR1-A: pure conf-only uncertainty bar for SPA payload.

    Uses only existing confidence_pred / label from the decision card / hero.
    Never invents numeric scores, never maps IoU→ROS, never sets fusion ON / GO_Q.
    Empty conf → honest empty fill + band ``sin conf``.
    """
    conf: float | None = None
    if confidence_pred is not None:
        try:
            c = float(confidence_pred)
        except (TypeError, ValueError):
            c = float("nan")
        if math.isfinite(c):
            conf = max(0.0, min(1.0, c))

    band = str(confidence_label or "").strip()
    if not band and conf is not None:
        if conf < 0.34:
            band = "baja"
        elif conf < 0.67:
            band = "media"
        else:
            band = "alta"
    if not band:
        band = "sin conf"

    fill_pct = int(round(conf * 100.0)) if conf is not None else 0

    return {
        "schema": "wfd_uncertainty_bar_ui_v1",
        "marker": "uncertainty-bar",
        "confidence_pred": conf,
        "fill_pct": fill_pct,
        "band": band,
        "label": UNCERTAINTY_BAR_LABEL,
        "note": UNCERTAINTY_BAR_NOTE,
        "emphasis": "no es ROS",
        "source": "existing_confidence_pred_only",
        "invents_scores": False,
        "is_ros": False,
        "iou_is_not_ros": True,
        "empty": conf is None,
        "field_ops_ml_live_fusion": _fusion_rail(),
        "go_q_invent_forbidden": True,
    }


SPLIT_CONF_BANNER = "Conf. ML ≠ Conf. ROS · no es despacho táctico"
SPLIT_CONF_ML_HINT = "calidad de card · no es ROS"
SPLIT_CONF_ROS_HINT = "métrica ops si existe · IoU ≠ ROS · sin inventar"


def build_split_conf_view(
    *,
    confidence_pred: float | int | None = None,
    confidence_label: str | None = None,
    ops_metrics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Mes2 PR3-A: split ML vs ROS confidence from existing fields only.

    Never invents ROS scores, never maps IoU→ROS, never sets fusion ON / GO_Q.
    Missing ops → honest ``sin conf ROS``.
    """
    ml_bar = build_uncertainty_bar_view(
        confidence_pred=confidence_pred,
        confidence_label=confidence_label,
    )
    ops = ops_metrics if isinstance(ops_metrics, dict) else {}
    ros_num: float | None = None
    ros_grade: str | None = None
    raw_ros = ops.get("ros_confidence")
    if raw_ros is not None:
        try:
            c = float(raw_ros)
        except (TypeError, ValueError):
            c = float("nan")
        if math.isfinite(c):
            ros_num = max(0.0, min(1.0, c))
    if ros_num is None and ops.get("quality_grade"):
        ros_grade = str(ops.get("quality_grade"))

    if ros_num is not None:
        ros_display = f"{int(round(ros_num * 100.0))}% (ops)"
        ros_empty = False
    elif ros_grade:
        ros_display = f"grade {ros_grade} (ops · no ML)"
        ros_empty = False
    else:
        ros_display = "— (sin conf ROS)"
        ros_empty = True

    ml_display = (
        f"{ml_bar['fill_pct']}% · {ml_bar['band']}" if not ml_bar["empty"] else "—"
    )

    return {
        "schema": "wfd_split_conf_ui_v1",
        "marker": "split-conf",
        "banner": SPLIT_CONF_BANNER,
        "ml": {
            "label": "Conf. ML / predicción",
            "display": ml_display,
            "hint": SPLIT_CONF_ML_HINT,
            "confidence_pred": ml_bar["confidence_pred"],
            "is_ros": False,
        },
        "ros": {
            "label": "Conf. ROS / ops",
            "display": ros_display,
            "hint": SPLIT_CONF_ROS_HINT,
            "ros_confidence": ros_num,
            "quality_grade": ros_grade,
            "empty": ros_empty,
        },
        "ml_neq_ros": True,
        "iou_is_not_ros": True,
        "invents_scores": False,
        "field_ops_ml_live_fusion": _fusion_rail(),
        "go_q_invent_forbidden": True,
        "go_q_met": False,
        "note": "Conf. ML ≠ Conf. ROS · IoU ≠ ROS · no es despacho táctico · fusion ON",
    }


def build_sr_ladder(*, decision: str | None = None) -> dict[str, Any]:
    """Support/recommendation ladder for SPA (UI markers + non-claims)."""
    dec = (decision or "ABSTAIN").strip().upper()
    if dec == "GO":
        # Lab/eng GO on card ≠ field GO sell — clamp ladder highlight to S2
        active = "S2"
        note = "Card GO (lab/eng) ≠ field GO · fusion ON · no vender despacho"
    elif dec == "HOLD":
        active = "S1"
        note = "HOLD: soporte limitado · no inventar certeza"
    elif dec in {"ABSTAIN", "BRIEF", ""}:
        active = "S0"
        note = "ABSTAIN/BRIEF: observar · callarse es feature"
    else:
        active = "S0"
        note = f"Decisión {dec}: default observar · no claims de campo"

    return {
        "schema": "wfd_sr_ladder_ui_v1",
        "marker": "sr-ladder",
        "title": "Escala SR (soporte / recomendación)",
        "active_id": active,
        "levels": [dict(x) for x in SR_LADDER_LEVELS],
        "non_claims": list(SR_NON_CLAIMS),
        "claims_guardian": (
            "Claims Guardian checklist: no field GO sell · no fusion ON · "
            "no GO_Q complete · no IoU=ROS · marketing embargado hasta clear humano"
        ),
        "note": note,
        "field_ops_ml_live_fusion": _fusion_rail(),
        "go_q_invent_forbidden": True,
    }


def build_h1_eng_rehearsal(
    *,
    repo_root: Path | None = None,
    live_ops_enabled: bool = False,
) -> dict[str, Any]:
    """H1 eng dry-run pack for SPA (A6). Never sets go_q_met true."""
    root = Path(repo_root) if repo_root is not None else Path.cwd()
    session: dict[str, Any] = {}
    session_path = root / _H1_SESSION_REL
    if session_path.is_file():
        try:
            raw = json.loads(session_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                session = raw
        except (OSError, UnicodeError, json.JSONDecodeError):
            session = {}

    # Hard rails: product surface never promotes GO_Q from eng rehearsal
    go_q_met = False
    eng_ready = bool(session.get("eng_session_ready", True))
    steps = [
        {
            "n": 1,
            "title": "Rails en voz alta",
            "detail": "GO_MES true · GO_Q partial · fusion ON · ABSTAIN = feature",
        },
        {
            "n": 2,
            "title": "Serve loopback (preferido)",
            "cmd": "python -m wildfire_front app --fire _sla_measure --serve",
            "detail": "http://127.0.0.1:8766/ · Estado → Decidir → Acta live",
        },
        {
            "n": 3,
            "title": "Demo-day one-shot (no inventa GO_Q)",
            "cmd": "python -m wildfire_front app --demo-day",
            "detail": "Presentador H1 eng · go_q_met sigue false",
        },
        {
            "n": 4,
            "title": "Sin serve: copy-CLI",
            "cmd": "python -m wildfire_front app --fire _sla_measure --open",
            "detail": "liveUnavailableFallback · no HTTP 501 desnudo",
        },
        {
            "n": 5,
            "title": "Límite humano",
            "detail": (
                "Acta tercero firmada es humana · "
                "python scripts/record_h1_demo_complete.py solo con acta real"
            ),
        },
    ]
    return {
        "schema": "wfd_h1_eng_rehearsal_ui_v1",
        "marker": "h1-rehearsal",
        "title": "Ensayo H1 eng (12 min · no es demo tercero)",
        "go_q_met": go_q_met,
        "go_q_note": str(
            session.get("go_q_note") or "Human third-party demo + signed acta still required"
        ),
        "eng_session_ready": eng_ready,
        "product_unlock": False,
        "live_ops_enabled": bool(live_ops_enabled),
        "serve_cmd": "python -m wildfire_front app --fire _sla_measure --serve",
        "demo_day_cmd": "python -m wildfire_front app --demo-day",
        "offline_cmd": "python -m wildfire_front app --fire _sla_measure --open",
        "cheatsheet": "docs/CHEATSHEET_DEMO_12MIN.md",
        "app_doc": "docs/APP.md",
        "steps": steps,
        "human_next": list(session.get("human_next") or [])[:6]
        or [
            "Agendar tercero externo",
            "Demo 12 min con cheatsheet",
            "Acta real (no PENDING)",
            "record_h1_demo_complete.py con acta firmada",
        ],
        "non_claims": [
            "go_q_met=false en esta superficie de producto",
            "No es acta H1 con tercero",
            "No fusion ON · no despacho táctico",
        ],
        "eng_only": True,
        "not_third_party_acta": True,
        "go_q_invent_forbidden": True,
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


def _empty_decision_log_surface(
    *,
    decision_card: dict[str, Any] | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Honest empty / sin-sidecar surface — never invent decision_id or fake ACK."""
    card = decision_card if isinstance(decision_card, dict) else {}
    # Card decision may be shown as context only; id stays None (no invent).
    return {
        "schema": "wfd_decision_log_ui_v1",
        "marker": "decision-log",
        "mode": "stub",
        "source": "sin_sidecar",
        "path_rel": None,
        "id": None,
        "decision_id": None,
        "decision": card.get("decision"),
        "event_id": card.get("event_id"),
        "confidence_pred": None,
        "confidence_pred_label": None,
        "ack": None,
        "ack_backend": None,
        "acked": False,
        "ack_ui_only": True,
        "ack_requires_live_ops": True,
        "go_q_met": False,
        "n_entries": 0,
        "note": note
        or (
            "Sin sidecar decision_log.jsonl · no inventa decision_id · "
            "ACK backend requiere app --serve · no inventa GO_Q · fusion ON"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


def load_decision_log_surface(
    *,
    work_dir: Path | None,
    decision_card: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any]:
    """Mes2 PR2-A: map #31 ``decision_log.jsonl`` → SPA decision-log surface.

    Uses shipped ``load_decision_log`` (allowlisted). Latest entry wins.
    Empty / path fail → honest stub (no invented decision_id, no fake ACK).
    Never mutates disk, never sets GO_Q, fusion stays OFF.
    """
    from wildfire_front.product.decide_service import PathNotAllowedError
    from wildfire_front.product.decision_log import (
        DECISION_LOG_FILENAME,
        DecisionLogError,
        load_decision_log,
    )

    card = decision_card if isinstance(decision_card, dict) else {}

    if work_dir is None:
        return _empty_decision_log_surface(decision_card=card)

    allow_base = Path(base) if base is not None else (
        Path(repo_root) if repo_root is not None else None
    )

    try:
        entries = load_decision_log(
            work_dir,
            base=allow_base,
            include_repo_root=include_repo_root,
        )
    except PathNotAllowedError:
        return _empty_decision_log_surface(
            decision_card=card,
            note=(
                "work_dir fuera de allowlist · sin sidecar legible · "
                "no inventa decision_id · fusion ON · no GO_Q invent"
            ),
        )
    except (OSError, UnicodeError, DecisionLogError, ValueError, TypeError):
        return _empty_decision_log_surface(
            decision_card=card,
            note=(
                "Error leyendo decision_log.jsonl · sin inventar entradas · "
                "fusion ON · no GO_Q invent"
            ),
        )

    if not entries:
        return _empty_decision_log_surface(decision_card=card)

    # Latest append is product "current" entry
    found = entries[-1]
    did = found.get("decision_id")
    if not did:
        return _empty_decision_log_surface(
            decision_card=card,
            note=(
                "Sidecar sin decision_id válido · fail closed · "
                "no inventa id · fusion ON"
            ),
        )

    ack_obj = found.get("ack") if isinstance(found.get("ack"), dict) else None
    acked = bool(ack_obj and ack_obj.get("acked") is True)

    return {
        "schema": "wfd_decision_log_ui_v1",
        "marker": "decision-log",
        "mode": "sidecar_read",
        "source": "decision_log_jsonl",
        "path_rel": DECISION_LOG_FILENAME,
        "id": str(did),
        "decision_id": str(did),
        "decision": found.get("decision") or card.get("decision"),
        "event_id": found.get("event_id") or card.get("event_id"),
        "confidence_pred": found.get("confidence_pred"),
        "confidence_pred_label": found.get("confidence_pred_label"),
        "ack": ack_obj,
        "ack_backend": ack_obj if ack_obj is not None else None,
        "acked": acked,
        "ack_ui_only": False,
        "ack_requires_live_ops": True,
        "go_q_met": False,
        "n_entries": len(entries),
        "note": (
            "Sidecar #31 decision_log.jsonl (última entrada) · "
            "ACK backend solo con app --serve loopback · "
            "no inventa GO_Q · fusion ON · conf ML ≠ ROS"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


def _empty_vv_scorecard_surface(*, note: str | None = None) -> dict[str, Any]:
    """Honest empty / sin-sidecar V&V surface — never invent field scores."""
    return {
        "schema": "wfd_vv_scorecard_ui_v1",
        "marker": "vv-scorecard",
        "mode": "sin_sidecar",
        "source": "sin_sidecar",
        "path_rel": None,
        "status": None,
        "eng_stub": True,
        "event_id": None,
        "go_q_met": False,
        "go_q": "partial",
        "field_ops_fusion": "OFF",
        "field_iou": None,
        "field_ros": None,
        "field_grade": None,
        "metrics_field_null": True,
        "invents_field_scores": False,
        "note": note
        or (
            "Sin sidecar vv_scorecard.json · no inventa field IoU/ROS/grade · "
            "eng_stub only · fusion ON · GO_Q partial · no es despacho"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


def load_vv_scorecard_surface(
    *,
    work_dir: Path | None,
    repo_root: Path | None = None,
    base: Path | None = None,
    include_repo_root: bool = True,
) -> dict[str, Any]:
    """Mes3 W1-A: read-only map of #34 ``vv_scorecard.json`` → SPA surface.

    Uses shipped ``load_vv_scorecard`` (allowlisted). Missing file → honest empty.
    Never mutates disk, never surfaces field IoU/ROS/grade numbers, never GO_Q.
    """
    from wildfire_front.product.decide_service import PathNotAllowedError
    from wildfire_front.product.vv_sidecar import (
        VV_SCORECARD_FILENAME,
        VvSidecarError,
        load_vv_scorecard,
        scorecard_summary,
    )

    if work_dir is None:
        return _empty_vv_scorecard_surface()

    allow_base = Path(base) if base is not None else (
        Path(repo_root) if repo_root is not None else None
    )

    try:
        card = load_vv_scorecard(
            work_dir,
            base=allow_base,
            include_repo_root=include_repo_root,
        )
    except FileNotFoundError:
        return _empty_vv_scorecard_surface()
    except PathNotAllowedError:
        return _empty_vv_scorecard_surface(
            note=(
                "work_dir fuera de allowlist · sin sidecar V&V legible · "
                "no inventa field scores · fusion ON · GO_Q partial"
            ),
        )
    except (OSError, UnicodeError, VvSidecarError, ValueError, TypeError, json.JSONDecodeError):
        return _empty_vv_scorecard_surface(
            note=(
                "Error leyendo vv_scorecard.json · sin inventar métricas de campo · "
                "fusion ON · GO_Q partial"
            ),
        )

    summary = scorecard_summary(card)
    raw_rails = summary.get("rails")
    rails: dict[str, Any] = raw_rails if isinstance(raw_rails, dict) else {}
    return {
        "schema": "wfd_vv_scorecard_ui_v1",
        "marker": "vv-scorecard",
        "mode": "sidecar_read",
        "source": "vv_scorecard_json",
        "path_rel": VV_SCORECARD_FILENAME,
        "status": summary.get("status") or "eng_stub",
        "eng_stub": True,
        "event_id": summary.get("event_id"),
        "go_q_met": False,
        "go_q": rails.get("GO_Q") or "partial",
        "field_ops_fusion": rails.get("field_ops_fusion") or "OFF",
        # Always null on the product surface — do not echo sidecar field_* if present.
        "field_iou": None,
        "field_ros": None,
        "field_grade": None,
        "metrics_field_null": True,
        "invents_field_scores": False,
        "note": (
            "Sidecar #34 vv_scorecard.json (lectura) · eng_stub · "
            "no field IoU/ROS/grade · no inventa GO_Q · fusion ON · no es despacho"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


WEAKNESS_BOARD_REL = Path("docs") / "WEAKNESS_BOARD.json"
_SECOND_ANCHOR_HIDDEN_COPY = "1 ancla grade-A (Tobarra) · no inventar 2ª"


def _cited_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    num = float(value)
    if not math.isfinite(num) or num <= 0:
        return None
    return num


def _confirmed_cited_fires(board: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    fires = board.get("fires")
    if not isinstance(fires, list):
        return rows
    for row in fires:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "").strip().lower()
        astatus = str(row.get("anchor_status") or "").strip().lower()
        if status != "confirmed" and astatus != "confirmed":
            continue
        vp = _cited_number(row.get("vp_m_min_cited"))
        ha = _cited_number(row.get("area_ha_cited"))
        if vp is None or ha is None:
            continue
        rows.append(row)
    return rows


def second_anchor_surface(board_json: dict[str, Any] | None) -> dict[str, Any]:
    """W3-A: show 2nd confirmed anchor only if JSON summary *and* rows agree.

    Fail-closed: a lying ``grade_a_ops_anchors >= 2`` with only one confirmed
    cited fire stays hidden. Never invent a 2nd grade-A.
    """
    hidden = {
        "visible": False,
        "n_confirmed_cited": 0,
        "grade_a_ops_anchors": None,
        "copy": _SECOND_ANCHOR_HIDDEN_COPY,
        "fires": [],
        "invents_second_anchor": False,
    }
    if not isinstance(board_json, dict):
        return hidden
    summary = board_json.get("summary")
    summary_d = summary if isinstance(summary, dict) else {}
    try:
        grade_a = int(summary_d.get("grade_a_ops_anchors") or 0)
    except (TypeError, ValueError):
        grade_a = 0
    confirmed = _confirmed_cited_fires(board_json)
    hidden["n_confirmed_cited"] = len(confirmed)
    hidden["grade_a_ops_anchors"] = grade_a
    if grade_a < 2 or len(confirmed) < 2:
        return hidden
    shown = []
    for row in confirmed:
        shown.append(
            {
                "fire_id": row.get("fire_id"),
                "status": row.get("status"),
                "vp_m_min_cited": _cited_number(row.get("vp_m_min_cited")),
                "area_ha_cited": _cited_number(row.get("area_ha_cited")),
            }
        )
    return {
        "visible": True,
        "n_confirmed_cited": len(confirmed),
        "grade_a_ops_anchors": grade_a,
        "copy": f"{len(confirmed)} anclas grade-A confirmadas (cite)",
        "fires": shown,
        "invents_second_anchor": False,
    }


def _empty_weakness_board_surface(*, note: str | None = None) -> dict[str, Any]:
    """Honest empty / missing board — never invent counts, Vp/ha, or 2nd grade-A."""
    return {
        "schema": "wfd_if_weakness_board_ui_v1",
        "marker": "weakness-board",
        "mode": "sin_board",
        "source": "sin_board",
        "path_rel": None,
        "empty": True,
        "n_fires": None,
        "n_confirmed": None,
        "n_ml_strong": None,
        "n_no_use": None,
        "grade_a_ops_anchors": None,
        "go_q": "partial",
        "go_q_met": False,
        "field_ops_ml_fusion": "ON",
        "hellin_status": None,
        "freeze_ml": True,
        "invented_vp_ha": False,
        "second_anchor": second_anchor_surface(None),
        "fires": [],
        "invents_counts": False,
        "invents_vp_ha": False,
        "invents_ml_strong": False,
        "note": note
        or (
            "Sin docs/WEAKNESS_BOARD.json · no inventa n_fires/n_confirmed/"
            "n_ml_strong/grade_a · fusion ON · GO_Q partial · no es despacho"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_weakness_board_surface(
    *,
    repo_root: Path | None = None,
    board_path: Path | None = None,
    base: Path | None = None,
) -> dict[str, Any]:
    """W1-A / W3-A: read-only map of ``docs/WEAKNESS_BOARD.json`` → SPA.

    Allowlisted under repo_root (or ``base``). Missing/unreadable → honest empty.
    Never mutates disk, never invents counts / Vp/ha / 2nd grade-A / GO_Q.
    """
    from wildfire_front.product.path_sandbox import (
        PathNotAllowedError,
        exists_file,
        is_under,
        read_json,
        realpath,
    )

    root = Path(repo_root) if repo_root is not None else Path.cwd()
    allow = Path(base) if base is not None else root
    path = Path(board_path) if board_path is not None else (root / WEAKNESS_BOARD_REL)

    try:
        allow_real = realpath(allow)
        path_real = realpath(path)
    except OSError:
        return _empty_weakness_board_surface(
            note="path ilegible · no inventa conteos · fusion ON · GO_Q partial"
        )

    if not is_under(path_real, allow_real):
        return _empty_weakness_board_surface(
            note=(
                "WEAKNESS_BOARD fuera de allowlist · no inventa conteos · "
                "fusion ON · GO_Q partial"
            ),
        )
    if not exists_file(path_real):
        return _empty_weakness_board_surface()

    try:
        raw = read_json(path_real, roots=[allow_real])
    except FileNotFoundError:
        return _empty_weakness_board_surface()
    except PathNotAllowedError:
        return _empty_weakness_board_surface(
            note=(
                "WEAKNESS_BOARD fuera de allowlist · no inventa conteos · "
                "fusion ON · GO_Q partial"
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return _empty_weakness_board_surface(
            note=(
                "Error leyendo WEAKNESS_BOARD.json · no inventa conteos/Vp/ha · "
                "fusion ON · GO_Q partial"
            ),
        )

    if not isinstance(raw, dict) or raw.get("schema") != "wfd_if_weakness_board_v1":
        return _empty_weakness_board_surface(
            note="schema inválido · no inventa conteos · fusion ON · GO_Q partial"
        )

    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    rails = raw.get("rails") if isinstance(raw.get("rails"), dict) else {}
    fires_in = raw.get("fires") if isinstance(raw.get("fires"), list) else []
    fires: list[dict[str, Any]] = []
    for row in fires_in:
        if not isinstance(row, dict):
            continue
        fires.append(
            {
                "fire_id": row.get("fire_id"),
                "honesty_class": row.get("honesty_class"),
                "status": row.get("status"),
                "use_flag": row.get("use_flag"),
                "blocking_gap": row.get("blocking_gap"),
                "vp_m_min_cited": _cited_number(row.get("vp_m_min_cited")),
                "area_ha_cited": _cited_number(row.get("area_ha_cited")),
            }
        )
    hellin = next((f for f in fires if f.get("fire_id") == "hellin_2024"), None)
    hellin_status = rails.get("hellin_status_ssot") or (hellin or {}).get("status")
    return {
        "schema": "wfd_if_weakness_board_ui_v1",
        "marker": "weakness-board",
        "mode": "board_read",
        "source": "weakness_board_json",
        "path_rel": "docs/WEAKNESS_BOARD.json",
        "empty": False,
        "n_fires": _int_or_none(summary.get("n_fires")),
        "n_confirmed": _int_or_none(summary.get("n_confirmed")),
        "n_ml_strong": _int_or_none(summary.get("n_ml_strong")),
        "n_no_use": _int_or_none(summary.get("n_no_use")),
        "grade_a_ops_anchors": _int_or_none(summary.get("grade_a_ops_anchors")),
        "go_q": rails.get("go_q") or "partial",
        "go_q_met": False,
        "field_ops_ml_fusion": rails.get("field_ops_ml_fusion") or "ON",
        "hellin_status": hellin_status,
        "freeze_ml": bool(rails.get("freeze_ml", True)),
        "invented_vp_ha": False,
        "second_anchor": second_anchor_surface(raw),
        "fires": fires,
        "invents_counts": False,
        "invents_vp_ha": False,
        "invents_ml_strong": False,
        "note": (
            "docs/WEAKNESS_BOARD.json (lectura) · no POST · no promote · "
            "no inventa Vp/ha · fusion ON · GO_Q partial · no es despacho"
        ),
        "field_ops_ml_live_fusion": _fusion_rail(),
    }
