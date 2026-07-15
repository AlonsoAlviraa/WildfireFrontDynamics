# Entrega Observatorio — v2 científica

> **Fecha:** 2026-07-15  
> **Carpeta canónica:** `outputs/observatorio/`  
> **Abrir primero:** `outputs/observatorio/index.html`

---

## Mensaje para el observatorio (1 párrafo)

Entregamos un **paquete de dinámica observada** de frentes térmicos (LWIR georreferenciado), no un modelo de predicción. Por incendio hay un **informe operativo en español** (`operational_report.html`) con: área proxy (ha), velocidad de avance con IQR, azimut dominante cuando es defendible, grado de calidad A/B/C, y comparación con anclas INFOCAM cuando existen. **Tobarra** queda en grado **A**: Vp mediana **~4.3 m/min** frente a ancla INFOCAM **7 m/min** (mismo orden de magnitud, ratio ~0.62). Cardoso y Hellín quedan en grado **B** (máscara limpia pero **velocidad abstención** — mejor callar que inventar).

---

## Antes vs ahora (por qué v1 no servía)

| Métrica Tobarra | v1 (flojo) | **v2 científico** |
|-----------------|------------|-------------------|
| Componentes (ruido) | hasta **1264** | mediana **1.5** (frente principal) |
| Puntos velocidad útiles | 33 / 6377 (ratio 0.5%) | **32 defendibles** (filtrados) |
| Vp mediana | **0.78** m/min | **4.31** m/min |
| vs INFOCAM 7 m/min | ratio 0.11 (inútil) | ratio **0.62** (orden de magnitud) |
| Grado calidad | no existía | **A — útil con cautela** |
| Documento para ellos | report técnico genérico | **operational_report.html** ES |

Mejoras científicas aplicadas:

1. Cierre/apertura morfológica + top-N componentes (frente principal).  
2. Frames consecutivos espacialmente coherentes (no mezclar pasadas lejanas).  
3. Velocidades con filtro de **plausibilidad física** (descarta >60 m/min y Δt <15 s).  
4. Métricas operativas: área ha, IQR Vp, azimut, grado A/B/C.  
5. Comparación explícita con INFOCAM sin fingir perímetro oficial.

---

## Cómo reproducir

```bash
python scripts/build_observatory_pack.py \
  --fires tobarra_20240802,cardoso_2025,hellin_2024 \
  --output-root outputs/observatorio_v2

python scripts/finalize_observatorio_v2.py
```

---

## Resultados por incendio (v2)

| Incendio | Grado | Vp med (m/min) | Área máx ha | N vel | vs INFOCAM |
|----------|-------|----------------|-------------|-------|------------|
| **tobarra_20240802** | **A** | **4.31** | 51.9 | 32 | ratio **0.62** |
| cardoso_2025 | B | — (abstención) | 60.7 | 0 | n/d |
| hellin_2024 | B | — (abstención) | 59.0 | 0 | n/d |

**Interpretación Cardoso/Hellín:** la limpieza de máscara funciona (1 componente), pero el matching temporal no produce desplazamientos físicamente creíbles → el sistema **se abstiene** (correcto científicamente).

---

## Límites (no negociables en comunicación)

1. Máscara térmica ≠ perímetro oficial / parte INFOCAM.  
2. Área ha es **proxy de máscara**, puede no ser monótona.  
3. Vp es estimación geométrica con abstención; no es Vp de parte.  
4. **No** es predicción 24 h ni ML operacional.  
5. Grado C o B con abstención de velocidad → **no usar para decidir medios**.

---

## Qué les pedimos a ellos para la siguiente iteración

1. Perímetros vectoriales oficiales o croquis por hora (validación geométrica real).  
2. Confirmación de Vp/área de más IF (como Tobarra 7 m/min, 39 ha).  
3. Preferencia de sensor/canal (LWIR vs EO) y umbral de campo si lo tienen.

Con eso el grado A se puede convertir en **validado**, no solo “útil con cautela”.

---

## Pista ML (anexo, no es el entregable)

v21 sigue como baseline I+D (IoU 0.226). clean12 no se promocionó.  
**No abrir la reunión del observatorio con IoU.**
