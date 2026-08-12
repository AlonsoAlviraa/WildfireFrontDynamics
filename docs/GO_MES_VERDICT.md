# GO_MES — veredicto (mínimo plan 1 mes)

**Fecha:** 2026-08-04  
**Veredicto:** **GO_MES = true**  
**Fórmula (PLAN_1_MES_MEJORA_GLOBAL §1):**

```
GO_MES = O1 ∧ O4 ∧ P1 ∧ M2 ∧ E1
```

Machine: `docs/GO_MES_VERDICT.json`

---

## Componentes

| Gate | Definición plan | Met? | Evidencia |
|------|-----------------|------|-----------|
| **O1** | ≥2 IF ancla confirmed + ratio ROS/Vp ∈ [0.5, 2] | **sí** | Tobarra 5.71/7 ≈ **0.82** grade A; Hellín 27.9/50 ≈ **0.56** grade B — `anchor_scorecard.json` |
| **O4** | Brief ops ≤5 min | **sí** | Field kit + incident briefing |
| **P1** | `incident_runtime` smoke en **2 IF reales sin crash** | **sí** | `python scripts/smoke_incident_runtime.py --p1-two-real --skip-synthetic` → both `updated` |
| **M2** | v34 holdout IoU ≥ 0.890 | **sí** | catalog ~0.8963 provenance |
| **E1** | CI + smokes | **sí** | pytest + smoke runtime |

---

## Qué **no** se reclama

| Item | Estado | Nota |
|------|--------|------|
| **GO_MES+** | false | O2 nacional, O5 2º grade A, M5, D1 |
| **O5** 2º grado A | OPEN | Solo Tobarra es structural **A**; Hellín best **B** |
| Hellín grade A | eng BLOCKED | Ver `P1_HELLIN_ENG_STATUS.md` (reglas A vs Vp=50) |
| `ml_product_go` | false | lab only |
| field_ops fusion | OFF | policy freeze |
| GO_Q | partial | **Bloqueo principal: M3.2** demo tercero + acta firmada. **M3.4** informe eng-filled: `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` (sello/firma humana opcional si se archiva formal) |

**Importante:** en el plan, **P1 ≠ grade A**. Grade A del 2º IF es **GO_MES+ / O5**. Habíamos sobre-restringido P1; el smoke en 2 IF reales cierra el mínimo.

---

## Comandos de reproducción

```powershell
# O1 ratios
python scripts/score_infocam_anchors.py

# P1 — 2 IF reales
python scripts/smoke_incident_runtime.py --p1-two-real --skip-synthetic

# Hellín vs Vp 50 (ops pack)
python scripts/score_hellin_track_a.py
```

---

## Anclas

| IF | Vp | ROS pack | Ratio | Grade pack |
|----|---:|---------:|------:|------------|
| Tobarra | 7 | ~5.71 | 0.82 | A |
| Hellín | 50 | ~27.9 | 0.56 | B |

---

## Siguiente (post GO_MES)

1. **Humano (bloquea GO_Q completo):** demo tercero + acta (`GUION_DEMO_30MIN_POST_O1.md` · `ACTA_DEMO_TERCERO_TEMPLATE.md`) → **M3.2**  
2. **M3.4:** informe eng-filled ya en `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md`; sello humano opcional  
3. **Eng opcional:** O5 / grade A Hellín o 2º IF A  
4. **O2** perímetro nacional cuando exista  
