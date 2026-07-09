# 📋 PROMPT MAESTRO — Siguientes Sprints y Mejoras de Código

> **Documento generador**: copia este archivo en un nuevo chat de Cline/Claude para que el asistente arranque con contexto completo sobre el proyecto WildfireFrontDynamics.

---

## 🎯 ROL Y SKILLS REQUERIDAS

Actúa como un **equipo multidisciplinar** integrado por:

### 🌡️ Experto en Meteorología y Física de Incendios
- Modelos de propagación: **Rothermel**, **FARSITE**, **Prometheus**, **WRF-Fire**
- Meteorología de mesoescala: **AEMET Open Data**, **WRF**, **ERA5 (Copernicus CDS)**
- Combustibles: modelos **Scott & Burgan** (40 NB/GR/TU/TL), **FFMC/DMC/DC** (Canadian FWI)
- Teledetección térmica: bandas **LWIR** (8-14 µm), **SWIR** (Sentinel-2 B12), **MODIS/VIIRS Active Fire**
- Índices de vegetación: **NDVI**, **EVI**, **NBR** (Normalized Burn Ratio)

### 🧠 Experto en Machine Learning / Deep Learning
- **PyTorch** avanzado: AMP, `torch.compile`, DistributedDataParallel, custom autograd
- Arquitecturas: **A3C-LSTM**, **U-Net + ConvLSTM**, **Vision Transformers (ViT)**, **SegFormer**, **DeepLab v3+**
- Loss functions: **Focal loss**, **Dice+BCE**, **Tversky**, **boundary loss**, **physics-informed NN**
- Transfer learning: fine-tuning de modelos fundacionales (SatLas, Prithvi, Clay)
- **Kaggle**: kernels GPU T4/P100, datasets, API de submission y descarga de outputs
- Experiment tracking: **MLflow**, **Weights & Biases**
- MLOps: ONNX export, TensorRT, TorchScript, FastAPI

### 🗺️ Experto en GIS / Teledetección
- **GDAL/rasterio**: reproyección EPSG:32630 (UTM 30N), mosaico, recorte
- **Sentinel-2** (Copernicus), **Landsat 8/9** (USGS), **DEM PNOA** (IGN España)
- **QGIS** para validación visual de máscaras
- Catálogo **Copernicus EMS**, **Copernicus Global Land Service**
- **Google Earth Engine** para extracción masiva de reflectancias

### 💻 Ingeniero de Software Senior
- **Python 3.12+**: type hints, async, dataclasses, pathlib
- **Testing**: pytest, fixtures, mocks para rasterio/torch
- **CI/CD**: GitHub Actions, Docker, pre-commit hooks
- **Code review**: SOLID, DRY, clean architecture, domain-driven design

---

## 📂 RUTAS Y DATASETS DEL PROYECTO

### Estructura del repositorio
```
c:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics\
├── wildfire_front/           # Paquete Python principal
│   ├── __init__.py
│   ├── cli.py                # CLI: wildfire-front ...
│   ├── evaluation.py         # Métricas (IoU, precision, recall, F1)
│   ├── geometry_speed.py     # Cálculo de velocidad de frente (ROS)
│   ├── identity.py           # Identidad de incendios (tracking)
│   ├── models.py / .pyi      # Type stubs del modelo ML
│   ├── outputs.py            # Serialización de resultados
│   ├── quality.py            # Quality gates (precision/recall mínimos)
│   ├── real_if.py            # Pipeline de incendios reales
│   ├── reconstruction.py     # Reconstrucción de secuencia temporal
│   ├── synthetic.py          # Generador de datos sintéticos
│   ├── visual_qa.py          # Visualización para QA
│   ├── ingestion/
│   │   ├── geotiff.py        # Lectura GeoTIFF, matching máscaras
│   │   └── ...
│   └── ml/
│       ├── dataset.py        # WildfireDataset + NpzWildfireDataset
│       ├── train.py          # Loss focal + vectorizada + fine-tuning
│       ├── meta_labeler.py   # RandomForest meta-labeler
│       ├── physics.py        # Physics loss (Rothermel ROS)
│       ├── types.py          # Protocolos/Type hints
│       └── weights.py        # Carga de pesos pre-entrenados
├── models/
│   ├── config.json           # Config de canales (17ch)
│   └── model.py              # A3C_PerCellModel_LSTM (5M params)
├── kaggle_job/
│   ├── run_mega_training.py  # Pipeline Kaggle completo (v7 vectorizado)
│   ├── run_training.py       # Pipeline Kaggle legacy
│   ├── preprocess_ndws.py    # Preprocesado Next Day Wildfire Spread → NPZ
│   └── kernel-metadata.json  # Metadata del kernel Kaggle
├── data/
│   ├── candidates/
│   │   └── semireal_controlled_001/   # Fixture semireal (4 frames GeoTIFF)
│   │       ├── images/                 # 4 imágenes GeoTIFF
│   │       └── masks/                  # 4 máscaras binarias GeoTIFF
│   └── real_if/
│       └── raw_dropbox/               # Crudo recibido de Dropbox
│           ├── Heligrafics/           # Drones térmicos (LWIR)
│           │   ├── TOBARRA_2024-08-02/
│           │   ├── LA_ESTRELLA_2024-09-12/
│           │   └── ...
│           └── GEA_CyL/              # Imágenes de Castilla y León
├── outputs/
│   └── tobarra_lwir/
│       └── ingest_manifest.csv       # Manifiesto de ingesta (SHA-256, timing)
├── scripts/                  # 15+ scripts de utilidad
├── tests/                    # 11 suites pytest
├── research/                 # 9 docs de investigación
└── docs/                     # 25+ documentos de arquitectura y estado
```

