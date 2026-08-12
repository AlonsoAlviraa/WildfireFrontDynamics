# Scorecard mes 1 — WildfireFrontDynamics

> Ventana plan: 2026-07-17 → 2026-08-17  
> Actualizado: **2026-08-03** (Hellín 2ª ancla confirmed + pack Pablo 0308)  
> Canonical: `docs/PROJECT_STATUS.md` · recompute: `docs/O1_GOMES_RECOMPUTE_20260803.json`

## Producto congelado

| ID | Métrica | Estado |
|----|---------|--------|
| `clm_ensemble_v34` | U1 TEST honest IoU ~**0.86** · ECE ~**0.15**; catalog holdout **0.8963** provenance; Tobarra LOFO fresh **KILL** (0.478) | GO lab / no `ml_product_go` |
| `clm_v28` | IoU 0.838 Δ +0.196 | GO fallback |
| `ndws_v21` | IoU 0.226 Δ +0.076 | GO research; G1 KILL |
| `front_dynamics_v1` / `incident_runtime_v1` | packs + watch | GO código |
| Decision Card + policies | GO/HOLD/ABSTAIN · field_ops fusion **OFF** | GO eng |
| Fuel / AEMET / envelope v3 | Tobarra pipeline scorecard PASS | GO eng (no táctico) |

## Gates mes

| Gate | Criterio | Estado | Evidencia |
|------|----------|--------|-----------|
| **M2** v34 no regresa | IoU ≥ 0.890 catalog | **GO** | manifest |
| **E1** CI/smokes | tests + smokes | **GO eng** | main green |
| **P1** incident 2 IF | smoke 2 IF **reales sin crash** (plan §1) | **PASS** | `smoke_incident_runtime.py --p1-two-real` Tobarra+Hellín `updated` |
| **O1** multi-ancla | ≥2 confirmed + ratio ∈[0.5,2] | **PASS** | Tobarra **0.82** + Hellín **0.56** — `anchor_scorecard.json` |
| **O2** Hausdorff oficial | P50 o abstención | **BLOCKED** | sin perímetro nacional |
| **O2** CEMS/open | perímetro multi-temporal | **GO_PROXY** | CEMS + REDIAM + RAI + Pablo multi-IF KMZ |
| **O3** temporal | ventanas | PARTIAL | Tobarra (+ Cardoso timeline ha proxy) |
| **O4** brief 5 min | field kit | **GO eng** | FIELD_KIT + briefing |
| **O5** 2º grado A | 2º IF | **OPEN** | requiere front_dynamics Hellín grado A (o equivalente) |
| **D1** CyL | datos o follow-up | **FOLLOW_UP / WAIT** | 4082/2026 silence ~**17 ago** — `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md` |
| **M5** v35 datos | multi_if mejor | **NO_DATA** | sin fuego nuevo no-Cardoso |
| **Piloto honesty** | 3 sitios card | **GO eng** | `PILOT_HONESTY_CARD.md` |
| **Demo multi-CCAA** | Tobarra·Níjar·Caminomorisco | **GO eng** | `build_demo_multi_ccaa.py` |

## GO_MES

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

| Componente | Met? |
|------------|------|
| O1 | **sí** — 2 confirmed + 2 ratios in-band |
| O4 | **sí** |
| P1 | **sí** — smoke 2 IF reales (Tobarra+Hellín) sin crash |
| M2 | **sí** |
| E1 | **sí** |

**Veredicto mes (2026-08-04):** **GO_MES** — ver `docs/GO_MES_VERDICT.md`.  
**Veredicto ingeniería:** **GO_ENG**.  
**O5 / GO_MES+:** OPEN (2º structural grade A; Hellín best **B**).  
**Track A ops:** ROS **27.9** / Vp **50** · ratio **0.56** · grade **B** (compatibilidad ancla OK; grade A eng-blocked).  
**No inflar:** P1 ≠ grade A; no k conjunto; fusion OFF; GO_Q sigue necesitando demo.

## Anclas confirmed

| IF | Vp m/min | ha | Fuente |
|----|---------:|---:|--------|
| Tobarra 2024-08-02 | 7 | 39 | INFOCAM parte |
| Hellín 2024-07-19 | **50** | 100* | Boletín UNAP 20/07/2024 (*estimada no oficial) |

## Entregables ingeniería (cerrados)

- [x] Catalog + CLI v34 (+ alias)  
- [x] PRODUCTO_DUAL, DATA_INTAKE_STATUS, FIELD_KIT  
- [x] Fuel PR-α / PR-β (AEMET, envelope, scorecard)  
- [x] O1 multi-ancla (Hellín)  
- [x] Cardoso timeline Δha proxy  
- [x] La Estrella cartografía lecturas (no confirmed)  

## Pendiente humano / eng

- [x] Track A: score Hellín front_dynamics vs Vp 50 (grade B, ratio 0.32)  
- [ ] Mejorar Hellín a grade A / ratio ∈ [0.5,2] (más frames, menos FOV basura) o P1 BLOCKED documentado  
- [ ] Perímetro oficial Hausdorff (O2)  
- [ ] 1 demo con tercero + acta (M3.2)  
- [ ] Opcional: Vp formal La Estrella / Cardoso para 3ª ancla  
- [ ] Reentreno GPU multi_if **solo** si llegan datos nuevos  

## Próximo ritual

- **Semanal:** `python scripts/run_plan_cycle.py --execute-m1` + graph `wfd-status-sync`  
- **Principal eng:** Hellín ops grade A (P1/O5)  
- **No:** calibrar k único Tobarra↔Hellín  
