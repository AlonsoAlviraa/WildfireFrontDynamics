# One-pager — qué se vende (rediseño)

## No vendemos

- Mapitas CEMS (ya son gratis en Copernicus)
- “IoU mágico” como si fuera extinción
- ROS inventado con Δt falso como orden táctica
- **99.9999% de acierto del fuego** (eso sería mentira)

## Sí vendemos

| Entregable | Valor de pago |
|------------|----------------|
| **Fire Decision Card** | GO / HOLD / **ABSTAIN** con confianza 0–1 y motivos |
| **Audit trail** | hash de inputs/outputs, versión, UTC, fuente |
| **Metrics Hub** | todas las métricas ML + ops + open + gates en un sitio |
| **Reliability gate** | el sistema **no emite GO** si faltan fuentes (diseño anti-silencio) |
| **Dual field** | LWIR cuando hay dron + open CEMS cuando no |

## Fiabilidad “cinco nueves” (definición contractual)

| Claim | Significado |
|-------|-------------|
| Residual silent-GO risk | **≤ 1×10⁻⁶** bajo suite de tests de abstención/gates |
| Predicción del incendio | **NO reclamada** al 99.9999% — se muestra `confidence_pred` real (p.ej. MEDIUM) |

## Demo

```bash
python scripts/reliability_gate.py
python scripts/build_metrics_hub.py
# abrir docs/METRICS_DASHBOARD.html
```

## Métricas (siempre visibles)

Ver `docs/METRICS_HUB.md` — ML IoU/Δ/growth, ops ROS/grade/ratio, CEMS ha/timeline/Hausdorff, gates, decision card.

## Precio / piloto (plantilla)

- Setup decision card + hub en 1 sala de crisis  
- 3 IF open + 1 secuencia térmica del cliente  
- Informe de abstenciones (cuándo el sistema se calla)  

Eso es lo que justifica factura: **confianza operativa y auditoría**, no otro GIS.
