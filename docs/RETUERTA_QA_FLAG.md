# Retuerta 2025 — QA flag (S1)

**Status:** `AREA_ANOMALOUS_LIKELY_MASK_OR_FOV`  
**Pack:** `outputs/observatorio/retuerta_2025/`  
**ROS primaria reportada:** ~58.7 m/min (grado B)  
**Área máx. máscara:** ~**4209 ha**

## Por qué se flagea

- Superficie de máscara térmica irreal para el uso de validación multi-ancla.
- Probable causa: FOV amplio, umbral que captura fondo caliente, fusión de componentes, o georreferencia/resolución mal interpretada — **no** un bug aislado del estimador ROS.
- **No usar** Retuerta para O1/O5 ni para comparar con parte hasta re-QA de máscaras.

## Acción S1 (sin retocar motor)

1. Revisar `artifacts/retuerta_2025_*` (reprojected + masks).
2. Si no se corrige en S1–S2: `usable=false` en inventario y excluir de scorecards multi-IF.
3. Hipótesis H-RET del loop 1M: fallo de pipeline de máscara, no de `front_dynamics_v1`.

## Criterio de re-entrada

- `area_ha_max` en rango plausible del IF (orden de decenas–cientos ha, no miles sin justificación).
- Grado y ROS re-calculados tras fix de máscara; ratio vs ancla solo si hay Vp/ha.
