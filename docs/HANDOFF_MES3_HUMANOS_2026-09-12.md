# Handoff Mes 3 — humanos A/B (2026-09-12)

**Ventana:** 12 sep → 11 oct 2026  
**Plan:** [`docs/PLAN_MES3_AGENTES_A_B_2026-09-12.md`](PLAN_MES3_AGENTES_A_B_2026-09-12.md)  
**No** para bots Grok (salvo Alonso despierte crew).

## Tip esperado al start

- Gates: GO_MES true · GO_Q **partial** · fusion **ON** (cap 0.20 / abstain 0.45) ≠ despacho · FREEZE_ML · Hellín `pending_external` · GO_MES+ false
- Mes2 eng: PR1–PR3-A en main (#31/#32/#34/#35/#38); **cerrar #39** PR3-B si sigue abierto
- SSOT: `docs/CURRENT_STATE.md`

## Primera semana (abrir esto)

| Agente | Branch | Scope |
|--------|--------|-------|
| **A** | `feat/mes3-a-w1-vv-ui` | Lectura UI V&V eng + notas E2E |
| **B** | `feat/mes3-b-w1-freeze-ci` | Data-request FREEZE + forensics allowlist + CI smokes |

Ventanas Madrid: A 09–13 · B 14–18 · 1 PR/agente · squash + CI verde.

## Fuera de A/B

- Flip GO_Q / promote Hellín / marketing / tokens → **solo Alonso**
