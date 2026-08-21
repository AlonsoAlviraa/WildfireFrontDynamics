# Resultado de la campaña WFIGS grande en TRAIN/DEV

Fecha de cierre: 2026-08-21  
Script: `scripts/run_wfigs_large_dev_campaign.py`  
Informe de ejecución: `LARGE_DEV_CAMPAIGN_REPORT.json` (artefacto local, no publicado)

## Alcance

Se ejecutó la cosecha ampliada con un máximo de 50 eventos por región GACC
(`events_per_region=50`; el año solo agrupa la materialización),
rejilla de `256×256`, resolución de 60 m y fracción mínima de píxeles válidos
de 0,70. El script sólo permitió los assignments `train` y `validation`.
No se materializó, leyó ni evaluó ningún `test`, confirmación o conjunto
prospectivo.

## Conteos comprobados

| Split | Eventos/pairs seleccionados | Materializados | Rechazados | Motivos de rechazo | Tensores |
|---|---:|---:|---:|---|---:|
| TRAIN | 287 | 235 | 52 | 25 `insufficient_clear_valid_pixels`; 3 `t0_geometry_outside_fixed_grid`; 24 `t1_geometry_truncated` | 235 |
| VALIDATION | 87 | 76 | 11 | 5 `insufficient_clear_valid_pixels`; 6 `t1_geometry_truncated` | 76 |
| **Total** | **374** | **311** | **63** | **0 fallos de escritura** | **311** |

El informe marca `samples_failed=0`, por lo que los 311 samples elegibles se
escribieron correctamente. Los splits contienen un evento por asignación y
son disjuntos por `event_id`.

## Composición regional

TRAIN: EACC 6, GBCC 44, NRCC 41, NWCC 50, ONCC 19, OSCC 24, RMCC 46,
SACC 7, SWCC 50.  
VALIDATION: EACC 1, GBCC 15, NRCC 8, NWCC 31, ONCC 4, OSCC 1, RMCC 7,
SACC 1, SWCC 19.

## Interpretación de los rechazos

- `insufficient_clear_valid_pixels`: el recorte no alcanza la cobertura mínima
  de observación fiable; se conserva el rechazo para evitar etiquetas débiles.
- `t0_geometry_outside_fixed_grid`: la geometría inicial no cae en la rejilla
  fija del ejemplo y se descarta para mantener una representación comparable.
- `t1_geometry_truncated`: el perímetro final queda recortado por la rejilla;
  no se usa como objetivo de crecimiento porque produciría una etiqueta
  artificialmente incompleta.

Estos filtros son previos al entrenamiento y no constituyen imputación ni
relleno de geometrías.

## Controles de aislamiento y derechos

- `test_materialized=false` y no existe `test.json` en el dataset resultante.
- `test_used_for_selection=false` en el informe final.
- El uso resuelto es **entrenamiento interno no comercial**.
- No se publican datos WFIGS crudos, geometrías, teselas, tensores,
  predicciones por píxel ni checkpoints. Sólo pueden publicarse código,
  configuración, metodología, gráficos y métricas agregadas.

## Qué habilita

Este corte deja una cohorte reproducible de 235 muestras TRAIN y 76 DEV para
reentrenar/adaptar el modelo con el mismo protocolo congelado y comparar contra
el ensemble RCDA/WFIGS anterior. Aún no es un resultado de generalización:
primero debe ejecutarse el entrenamiento, repetir semillas y aplicar la puerta
de estabilidad en DEV. La confirmación y el conjunto prospectivo permanecen
cerrados hasta que exista una mejora estable y documentada.

## Verificación realizada

Se comprobó la existencia del informe final, los conteos por split, el desglose
de rechazos, `samples_failed=0`, la ausencia de `test.json` y la política de
derechos embebida en el informe. Los artefactos pesados permanecen fuera de Git
por diseño.
