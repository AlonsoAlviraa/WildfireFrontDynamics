# Scorecard mes 1 — WildfireFrontDynamics

> Ventana plan: 2026-07-17 → 2026-08-17  
> Actualizado en loop-engineering automatizado: **2026-07-17** (cierre parcial de entregables de ingeniería; gates de datos externos siguen OPEN/BLOCKED)

## Producto congelado

| ID | Métrica | Estado |
|----|---------|--------|
| `clm_ensemble_v34` | IoU **0.8963** Δ **+0.2545** growth **0.9071** | GO |
| `clm_v28` | IoU 0.838 Δ +0.196 | GO fallback |
| `ndws_v21` | IoU 0.226 Δ +0.076 | GO research; G1 KILL |
| `front_dynamics_v1` / `incident_runtime_v1` | packs + watch | GO código |

## Gates mes

| Gate | Criterio | Estado | Evidencia |
|------|----------|--------|-----------|
| **M2** v34 no regresa | IoU ≥ 0.890 | **GO** | manifest + tests temps |
| **E1** CI/smokes | tests + smokes | **PARTIAL→GO eng** | `make test`, `demo_dual_product`, Makefile |
| **P1** incident 2 IF | smoke 2 IF reales | **PARTIAL** | synthetic + Tobarra path en smokes; 2º IF depende de QA |
| **O1** multi-ancla | ≥2 confirmed | **OPEN** | solo Tobarra confirmed; Cardoso pending_external |
| **O2** Hausdorff oficial nacional | P50 o abstención | **BLOCKED** | sin perímetro nacional |
| **O2** CEMS open (Pista B) | perímetro multi-temporal | **GO_PROXY** | EMSR578/583 · `docs/PISTA_B_OPEN_IF.md` |
| **O3** temporal | ventanas | PARTIAL | Tobarra histórico |
| **O4** brief 5 min | field kit | **GO eng** | `docs/FIELD_KIT_INCIDENT.md` + outbox briefing |
| **O5** 2º grado A | 2º IF | **OPEN** | requiere ancla |
| **D1** CyL | datos o follow-up | **FOLLOW_UP** | CONTACTOS + SOLICITUD_TRANSPARENCIA_CYL |
| **M5** v35 datos | multi_if mejor | **NO_GO forzado** | sin fuego nuevo no-Cardoso en parches |

## GO_MES

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

| Componente | Met? |
|------------|------|
| O1 | ❌ OPEN (dato externo) |
| O4 | ✅ field kit + briefing |
| P1 | ⚠️ PARTIAL (código listo; 2 IF reales QA-limited) |
| M2 | ✅ |
| E1 | ✅ tests + demo scripts |

**Veredicto mes (hoy):** **NO_GO_MES** — bloqueado por **datos externos** (2ª ancla, perímetro), no por regresión de producto.  
**Veredicto ingeniería automatizable:** **GO_ENG** — v34 alineado, docs, tests, field kit, inventory, O2 blocked honesto, demo one-cmd.

## Entregables ingeniería (cerrados en loop)

- [x] Catalog + CLI v34 (+ alias v30)  
- [x] PRODUCTO_DUAL, DATA_INTAKE_STATUS, FIELD_KIT  
- [x] Tests temperatures + catalog  
- [x] O2 BLOCKED documentado  
- [x] CyL follow-up registrado  
- [x] `scripts/demo_dual_product.py`  
- [x] Makefile smoke-ops / smoke-ml / demo  

## Pendiente humano / externo (no automatizable)

- [ ] Respuesta INFOCAM/CMA con Vp/ha Cardoso (u otro IF)  
- [ ] Perímetro oficial para Hausdorff  
- [ ] Máscaras Polán / completar LA ACOM2  
- [ ] Push remoto + tag `product-v34` (autorización usuario)  
- [ ] Reentreno GPU multi_if si llegan datos nuevos  

## Próximo ritual

Cada viernes: actualizar esta tabla; no abrir bucle ML ∞ sin fuego nuevo.