### Datasets en uso y planificados

| Dataset | Tipo | Ruta / Fuente | Origen | # Muestras | Formato | Madurez |
|---------|------|---------------|--------|------------|---------|---------|
| **semireal_controlled_001** | Semireal | `data/candidates/semireal_controlled_001/` | Fixture interno | 4 frames | GeoTIFF (EPSG:32630) | ✅ Listo |
| **Tobarra LWIR (2024-08-02)** | Real táctico | `data/real_if/raw_dropbox/Heligrafics/TOBARRA_2024-08-02/` | **Tobarra, Albacete, Castilla-La Mancha** | ~120 frames LWIR | GeoTIFF reproyectado | ✅ Ingerido |
| **La Estrella (2024-09-12)** | Real táctico | `data/real_if/raw_dropbox/Heligrafics/LA_ESTRELLA_2024-09-12/` | Castilla-La Mancha | ~80 frames | JPEG/GeoTIFF mixto | 🔄 En ingesta |
| **GEA CyL** | Real táctico | `data/real_if/raw_dropbox/GEA_CyL/` | Castilla y León | ~200 imágenes | JPEG/RGB | 🔄 Pendiente |
| **Next Day Wildfire Spread (NDWS)** | Sintético satelital | Kaggle → `kaggle_job/preprocess_ndws.py` | EE.UU. (Google Earth) | ~18K+ muestras | TFRecord → NPZ | ✅ Pipeline listo |
| **FLAME / FLAME 3** | Real UAV | Kaggle (pendiente descarga) | EE.UU. controlado | ~30K+ frames | MP4/PNG | ⏳ A auditar |
| **AEMET Open Data** | Meteorológico | API AEMET (`aemet-open-data`) | España | Series temporales | JSON/JSON-LD | ⏳ A integrar |
| **Sentinel-2 (Copernicus)** | Satelital | Copernicus SciHub / Earth Engine | Global (España) | Multiespectral | JP2/GeoTIFF | ⏳ A integrar |
| **ERA5 (Copernicus CDS)** | Reanálisis meteorológico | `cds.climate.copernicus.eu` | Global | Reanálisis horario | NetCDF | ⏳ A integrar |
| **DEM PNOA** | Topográfico | IGN España (`centrodedescargas.cnig.es`) | España | MDT 5m/2m | GeoTIFF | ⏳ A integrar |
| **Copernicus EMS** | Activación rápida | `emergency.copernicus.eu` | Europa (España) | Activaciones | GeoTIFF/SHP | ⏳ Referencia |

