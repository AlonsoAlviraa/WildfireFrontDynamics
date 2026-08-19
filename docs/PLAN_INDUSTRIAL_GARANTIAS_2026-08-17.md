# Plan: industrializar con garantías (2026-08-17)

**Tipo:** producto / gates — no es un sprint de IoU.  
**SSOT flags:** `docs/CURRENT_STATE.md` · `docs/ML_PRODUCT_GO_STATUS.json` · `docs/GO_TOTAL_STATUS.json`  
**Gate script:** `python scripts/industrial_product_gate.py` · `make industrial-gate`

## Norte

Industrial no es predecir el fuego al 99 %. Es un sistema que un organismo puede **usar y auditar**:

1. GO / HOLD / ABSTAIN con política (`field_ops` / `research_open`).
2. **Nunca** GO si faltan fuentes, el grade es bajo o R1–R4 no se midieron.
3. Toda cifra trae fuente + versión + UTC + hash.
4. Ops (frente LWIR / ROS observado) no se mezcla con IoU next-day.
5. El modelo se congela hasta datos que cambien la física.

**Primer firmante (decidido):** observatorio / CMA post-proceso.  
**H1 tercero:** deseado, **no agendado**. GO_Q sigue partial. T2 no es camino crítico de 30 días.

## Garantías de sistema

| ID | Garantía | Target |
|----|----------|--------|
| R1 | Determinismo (mismos hashes → mismos artefactos) | 100 % CI |
| R2 | 0 GO si falta fuente / grade / reliability | 0 bypass |
| R3 | Abstención si confianza &lt; umbral | 100 % suite |
| R4 | Provenance en toda métrica | 100 % |
| R5 | Silent-GO sin R1–R4 | &lt; 10⁻⁶ en tests |
| R6 | IoU ≠ ROS ≠ Vp; fusión solo en la tarjeta | contract test |
| R7 | No-cite = no-promote | `refuse_promote_without_cite` |
| R8 | stamp = CURRENT_STATE = flags | `check_release_flags` PASS |

El “99,9999 %” **solo** es R5 (GO silencioso del pipeline).

## Tracks

| ID | Qué | Bloquea industrial interno |
|----|-----|----------------------------|
| **T0** | RCDA/Caldor `holdout_only` en catálogo; product-gate | sí |
| **T1.1** | `field_ops` GO → ABSTAIN si `system_reliability_pass=false` | sí (ya en `decide`) |
| **T1.2–T1.6** | Replay (sidecar en bundle), SLA Tobarra decide, sidecar outbox, API fail-closed, fusion cap 0.20 | sí |
| **T2** | Demo + acta tercero → GO_Q complete | no (sí para GO_TOTAL comercial) |
| **T3** | 2ª ancla Hellín/Cardoso + path O2 | no (sí para GO_MES+ / operable) |
| **T4** | Nuevo train solo si ≥3 IF + meteo espacial + Δt + split sellado | n/a |
| **T5** | Honesty card / one-pager anclado a T1; no funding UE sin T2 | no |

**Kill:** reabrir RCDA como producto, v35, Tobarra KEEP, Hellín `confirmed` sin cite, entrenar Caldor 15 pares.

## Criterio “industrial interno” (CMA)

1. `field_ops` no puede emitir GO con reliability FAIL (test rojo si se rompe).
2. `check_release_flags` PASS + `industrial_product_gate` PASS.
3. Catálogo: `front_dynamics_v1` + `clm_ensemble_v34` lab; RCDA/Caldor no ready.
4. Decision Card con hashes + policy_id + disclaimers.
5. GO_Q partial hasta acta real; one-pager no dice “validado por emergencias”.

## Verify

```bash
python scripts/industrial_product_gate.py
make industrial-gate
python scripts/check_release_flags.py
```
