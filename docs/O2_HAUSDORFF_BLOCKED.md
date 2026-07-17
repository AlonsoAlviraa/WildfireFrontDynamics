# O2 Hausdorff oficial — BLOCKED (honesto)

**Fecha:** 2026-07-17  
**Gate:** O2 (perímetro oficial vs frente reconstruido)

## Estado

| Nivel | Estado | Evidencia |
|-------|--------|-----------|
| **O2 nacional/catastral oficial** | **BLOCKED** | Sin SHP/GPKG nacional para Tobarra/Cardoso |
| **O2 open CEMS delineation (Pista B)** | **GO_PROXY** | Packs `outputs/open_if/emsr578` y `emsr583` (perímetros `observedEventA`, multi-MONIT) |

CEMS **no** sustituye perímetro nacional; sí permite demo reproducible de Hausdorff / área / timeline **sin LWIR**.

## Prohibido

- Usar KMZ/KML de vuelo o drops de dron como “perímetro oficial”
- Reportar P50 Hausdorff inventado o contra máscaras MAD sin auditoría

## Pipeline preparado (cuando lleguen datos)

```bash
# Cuando exista un perímetro oficial:
python scripts/eval_perimeter_hausdorff.py --help
```

Criterio GO futuro: P50 < 50 m **o** abstención justificada por calidad del perímetro.

## Acción

1. Solicitar a Observatorio/INFOCAM perímetro oficial Tobarra y/o Cardoso.  
2. Registrar ruta + hash en `data/infocam_anchors.json` o provenance pack.  
3. Correr eval y volcar a scorecard mes.  

Hasta entonces: **O2 = BLOCKED** en scorecard (no es fallo de código).
