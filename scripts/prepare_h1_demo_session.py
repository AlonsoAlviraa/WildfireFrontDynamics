#!/usr/bin/env python3
"""B1 — Prepare H1 demo session (12 min) without closing GO_Q.

Runs eng dry-run path, refreshes acta draft, writes calendar invite + session JSON.
Does **not** call record_h1_demo_complete (that needs a signed third-party acta).

Usage:
  python scripts/prepare_h1_demo_session.py
  python scripts/prepare_h1_demo_session.py --skip-dry-run
"""

from __future__ import annotations

import argparse
import json
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


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        env={
            **dict(**dict(__import__("os").environ.items())),
            "PYTHONPATH": str(ROOT),
        },
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def build_invite_md(*, when_hint: str) -> str:
    return f"""# Invitación calendario — Demo WFD 12 min (H1 / GO_Q)

> **Copia/pega a Google Calendar / Outlook.**
> **Eng no cierra GO_Q** — al terminar, rellenar acta real y:

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

## Título
WildfireFrontDynamics — demo decisión 12 min (HITL, fusion OFF)

## Cuándo (propuesta)
{when_hint}

## Duración
12–15 min (+ 5 min Q&A opcional)

## Asistentes
- **Presentador (repo):** _rellenar nombre_
- **Tercero externo (obligatorio):** _emergencias / uni / partner_ — **sin tercero no hay H1**

## Agenda (cheatsheet industrial SPA C2)

| Min | Bloque |
|----:|--------|
| 0–1 | Rails: GO_MES true · GO_Q **partial** · fusion **OFF** · ABSTAIN = feature |
| 1–3 | **SPA industrial C2** primary surface (`app`) · actos Estado · Decidir · Acta |
| 3–7 | Ver / callarse / Decision Card (4 actos operario) |
| 7–11 | Pack third-party + replay |
| 11–12 | Límites + ask · acta |

Detalle: `{CHEATSHEET.relative_to(ROOT).as_posix()}`
Runbook: `{RUNBOOK.relative_to(ROOT).as_posix()}`

## Setup 30 s (presentador) — SPA C2 primary

```powershell
cd <repo_WFD>
$env:PYTHONPATH = "."
python -m wildfire_front app --demo-day
# o: python -m wildfire_front app --fire _sla_measure --serve
# file:// estático: python -m wildfire_front app --fire _sla_measure --open
python -m wildfire_front operator checklist
```

## Kill list verbal (obligatorio)
- No ROS inventado
- No field_ops ML live fusion ON
- No vender Tobarra LOFO ~0.48 como producto de campo
- No “apagamos incendios con IA”
- No inventar GO_Q complete sin acta firmada de tercero

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

    # 1) Acta draft
    code, out = _run([sys.executable, str(ROOT / "scripts" / "prepare_h1_acta_draft.py")])
    steps.append(
        {
            "id": "prepare_acta_draft",
            "exit_code": code,
            "ok": code == 0 and DRAFT.is_file(),
            "draft": _rel(DRAFT),
        }
    )

    # 2) Dry-run third party path
    dry = {"skipped": True}
    if not args.skip_dry_run:
        dcode, dout = _run([sys.executable, str(ROOT / "scripts" / "dry_run_demo_third_party.py")])
        dry = {
            "skipped": False,
            "exit_code": dcode,
            "ok": dcode == 0,
            "tail": "\n".join(dout.strip().splitlines()[-8:]),
        }
        steps.append({"id": "dry_run_demo_third_party", **dry})

    # 3) Prove record refuses PENDING draft
    rcode, rout = _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "record_h1_demo_complete.py"),
            "--acta",
            str(DRAFT),
        ]
    )
    refuse_ok = rcode == 2
    steps.append(
        {
            "id": "record_refuses_pending_draft",
            "exit_code": rcode,
            "ok": refuse_ok,
            "note": "exit 2 expected — must not mutate GO_Q from draft",
        }
    )

    # 4) Flags check if present
    flags_script = ROOT / "scripts" / "check_release_flags.py"
    if flags_script.is_file():
        fcode, _ = _run([sys.executable, str(flags_script)])
        steps.append({"id": "check_release_flags", "exit_code": fcode, "ok": fcode == 0})

    invite = build_invite_md(when_hint=when_hint)
    INVITE_MD.write_text(invite, encoding="utf-8")

    eng_ready = all(s.get("ok") for s in steps if s["id"] != "dry_run_demo_third_party") and (
        dry.get("skipped") or dry.get("ok")
    )

    payload = {
        "schema": "wfd_h1_demo_session_ready_v1",
        "prepared_at_utc": now.isoformat(),
        "product_unlock": False,
        "go_q_met": False,
        "go_q_note": "Human third-party demo + signed acta still required",
        "go_q_invent_forbidden": True,
        "eng_session_ready": bool(eng_ready),
        "suggested_slot_utc": when.isoformat(),
        "demo_entry": {
            "primary": "python -m wildfire_front app --demo-day",
            "serve": "python -m wildfire_front app --fire _sla_measure --serve",
            "static_open": "python -m wildfire_front app --fire _sla_measure --open",
            "demo_day_cmd": "python -m wildfire_front app --demo-day",
            "live_ops": True,
            "live_endpoints": [
                "/live/v1/status",
                "/live/v1/decide",
                "/live/v1/export-acta",
            ],
            "artifact": "outputs/app/index.html",
            "surface": "industrial_spa_c2",
            "primary_acts": ["Estado", "Decidir", "Acta"],
            "cheatsheet": _rel(CHEATSHEET),
            "runbook": _rel(RUNBOOK),
        },
        "artifacts": {
            "cheatsheet": _rel(CHEATSHEET),
            "runbook": _rel(RUNBOOK),
            "calendar_invite": _rel(INVITE_MD),
            "acta_draft": _rel(DRAFT),
            "spa_app": "outputs/app/index.html",
            "record_cli": (
                "python scripts/record_h1_demo_complete.py "
                "--acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md"
            ),
        },
        "human_next": [
            "Agendar tercero externo (copiar docs/H1_CALENDAR_INVITE.md)",
            "Correr SPA industrial live: python -m wildfire_front app --demo-day",
            "Correr demo 12 min con cheatsheet (docs/CHEATSHEET_DEMO_12MIN.md)",
            "Rellenar acta real (no PENDING)",
            "python scripts/record_h1_demo_complete.py --acta <acta_firmada>",
        ],
        "steps": steps,
        "rails": {
            "GO_MES": True,
            "GO_Q": "partial",
            "go_q_met": False,
            "go_q_invent_forbidden": True,
            "ml_product_go": "true_lab_only",
            "field_ops_fusion": "OFF",
        },
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
