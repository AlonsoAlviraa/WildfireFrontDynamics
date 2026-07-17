# Rediseño de producto — por qué pagarían (y por qué no)

> Loop-engineering · 2026-07-17  
> Premisa del usuario: *“nadie va a pagar por esto”* → correcto si vendemos mapitas CEMS o IoU suelto.

---

## 1. Diagnóstico brutal (por qué no se vende el pack actual)

| Oferta actual | Por qué no pagan |
|---------------|------------------|
| HTML Leaflet + GeoJSON CEMS | EFFIS/CEMS ya es gratis en el portal Copernicus |
| Score dual 95 vs 39 | Score **interno** inventado; no es valor de campo |
| “VENTA_GO” | No es carta de interés ni ROI |
| ML IoU 0.896 | Interesante para TFG; **no** es SLA de extinción |
| ROS proxy Δt=24h | Un mando no firma sobre eso |

**Conclusión:** el valor no es “otro visor de perímetros”.  
El valor de pago en emergencias es: **decisión auditada, incertidumbre explícita, y saber cuándo NO actuar con el modelo**.

---

## 2. Qué SÍ se paga en el sector (anclado a evidencia)

| Producto pagable | Comprador | Lo que firma |
|------------------|-----------|--------------|
| **Decision support con abstención** | CMA / GEACAM / mandos | “solo emito recomendación si grade ≥ umbral” |
| **Audit trail + provenance** | Jurídico / calidad | hash de inputs, versión, timestamp, fuente |
| **Fusión multi-fuente con confianza** | Sala de crisis | CEMS + FIRMS + (si hay) LWIR + ancla, con pesos y flags |
| **SLA de pipeline** | IT / observatorio | rebuild determinista, tests, tiempos |
| **ML transfer documentado** | I+D / TFG / consultoría | protocolo holdout, no leakage |

---

## 3. “99.9999%” — definición honesta (obligatoria)

**Prohibido:** “predecimos el fuego con 99.9999% de acierto”.

**Permitido (reliability de sistema):**

| Claim | Definición medible | Target |
|-------|-------------------|--------|
| **R1 Determinismo** | Mismos inputs (hash) → mismos artefactos (hash) | 100% en tests |
| **R2 Gates** | Nunca emite GO si falta fuente / grade bajo | 0 bypass |
| **R3 Abstención** | Si confianza &lt; umbral → **ABSTAIN**, no inventa | 100% en suite |
| **R4 Provenance** | Toda métrica lleva fuente + versión + UTC | 100% |
| **R5 Test suite** | pytest módulos producto/confianza | PASS |

**“Cinco nueves” (99.9999%)** se interpreta aquí como:

> Probabilidad de que el **pipeline emita un GO sin cumplir R1–R4** en condiciones de test automatizado → **&lt; 10⁻⁶** (diseño por abstención + asserts; no es probabilidad bayesiana del fuego).

La **confianza en la predicción física del incendio** se reporta aparte (p.ej. 0–1 calibrada / grade A–D), típicamente **mucho menor**, y se enseña en el dashboard.

---

## 4. Producto rediseñado: **Fire Decision Card (FDC)**

Unidad de venta: no “un mapa”, sino una **tarjeta de decisión**:

```
event_id | sources[] | decision: GO | HOLD | ABSTAIN
confidence_pred ∈ [0,1]   # incertidumbre del fenómeno
confidence_system ∈ {PASS/FAIL}  # R1–R4
metrics{...}  # todas las métricas disponibles
audit{input_hash, output_hash, git, utc}
disclaimers[]
```

### Funcionalidades nuevas (mínimo viable pagable)

1. **Metrics Hub** — un JSON/MD/HTML con *todas* las métricas (ML, ops, open, gates).  
2. **Confidence engine** — score 0–1 + decisión ABSTAIN/HOLD/GO.  
3. **Audit trail** — hashes SHA-256 de inputs/outputs.  
4. **Reliability gate** — script que falla si se intenta “vender” sin gates.  
5. **Fusión multi-fuente** — tabla de fuentes con peso y estado.  
6. **Dashboard** — una página que enseña métricas, no eslóganes.

---

## 5. Métricas que se muestran siempre (contrato de transparencia)

### ML
- test_iou, improvement_vs_copy, growth_iou, n_patches, protocol, temps, mix

### Ops (si hay incidente)
- primary_ros_m_min, grade, area_ha, ratio vs ancla, n_frames

### Open CEMS
- max_area_ha, timeline_steps, growth_ha/h, hausdorff_m, assumed_dt_h

### Sistema
- pytest pass/fail, determinism hash match, abstention rate in suite, gate matrix

---

## 6. PR plan de implementación

| PR | Entrega |
|----|---------|
| PR1 | Design (este doc) |
| PR2 | `wildfire_front/product/confidence.py` + tests |
| PR3 | `scripts/build_metrics_hub.py` + dashboard |
| PR4 | `scripts/reliability_gate.py` + audit hashes |
| PR5 | Decision card JSON + update one-pager (honest paid value) |

---

## 7. Criterio de éxito de este loop

- [x] Dashboard con métricas de **todo** lo existente (`docs/METRICS_DASHBOARD.html`)  
- [x] Decision card con ABSTAIN por defecto si faltan fuentes  
- [x] Reliability gate documentado (sin claim falso de predicción)  
- [x] Tests verdes (`tests/test_confidence_product.py`)  
- [x] One-pager reescrito: se vende **confianza + auditoría**, no “mapitas”  

**Comandos:** `python scripts/reliability_gate.py` · `python scripts/build_metrics_hub.py`  
