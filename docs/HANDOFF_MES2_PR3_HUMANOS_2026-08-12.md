# Handoff Mes2 PR3 — Agentes humanos A y B

**Fecha:** 2026-08-12 · **Repo tip:** `main` post-#31/#32/#34/#35  
> **Historical handoff.** Living gates: `docs/CURRENT_STATE.md` — field_ops ML fusion **ON** (human 2026-08-13) ≠ GO_Q complete ≠ despacho. Table below is the rail **at filing**.
**Plan:** `docs/PLAN_MES2_PR3_AGENTES_A_B.md` · **SSOT gates:** `docs/CURRENT_STATE.md`  
**Quién:** compañeros humanos A/B — **no** bots Grok como “Agente A/B”.

## Rails (no tocar)

| Rail | Valor |
|------|--------|
| field_ops ML fusion | **OFF** |
| GO_Q | **partial** (nunca inventar true / complete) |
| FREEZE_ML | activo — no retrain |
| Hellín | `pending_external` hasta cite + Alonso |
| #10 / b2-b3 secret base | **no merge** |

## Quién hace qué (siguiente)

| Agente | PR | Branch sugerida | Dueño de paths |
|--------|-----|-----------------|----------------|
| **A** | **PR3-A** H1 eng polish + **split-conf** ML≠ROS | `feat/mes2-a-pr3-h1-split-conf` | `app_spa*` / `spa_honesty_ui` / SPA tests / APP+cheatsheet only |
| **B** | **PR3-B** **sector ROS** eng default + tests | `feat/mes2-b-pr3-sector-ros` | `emergency_products` / `sector_ros_local` / physics / backend tests / CURRENT_STATE eng note **sin** flip gates |

Máx. **1 PR abierto por agente**. Paths disjuntos. A merge 09–13 · B 14–18 (Madrid).

## Ya shipped (no rehacer)

- #32 uncertainty bar · #31 decision-log backend · #35 decision-log UI+ACK · #34 V&V stub  
- #19 SPA · #18/#22 operator · #29 H1/SR ladder

## Verify one-liners

```powershell
python scripts/check_release_flags.py
# A
make test-spa
# B
python -m pytest tests/test_sector_ros_local.py tests/test_emergency_products.py tests/test_check_release_flags.py -q
```

## No inventar / no merge

- **No** bots Grok como Agente A/B · **no** inventar `GO_Q=true`  
- `GO_Q=true` / fusion ON / GO_MES+ true sin evidencia  
- Promote Hellín sin cite literal + humano  
- Marketing outbound sin Claims clear  
- Cherry-pick desde bases con secretos  
- A tocando `decide_service` / `vv_sidecar` / `emergency_products` · B tocando `app_spa*`

## Humano Alonso (fuera de A/B)

Agenda H1 + acta firmada · tokens fuera de git · Claims clear · único cierre de GO_Q con evidencia.