### Castilla-La Mancha — Datos clave
- **Tobarra (Albacete)**: Incendio 2024-08-02, capturado por drone Heligrafics con sensor **LWIR (Long-Wave Infrared)**. Es el dataset real más maduro del proyecto (~120 frames a 0.5 m/pixel, EPSG:32630). Ingerido con segmentación MAD adaptive (z=3.5) → máscaras binarias. Manifiesto en `outputs/tobarra_lwir/ingest_manifest.csv`.
- **La Estrella**: Incendio 2024-09-12, también Heligrafics. En proceso de ingesta.
- **Vegetación típica**: monte mediterráneo (Pinus halepensis, Quercus ilex, matorral), modelos de combustible 4-7 de Rothermel adaptados a España (PROMETEO).

---

## 🏗️ ARQUITECTURA ML ACTUAL (v7)

### Modelo: A3C_PerCellModel_LSTM
```
Entrada: (1, 3, 17, 30, 30) — secuencia temporal de 3 frames, 17 canales, parche 30×30
  │
  ├─ CNN Encoder por timestep (17→64→128→256, GroupNorm + Dropout 0.2)
  │   └─ Global AvgPool → vector (1, 256) por timestep
  │
  ├─ LSTM temporal (256→256, 1 layer) → contexto global
  │
  ├─ Gated Fusion: gate = sigmoid(concat[last_spatial, temporal_ctx])
  │   fused = gate * temporal + (1-gate) * last_spatial
  │
  ├─ Refinement Conv (256→256, 3×3, GroupNorm, ReLU)
  │
  ├─ Policy Head (per-cell): Linear(256×9 → 256 → 8) — 8 logits de propagación
  └─ Value Head: GlobalAvgPool → Linear(256→64→1) — estimación de valor
```

### 17 Canales de entrada
| Canal | Variable | Origen | Normalización |
|-------|----------|--------|---------------|
| 0 | DEM slope | PNOA/sintético | radianes |
| 1 | DEM aspect | PNOA/sintético | radianes |
| 2 | Temperatura | AEMET/constante | °C |
| 3 | Humedad | AEMET/constante | % |
| 4 | Wind speed | AEMET/constante | m/s |
| 5 | Wind direction | AEMET/constante | grados |
| 6 | Precipitación | AEMET/constante | mm |
| 7 | Presión | AEMET/constante | hPa |
| 8 | Nubosidad | AEMET/constante | % |
| 9 | Visibilidad | AEMET/constante | km |
| 10 | Dew point | AEMET/constante | °C |
| 11 | Thermal/NDVI | LWIR (Tobarra) o NDVI | z-score |
| 12-15 | FSM (one-hot) | Fuel model | 4 clases |
| 16 | FFMC | Canadian FWI | [0,1] = ffmc/101 |

### Loss function (v7 — vectorizada)
- **Focal BCE** (γ=2.0, pos_weight=3.0) — penaliza falsos negativos
- **Spread-direction bonus** (soft IoU, peso 0.5)
- **Physics loss** (Rothermel ROS, λ=0.1)
- Vectorizada con `F.unfold` → 10-50x más rápida que el loop per-cell

### Meta-labeler
- RandomForest (100 estimators, max_depth=10)
- Features: probabilidad, entropía, slope, aspect, wind, humedad, temp
- Entrenado sobre VAL, evaluado sobre TEST (leak-free)

---

## 🚀 SPRINTS PLANIFICADOS

### Sprint v7 — RE-EJECUTAR MEGA ENTRENAMIENTO VECTORIZADO ✅ CÓDIGO LISTO
**Objetivo**: Lanzar en Kaggle con la loss vectorizada (commit `25ae593`).
- Pre-entrenamiento NDWS: 15 épocas, warmup 2 + cosine decay
- Fine-tuning Tobarra: 10 épocas, lr=2e-5
- Meta-labeler en val→test
- **Estado**: Código commiteado y pusheado. Falta ejecutar en Kaggle.
- **Esperado**: ~5x reducción de tiempo por época (25 min → ~5 min en T4)

### Sprint v8 — AUMENTO DE DATASET REAL Y MULTIMODAL
**Objetivo**: Multiplicar los datos tácticos de Castilla-La Mancha y España.
- [ ] Integrar La Estrella (2024-09-12) en pipeline de ingesta
- [ ] Auditar y ingerir GEA CyL (Castilla y León, ~200 imágenes RGB)
- [ ] Descargar y auditar FLAME/FLAME 3 desde Kaggle
- [ ] Conectar API AEMET Open Data para reemplazar constantes meteorológicas por datos reales por incendio
- [ ] Descargar DEM PNOA (2m) para Tobarra y La Estrella
- [ ] Aumentar augmentación: rotaciones 90°/180°/270°, mixup temporal, CutMix espacial
- [ ] Generar versiones NPZ de todos los datasets reales para entrenamiento en Kaggle

