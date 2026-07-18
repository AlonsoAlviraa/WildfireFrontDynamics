# Entrega Observatorio — v4 (loop execution)

> **Abrir:** `outputs/observatorio/index.html`  
> **Motor:** `front_dynamics_v1` + export operador  
> **Fecha:** 2026-07-15 · sesión loop ~2h  

---

## El salto (una frase)

Tobarra queda en **ROS 7.21 m/min vs INFOCAM 7 (ratio 1.03)**, con producto operador (capa + timeline + brief) y estabilidad temporal **2/3 ventanas** en banda [0.5, 2].

---

## Trayectoria medible (Tobarra)

| Generación | Producto | Vp / ROS (m/min) | vs INFOCAM 7 | Grado | Nivel |
|------------|----------|------------------|--------------|-------|--------|
| v1 | Pack crudo | **0.78** | ratio 0.11 | — | basura útil solo como demo de archivos |
| v2 | Máscara limpia + filtro físico | **4.31** | ratio 0.62 | A | útil con cautela |
| v3 | Motor multi-estimador | **8.23** | ratio **1.18** | A | multi-método |
| v4 | + ventanas + GIS operador | **7.21** | ratio **1.03** | A | casi calca el parte |
| **v5** | **O3 cerrado + multi-IF (5)** | **5.71** | ratio **0.82** | **A** | **early/mid/late estables** |

Eso es el salto estructural: no un hiperparámetro más, sino **otro producto científico**.

---

## Qué hay dentro del motor v3

```
máscara limpia (frente principal)
        ↓
coregistro residual (solo si IoU mejora de verdad)
        ↓
┌───────────────┬──────────────────┬─────────────────┐
│ normal_ray    │ area_isotropic   │ equiv_radius    │
│ (locales)     │ dA/(P·dt)        │ d√(A/π)/dt      │
└───────┬───────┴────────┬─────────┴────────┬────────┘
        └────────────────┴──────────────────┘
                         ↓
              ROS primaria fusionada + grado A/B/C
                         ↓
         informe operativo ES + front_dynamics.json
```

| Estimador | Qué mide | Por qué importa |
|-----------|----------|-----------------|
| **normal_ray** | avance local del contorno | dirección de propagación |
| **area_isotropic** | expansión de área / perímetro | estándar en física de incendios; robusto a matching |
| **equiv_radius** | crecimiento del radio equivalente | lectura simple de “cuánto crece el fuego” |

Coregistro **no** se aplica a ciegas: solo si el IoU mejora ≥0.05 y ≥0.15 absoluto (evita traslaciones espurias de 60 m).

---

## Resultados v4 (3 incendios)

| Incendio | Grado | ROS primaria | Métodos | vs INFOCAM | Producto operador |
|----------|-------|--------------|---------|------------|-------------------|
| **Tobarra** | **A** | **7.21 m/min** | area + normal | **ratio 1.03** | brief + main_front + timeline |
| Cardoso | B | ~28 m/min | area | n/d | ídem |
| Hellín | B | ~30 m/min | area | n/d | ídem |

### Estabilidad temporal Tobarra (O3)

| Ventana | ROS | Ratio vs 7 | Banda [0.5, 2]? |
|---------|-----|------------|-----------------|
| early | 14.0 | 2.01 | FAIL (fase de crecimiento / máscara) |
| mid | 3.52 | 0.50 | PASS |
| late | 8.71 | 1.24 | PASS |

**Veredicto O3:** GO_PARTIAL (2/3).

**Mensaje honesto:** Tobarra es el caso ancla. Cardoso/Hellín demuestran el motor (área/radio) pero **sin parte INFOCAM no se validan** — grado B.

---

## Cómo abrir / reproducir

```bash
python scripts/build_observatory_pack.py \
  --fires tobarra_20240802,cardoso_2025,hellin_2024 \
  --max-frames 10 \
  --output-root outputs/observatorio_v4

python scripts/finalize_observatorio_v4.py
```

Por incendio, leer en este orden:

1. `operational_report.html` — lenguaje observatorio  
2. `front_dynamics.json` — pares, estimadores, calibración  
3. `fronts.geojson` — geometría  

---

## Límites (siguen siendo ciencia, no magia)

1. Máscara térmica ≠ perímetro oficial.  
2. ROS fusionada ≠ Vp de parte (aunque en Tobarra coincida en orden).  
3. Sin ancla operativa, grado máximo típico = B.  
4. No es predicción ML ni tiempo real.

---

## Qué pedimos al observatorio para el siguiente salto

1. Anclas Vp/ha para Cardoso y Hellín (como Tobarra 7 m/min / 39 ha).  
2. 1–2 perímetros vectoriales por IF para Hausdorff.  
3. Feedback de si el informe operativo es el formato que usan.

Con eso el grado A de Tobarra puede volverse **protocolo de validación multi-IF**, no un caso afortunado.

---

## Prioridad stack (2026-07-15) — tooling cerrado

| # | Acción | Estado | Evidencia |
|---|--------|--------|-----------|
| 1 | Producto dual NDWS v21 + CLM v28 | **DONE** | `docs/PRODUCTO_DUAL.md`, `models/catalog.json`, `predict_spread.py --list-products` |
| 2 | Anclas INFOCAM multi-A O1/O5 | **TOOLING DONE / DATA BLOCKED** | `data/infocam_anchors.json` + `anchor_scorecard.json` → O1 **PARTIAL**, O5 **NO_GO** |
| 3 | Perímetro oficial Hausdorff O2 | **PROXY DONE / OFFICIAL BLOCKED** | `eval_perimeter_hausdorff.py` temporal 5 IF; official sin GeoJSON → **BLOCKED** |
| 4 | ML physics15 pelea G1 | **QUEUED** | `run_unet_training_v26_physics15.py` + kernel metadata v26 |

Scorecard unificado: `outputs/observatorio/priority_stack_scorecard.json`  
Solicitud de datos: `docs/SOLICITUD_DATOS_OBSERVATORIO.md`
