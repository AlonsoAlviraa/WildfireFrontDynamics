# One-pager — qué se vende (rediseño)

> **EMBARGO outbound** hasta Claims Guardian clear.  
> **Gates (SSOT `docs/CURRENT_STATE.md`):** GO_Q **partial** · field_ops ML fusion **OFF** · `ml_product_go` **lab only** · FREEZE_ML.  
> **No** es despacho táctico.

## No vendemos

- Mapitas CEMS (ya son gratis en Copernicus)
- “IoU mágico” como si fuera extinción
- ROS inventado con Δt falso como orden táctica
- **99.9999% de acierto del fuego** (eso sería mentira)
- **“Cinco nueves” / residual silent-GO ≤ 1×10⁻⁶** como claim contractual (retirado 2026-08-12 — sin scorecard/stamp)
- GO_Q complete / field sell-ready sin demo tercero + acta firmada

## Sí vendemos

| Entregable | Valor de pago |
|------------|----------------|
| **Fire Decision Card** | GO / HOLD / **ABSTAIN** con confianza 0–1 y motivos |
| **Audit trail** | hash de inputs/outputs, versión, UTC, fuente |
| **Metrics Hub** | todas las métricas ML + ops + open + gates en un sitio |
| **Reliability gate** | diseño **anti-silencio**: el sistema puede **ABSTAIN/HOLD** si faltan fuentes (no inventamos tasa ≤1e-6) |
| **Dual field** | LWIR cuando hay dron + open CEMS cuando no |

## Fiabilidad (honest)

| Claim | Significado |
|-------|-------------|
| Anti-silent-GO | Por **diseño de gates/abstención** + tests de uso; **no** hay stamp contractual de ≤1×10⁻⁶ |
| Predicción del incendio | **NO reclamada** al 99.9999% — se muestra `confidence_pred` real (p.ej. MEDIUM) |
| GO_Q | **partial** hasta demo tercero + acta firmada |

## Demo

Preferido (H1 / tercero):

```bash
python -m wildfire_front app --demo-day
```

Alternativas de ensayo eng:

```bash
python scripts/show_all.py
# abre docs/commander/index.html  ← app sala de mando
# + docs/PORTAL.html
```

```bash
python -m wildfire_front operator   # cheatsheet 12 min (ensayo)
```

En **campo**, cada `incident update` escribe la Decision Card en el outbox:

`outbox/fire_decision_card.json` · `outbox/fire_decision_card.md`

**API mínima (integración demo):**

```bash
python -m wildfire_front serve-decide --port 8765
# POST http://127.0.0.1:8765/v1/decide  → JSON GO/HOLD/ABSTAIN + latency_ms
# POST http://127.0.0.1:8765/v1/replay  → verifica output_hash (forense)
```

**Acta + radio (auditor / mando):**

```bash
python -m wildfire_front export-acta --work-dir outputs/incidents/IF_x
python -m wildfire_front replay-decide --work-dir outputs/incidents/IF_x  # debe replay_ok
```

**Política por organismo** (mismos datos, distinto umbral):

```bash
python -m wildfire_front decide --list-policies
python -m wildfire_front decide --use-ml-v34 --policy field_ops      # sala: ML-only → ABSTAIN
python -m wildfire_front decide --use-ml-v34 --policy research_open  # lab: HOLD posible
```

## Métricas (siempre visibles)

Ver `docs/METRICS_HUB.md` — ML IoU/Δ/growth, ops ROS/grade/ratio, CEMS ha/timeline/Hausdorff, gates, decision card.  
IoU de catálogo ≠ ROS / Vp. `ml_product_go` lab ≠ field fusion.

## Precio / piloto (plantilla)

- Setup decision card + hub en 1 sala de crisis  
- 3 IF open + 1 secuencia térmica del cliente  
- Informe de abstenciones (cuándo el sistema se calla)  

Eso es lo que justifica factura: **confianza operativa y auditoría**, no otro GIS.
