#!/usr/bin/env python3
"""B1 — Prepare H1 demo session (12 min) without closing GO_Q.

Writes calendar invite + session JSON. Optionally runs eng dry-run / acta draft
helpers when those scripts exist. Does **not** close GO_Q (needs signed third-party acta).

Usage:
  python scripts/prepare_h1_demo_session.py
  python scripts/prepare_h1_demo_session.py --skip-dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "H1_DEMO_SESSION_READY.json"
INVITE_MD = ROOT / "docs" / "H1_CALENDAR_INVITE.md"
CHEATSHEET = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
RUNBOOK = ROOT / "docs" / "H1_GO_Q_RUNBOOK.md"
DRAFT = ROOT / "docs" / "actas" / "ACTA_DEMO_PENDING_HUMAN.md"
DEMO_PACK = ROOT / "outputs" / "demo_third_party"
RELIABILITY = ROOT / "docs" / "RELIABILITY_GATE_REPORT_THIRD_PARTY.md"
GO_TOTAL = ROOT / "docs" / "GO_TOTAL_STATUS.json"

DEMO_PACK_REQUIRED = (
    "README.md",
    "fire_decision_card.json",
    "fire_decision_card.md",
    "forensic_manifest.json",
    "replay_manifest.json",
    "replay_sources.json",
)


def load_stamp_rails(root: Path | None = None) -> dict[str, Any]:
    """Snapshot ML product stamp rails. Never invent GO_Q complete."""
    root = root or ROOT
    stamp_path = root / "docs" / "ML_PRODUCT_GO_STATUS.json"
    fusion = "OFF"
    go_q: Any = "partial"
    go_mes = True
    go_mes_plus = False
    if stamp_path.is_file():
        try:
            stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            stamp = {}
        if isinstance(stamp, dict):
            if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
                fusion = "ON"
            rails = stamp.get("rails") if isinstance(stamp.get("rails"), dict) else {}
            if rails.get("field_ops_fusion") is not None:
                fusion = str(rails["field_ops_fusion"]).upper()
            gq = stamp.get("GO_Q", "partial")
            if gq is True or str(gq).lower() in {"true", "complete", "full"}:
                go_q = "partial"
            elif gq is not None:
                go_q = gq
            if "GO_MES" in stamp:
                go_mes = bool(stamp["GO_MES"])
            if "GO_MES_plus" in stamp:
                go_mes_plus = bool(stamp["GO_MES_plus"])
    return {
        "GO_MES": go_mes,
        "GO_Q": go_q,
        "ml_product_go": "true_lab_only",
        "field_ops_fusion": fusion,
        "GO_MES_plus": go_mes_plus,
    }


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def _run(cmd: list[str]) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def _pack_ok() -> tuple[bool, list[str]]:
    """Check the compact third-party replay contract without rebuilding it."""
    missing = [name for name in DEMO_PACK_REQUIRED if not (DEMO_PACK / name).is_file()]
    return not missing, missing


def write_go_total_status(
    *,
    now: datetime,
    eng_ready: bool,
    pack_step: dict,
    rel_step: dict,
    refuse_verified: bool,
    h1_slot: str = "not_booked",
) -> dict:
    """Write an honest GO_TOTAL snapshot; only the signed-acta CLI may close it."""
    human_blockers = [
        {
            "id": "agenda_tercero",
            "owner": "human",
            "status": "open",
            "blocks": ["GO_Q", "GO_TOTAL"],
            "detail": "Agendar una persona externa real; ingeniería no inventa identidad ni cita.",
        },
        {
            "id": "run_demo_12min",
            "owner": "human",
            "status": "open",
            "blocks": ["GO_Q", "GO_TOTAL"],
            "detail": "Ejecutar la demo con el tercero y completar un acta real.",
        },
        {
            "id": "signed_h1_acta",
            "owner": "human",
            "status": "open",
            "blocks": ["GO_Q", "GO_TOTAL"],
            "detail": "Registrar acta no-PENDING mediante record_h1_demo_complete.py.",
        },
    ]
    stretch = {
        "id": "go_mes_plus",
        "owner": "human",
        "status": "open",
        "blocks": ["GO_MES+"],
        "blocks_go_total": False,
        "detail": "Segundo grade-A/O2 nacional; stretch separado de GO_TOTAL.",
    }
    payload = {
        "schema": "wfd_go_total_status_v1",
        "as_of_utc": now.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "met": False,
        "go_total": False,
        "h1_slot": {
            "status": h1_slot,
            "owner": "human",
            "detail": "Requiere tercero externo y acta real; no se infiere de un dry-run.",
        },
        "gates": {
            "GO_MES": True,
            "GO_Q": "partial",
            "GO_MES_plus": False,
            "ml_product_go": True,
            "field_ops_fusion": "ON",
        },
        "go_q": {
            "met": False,
            "status": "partial",
            "eng_session_ready": bool(eng_ready),
            "h1_acta": None,
        },
        "inventory": {
            "blockers": [
                {
                    "id": "prepare_h1_demo_session",
                    "owner": "eng",
                    "status": "closed" if eng_ready else "open",
                    "blocks": [],
                },
                *human_blockers,
                stretch,
            ]
        },
        "eng_closable": {
            "prepare_h1_demo_session": bool(eng_ready),
            "demo_third_party_pack": bool(pack_step.get("ok")),
            "reliability_third_party": bool(rel_step.get("ok")),
            "record_h1_refuses_pending": bool(refuse_verified),
            "check_release_flags_complete_only_with_h1_acta": True,
        },
        "remaining_human_steps": [
            {"id": row["id"], "owner": "human", "detail": row["detail"]}
            for row in human_blockers
        ],
        "human_commands": [
            "# Agendar tercero externo y ejecutar la demo; no inventar nombres.",
            "# Copiar el draft a docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md y rellenarlo.",
            "python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md",
            "python scripts/check_release_flags.py",
        ],
    }
    GO_TOTAL.parent.mkdir(parents=True, exist_ok=True)
    GO_TOTAL.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def build_invite_md(*, when_hint: str, fusion: str | None = None) -> str:
    rail = str(fusion or load_stamp_rails()["field_ops_fusion"] or "OFF").upper()
    kill_fusion = (
        "fusion ON ≠ GO_Q complete ≠ despacho táctico"
        if rail == "ON"
        else "No field_ops ML live fusion ON"
    )
    return f"""# Invitación calendario — Demo WFD 12 min (H1 / GO_Q)