**Archivos a tocar**:
- `wildfire_front/ingestion/geotiff.py` — soporte para nuevos formatos
- `scripts/prepare_real_if_geotiffs.py` — automatizar descarga DEM
- `scripts/build_real_if_frame_manifest.py` — nuevos incendios
- `kaggle_job/preprocess_ndws.py` — función para empaquetar reales a NPZ
- **NUEVO**: `scripts/integrate_aemet_weather.py` — API AEMET
- **NUEVO**: `scripts/download_dem_pnoa.py` — descarga DEM IGN

### Sprint v9 — ARQUITECTURA NEXT-GEN (U-Net + ConvLSTM)
**Objetivo**: Reemplazar el loop per-cell por segmentación end-to-end.
- [ ] Implementar **U-Net + ConvLSTM** como modelo primario (según `PROPUESTA_ARQUITECTURA_PREDICCION_ML.md`)
- [ ] Salida: mapa sigmoide (H×W) directo, sin iterar celdas
- [ ] Transfer learning desde SatLas / Prithvi / Clay
- [ ] Comparar A3C-LSTM vs U-Net+ConvLSTM en Tobarra (test holdout)
- [ ] Implementar **Tversky loss** (α=0.7, β=0.3) para optimizar recall
- [ ] Añadir **boundary loss** para mejorar bordes de frente

**Archivos a tocar**:
- **NUEVO**: `models/unet_convlstm.py` — nueva arquitectura
- `wildfire_front/ml/train.py` — añadir dice/tversky/boundary loss
- `wildfire_front/ml/weights.py` — soporte para cargar SatLas/Prithvi
- **NUEVO**: `scripts/compare_base_vs_finetuned.py` (existe, ampliar)

### Sprint v10 — FÍSICA MEJORADA Y CALIBRACIÓN
**Objetivo**: Hacer que el modelo respete leyes físicas de propagación.
- [ ] Integrar **PROMETEO** (Rothermel español) como teacher en loss
- [ ] Calibrar modelos de combustible Scott & Burgan 40 para Castilla-La Mancha
- [ ] Descargar datos de combustión del **Mapa Forestal de España** (MFE50)
- [ ] Añadir restricción: ROS máximo físico según viento + pendiente + FFMC
- [ ] Validar predicciones contra observaciones de campo (Tobarra timed)

**Archivos a tocar**:
- `wildfire_front/ml/physics.py` — ampliar Rothermel + PROMETEO
- **NUEVO**: `wildfire_front/ml/fuel_models.py` — catálogo Scott & Burgan 40
- **NUEVO**: `scripts/download_fuel_map_spain.py` — MFE50

### Sprint v11 — OPERACIONAL: API + DASHBOARD
**Objetivo**: Desplegar el modelo para uso en emergencias.
- [ ] API REST con FastAPI: `POST /predict` → recibe GeoTIFF + meteo → devuelve máscara predicha
- [ ] Exportar modelo a **ONNX** + **TensorRT** para inferencia <100ms
- [ ] Dashboard Streamlit/Grafana: mapa interactivo con predicción
- [ ] Integración con **AEMET** tiempo real (polling cada 10 min)
- [ ] Alertas automáticas vía Telegram/Slack

**Archivos a tocar**:
- **NUEVO**: `api/main.py` — FastAPI server
- **NUEVO**: `api/models.py` — Pydantic schemas
- **NUEVO**: `dashboard/app.py` — Streamlit
- **NUEVO**: `scripts/export_onnx.py`

---

## 🔧 MEJORAS DE CÓDIGO ESPECIALIZADAS

### 1. Vectorización del forward pass (inferencia)
El método `get_action_and_value()` en `models/model.py` todavía itera celda por celda. En inferencia esto es lento. Implementar versión vectorizada que use `F.unfold` + `torch.sigmoid` directo sobre todo el feature map, generando un mapa (H×W) de probabilidades en una sola pasada.

