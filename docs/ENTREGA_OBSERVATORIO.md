# Entrega Observatorio — v3 estructural

> **Abrir:** `outputs/observatorio/index.html`  
> **Motor:** `front_dynamics_v1` (coregistro + ROS multi-estimador)  
> **Fecha:** 2026-07-15

---

## El salto (una frase)

Pasamos de **máscaras ruidosas con Vp inventada** a un **motor de dinámica de frente** que fusiona tres estimadores físicos y, en Tobarra, recupera **ROS ≈ 8.2 m/min frente a INFOCAM 7** (ratio **1.18**).

---

## Trayectoria medible (Tobarra)

| Generación | Producto | Vp / ROS (m/min) | vs INFOCAM 7 | Grado | Nivel |
|------------|----------|------------------|--------------|-------|--------|
| v1 | Pack crudo | **0.78** | ratio 0.11 | — | basura útil solo como demo de archivos |
| v2 | Máscara limpia + filtro físico | **4.31** | ratio 0.62 | A | útil con cautela |
| **v3** | **Motor multi-estimador** | **8.23** | ratio **1.18** | **A** | **mismo orden + multi-método** |

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

## Resultados v3 (3 incendios)

| Incendio | Grado | ROS primaria | Métodos | vs INFOCAM | Para ellos |
|----------|-------|--------------|---------|------------|------------|
| **Tobarra** | **A** | **8.23 m/min** | area + radius + normal | **ratio 1.18** | Usable como orientación con ancla |
| Cardoso | B | ~30 m/min | area | n/d | Orientativo; sin ancla local |
| Hellín | B | ~35 m/min | radius | n/d | Orientativo; muestra corta |

**Mensaje honesto:** Tobarra es el caso ancla. Cardoso/Hellín demuestran el motor (área/radio) pero **sin parte INFOCAM no se validan** — grado B.

---

## Cómo abrir / reproducir

```bash
python scripts/build_observatory_pack.py \
  --fires tobarra_20240802,cardoso_2025,hellin_2024 \
  --max-frames 10 \
  --output-root outputs/observatorio_v3

python scripts/finalize_observatorio_v3.py
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
