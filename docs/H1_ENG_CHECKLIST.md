# H1 eng checklist — GO_Q path (human calendar still open)

> **As of eng refresh:** re-run `python scripts/prepare_h1_demo_session.py`  
> **Rails:** GO_MES true · GO_Q **partial** · fusion **ON** ≠ despacho · GO_MES+ false  
> **SSOT plan:** `docs/PLAN_1M_GO_LATAM_2026-08-13.md` (W1-H1/H2 human; W1-E1 eng)

## Eng-done (do not re-invent)

| Item | Status | Proof |
|------|--------|-------|
| Session JSON | eng | `docs/H1_DEMO_SESSION_READY.json` · `go_q_met=false` |
| Calendar invite text | eng | `docs/H1_CALENDAR_INVITE.md` (copy/paste only) |
| Demo pack | eng | `outputs/demo_third_party/` |
| Reliability pointer | eng | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` |
| Refuse PENDING | eng | `record_h1_demo_complete.py` exit **2** on draft |
| Flags path complete+acta | eng | `check_release_flags` only allows GO_Q complete with real `h1_acta` |
| GO_TOTAL status | eng | `docs/GO_TOTAL_STATUS.json` · `met=false` · `h1_slot.status=not_booked` |

## Human-only (Alonso) — eng will not invent

| Step | Artifact / action |
|------|-------------------|
| **W1-H1** Book **1 external tercero** | Paste invite from `docs/H1_CALENDAR_INVITE.md` into Calendar/Outlook; set real name + time |
| Dry-run operator acts 1–4 (optional) | `python -m wildfire_front operator checklist` — **no** GO_Q claim |
| Demo 12 min | `docs/CHEATSHEET_DEMO_12MIN.md` + kill list verbal |
| Signed acta | `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` (not PENDING) |
| Record | `python scripts/record_h1_demo_complete.py --acta …` → exit 0 |
| Verify | `python scripts/check_release_flags.py` PASS with GO_Q complete |

## `h1_slot` field

In `docs/GO_TOTAL_STATUS.json` and session JSON:

| Value | Meaning |
|-------|---------|
| `not_booked` | Default eng truth until Alonso confirms a calendar event |
| `booked_human_open` | Human set after real invite accepted (eng may pass `--h1-slot booked_human_open` only when human says so) |
| `done` | Only after real demo + acta recorded |

**Eng default:** always leave `not_booked` unless Alonso explicitly confirms.

## 2nd outreach template (S3 partial path — if first slot fails)

Copy/adapt; **fill real names only when known — never invent**:

```
Asunto: [WFD] Demo decisión 12 min — segundo intento de agenda

Hola <nombre real o cargo público>,

Seguimos buscando 12–15 min para una demo HITL de apoyo a decisión en incendios
(WildfireFrontDynamics). No es despacho táctico; fusion ML en field_ops está ON
bajo peso acotado y ABSTAIN es feature.

Propuesta: <fecha UTC> o alternativa que os encaje.
Material: cheatsheet 12 min + pack third-party en repo.

Tras la call pedimos un acta corta (Fecha / Presentador / Tercero) para cerrar
nuestro gate GO_Q — sin acta no reclamamos complete.

Gracias,
Alonso
```

Log outreach attempts in personal notes or optional `docs/_outreach_send_log_*.json` — do not invent SENT counts on the claim board.

## Commands

```bash
python scripts/prepare_h1_demo_session.py
python scripts/check_release_flags.py
python -m wildfire_front operator checklist
# After real acta only:
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```
