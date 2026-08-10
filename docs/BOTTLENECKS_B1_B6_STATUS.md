# Bottlenecks B1–B6 — status after goal pass (2026-08-10)

> **SSOT companion:** `docs/AUDIT_BOTTLENECKS_B1_B10_INDUSTRY.md` · gates: `docs/CURRENT_STATE.md`  
> **Goal:** merge PRs (VisionSetil ML stack) + clear eng-controllable B2/B3; honest status on B1/B4/B5/B6.

| ID | Cuello | Sev. | Control eng | ETA | **Estado tras este goal** | Acción residual |
|----|--------|------|-------------|-----|---------------------------|-----------------|
| **B1** | H1 humano (demo+acta) | crítica | **no** | 1 call 30 min | **ENG READY / HUMAN OPEN** — `scripts/prepare_h1_demo_session.py` + `docs/H1_CALENDAR_INVITE.md`; GO_Q still partial | Agendar tercero + acta firmada + `record_h1_demo_complete.py` |
| **B2** | Docs/flags desalineados | alta | **sí** | ½ día | **MITIGADO** | `scripts/check_release_flags.py` PASS; stamp GO_MES alineado; actas/curso corregidos |
| **B3** | Repo noise (`_*`, untracked) | alta | **sí** | 1–2 h | **MITIGADO** | `.gitignore` AI/data caches endurecido; no `_FINAL_*` en raíz |
| **B4** | Solo 1 grade A ops | alta | parcial | semanas | **OPEN** — grades via `b4_b5_status_probe.py` (null if scorecards missing); calendar `docs/B4_B5_UNBLOCK_CALENDAR.md` | Datos 2º IF / commit scorecards / re-score Hellín sin k-fit |
| **B5** | O2 nacional BLOCKED | media-alta | **no** | externo | **OPEN / BLOCKED** — follow-up calendar in `B4_B5_UNBLOCK_CALENDAR.md` | FOI/partner; no flags |
| **B6** | ML Tobarra LOFO ~0.48 | alta si vende ML | solo datos | mes+ | **CLOSED process (KILL)** | No thrash; FREEZE+REQUEST_DATA; pitch sealed LOFO ~0.79 |

## Verificación eng (B1 / B4 / B5 prep)

```bash
python scripts/prepare_h1_demo_session.py --skip-dry-run
# → docs/H1_CALENDAR_INVITE.md + docs/H1_DEMO_SESSION_READY.json (go_q_met=false)

python scripts/b4_b5_status_probe.py
# → docs/B4_B5_STATUS.json (calendar facts only; no grade invention)
```

## Verificación eng (B2)

```bash
python scripts/check_release_flags.py
# expect: status=PASS exit=0
pytest tests/test_check_release_flags.py -q
```

## Rails no negociables

| Flag | Valor |
|------|--------|
| field_ops ML fusion | **OFF** |
| ml_product_go | **true (lab only)** |
| GO_MES | **true** (mínimo) |
| GO_MES+ | **false** |
| GO_Q | **partial** (B1) |
| Tobarra KEEP reopen | **false** (KILL) |

## VisionSetil (merge side of this goal)

| Item | Status |
|------|--------|
| Stack execute-plan `99d05a8a` (11 PRs) | **MERGED** → `main` via [PR #24](https://github.com/AlonsoAlviraa/VisionSetil/pull/24) |
| product_unlock | **false** |
| E22 GPU train | still operator GAP |

## What this goal does **not** claim

- B1 closed (needs human demo)  
- B4 second grade A  
- B5 national cadastre  
- B6 Tobarra IoU > Head A without new data  
- field_ops fusion ON  
