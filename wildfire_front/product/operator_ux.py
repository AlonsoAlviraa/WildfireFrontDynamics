"""Operator-only UX: one entry, traffic lights, plain language, GO_Q gap.

Used by ``wildfire-front operator``. Pure helpers — no pack rebuild side effects.
Honesty rails: never invent GO_Q=true; ABSTAIN is a feature, not a crash.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .teach_path import (
    CHEATSHEET_PATH,
    COURSE_PATH,
    KEY_PATHS,
    NEXT_HUMAN,
    TEACH_ACTS,
    load_gate_snapshot,
    rails_one_liner,
    resolve_repo_root,
    ssot_field_ops_fusion,
)

# Written by ``operator do`` so checklist can distinguish presence vs ensayo.
OPERATOR_SESSION_REL = Path("outputs") / "operator_ux_last_run.json"

# ── Traffic light ─────────────────────────────────────────────────────────

LIGHT_GREEN = "VERDE"
LIGHT_YELLOW = "AMARILLO"
LIGHT_RED = "ROJO"

OPERATOR_CHECKLIST: list[dict[str, str]] = [
    {
        "id": "entry",
        "label": "Sabe el único comando de entrada en <30 s",
        "hint": "python -m wildfire_front operator",
    },
    {
        "id": "semaphore",
        "label": "Lee el semáforo (listo / falta / bloqueado)",
        "hint": "VERDE=listo · AMARILLO=falta algo · ROJO=bloqueado",
    },
    {
        "id": "act1",
        "label": "Acto 1 Ver — multi-CCAA sin ayuda",
        "hint": "operator do --act 1",
    },
    {
        "id": "act2",
        "label": "Acto 2 Callarse — entiende ABSTAIN como feature",
        "hint": "operator do --act 2",
    },
    {
        "id": "act3",
        "label": "Acto 3 Decidir — Decision Card en lenguaje normal",
        "hint": "operator do --act 3",
    },
    {
        "id": "act4",
        "label": "Acto 4 Probar — pack + replay sin magia negra",
        "hint": "operator do --act 4",
    },
    {
        "id": "go_q",
        "label": "Sabe qué falta para GO_Q (demo terceros)",
        "hint": "H1/M3.2: demo con tercero real + acta firmada",
    },
]


def _light_for_gate(key: str, value: Any) -> str:
    """Map a gate value to traffic light."""
    if key == "GO_MES":
        if value is True or value == "true":
            return LIGHT_GREEN
        if value == "unknown" or value is None:
            return LIGHT_YELLOW
        return LIGHT_RED
    if key == "GO_Q":
        if value is True or value in ("true", "complete", "done"):
            return LIGHT_GREEN
        if value in ("partial", "unknown", None) or value is False:
            return LIGHT_YELLOW
        return LIGHT_YELLOW
    if key == "field_ops_ml_live_fusion":
        # ON is the honest rail after 2026-08-13 human promote
        if str(value).upper() == "ON" or value is True:
            return LIGHT_GREEN
        return LIGHT_YELLOW
    if key == "ml_product_go":
        if value is False or value == "false":
            return LIGHT_GREEN  # honest lab not promoted
        return LIGHT_YELLOW
    return LIGHT_YELLOW


def _light_for_presence(ok: bool) -> str:
    return LIGHT_GREEN if ok else LIGHT_YELLOW


def _overall_light(items: list[str]) -> str:
    if LIGHT_RED in items:
        return LIGHT_RED
    if LIGHT_YELLOW in items:
        return LIGHT_YELLOW
    return LIGHT_GREEN


def go_q_missing_plain(gates: dict[str, Any] | None = None) -> dict[str, Any]:
    """What is missing for GO_Q in operator language (never invent complete)."""
    g = gates or {}
    go_q = g.get("GO_Q", "partial")
    complete = go_q is True or go_q in ("true", "complete", "done")
    return {
        "go_q_complete": complete,
        "status": "listo" if complete else "falta_humano",
        "light": LIGHT_GREEN if complete else LIGHT_YELLOW,
        "what_is_missing": (
            []
            if complete
            else [
                "Demo en vivo con una persona EXTERNA al repo (emergencias / uni / partner)",
                "Acta rellenada con fecha + presentador + nombre del tercero (sin placeholders)",
                "Registrar con: python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_....md",
            ]
        ),
        "what_eng_already_did": [
            "Camino eng H3 (teach → show → pack + replay) listo",
            "Plantilla de acta y runbook H1",
            "Pack third-party + reliability report",
        ],
        "one_liner": (
            "GO_Q cerrado."
            if complete
            else (
                "Para GO_Q falta SOLO lo humano: demo con tercero real + acta firmada (H1/M3.2). "
                "Más ML o más scripts NO cierran GO_Q."
            )
        ),
        "runbook": "docs/H1_GO_Q_RUNBOOK.md",
        "acta_template": KEY_PATHS.get("acta_template", "docs/ACTA_DEMO_TERCERO_TEMPLATE.md"),
        "next_human": NEXT_HUMAN,
    }


# Role playbooks for ``wildfire-front brief`` (professional one-screen summary).
BRIEF_ROLES: frozenset[str] = frozenset({"operator", "field", "lab", "decision"})
_BRIEF_ROLES = BRIEF_ROLES  # backward-compatible alias

ROLE_PLAYBOOKS: dict[str, dict[str, Any]] = {
    "operator": {
        "title": "Operario / demo",
        "audience": "demo con terceros · puerta de entrada",
        "sequence": [
            "python -m wildfire_front brief --role operator",
            "python -m wildfire_front operator",
            "python -m wildfire_front operator do --act 1",
            "python -m wildfire_front operator do --act 3",
            "python -m wildfire_front next",
        ],
        "primary_cmd": "python -m wildfire_front operator",
    },
    "field": {
        "title": "Campo (incident runtime)",
        "audience": "drop-zone · outbox · Decision Card field_ops",
        "sequence": [
            "python -m wildfire_front brief --role field",
            "python -m wildfire_front incident",
            "python -m wildfire_front incident doctor --inbox DIR [--masks DIR]",
            "python -m wildfire_front incident update --inbox DIR --work-dir DIR",
            "python -m wildfire_front decide --policy field_ops --explain",
        ],
        "primary_cmd": "python -m wildfire_front incident doctor --inbox DIR",
    },
    "lab": {
        "title": "ML lab",
        "audience": "scorecard lab · no field fusion · IoU ≠ ROS",
        "sequence": [
            "python -m wildfire_front brief --role lab",
            "python -m wildfire_front ml",
            "python -m wildfire_front ml show",
            "python -m wildfire_front ml doctor",
            "python -m wildfire_front ml freeze",
        ],
        "primary_cmd": "python -m wildfire_front ml show",
    },
    "decision": {
        "title": "Decision / forensics",
        "audience": "GO/HOLD/ABSTAIN + acta + replay",
        "sequence": [
            "python -m wildfire_front brief --role decision",
            "python -m wildfire_front decide --policy field_ops --explain",
            "python -m wildfire_front export-acta --work-dir DIR",
            "python -m wildfire_front replay-decide --work-dir DIR",
        ],
        "primary_cmd": "python -m wildfire_front decide --policy field_ops --explain",
    },
}
_ROLE_PLAYBOOKS = ROLE_PLAYBOOKS  # backward-compatible alias


def build_operator_brief(
    repo: Any = None,
    *,
    role: str = "operator",
) -> dict[str, Any]:
    """Professional one-screen brief (new CLI surface; not the traffic-light board).

    Stable schema ``wfd_operator_brief_v1`` for partners / scripts. Never invents
    GO_Q complete; never claims tactical dispatch; reports field fusion from catalog.
    """
    role_key = str(role or "operator").strip().lower()
    if role_key not in BRIEF_ROLES:
        role_key = "operator"
    play = ROLE_PLAYBOOKS[role_key]
    status = build_operator_status(repo)
    gates = dict(status.get("gates") or {})
    go_q = dict(status.get("go_q") or {})
    fusion = ssot_field_ops_fusion()
    if fusion in ("FALSE", "0", "NO"):
        fusion = "OFF"

    next_action: dict[str, Any]
    if role_key == "operator":
        if not go_q.get("go_q_complete"):
            next_action = {
                "id": "h1_demo_tercero",
                "priority": "P0",
                "summary": go_q.get("one_liner")
                or "GO_Q partial: falta demo+acta con tercero real",
                "command": "python -m wildfire_front next",
                "owner": "human",
            }
        else:
            next_action = {
                "id": "rehearse_acts",
                "priority": "P1",
                "summary": "GO_Q listo — ensayar 4 actos antes de la sesión",
                "command": "python -m wildfire_front operator do --all",
                "owner": "operator",
            }
    elif role_key == "lab":
        next_action = {
            "id": "lab_show_rails",
            "priority": "P1",
            "summary": "Revisar scorecard lab (IoU ≠ ROS; fusion field ON ≠ despacho)",
            "command": "python -m wildfire_front ml show",
            "owner": "lab",
        }
    elif role_key == "field":
        next_action = {
            "id": "field_doctor",
            "priority": "P0",
            "summary": "Pre-flight del drop-zone antes de update/watch",
            "command": "python -m wildfire_front incident doctor --inbox DIR",
            "owner": "field",
        }
    else:
        next_action = {
            "id": "decide_field_ops",
            "priority": "P0",
            "summary": "Decision Card con política field_ops (ABSTAIN es válido)",
            "command": "python -m wildfire_front decide --policy field_ops --explain",
            "owner": "decision",
        }

    return {
        "schema": "wfd_operator_brief_v1",
        "product": "WildfireFrontDynamics",
        "version": "0.1.0",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "role": role_key,
        "role_title": play["title"],
        "audience": play["audience"],
        "disclaimer": (
            "Not validated tactical dispatch. Thermal mask ≠ official perimeter. "
            "15/30/60 envelopes are extrapolated guidance only."
        ),
        "rails": {
            "field_ops_ml_live_fusion": fusion,
            "ml_product_go": bool(gates.get("ml_product_go", True)),
            "iou_is_not_ros": True,
            "lab_go_ne_field_fusion": True,
            "not_tactical_dispatch": True,
            "go_q_invent_forbidden": True,
        },
        "gates": {
            "GO_MES": gates.get("GO_MES"),
            "GO_Q": gates.get("GO_Q", "partial"),
            "ml_product_go": gates.get("ml_product_go"),
            "field_ops_ml_live_fusion": fusion,
        },
        "overall_light": status.get("overall_light"),
        "headline": status.get("overall_plain"),
        "go_q": {
            "complete": bool(go_q.get("go_q_complete")),
            "one_liner": go_q.get("one_liner"),
            "status": go_q.get("status"),
            "runbook": go_q.get("runbook"),
        },
        "next_action": next_action,
        "recommended_sequence": list(play["sequence"]),
        "primary_command": play["primary_cmd"],
        "related": {
            "operator_board": "python -m wildfire_front operator",
            "command_map": "python -m wildfire_front help",
            "doctor": "python -m wildfire_front doctor",
            "ml_hub": "python -m wildfire_front ml",
            "incident_hub": "python -m wildfire_front incident",
        },
        "docs": dict(status.get("docs") or {}),
        "eng_path_ready": bool(status.get("eng_path_ready")),
    }


def format_operator_brief_human(brief: dict[str, Any] | None = None, *, repo: Any = None) -> str:
    """ES-first professional brief for partners / operators (one screen)."""
    data = brief or build_operator_brief(repo)
    rails = data.get("rails") or {}
    gates = data.get("gates") or {}
    go_q = data.get("go_q") or {}
    nxt = data.get("next_action") or {}
    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WFD · BRIEF OPERATIVO  (no despacho táctico)            ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        f"  Producto:  {data.get('product')}  ·  v{data.get('version')}",
        f"  Rol:       {data.get('role_title')} ({data.get('role')})",
        f"  Audiencia: {data.get('audience')}",
        f"  Semáforo:  {data.get('overall_light')}",
        "",
        "── Gates (honestos) ──",
        f"  GO_MES={gates.get('GO_MES')}  ·  GO_Q={gates.get('GO_Q')}",
        f"  ml_product_go={gates.get('ml_product_go')}  ·  field_ops fusion={rails.get('field_ops_ml_live_fusion')}",
        "  Rails: lab GO ≠ field fusion · IoU ≠ ROS · no inventar GO_Q",
        "",
        "── Situación ──",
        f"  {data.get('headline')}",
        f"  GO_Q: {go_q.get('one_liner')}",
        "",
        "── Próxima acción ──",
        f"  [{nxt.get('priority')}] {nxt.get('summary')}",
        f"  → {nxt.get('command')}",
        f"  owner: {nxt.get('owner')}",
        "",
        "── Secuencia recomendada ──",
    ]
    for i, cmd in enumerate(data.get("recommended_sequence") or [], 1):
        lines.append(f"  {i}. {cmd}")
    lines.extend(
        [
            "",
            f"  Primary:  {data.get('primary_command')}",
            f"  Tablero:  {(data.get('related') or {}).get('operator_board')}",
            f"  Mapa:     {(data.get('related') or {}).get('command_map')}",
            "",
            f"  ⚠  {data.get('disclaimer')}",
            "",
        ]
    )
    return "\n".join(lines)


def build_operator_status(repo: Any = None) -> dict[str, Any]:
    """Full operator board: lights, 4 acts, GO_Q gap, presence."""
    snap = load_gate_snapshot(repo)
    gates = dict(snap.get("gates") or {})
    presence = dict(snap.get("presence") or {})

    light_items = {
        "GO_MES": _light_for_gate("GO_MES", gates.get("GO_MES")),
        "GO_Q": _light_for_gate("GO_Q", gates.get("GO_Q")),
        "field_ops_ml_live_fusion": _light_for_gate(
            "field_ops_ml_live_fusion", gates.get("field_ops_ml_live_fusion")
        ),
        "ml_product_go": _light_for_gate("ml_product_go", gates.get("ml_product_go")),
        "demo_multi_ccaa": _light_for_presence(bool(presence.get("demo_multi_ccaa_index"))),
        "pilot_honesty": _light_for_presence(bool(presence.get("pilot_honesty_index"))),
        "demo_third_party": _light_for_presence(bool(presence.get("demo_third_party"))),
    }
    overall = _overall_light(list(light_items.values()))
    # Operator can demo eng path if artifacts ok and GO_MES true — still yellow overall if GO_Q partial
    eng_ready = (
        light_items["GO_MES"] == LIGHT_GREEN
        and light_items["demo_third_party"] == LIGHT_GREEN
        and light_items["field_ops_ml_live_fusion"] == LIGHT_GREEN
    )

    acts_brief = [
        {
            "id": a["id"],
            "name": a["name"],
            "title": a["title"],
            "message": a["message"],
            "operator_command": f"python -m wildfire_front operator do --act {a['id']}",
            "light": (
                LIGHT_GREEN
                if (
                    (a["id"] == 1 and presence.get("demo_multi_ccaa_index"))
                    or (a["id"] == 2 and presence.get("pilot_honesty_index"))
                    or (a["id"] == 3)  # decide always runnable
                    or (a["id"] == 4 and presence.get("demo_third_party"))
                )
                else LIGHT_YELLOW
            ),
        }
        for a in TEACH_ACTS
    ]

    go_q = go_q_missing_plain(gates)

    return {
        "schema": "wfd_operator_status_v1",
        "entry_command": "python -m wildfire_front operator",
        "overall_light": overall,
        "overall_plain": _overall_plain(overall, eng_ready, go_q),
        "lights": light_items,
        "gates": gates,
        "presence": presence,
        "acts": acts_brief,
        "go_q": go_q,
        "legend": {
            LIGHT_GREEN: "listo",
            LIGHT_YELLOW: "falta algo (no roto)",
            LIGHT_RED: "bloqueado",
        },
        "rails_line": rails_one_liner(
            {
                "GO_MES": gates.get("GO_MES"),
                "GO_Q": gates.get("GO_Q", "partial"),
                "ml_product_go": gates.get("ml_product_go", True),
                "field_ops_ml_live_fusion": gates.get("field_ops_ml_live_fusion", "OFF"),
            }
        ),
        "docs": {
            "course": COURSE_PATH,
            "cheatsheet": CHEATSHEET_PATH,
            "start_here": KEY_PATHS.get("start_here", "docs/START_HERE.md"),
            "h1_runbook": "docs/H1_GO_Q_RUNBOOK.md",
        },
        "eng_path_ready": eng_ready,
    }


def _overall_plain(overall: str, eng_ready: bool, go_q: dict[str, Any]) -> str:
    if overall == LIGHT_GREEN and go_q.get("go_q_complete"):
        return "Todo listo para demo con terceros (GO_Q cerrado)."
    if eng_ready:
        return (
            "Camino de operario LISTO para ensayar los 4 actos. "
            "GO_Q sigue abierto: falta demo+acta con tercero real."
        )
    if overall == LIGHT_RED:
        return "Hay un bloqueo. Mira las filas ROJO abajo."
    return (
        "Falta preparar algún demo (AMARILLO). "
        "Ejecuta: python -m wildfire_front operator do --act N"
    )


def format_operator_human(
    status: dict[str, Any] | None = None,
    *,
    quiet: bool = False,
    verbose: bool = False,
    repo: Any = None,
) -> str:
    """Spanish-friendly operator board (the only screen they need)."""
    st = status or build_operator_status(repo)
    lights = st.get("lights") or {}
    legend = st.get("legend") or {}
    go_q = st.get("go_q") or {}
    acts = st.get("acts") or []

    if quiet:
        lines = [
            f"semáforo: {st.get('overall_light')}",
            f"GO_Q: {(st.get('gates') or {}).get('GO_Q', 'partial')}",
            go_q.get("one_liner", ""),
        ]
        return "\n".join(lines) + "\n"

    def row(label: str, light: str, detail: str) -> str:
        meaning = legend.get(light, "")
        return f"  [{light:<8}] {label:<28} {detail}  ({meaning})"

    lines = [
        "╔══════════════════════════════════════════════════════════╗",
        "║  WFD · MODO OPERARIO  (único comando de entrada)         ║",
        "╚══════════════════════════════════════════════════════════╝",
        "",
        "  Setup (PowerShell, una vez por terminal):",
        "    cd <repo>",
        '    $env:PYTHONPATH = "."',
        "",
        f"  Comando:  {st.get('entry_command')}",
        f"  Semáforo: {st.get('overall_light')}  —  {st.get('overall_plain')}",
        f"  Rails:    {st.get('rails_line')}",
        "",
        "── Leyenda ──────────────────────────────────────────────",
        f"  {LIGHT_GREEN}    = listo",
        f"  {LIGHT_YELLOW} = falta algo (el sistema NO está roto)",
        f"  {LIGHT_RED}     = bloqueado",
        "",
        "── Estado ───────────────────────────────────────────────",
        row("GO_MES (mes eng)", lights.get("GO_MES", LIGHT_YELLOW), "criterio mes"),
        row(
            "GO_Q (demo terceros)",
            lights.get("GO_Q", LIGHT_YELLOW),
            str((st.get("gates") or {}).get("GO_Q", "partial")),
        ),
        row(
            "ML fusion field_ops",
            lights.get("field_ops_ml_live_fusion", LIGHT_YELLOW),
            str((st.get("gates") or {}).get("field_ops_ml_live_fusion", "OFF")),
        ),
        row(
            "Demo multi-CCAA",
            lights.get("demo_multi_ccaa", LIGHT_YELLOW),
            "acto 1",
        ),
        row(
            "Pilot honesty",
            lights.get("pilot_honesty", LIGHT_YELLOW),
            "acto 2",
        ),
        row(
            "Pack third-party",
            lights.get("demo_third_party", LIGHT_YELLOW),
            "acto 4",
        ),
        "",
        "── Los 4 pasos (solo estos) ─────────────────────────────",
    ]
    for a in acts:
        light = a.get("light", LIGHT_YELLOW)
        lines.append(f"  {a.get('id')}. [{light}] {a.get('title')}")
        lines.append(f"     → {a.get('operator_command')}")
        if verbose:
            lines.append(f"       ({a.get('message')})")
    lines.extend(
        [
            "",
            "── Qué falta para GO_Q ──────────────────────────────────",
            f"  {go_q.get('one_liner', '')}",
        ]
    )
    missing = go_q.get("what_is_missing") or []
    if missing:
        lines.append("  Checklist humano:")
        for i, m in enumerate(missing, 1):
            lines.append(f"    {i}. {m}")
    lines.extend(
        [
            f"  Runbook: {go_q.get('runbook', 'docs/H1_GO_Q_RUNBOOK.md')}",
            f"  Acta:    {go_q.get('acta_template', KEY_PATHS.get('acta_template'))}",
            "",
            "── Ayuda rápida ─────────────────────────────────────────",
            "  (sin comando) / operator / operador / ops / status → este tablero",
            "  help / commands                            → mapa por rol",
            "  doctor                                     → pre-flight ML lab",
            "  ensayo  (= do --all)                       → 4 actos compactos",
            "  next / go_q                                → qué falta para GO_Q",
            "  checklist                                  → checklist de operario",
            "  operator do --act 1|2|3|4                  → un acto",
            "  operator explain-abstain                   → por qué se calla",
            "  make operator | ensayo | operator-next",
            "",
            "  ABSTAIN = el producto se calla a propósito (no es un bug).",
            f"  Curso: {COURSE_PATH} · Cheatsheet: {CHEATSHEET_PATH}",
            "",
        ]
    )
    return "\n".join(lines)


def format_operator_next(
    status: dict[str, Any] | None = None,
    checklist: dict[str, Any] | None = None,
    *,
    quiet: bool = False,
    verbose: bool = False,
    repo: Any = None,
) -> str:
    """What to do next — eng path vs human GO_Q (never invents complete)."""
    st = status or build_operator_status(repo)
    check = checklist or evaluate_operator_checklist(status=st, repo=repo)
    go_q = st.get("go_q") or {}
    eng_ready = bool(st.get("eng_path_ready"))
    session_ok = bool(check.get("session_all_four_ok"))
    loop_done = bool(check.get("loop_done"))

    if quiet:
        return (
            f"eng_path_ready={eng_ready} session_4ok={session_ok} "
            f"GO_Q={go_q.get('status', 'partial')}\n"
            f"{go_q.get('one_liner', '')}\n"
        )

    lines = [
        "=== Operario · NEXT ===",
        f"Semáforo global: {st.get('overall_light')}  ·  eng_path_ready={eng_ready}",
        f"Ensayo 4 actos registrado: {session_ok}  ·  checklist loop_done={loop_done}",
        "",
        "── Ahora (eng, ya listo si session OK) ─────────────────────",
    ]
    if not session_ok:
        lines.extend(
            [
                "  1. python -m wildfire_front ensayo",
                "  2. python -m wildfire_front operator checklist",
            ]
        )
    else:
        lines.extend(
            [
                "  Eng de los 4 actos: HECHO (sello en outputs/operator_ux_last_run.json).",
                "  Puedes re-ensayar: python -m wildfire_front ensayo",
            ]
        )
    lines.extend(
        [
            "",
            "── Qué falta para GO_Q (solo humano) ─────────────────────",
            f"  {go_q.get('one_liner', '')}",
        ]
    )
    for i, m in enumerate(go_q.get("what_is_missing") or [], 1):
        lines.append(f"  {i}. {m}")
    lines.extend(
        [
            f"  Runbook: {go_q.get('runbook', 'docs/H1_GO_Q_RUNBOOK.md')}",
            f"  Acta:    {go_q.get('acta_template', KEY_PATHS.get('acta_template'))}",
            "",
            "  Más eng o más ML NO cierran GO_Q.",
            "",
        ]
    )
    if verbose:
        lines.append(f"  Rails: {st.get('rails_line')}")
        lines.append("")
    return "\n".join(lines)


def format_abstain_plain(card: dict[str, Any] | None = None) -> str:
    """Plain-language explanation when the system stays silent (ABSTAIN)."""
    decision = (card or {}).get("decision", "ABSTAIN")
    reasons = list((card or {}).get("reasons") or [])
    sources = (card or {}).get("sources") or []
    missing_src: list[str] = []
    if isinstance(sources, list):
        for s in sources:
            if isinstance(s, dict) and not s.get("available"):
                missing_src.append(str(s.get("id") or "?"))
    if not missing_src:
        for r in reasons:
            rs = str(r)
            if rs.startswith("missing:"):
                missing_src.append(rs.split(":", 1)[-1])

    lines = [
        "┌─────────────────────────────────────────────────────────┐",
        "│  EL SISTEMA SE CALLA (ABSTAIN) — esto NO es un fallo    │",
        "└─────────────────────────────────────────────────────────┘",
        "",
        f"  Decisión: {decision}",
        "",
        "  En lenguaje normal:",
        "  · No hay suficientes fuentes de confianza para recomendar acción.",
        "  · El producto prefiere callarse a inventar un GO peligroso.",
        "  · ABSTAIN es una FEATURE de seguridad, no un crash ni un bug.",
        "",
    ]
    if missing_src:
        lines.append("  Fuentes que faltan en esta ejecución:")
        for m in missing_src:
            plain = {
                "ops": "ops térmico (dron/LWIR) — no hay secuencia cargada",
                "open_cems": "perímetro open CEMS — no hay pack abierto",
                "ml_clm_ensemble": "ML lab (holdout) — no se fusiona en field_ops por defecto",
            }.get(m, m)
            lines.append(f"    · {plain}")
        lines.append("")
    lines.extend(
        [
            "  Qué puede hacer un operario:",
            "    1. Entender el mensaje (ya lo estás haciendo).",
            "    2. Cargar datos reales (ops / open pack) si existen.",
            "    3. En demo: operator do --act 2  (pilot honesty) y acto 4 (pack).",
            "    4. Nunca forzar un GO sin fuentes — viola la política field_ops.",
            "",
            f"  Rails: field_ops ML live fusion = {ssot_field_ops_fusion()} · ml_product_go = true",
            "  Doc: docs/PILOT_HONESTY_CARD.md · docs/PRODUCTO_DUAL.md",
            "",
        ]
    )
    return "\n".join(lines)


def write_operator_session(
    acts: list[dict[str, Any]],
    *,
    repo: Path | None = None,
    mode: str = "do",
    merge: bool | None = None,
) -> Path:
    """Persist last operator do session under outputs/ (not a GO_Q claim).

    ``do --all`` replaces the stamp. Single ``do --act N`` **merges** into the
    previous stamp so one act cannot wipe a completed 4-act rehearsal.
    """
    root = resolve_repo_root(repo)
    path = root / OPERATOR_SESSION_REL
    path.parent.mkdir(parents=True, exist_ok=True)

    # Default: merge for single-act modes; replace for full rehearsal
    if merge is None:
        merge = "all" not in str(mode)

    ok_from_run = {int(a["act"]) for a in acts if a.get("ok")}
    fail_from_run = {int(a["act"]) for a in acts if not a.get("ok")}
    ok_acts_set: set[int] = set(ok_from_run)
    prev_acts: list[dict[str, Any]] = []
    if merge:
        prev = load_operator_session(root)
        if isinstance(prev, dict):
            for a in prev.get("ok_acts") or []:
                try:
                    ok_acts_set.add(int(a))
                except (TypeError, ValueError):
                    continue
            # re-run failure removes that act from the stamp
            ok_acts_set -= fail_from_run
            if isinstance(prev.get("acts"), list):
                prev_acts = list(prev["acts"])

    ok_acts = sorted(ok_acts_set)
    # history: keep previous act rows + this run (cap length)
    history = (prev_acts + list(acts))[-12:]
    payload = {
        "schema": "wfd_operator_session_v1",
        "utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mode": mode,
        "acts": history if merge else list(acts),
        "ok_acts": ok_acts,
        "all_four_ok": set(ok_acts) >= {1, 2, 3, 4},
        "honesty": (
            "Session stamp = eng rehearsal ran; NOT third-party H1; "
            "does not flip GO_Q. Single do --act merges; do --all replaces."
        ),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_operator_session(repo: Path | None = None) -> dict[str, Any] | None:
    """Load last session stamp if present and well-formed."""
    root = resolve_repo_root(repo)
    path = root / OPERATOR_SESSION_REL
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None


def evaluate_operator_checklist(
    *,
    status: dict[str, Any] | None = None,
    simulated_pass: dict[str, bool] | None = None,
    repo: Any = None,
) -> dict[str, Any]:
    """Evaluate operator checklist against current board + optional sim flags.

    ``simulated_pass`` lets tests mark acts completed after a dry run.
    Without simulation, eng-side items auto-pass when presence/gates allow;
    human GO_Q item only passes if GO_Q is complete.
    Session stamp (``operator do``) upgrades basis from artifact_presence → session_ran.
    """
    st = status or build_operator_status(repo)
    lights = st.get("lights") or {}
    go_q = st.get("go_q") or {}
    sim = simulated_pass or {}
    session = load_operator_session(repo)
    session_ok: set[int] = set()
    if isinstance(session, dict):
        for a in session.get("ok_acts") or []:
            try:
                session_ok.add(int(a))
            except (TypeError, ValueError):
                continue
        if not session_ok and session.get("all_four_ok"):
            session_ok = {1, 2, 3, 4}

    # Auto basis: artifact presence / command surface — NOT "human ran the demo".
    # Override with simulated_pass after a real operator do --act N session.
    basis: dict[str, str] = {
        "entry": "command_surface",
        "semaphore": "board_renders",
        "act1": "artifact_presence",
        "act2": "artifact_presence",
        "act3": "command_surface",
        "act4": "artifact_presence",
        "go_q": "gate_or_awareness",
    }
    auto: dict[str, bool] = {
        "entry": True,  # command exists if we are here
        "semaphore": st.get("overall_light") in (LIGHT_GREEN, LIGHT_YELLOW, LIGHT_RED),
        "act1": lights.get("demo_multi_ccaa") == LIGHT_GREEN,
        "act2": lights.get("pilot_honesty") == LIGHT_GREEN,
        "act3": True,  # decide always available
        "act4": lights.get("demo_third_party") == LIGHT_GREEN,
        "go_q": bool(go_q.get("go_q_complete")),
    }
    # Session stamp: ensayo real (aún no es H1 tercero)
    for n in (1, 2, 3, 4):
        key = f"act{n}"
        if n in session_ok and auto.get(key):
            basis[key] = "session_ran"
            auto[key] = True
        elif n in session_ok:
            # Ran even if artifact flag flaky — still count as executed
            basis[key] = "session_ran"
            auto[key] = True
    # Merge simulation overrides (e.g. after operator do --act N in a session)
    for k, v in sim.items():
        if k in auto:
            auto[k] = bool(v)
            basis[k] = "simulated_or_session"

    items: list[dict[str, Any]] = []
    for spec in OPERATOR_CHECKLIST:
        iid = spec["id"]
        ok = bool(auto.get(iid, False))
        note = None
        if ok and iid.startswith("act") and basis.get(iid) == "artifact_presence":
            note = "artefacto listo (ejecuta do --act / do --all para ensayar en vivo)"
        elif ok and iid.startswith("act") and basis.get(iid) == "session_ran":
            utc = (session or {}).get("utc", "?")
            note = f"ensayo registrado ({utc}) — aún no es H1 tercero"
        elif ok and iid == "act3" and basis.get(iid) == "command_surface":
            note = "decide siempre ejecutable (vacío → ABSTAIN feature)"
        items.append(
            {
                "id": iid,
                "label": spec["label"],
                "hint": spec["hint"],
                "pass": ok,
                "light": LIGHT_GREEN if ok else LIGHT_YELLOW,
                "basis": basis.get(iid, "unknown"),
                **({"note": note} if note else {}),
            }
        )

    n_pass = sum(1 for i in items if i["pass"])
    n_total = len(items)
    # Stop criterion for UX loop: all 4 acts + entry + semaphore + knows GO_Q gap
    # GO_Q item "pass" means operator *knows* the gap OR gate complete.
    # For eng loop, knowing the gap = we surface one_liner (always) → treat
    # go_q checklist as pass when one_liner present and not complete (aware).
    knows_go_q = bool(go_q.get("one_liner")) and (
        bool(go_q.get("go_q_complete")) or bool(go_q.get("what_is_missing"))
    )
    for it in items:
        if it["id"] == "go_q" and not it["pass"] and knows_go_q:
            # Operator knows what is missing (awareness), not that gate is closed
            it["pass"] = True
            it["light"] = LIGHT_GREEN
            it["note"] = "sabe el hueco (GO_Q aún partial)"
            it["basis"] = "awareness_not_complete"
            n_pass = sum(1 for i in items if i["pass"])

    all_acts = all(i["pass"] for i in items if i["id"].startswith("act"))
    entry_ok = all(i["pass"] for i in items if i["id"] in ("entry", "semaphore", "go_q"))
    loop_done = all_acts and entry_ok
    session_all = bool(session and session.get("all_four_ok"))

    honesty = (
        "pass en actos 1/2/4 sin sello = artefacto en disco (listo para do). "
        "basis=session_ran = ensayo eng registrado (do --all / do --act). "
        "NO es demo H1 con tercero. GO_Q complete solo con H1."
    )
    if session_all:
        summary = (
            "Ensayo 4 actos REGISTRADO + sabe GO_Q. Loop UX eng CERRADO "
            "(H1 humano / GO_Q partial sigue pendiente)."
        )
    elif loop_done:
        summary = (
            "Operario eng-path LISTO: 4 actos ejecutables + sabe GO_Q. "
            "Loop UX eng CERRADO (H1 humano sigue pendiente). "
            "Tip: operator do --all para registrar ensayo."
        )
    else:
        summary = f"Checklist {n_pass}/{n_total}. Falta completar actos o claridad GO_Q."

    return {
        "schema": "wfd_operator_checklist_v1",
        "items": items,
        "n_pass": n_pass,
        "n_total": n_total,
        "all_four_acts": all_acts,
        "knows_go_q_gap": knows_go_q,
        "loop_done": loop_done,
        "session_all_four_ok": session_all,
        "session_utc": (session or {}).get("utc"),
        "overall_light": LIGHT_GREEN if loop_done else LIGHT_YELLOW,
        "honesty": honesty,
        "summary": summary,
        "go_q_one_liner": go_q.get("one_liner"),
    }


def format_checklist_human(result: dict[str, Any]) -> str:
    lines = [
        "=== Checklist operario ===",
        f"Semáforo: {result.get('overall_light')}  ·  {result.get('n_pass')}/{result.get('n_total')}",
    ]
    if result.get("session_utc"):
        lines.append(
            f"Último ensayo: {result.get('session_utc')}  ·  "
            f"4 actos OK en sello: {result.get('session_all_four_ok')}"
        )
    lines.append("")
    for it in result.get("items") or []:
        mark = "OK" if it.get("pass") else "··"
        lines.append(f"  [{mark}] {it.get('label')}")
        if not it.get("pass"):
            lines.append(f"       hint: {it.get('hint')}")
        elif it.get("note"):
            lines.append(f"       note: {it.get('note')}")
    lines.extend(
        [
            "",
            result.get("summary", ""),
            f"GO_Q: {result.get('go_q_one_liner', '')}",
        ]
    )
    honesty = result.get("honesty")
    if honesty:
        lines.append(f"Honestidad: {honesty}")
    lines.append("")
    return "\n".join(lines)
