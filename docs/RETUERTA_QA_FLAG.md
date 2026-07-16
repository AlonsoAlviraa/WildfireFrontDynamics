# Retuerta 2025 — QA flag (S1)

**Status:** `FIXED_FOV_FILTER` (2026-07-16) — was `AREA_ANOMALOUS`  
**Pack:** `outputs/observatorio/retuerta_2025/`  
**Antes:** area_ha_max ~**4209 ha** (frame 16k×27k)  
**Después:** area_ha_max ~**280 ha**, n_obs=5, grado **B**, ROS ~59 m/min (sin ancla)

## Causa raíz (confirmada)

- Fallback de `_select_coherent_pairs` ignoraba `max_side` y metía el FOV completo Heligrafics.
- Clustering espacial dejaba solo 1–2 frames útiles.

## Fix industrial (código)

- Hard cap en fallback FOV + no usar el 30% de frames más grandes.
- Si el mejor cluster espacial es pobre, usar todos los frames bajo `max_side` ordenados por tiempo.

## Acción S1 (sin retocar motor)

1. Revisar `artifacts/retuerta_2025_*` (reprojected + masks).
2. Si no se corrige en S1–S2: `usable=false` en inventario y excluir de scorecards multi-IF.
3. Hipótesis H-RET del loop 1M: fallo de pipeline de máscara, no de `front_dynamics_v1`.

## Criterio de re-entrada

- `area_ha_max` en rango plausible del IF (orden de decenas–cientos ha, no miles sin justificación).
- Grado y ROS re-calculados tras fix de máscara; ratio vs ancla solo si hay Vp/ha.