> **Copia/pega a Google Calendar / Outlook.**
> **Eng no cierra GO_Q** — al terminar, rellenar acta real y:

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

## Título
WildfireFrontDynamics — demo decisión 12 min (HITL, fusion {rail})

## Cuándo (propuesta)
{when_hint}

## Duración
12–15 min (+ 5 min Q&A opcional)

## Asistentes
- **Presentador (repo):** _rellenar nombre_
- **Tercero externo (obligatorio):** _emergencias / uni / partner_ — **sin tercero no hay H1**

## Agenda (cheatsheet)

| Min | Bloque |
|----:|--------|
| 0–1 | Rails en voz alta: GO_MES true · GO_Q partial · fusion **{rail}** · ml_product_go **lab only** · ABSTAIN = feature · fusion ON ≠ despacho |
| 1–4 | Ver multi-CCAA (3 contratos) |
| 4–6 | Callarse (pilot honesty / field_ops se calla) |
| 6–9 | Decision Card + explain |
| 9–11 | Pack third-party + replay |
| 11–12 | Límites + ask · acta |

Detalle: `{_rel(CHEATSHEET)}`
Runbook: `{_rel(RUNBOOK)}`

## Setup 30 s (presentador)

```powershell
cd <repo_WFD>
$env:PYTHONPATH = "."
python -m wildfire_front operator checklist
```

## Kill list verbal (obligatorio)
- No ROS inventado
- {kill_fusion}
- No vender Tobarra LOFO ~0.48 como producto de campo
- No “apagamos incendios con IA”

## Después de la call
1. Acta firmada: `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` (no PENDING)
2. `python scripts/record_h1_demo_complete.py --acta <acta>` → exit 0 cierra M3.2/GO_Q en status JSON
3. Si exit 2: campos vacíos / placeholder — **no se muta status** (correcto)

