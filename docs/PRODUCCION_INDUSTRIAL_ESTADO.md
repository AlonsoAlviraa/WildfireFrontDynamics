# Estado de producción industrial (2026-07-16)

Definición: `docs/INDUSTRIAL_PRODUCTION_GATES.md`  
Snapshot JSON: `docs/INDUSTRIAL_READINESS_STATUS.json`

## Qué SÍ se puede afirmar (shippable)

### 1. Ops — dinámica de frente observada (`front_dynamics_v1`)
| Métrica | Valor |
|---------|-------|
| Tobarra grado | **A** |
| ROS vs INFOCAM 7 m/min | **5.71 → ratio 0.82** |
| O3 ventanas | **GO 2/3** strict; late 0.48 near-miss; wide **3/3** |
| Packs IF | **7** (falta Polán sin máscaras) |
| Retuerta FOV bug | **FIXED** (4209 ha → ~280 ha) |
| Producto operador | DOCX CMA + GeoJSON + brief |

**Uso industrial legítimo:** apoyo post-proceso a CMA/observatorio con abstención y grado A/B/C.  
**No es:** despacho táctico en tiempo real.

### 2. ML — specialist CLM (`clm_v28`)
| Métrica | Valor |
|---------|-------|
| Holdout test G2 | IoU **0.838**, Δ **+0.196** |
| Smoke 15 patches | Δ **+0.086** PASS |
| Per-source (v28) | Cardoso/Estrella **+**; Tobarra ~0 |
| LOFO Tobarra (v29) | IoU **0.494**, Δ **+0.165** on held-out |

**Uso industrial legítimo:** predicción next-day en parches schema legacy17 de incendios CLM, con informe de fuentes.  
**No es:** ROS de dron ni NDWS global.

### 3. ML — baseline NDWS (`ndws_v21`)
| Métrica | Valor |
|---------|-------|
| G0 production | IoU **0.226**, Δ **+0.076** |
| G1 features v25/v26 | **NO_PROMOTE** |
| G1 temporal v27 | **RUNNING** |

**Uso industrial legítimo:** baseline de investigación NDWS.  
**No promover** sustituto hasta G1 o kill documentado.

## Qué NO se puede afirmar aún

| Claim | Por qué |
|-------|---------|
| Multi-ancla operativo O1/O5 | Solo Tobarra confirmed |
| Error geométrico oficial O2 | Sin perímetro vectorial |
| Predicción 15/30/60 min táctica | No validada |
| NDWS superó techo G1 | Pending/failed features |

## Productos freeze (hoy)

```
ndws_v21     → FREEZE G0 (research baseline)
clm_v28      → FREEZE G2 specialist (transfer GO + LOFO evidence)
front_dynamics_v1 → FREEZE ops engine (Tobarra A + multi-IF + FOV guard)
```

CLI smoke: `python scripts/smoke_production_products.py`

### LOFO all folds (lanzado y cerrado)
| Held-out | IoU | Δ copy |
|----------|-----|--------|
| CARDOSO | 0.798 | **+0.156** |
| LA_ESTRELLA_ACOM1 | 0.783 | **+0.424** |
| LA_ESTRELLA_ACOM2 | 0.693 | **+0.323** |
| tobarra | 0.494 | **+0.165** |
**all_positive: true** · mean Δ **+0.267**

## Siguiente para subir de nivel industrial

1. Anclas Vp/ha CMA → O1/O5  
2. 1 perímetro oficial → O2  
3. Cerrar G1 (v27) o KILL explícito  
4. LOFO folds restantes Cardoso/Estrella → tabla completa
