"""SPA honesty UI helpers (Agent A): uncertainty bar, H1 eng, SR ladder, decision-log.

Pure payload builders — no fusion ON, never invent GO_Q=true, never invent backend ACK.
Uncertainty bar is conf-only (existing confidence_pred) — never ROS / never invented scores.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

# Optional B sidecar names (read-only; absent → stub)
_DECISION_LOG_CANDIDATES = (
    "outbox/decision_log.json",
    "outbox/wfd_decision_log_v1.json",
    "decision_log.json",
    "outbox/decision_log/latest.json",
)

_H1_SESSION_REL = Path("docs") / "H1_DEMO_SESSION_READY.json"

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
        "field_ops_ml_live_fusion": "OFF",
        "go_q_invent_forbidden": True,
    }


def build_sr_ladder(*, decision: str | None = None) -> dict[str, Any]:
    """Support/recommendation ladder for SPA (UI markers + non-claims)."""
    dec = (decision or "ABSTAIN").strip().upper()
    if dec == "GO":
        # Lab/eng GO on card ≠ field GO sell — clamp ladder highlight to S2
        active = "S2"
        note = "Card GO (lab/eng) ≠ field GO · fusion OFF · no vender despacho"
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
        "field_ops_ml_live_fusion": "OFF",
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
            "detail": "GO_MES true · GO_Q partial · fusion OFF · ABSTAIN = feature",
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
        "field_ops_ml_live_fusion": "OFF",
    }


def load_decision_log_surface(
    *,
    work_dir: Path | None,
    decision_card: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """A8: read-only decision-log if B sidecar exists; else honest stub.

    Never mutates disk, never invents backend ACK, never sets GO_Q.
    """
    card = decision_card if isinstance(decision_card, dict) else {}
    event_id = card.get("event_id")
    decision = card.get("decision")
    found: dict[str, Any] | None = None
    source = "stub_ui"
    rel_path: str | None = None

    if work_dir is not None:
        wd = Path(work_dir)
        for rel in _DECISION_LOG_CANDIDATES:
            p = wd / rel
            if not p.is_file():
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                found = data
                source = "sidecar_file"
                rel_path = rel.replace("\\", "/")
                break
            if isinstance(data, list) and data and isinstance(data[0], dict):
                found = data[0]
                source = "sidecar_file_list_head"
                rel_path = rel.replace("\\", "/")
                break

    if found is not None:
        log_id = (
            found.get("id")
            or found.get("decision_id")
            or found.get("event_id")
            or event_id
            or "sidecar"
        )
        ack_backend = found.get("ack") or found.get("ack_state") or "unknown"
        return {
            "schema": "wfd_decision_log_ui_v1",
            "marker": "decision-log",
            "mode": "sidecar_read",
            "source": source,
            "path_rel": rel_path,
            "id": str(log_id),
            "decision": found.get("decision") or decision,
            "ack_backend": ack_backend,
            "ack_ui_only": True,
            "go_q_met": False,
            "note": (
                "Sidecar B leído en solo lectura · ACK UI local ≠ ACK backend · "
                "no inventa GO_Q · fusion OFF"
            ),
            "field_ops_ml_live_fusion": "OFF",
        }

    stub_id = event_id or (f"stub-{str(decision).lower()}" if decision else None)
    return {
        "schema": "wfd_decision_log_ui_v1",
        "marker": "decision-log",
        "mode": "stub",
        "source": "stub_ui",
        "path_rel": None,
        "id": str(stub_id) if stub_id else None,
        "decision": decision,
        "ack_backend": None,
        "ack_ui_only": True,
        "go_q_met": False,
        "note": (
            "Stub UI · backend B opcional ausente · ACK local only · "
            "no inventa GO_Q · fusion OFF · no es acta H1"
        ),
        "field_ops_ml_live_fusion": "OFF",
    }