### 2. Batch size > 1 (model restructure)
El modelo actual fuerza `batch_size=1` con un assert. Refactorizar `forward()` y `get_action_and_value()` para soportar `batch_size>1`, lo que multiplicaría el throughput por 4-8x en GPU T4.

### 3. torch.compile() para PyTorch 2.x
Añadir `model = torch.compile(model, mode="reduce-overhead")` en `run_mega_training.py` para compilación de grafos (hasta 30% extra de speedup).

### 4. Gradient accumulation
Con `batch_size=1`, los gradientes son ruidosos. Implementar **gradient accumulation** (4-8 pasos) para simular batch efectivo de 4-8 sin cambiar la arquitectura.

### 5. Progressive resizing
Entrenar primero con parches 30×30, luego aumentar a 60×60 y finalmente 120×120. Esto permite ver más contexto y acelera las primeras épocas.

### 6. Test-Time Augmentation (TTA)
En evaluación/inferencia: predecir la imagen original + sus 4 rotaciones (0°, 90°, 180°, 270°) y sus flips, promediar las 8 predicciones. Mejora IoU ~2-3%.

### 7. EMA (Exponential Moving Average) de pesos
Mantener una copia EMA del modelo (decay=0.999) y usarla para evaluación/inferencia. Mejora estabilidad y métricas finales.

### 8. Weights & Biases integration
Reemplazar los `print()` en `run_mega_training.py` por `wandb.init()` + `wandb.log()` para tracking de experimentos, visualización de máscaras predichas y comparación de runs.

### 9. Mixed-precision training completo
El script ya usa AMP pero el loss se castea a fp32. Probar mantener el loss en fp16/bf16 para mayor velocidad, con `torch.autocast` envolviendo toda la loss function.

### 10. Data loading asíncrono
Implementar **CUDA streams** para solapar transferencia de datos (CPU→GPU) con cómputo. Usar `torch.utils.data.DataLoader` con `pin_memory=True` + `non_blocking=True` en `.to(device)`.

---

## 📊 MÉTRICAS Y EVALUACIÓN

### Métricas actuales (`wildfire_front/evaluation.py`)
- IoU (Jaccard)
- Precision, Recall, F1
- False Positive Rate, False Negative Rate

### Métricas a añadir
- **Boundary F1**: precisión en bordes de frente (crítico para respuesta táctica)
- **Hausdorff Distance**: distancia máxima entre frente predicho y ground truth
- **Rate of Spread Error (ROS-E)**: error en velocidad de propagación (m/min)
- **Calibration**: Brier score, reliability diagram

### Quality gates (`wildfire_front/quality.py`)
```python
MIN_PRECISION = 0.70
MIN_RECALL = 0.60
MIN_IOU = 0.40
```
Ajustar estos umbrales según resultados del sprint v7.

---

## 🔗 LINKS Y REFERENCIAS

### APIs y fuentes de datos
- AEMET Open Data: `https://opendata.aemet.es/centrodedescargas/inicio`
- Copernicus CDS (ERA5): `https://cds.climate.copernicus.eu/`
- IGN PNOA DEM: `https://centrodedescargas.cnig.es/`
- Sentinel-2 SciHub: `https://scihub.copernicus.eu/`
- Google Earth Engine: `https://earthengine.google.com/`
- Kaggle Datasets: `https://www.kaggle.com/datasets`

### Modelos pretrained
- SatLas: `https://github.com/allenai/satlaspretrain`
- Prithvi (NASA/IBM): `https://huggingface.co/ibm-nasa-geospatial`
- Clay: `https://github.com/Clay-foundation/model`

### Papers clave
- Rothermel (1972): "A mathematical model for predicting fire spread"
- Finney (1998): FARSITE: Fire Area Simulator
- UNet (Ronneberger 2015): segmentación biomédica → aplicable a máscaras de fuego
- ConvLSTM (Shi 2015): predicción de precipitación → aplicable a secuencias temporales

---

## ✅ CÓMO USAR ESTE PROMPT

1. Copia este archivo completo
2. Pégalo en un nuevo chat de Cline/Claude
3. Añade al final: *"Implementa el Sprint vN que se indica a continuación: [descripción]"*
4. El asistente tendrá contexto completo del proyecto, datasets, arquitectura y próximos pasos

---

**Última actualización**: 2026-07-09 (post-v7 vectorización, commit `25ae593`)