## Estado eng pre-call
Ver `docs/H1_DEMO_SESSION_READY.json` (este prepare).
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prepare H1 12-min demo session (no GO_Q flip)")
    ap.add_argument("--skip-dry-run", action="store_true")
    ap.add_argument(
        "--when-days",
        type=int,
        default=3,
        help="Suggested start offset in days from now (default 3)",
    )
    args = ap.parse_args(argv)

    now = datetime.now(UTC)
    when = (now + timedelta(days=max(1, args.when_days))).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    when_hint = (
        f"**Propuesta eng:** {when.date().isoformat()} 10:00–10:15 (UTC) "
        f"— reprogramar con el tercero. Prepared UTC: {now.isoformat()}"
    )

    steps: list[dict] = []

    # 1) Acta draft (optional helper)
    acta_script = ROOT / "scripts" / "prepare_h1_acta_draft.py"
    if acta_script.is_file():
        code, _ = _run([sys.executable, str(acta_script)])
        steps.append(
            {
                "id": "prepare_acta_draft",
                "exit_code": code,
                "ok": code == 0 and DRAFT.is_file(),
                "draft": _rel(DRAFT) if DRAFT.is_file() else None,
            }
        )
    else:
        steps.append(
            {
                "id": "prepare_acta_draft",
                "exit_code": None,
                "ok": DRAFT.is_file(),
                "skipped": True,
                "note": "scripts/prepare_h1_acta_draft.py not in tree; using existing draft if present",
                "draft": _rel(DRAFT) if DRAFT.is_file() else None,
            }
        )

    # 2) Dry-run third party path (optional)
    dry: dict = {"skipped": True}
    dry_script = ROOT / "scripts" / "dry_run_demo_third_party.py"
    if not args.skip_dry_run and dry_script.is_file():
        dcode, dout = _run([sys.executable, str(dry_script)])
        dry = {
            "skipped": False,
            "exit_code": dcode,
            "ok": dcode == 0,
            "tail": "\n".join(dout.strip().splitlines()[-8:]),
        }
        steps.append({"id": "dry_run_demo_third_party", **dry})
    elif not args.skip_dry_run and not dry_script.is_file():
        steps.append(
            {
                "id": "dry_run_demo_third_party",
                "skipped": True,
                "ok": True,
                "note": "dry_run_demo_third_party.py not in tree — invite/session still written",
            }
        )
        dry = {"skipped": True, "ok": True}

    # 3) Prove record refuses PENDING draft (required for eng_session_ready when possible)
    record_script = ROOT / "scripts" / "record_h1_demo_complete.py"
    refuse_verified = False
    if record_script.is_file() and DRAFT.is_file():
        rcode, rout = _run(
            [sys.executable, str(record_script), "--acta", str(DRAFT)]
        )
        refuse_ok = rcode == 2
        refuse_verified = refuse_ok
        steps.append(
            {
                "id": "record_refuses_pending_draft",
                "exit_code": rcode,
                "ok": refuse_ok,
                "blocking": True,
                "note": "exit 2 expected — must not mutate GO_Q from draft",
                "tail": "\n".join(rout.strip().splitlines()[-4:]) if rout.strip() else None,
            }
        )
    else:
        steps.append(
            {
                "id": "record_refuses_pending_draft",
                "exit_code": None,
                "ok": False,
                "skipped": True,
                "blocking": True,
                "note": (
                    "record_h1_demo_complete.py missing or no draft — "
                    "eng_session_ready stays false until refuse-PENDING is verifiable"
                ),
            }
        )

    # 4) Flags check if present (informational; missing CURRENT_STATE must not block invite pack)
    flags_script = ROOT / "scripts" / "check_release_flags.py"
    if flags_script.is_file():
        fcode, fout = _run([sys.executable, str(flags_script)])
        steps.append(
            {
                "id": "check_release_flags",
                "exit_code": fcode,
                "ok": fcode == 0,
                "blocking": False,
                "tail": "\n".join(fout.strip().splitlines()[-4:]) if fout.strip() else None,
            }
        )

    stamp_rails = load_stamp_rails()
    invite = build_invite_md(when_hint=when_hint, fusion=str(stamp_rails["field_ops_fusion"]))
    INVITE_MD.parent.mkdir(parents=True, exist_ok=True)
    INVITE_MD.write_text(invite, encoding="utf-8")

    # eng_session_ready requires measured refuse-PENDING (exit 2). Does not flip GO_Q.
    dry_ok = dry.get("skipped") or dry.get("ok")
    eng_ready = bool(
        dry_ok
        and refuse_verified
        and INVITE_MD.is_file()
        and (CHEATSHEET.is_file() or RUNBOOK.is_file())
    )

    payload = {
        "schema": "wfd_h1_demo_session_ready_v1",
        "prepared_at_utc": now.isoformat(),
        "product_unlock": False,
        "go_q_met": False,
        "not_third_party_acta": True,
        "not_signed_acta": True,
        "go_q_note": "Human third-party demo + signed acta still required",
        "eng_session_ready": bool(eng_ready),
        "suggested_slot_utc": when.isoformat(),
        "artifacts": {
            "cheatsheet": _rel(CHEATSHEET),
            "runbook": _rel(RUNBOOK),
            "calendar_invite": _rel(INVITE_MD),
            "acta_draft": _rel(DRAFT) if DRAFT.is_file() else None,
            "record_cli": "python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md",
            "b4_b5_calendar": "docs/B4_B5_UNBLOCK_CALENDAR.md",
        },
        "human_next": [
            "Agendar tercero externo (copiar docs/H1_CALENDAR_INVITE.md)",
            "Correr demo 12 min con cheatsheet",
            "Rellenar acta real (no PENDING)",
            "python scripts/record_h1_demo_complete.py --acta <acta_firmada>",
        ],
        "steps": steps,
        "rails": stamp_rails,
        "not_claims": [
            "not GO_Q complete",
            "not invented tercero",
            (
                "fusion ON ≠ despacho táctico"
                if str(stamp_rails.get("field_ops_fusion")).upper() == "ON"
                else "not field_ops ML live fusion ON"
            ),
        ],
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": eng_ready,
                "session": _rel(OUT_JSON),
                "invite": _rel(INVITE_MD),
                "go_q_met": False,
            },
            indent=2,
        )
    )
    return 0 if eng_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
