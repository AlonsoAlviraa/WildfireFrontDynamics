# Handoff Mes2 PR3 — humanos A/B (2026-08-12)

**Para:** Agentes humanos A (Product Surface) y B (Platform & Data Honesty).  
**No** para bots Grok (crew en stand-down salvo Alonso).

## Estado tip `main`

- Gates: GO_MES true · GO_Q **partial** · fusion **OFF** · FREEZE_ML · Hellín `pending_external`
- PR2 cerrado: #35 (A UI decision-log+ACK) · #34 (B V&V eng stub)
- Brief ejecutable: [`docs/PLAN_MES2_PR3_AGENTES_A_B.md`](PLAN_MES2_PR3_AGENTES_A_B.md)
- SSOT flags: [`docs/CURRENT_STATE.md`](CURRENT_STATE.md)

## Qué abrir

| Agente | Branch | Scope corto |
|--------|--------|-------------|
| **A** | `feat/mes2-a-pr3-h1-polish` | H1 dry-run polish + split-conf residual (SPA/docs A) |
| **B** | `feat/mes2-b-pr3-sector-ros` | Sector ROS default physics/eng + tests (no SPA) |

Ventanas Madrid: A 09–13 · B 14–18 · 1 PR abierto/agente · squash + CI verde.

## Fuera de este handoff

- Flip GO_Q / promote Hellín / marketing → **solo Alonso**
- W3 data-request pack + CI gates → tras ambos PR3
