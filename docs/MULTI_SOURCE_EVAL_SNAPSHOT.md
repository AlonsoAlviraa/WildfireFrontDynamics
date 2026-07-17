# Evaluación multi-fuente (honesta) — snapshot mes

**Fecha:** 2026-07-17  
**Regla:** no reportar métricas LOFO-CARDOSO/test como holdout GO adicional (es el mismo test).

## ML ensemble v34 (holdout test Cardoso n=200)

| Métrica | Valor |
|---------|------:|
| model_iou | 0.8963 |
| improvement_vs_copy_iou | 0.2545 |
| model_iou_growth | 0.9071 |
| mix | 0.28 / 0.32 / 0.40 |
| temperatures | 0.7 / 0.7 / 1.3 |

## LOFO diagnostic (mix only, thr=0.5, no GO)

Desde loop 3-way / transfer mix (miembros freeze v28+EMA+multi_if):

| Fuente held-out | Mejor Δ (diag) | Nota |
|-----------------|----------------:|------|
| CARDOSO | ~0.256 | ≡ holdout test — **no usar para GO** |
| LA_ESTRELLA_ACOM1 | ~0.43 | Diagnostic transfer |
| LA_ESTRELLA_ACOM2 | ~0.33 | Diagnostic transfer |
| tobarra_20240802 | ~-0.03 | Difícil; train multi_if lo incluye |

## Ops ROS (Tobarra ancla)

| Fuente | ROS ops | Vp ref | ratio | Grado |
|--------|---------|--------|-------|-------|
| Tobarra 2024-08-02 | ~5.7 m/min (histórico pack) | 7.0 | ~0.82 | A (ancla confirmed) |
| Cardoso / otros | — | pending_external | — | sin ancla → no O1 |

## Conclusión

- **ML:** champion v34 estable; techo sin datos no-Cardoso nuevos.  
- **Ops:** multi-ancla O1 OPEN hasta Cardoso (u otro) con Vp/ha oficial.  
- **No mezclar** filas de esta tabla en un único “score táctico”.
