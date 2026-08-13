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

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs" / "H1_DEMO_SESSION_READY.json"
INVITE_MD = ROOT / "docs" / "H1_CALENDAR_INVITE.md"
CHEATSHEET = ROOT / "docs" / "CHEATSHEET_DEMO_12MIN.md"
RUNBOOK = ROOT / "docs" / "H1_GO_Q_RUNBOOK.md"
DRAFT = ROOT / "docs" / "actas" / "ACTA_DEMO_PENDING_HUMAN.md"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def snapshot_field_ops_fusion() -> str:
    """Same source as check_release_flags / catalog rail. Fail-closed OFF."""
    try:
        from wildfire_front.product.policy import field_ops_ml_live_fusion_rail

        rail = str(field_ops_ml_live_fusion_rail()).upper()
        if rail in {"ON", "OFF"}:
            return rail
    except Exception:
        pass
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
        rails = stamp.get("rails") or {}
        fusion = str(rails.get("field_ops_fusion") or "").upper()
        if fusion in {"ON", "OFF"}:
            return fusion
        if stamp.get("field_ops_allow_ml_live_in_fusion") is True:
            return "ON"
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        pass
    return "OFF"


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


def build_invite_md(*, when_hint: str, fusion: str) -> str:
    fusion = str(fusion or "OFF").upper()
    if fusion == "ON":
        fusion_title = "fusion ON ≠ despacho"
        fusion_kill = (
            "No vender fusion ON (cap 0.20 / abstain 0.45) como GO_Q / despacho / field GO"
        )
    else:
        fusion_title = "fusion OFF"
        fusion_kill = "No field_ops ML live fusion ON"
    return f"""# Invitación calendario — Demo WFD 12 min (H1 / GO_Q)

> **Copia/pega a Google Calendar / Outlook.**  
> **Eng no cierra GO_Q** — al terminar, rellenar acta real y:

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

## Título
WildfireFrontDynamics — demo decisión 12 min (HITL, {fusion_title})

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
| 0–1 | Rails en voz alta: GO_MES true · GO_Q partial · fusion **{fusion}** · ml_product_go **lab only** · ABSTAIN = feature |
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
- {fusion_kill}  
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
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Write invite + session JSON here (default: docs/). Use a temp dir in tests.",
    )
    args = ap.parse_args(argv)
    fusion = snapshot_field_ops_fusion()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (ROOT / "docs")
    out_json = out_dir / "H1_DEMO_SESSION_READY.json"
    invite_md = out_dir / "H1_CALENDAR_INVITE.md"

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

    invite = build_invite_md(when_hint=when_hint, fusion=fusion)
    invite_md.parent.mkdir(parents=True, exist_ok=True)
    invite_md.write_text(invite, encoding="utf-8")

    # eng_session_ready requires measured refuse-PENDING (exit 2). Does not flip GO_Q.
    dry_ok = dry.get("skipped") or dry.get("ok")
    eng_ready = bool(
        dry_ok
        and refuse_verified
        and invite_md.is_file()
        and (CHEATSHEET.is_file() or RUNBOOK.is_file())
    )

    payload = {
        "schema": "wfd_h1_demo_session_ready_v1",
        "prepared_at_utc": now.isoformat(),
        "product_unlock": False,
        "go_q_met": False,
        "go_q_note": "Human third-party demo + signed acta still required",
        "eng_session_ready": bool(eng_ready),
        "suggested_slot_utc": when.isoformat(),
        "artifacts": {
            "cheatsheet": _rel(CHEATSHEET),
            "runbook": _rel(RUNBOOK),
            "calendar_invite": _rel(invite_md),
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
        "rails": {
            "GO_MES": True,
            "GO_Q": "partial",
            "ml_product_go": "true_lab_only",
            "field_ops_fusion": fusion,
        },
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": eng_ready,
                "session": _rel(out_json),
                "invite": _rel(invite_md),
                "go_q_met": False,
            },
            indent=2,
        )
    )
    return 0 if eng_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
