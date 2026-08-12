# O2 Hausdorff oficial — nacional BLOCKED; Tobarra ops PARTIAL

**Fecha:** 2026-07-17 (actualizado **2026-07-30** con drop Pablo/GEACAM)  
**Gate:** O2 (perímetro oficial vs frente reconstruido)

## Estado

| Nivel | Estado | Evidencia |
|-------|--------|-----------|
| **O2 nacional/catastral oficial** | **BLOCKED** | Sin SHP/GPKG nacional EGIF/catastro para Tobarra/Cardoso |
| **O2 Tobarra ops multi-hora (Pablo/GEACAM)** | **PARTIAL_GO** | 2 KMZ perímetro activo 2024-08-02 18:30 (21.49 ha) y 21:43 (37.08 ha) en `data/real_if/pablo_geacam_20260730_tobarra/` |
| **O2 open CEMS delineation (Pista B)** | **GO_PROXY** | Packs `outputs/open_if/emsr578` y `emsr583` (perímetros `observedEventA`, multi-MONIT) |

CEMS **no** sustituye perímetro nacional; sí permite demo reproducible de Hausdorff / área / timeline **sin LWIR**.

Pablo KMZ **no** son catastro nacional: son **perímetro activo operativo** INFOCAM/GEACAM. Sirven para O2 **proxy Tobarra** (área multi-hora + Hausdorff ops↔ops / ops↔main_front con desajuste temporal). Cardoso **sin** perímetro nuevo.

## Prohibido

- Usar KMZ/KML de **vuelo / footprint** de dron como “perímetro oficial”
- Tratar perímetro operativo Pablo como catastro nacional sin caveat
- Reportar P50 Hausdorff inventado o contra máscaras MAD sin auditoría
- Convertir crecimiento de área (ha/h) en **Vp m/min**

## Pipeline

```bash
# Ops Tobarra (Pablo 2026-07-30) — eval + GeoJSON
python scripts/eval_tobarra_pablo_perimeters.py

# Parser reutilizable
# wildfire_front.ops_perimeter.parse_ops_perimeter / write_geojson

# Cuando exista un perímetro oficial nacional:
python scripts/eval_perimeter_hausdorff.py --help
```

Salida Tobarra ops: `outputs/tobarra_pablo_perimeters/eval_report.json`  
GeoJSON (default): `outputs/tobarra_pablo_perimeters/*.geojson` (intake drop se mantiene source-only)

Criterio GO nacional futuro: P50 < 50 m **o** abstención justificada por calidad del perímetro.

## Acción

1. ~~Solicitar muestra perímetro multi-hora Tobarra~~ — **recibido 2026-07-30** (ops).  
2. Seguir pidiendo perímetros multi-IF (Cardoso / Hellín / Estrella) + vectorial SHP/GPKG si posible.  
3. Mantener O2 **nacional = BLOCKED** en scorecard hasta EGIF/catastro.  
4. No promover anclas a `confirmed` sin Vp/ha de parte (Cardoso sigue `pending_external`).

**Scorecard:** O2 nacional **BLOCKED**; O2 Tobarra ops **PARTIAL** (no es fallo de código).
