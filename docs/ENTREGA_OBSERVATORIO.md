# Entrega Observatorio — borrador vivo

> **Fecha:** 2026-07-15  
> **Estado:** en construcción (semana 1 del plan de 2 semanas)  
> **Plan maestro:** `docs/PLAN_2_SEMANAS_OBSERVATORIO.md`

---

## Mensaje ejecutivo (para el observatorio)

Hemos separado **dos productos** para no mezclar promesas:

| Producto | Qué es | Estado actual |
|----------|--------|---------------|
| **A. Dinámica observada (este entregable)** | Con secuencias LWIR georreferenciadas: frentes, velocidades locales, abstenciones, reporte HTML | **En ejecución** — packs en `outputs/observatorio/` |
| **B. Predicción ML next-day (I+D)** | Modelo U-Net sobre dataset NDWS (satélite EE.UU.) | v21 IoU 0.226; **no** es predicción operacional CLM |

**No pedimos que se use el modelo ML como herramienta de emergencia.**  
El valor inmediato para el observatorio es el **paquete A**: trazabilidad, geometría y velocidades con incertidumbre.

---

## Cómo reproducir el paquete A

```bash
python scripts/build_observatory_pack.py \
  --fires tobarra_20240802,hellin_2024,retuerta_2025 \
  --max-frames 8 \
  --min-component-pixels 500
```

Salida:

```
outputs/observatorio/
  observatory_scorecard.json
  tobarra_20240802/
    report.html
    fronts.geojson
    local_speeds.csv
    summary.json
    ingest_manifest.csv
    ...
  hellin_2024/
  retuerta_2025/
```

---

## Ancla operativa Tobarra (INFOCAM)

| Fuente | Valor |
|--------|-------|
| Detección | 2024-08-02 16:42 |
| Superficie | 39 ha |
| Vp media | **7 m/min** |
| Intensidad | Media-Alta |
| Motor | Contraviento |

**Cómo leer la comparación:** la velocidad del pipeline se calcula sobre **máscaras automáticas LWIR** (candidato de frente), no sobre el perímetro oficial. Si la mediana del modelo está lejos de 7 m/min, **no invalidamos INFOCAM**: invalidamos o calibramos la segmentación/matching.

---

## Limitaciones (obligatorio comunicar)

1. Máscara MAD/threshold ≠ frente de llama validado en campo.  
2. Sin perímetro vectorial oficial independiente no hay Hausdorff “de verdad”.  
3. Submuestreo temporal (`max-frames`) para coste computacional: el pack es un **resumen defendible**, no el video completo a 0.5 m.  
4. Predicción 24 h satélite (NDWS) **no sustituye** observación táctica de dron.  
5. El sistema **se abstiene** cuando no hay intersección normal defendible.

---

## Criterios de aceptación (DoD)

Ver tabla A1–A8 en `PLAN_2_SEMANAS_OBSERVATORIO.md`.  
Actualizar esta sección cuando el scorecard marque gates en verde.

### Estado gates (2026-07-15)

| Gate | Estado | Evidencia |
|------|--------|-----------|
| A1 ≥3 incendios | ✅ | Tobarra, Cardoso, Hellín packs completos |
| A2 artefactos | ✅ | report.html, fronts.geojson, local_speeds.csv, summary.json, manifests |
| A5 ancla Tobarra | ✅ reportado | mediana **0.78 m/min** vs INFOCAM **7 m/min** (ratio ~0.11) |
| A7 este documento | ✅ | |

**Lectura honesta A5:** el sistema se abstiene en la mayoría de puntos (observable_ratio Tobarra ≈ 0.5%). La mediana sobre los pocos puntos observables queda **por debajo** de INFOCAM. Causas probables: máscara MAD ruidosa, matching de componentes frágil, submuestreo temporal. **No se presenta 0.78 como Vp oficial.**

---

## Pista B (I+D, anexo técnico)

- Schema `clean12` implementado (`wildfire_front/ml/feature_schema.py`).  
- Preprocess: `--schema clean12`.  
- Kernel script: `kaggle_job/run_unet_training_v23_clean12.py`.  
- Baseline a batir: v21 IoU 0.226 / Δ copy +0.076 (protocolo any_fire 979 patches).

---

## Próxima revisión con el observatorio (propuesta)

1. Abrir `report.html` de Tobarra juntos.  
2. Contrastar Vp mediana vs 7 m/min y discutir calibración de máscara.  
3. Acordar si el siguiente entregable es **más incendios** o **perímetros oficiales** para validación geométrica.
