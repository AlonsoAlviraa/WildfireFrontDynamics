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

## Demo (modo operario primero)

```bash
# Única puerta de entrada (semáforo + 4 actos + qué falta para GO_Q)
python -m wildfire_front
python -m wildfire_front ensayo          # = operator do --all
python -m wildfire_front operator checklist
```

```bash
# App sala de mando / portal (opcional, eng)
python scripts/build_commander_app.py
# start docs/commander/index.html
# rebuild pesado: python scripts/show_all.py
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

## Precio / piloto (plantilla)

- Setup decision card + hub en 1 sala de crisis  
- 3 IF open + 1 secuencia térmica del cliente  
- Informe de abstenciones (cuándo el sistema se calla)  

Eso es lo que justifica factura: **confianza operativa y auditoría**, no otro GIS.
