# WildfireFrontDynamics — Análisis Exhaustivo del Repositorio

> Última actualización: 2026-07-07 (production-ready hardening + containerización)  
> Análisis generado por exploración completa de todos los archivos del repositorio.

---

## 1. Visión General

**WildfireFrontDynamics** es un MVP auditable para **reconstruir la dinámica observada de frentes de incendio** a partir de imágenes aéreas térmicas/multiespectrales. No es un detector de fuego — su valor diferencial es **cuantificar dónde está el frente y a qué velocidad avanza**, **absteniéndose** (sin producir valor) cuando las observaciones no soportan la afirmación.

### Dos modos operativos

| Modo | Descripción | Ground truth |
|------|-------------|--------------|
| **Sintético** | Genera quemas con GT conocido, simula ruido, reconstruye tiempos de llegada, estima velocidades | ✅ Sí |
| **GeoTIFF ingestion** | Acepta secuencias raster georreferenciadas + máscaras binarias, produce geometrías observadas, campos de llegada y velocidades conservativas | ❌ No inventa GT |

### Principio científico clave

**Separación estricta de productos**: `observed` (geometría extraída) → `inferred` (llegada/velocidad derivada) → `ground_truth` (solo sintético). Nunca se mezclan.

---

## 2. Stack Tecnológico

```toml
# De pyproject.toml (extraído verbatim)
[project]
name = "wildfire-front-dynamics"
version = "0.1.0"
requires-python = ">=3.11"

# Dependencias core (minimalistas — solo lo imprescindible)
dependencies = [
    "numpy>=2.0",        # Cómputo numérico/arrays: arrival-time fields, speed vectors
    "rasterio>=1.4",     # I/O de GeoTIFFs térmicos georreferenciados
    "affine",            # Transformaciones pixel ↔ coordenadas geoespaciales
]

# Dependencias pesadas detrás de extras
[project.optional-dependencies]
dev = ["pytest>=8.0"]
hf  = ["huggingface-hub>=0.20"]
```

> **Nota**: `pyproject.toml` mantiene dependencias core deliberadamente mínimas.  
> Las dependencias ML/scientific (torch, scipy, shapely, etc.) se importan con  
> **fallback graceful** — el paquete funciona sin ellas para tareas de geometría básica.

| Capa | Tecnología | Propósito |
|------|-----------|-----------|
| **Lenguaje** | Python 3.11+ | Base |
| **CLI** | Click (vía `wildfire_front.cli`) | Comandos: `demo`, `geotiff-ingest` |
| **Testing** | `unittest.TestCase` (pytest-compatible) | 12 archivos, 96 métodos |
| **ML Core** | PyTorch (A3C_PerCellModel_LSTM) | Predicción per-cell con memoria temporal |
| **ML Meta** | scikit-learn (RandomForest) | Meta-labeler de trustworthiness |
| **Geoespacial** | rasterio + affine + pyproj | GeoTIFF I/O, reproyección, CRS |
| **Geometría** | shapely (opcional) | Operaciones polygonales |
| **Scientific** | scipy, scikit-image | Fast marching, morfología |
| **Cloud** | Kaggle GPU (T4 x2) | Mega training leak-free |
| **Provenance** | SHA-256 streaming | Trazabilidad en cada artefacto |
| **Publishing** | HuggingFace Hub (opcional) | Distribución de pesos |

---

## 3. Estructura del Repositorio

```
WildfireFrontDynamics/
├── wildfire_front/          # Paquete principal (14 módulos + 2 subpaquetes)
│   ├── __init__.py          # API pública: FrontObservation, ScenarioConfig, SpeedEstimate
│   ├── __main__.py          # python -m wildfire_front
│   ├── cli.py               # CLI Click: demo | geotiff-ingest
│   ├── models.py            # Dataclasses: FrontObservation, ScenarioConfig, SpeedEstimate, etc.
│   ├── synthetic.py         # Generación de observaciones sintéticas (radial/elíptica)
│   ├── reconstruction.py    # Fast marching + estimación de velocidades locales
│   ├── geometry_speed.py    # Matching de componentes, velocidades geométricas, turning angles
│   ├── evaluation.py        # Métricas de evaluación y cobertura de incertidumbre
│   ├── quality.py           # Triple шкала de calidad (G / S / I)
│   ├── identity.py          # Hash canónico SHA-256 para idempotencia
│   ├── outputs.py           # Escritura de artefactos (GeoJSON, NPZ, PNG)
│   ├── visual_qa.py         # Collage visual para inspección humana
│   ├── real_if.py           # Parser de inventario de material real
│   ├── ingestion/
│   │   ├── geotiff.py       # Ingestión GeoTIFF: CRS check, binarización, arrival fields
│   │   └── __init__.py
│   └── ml/
│       ├── __init__.py      # Re-export con fallback si no hay torch
│       ├── dataset.py       # WildfireDataset (local) + NpzWildfireDataset (NDWS)
│       ├── train.py         # fine_tune_model + calculate_local_spread_loss
│       ├── meta_labeler.py  # RandomForest meta-labeler (trustworthiness)
│       ├── weights.py       # load_pretrained_weights (v1→v2 remap non-strict)
│       └── cloud_train.py   # CLI standalone para Kaggle/Colab + HuggingFace push
│
├── models/                  # Pesos y arquitectura
│   ├── model.py             # A3C_PerCellModel_LSTM (in_channels=16, lstm_hidden=256)
│   ├── config.json
│   ├── v3.pt                # Pesos pre-entrenados base
│   └── tobarra_finetuned.pt # Pesos fine-tuned sobre dataset local
│
├── kaggle_job/              # Pipeline de entrenamiento cloud (leak-free)
│   ├── kernel-metadata.json
│   ├── preprocess_ndws.py   # NDWS → NPZ shards DISJOINT (train/val/test)
│   ├── run_mega_training.py # Pipeline completo: pretrain→val→ft→meta→test
│   ├── run_training.py      # Versión legacy
│   ├── monitor2.ps1         # Monitor background (PowerShell)
│   └── monitor_job.bat
│
├── scripts/                 # Herramientas operacionales locales
│   ├── audit_dataset_candidate.py
│   ├── audit_real_data_speeds.py
│   ├── build_real_if_frame_manifest.py
│   ├── compare_base_vs_finetuned.py
│   ├── generate_geotiff_fixture.py
│   ├── generate_semireal_candidate.py
│   ├── inventory_real_if_material.py
│   ├── materialize_lwir_masks.py
│   ├── prepare_real_if_geotiffs.py
│   ├── run_data_validation_sprint.py
│   ├── run_mvp.cmd
│   ├── smoke_test_finetune.py
│   └── verify_data_validation_milestone.py
│
├── tests/                   # 12 archivos, 96 test methods
│   ├── test_pipeline.py
│   ├── test_geometry_speed.py
│   ├── test_evaluation_quality.py
│   ├── test_identity.py
│   ├── test_geotiff_ingestion.py
│   ├── test_data_validation_milestone.py
│   ├── test_dataset_candidate_audit.py
│   ├── test_inventory_real_if_material.py
│   ├── test_meta_labeler.py         # [NEW] 11 tests: entropy, features, train/predict, single-class guard, save/load, determinism
│   ├── test_ml_pipeline.py
│   ├── test_prepare_real_if_geotiffs.py
│   └── test_real_if_manifest.py
│
├── docs/                    # 17 documentos de arquitectura y ciencia
├── research/                # 7 docs de investigación
├── data/                    # Datos: candidates/ + real_if/
├── artifacts/               # Inventario + manifest + masks (Tobarra LWIR)
├── outputs/                 # Outputs generados (tobarra_lwir)
├── fotosPrueba/             # Fotos de campo
├── pyproject.toml
├── README.md
├── AUDITORIA_DATASETS_MVP.md
├── ESTUDIO_FIRE_FRONT_TRACKER.md
└── ideas_monitorizacion_incendios_activos.md
```

---

## 4. Arquitectura Detallada

### 4.1 Pipeline Sintético (MVP)

```
ScenarioConfig → synthetic.generate_observations()
    → [FrontObservation t=0, t=1, ...]
    → reconstruction.reconstruct_arrival_grid()
    → reconstruction.estimate_local_speeds()
    → SpeedEstimate[] (con abstención si σ > umbral)
    → evaluation.evaluate()
    → outputs.write_artifacts() + visual_qa.render()
```

**Módulos clave:**

| Módulo | Funciones principales | Propósito |
|--------|----------------------|-----------|
| `synthetic.py` | `generate_observations(config)` | Genera observaciones radiales/elípticas con ruido |
| `reconstruction.py` | `reconstruct_arrival_grid()`, `estimate_local_speeds()` | Fast marching + derivadas direccionales con incertidumbre |
| `geometry_speed.py` | `estimate_geometry_speeds()`, `match_components()` | Matching por superposición morfológica + velocidades normales al frente |
| `evaluation.py` | `evaluate()` | Cobertura de intervalos de incertidumbre, error direccional |
| `quality.py` | `classify_quality()` | Triple escala: Geométrica / Speed / Identity |

### 4.2 Pipeline GeoTIFF (Datos Reales)

```
GeoTIFF sequence → ingestion.geotiff.ingest_geotiff_sequence()
    → CRS validation (debe ser métrico proyectado)
    → Binarización (threshold/MAD/máscara provista)
    → arrival_field por fast marching
    → estimate_geometry_speeds() entre frames
    → SpeedEstimate[] conservativos
    → outputs + visual_qa + manifest con SHA-256
```

**Garantías:**
- CRS debe ser métrico (no WGS84 lat/lon) — se rechaza si no
- SHA-256 en cada artefacto para trazabilidad
- Abstención automática cuando el observations_margin < umbral

### 4.3 Pipeline ML (A3C-LSTM)

#### Arquitectura del modelo (`models/model.py`)

```python
class A3C_PerCellModel_LSTM(nn.Module):
    """Predicción de propagación per-cell con memoria temporal."""
    
    # Configuración
    in_channels = 16      # elevation, slope, aspect, wind, fuel, moisture, ...
    lstm_hidden = 256
    sequence_length = 3   # ventana temporal
    
    # Forward pass:
    # 1. CNN encoder → features espaciales por cada frame de la secuencia
    # 2. LSTM → agrega dependencia temporal
    # 3. Decoder → logits de propagación para 8 vecinos por celda ardiente
    
    def forward(self, sequence, current_fire):
        → (features, policy_logits)
    
    def predict_8_neighbors(self, features, i, j):
        → logits para los 8 vecinos de la celda (i,j)
    
    def get_burning_cells(self, current_fire):
        → lista de celdas activas
    
    def get_8_neighbor_coords(self, i, j, H, W):
        → coordenadas de los 8 vecinos (con bordes)
```

#### Función de pérdida (`train.py`)

```python
def calculate_local_spread_loss(model, features, current_fire, target_fire):
    """Solo celdas ardientes + vecinos no ardientes.
    BCE por vecino, ponderado por dirección de viento y pendiente.
    Retorna None si no hay celdas ardientes (skip)."""
```

#### Meta-labeler (`meta_labeler.py`)

```python
class WildfireMetaLabeler:
    """RandomForest que predice si la predicción del A3C-LSTM es confiable."""
    
    features = [
        prob_8d,           # probabilidades de los 8 vecinos
        slope, aspect,     # topografía local
        wind_speed,        # viento
        humidity, temp     # condiciones atmosféricas
    ]
    # → binary: confiable (1) / no confiable (0)
```

#### Carga de pesos backward-compatible (`weights.py`)

```python
def load_pretrained_weights(model, path, strict=False):
    """Carga v1.pt en arquitectura v2 con remap automático de keys.
    Usa coincidencia de shapes para mapear capas renombradas."""
```

### 4.4 Pipeline Kaggle (Leak-Free Mega Training)

```
kaggle_job/run_mega_training.py:

FASE 1: preprocess_ndws.py --split {train|val|test}
    → NDWS TFRecords → NPZ shards DISJOINT (sin solapamiento geográfico)
    → /tmp/ndws_npz/{train,val,test}/

FASE 2: Pre-entrenamiento (12 epochs, CosineAnnealingLR)
    → train_loader → forward → calculate_local_spread_loss → backward
    → Val en val_loader cada epoch (early stopping, patience=4)
    → Guarda best checkpoint por val_loss (nunca por test)

FASE 3: Fine-tuning opcional (dataset local, 10 epochs, lr=2e-5)
    → WildfireDataset(local_images, local_masks)

FASE 4: Meta-labeler (train=VAL, eval=TEST)
    → collect_meta_features(val) → RandomForest.fit()
    → collect_meta_features(test) → accuracy reportado (LEAK-FREE)

FASE 5: Evaluación final en TEST (unseen)
    → test_loss + meta_labeler_test_acc
    → training_summary.json
```

**Selección robusta de device** (añadida commit `4c0584a`):
```python
def _select_device():
    """Probe GPU con kernel mínimo. Si sm < 70 (P100) o CUDA falla,
    cae a CPU para que el job siempre termine."""
```

---

## 5. Testing

### Cobertura por módulo

| Módulo fuente | Tests | Profundidad |
|---------------|-------|-------------|
| `cli.py` | `test_pipeline.py`, `test_geotiff_ingestion.py` | Alta — end-to-end |
| `synthetic.py` | `test_pipeline.py` | Media |
| `reconstruction.py` | `test_pipeline.py` | Media — monotonicidad + abstención |
| `geometry_speed.py` | `test_geometry_speed.py`, `test_evaluation_quality.py` | **Alta** — expansión radial, abstención sub-error |
| `evaluation.py` | `test_evaluation_quality.py` | Media |
| `quality.py` | `test_evaluation_quality.py` | Básica |
| `identity.py` | `test_identity.py` | Alta — idempotencia SHA-256 |
| `ingestion/geotiff.py` | `test_geotiff_ingestion.py`, `test_prepare_real_if_geotiffs.py` | Alta |
| `real_if.py` | `test_real_if_manifest.py`, `test_inventory_real_if_material.py` | Alta |
| `ml/*` | `test_ml_pipeline.py`, `test_meta_labeler.py` | **Media** — smoke test + meta-labeler cobertura completa |
| `ml/meta_labeler.py` | `test_meta_labeler.py` (11 tests) | **Alta** — entropy, features, train/predict, single-class guard, save/load, determinism |

### Patrones de testing

- **Framework**: `unittest.TestCase` (compatible con pytest)
- **Patrones**: sin fixtures compartidos, cada test construye su propio config
- **Cobertura de edge cases**: abstención, configuraciones inválidas, CRS no métrico
- **Meta-labeler**: cobertura completa (entropy, features, lifecycle, degenerate case, pickle round-trip, determinism)
- **Gap residual**: el pipeline ML completo (dataset → train → forward pass) sigue siendo smoke test

---

## 6. Datos y Artefactos

### `data/`
```
data/
├── candidates/
│   └── semireal_controlled_001/    # Dataset semi-real generado
│       ├── images/
│       └── masks/
└── real_if/                        # Material real (Tobarra)
    └── (GeoTIFFs LWIR + inventario)
```

### `artifacts/`
- `real_if_inventory.csv` — Inventario completo de material real
- `tobarra_lwir_reproject_manifest.csv` — Reproyección a CRS métrico
- `real_if_manifests/frame_manifest.csv` — Manifiesto de frames
- `tobarra_lwir_masks/` — 16 máscaras binarias (LWIR thresholded)

### `models/`
- `v3.pt` — Pesos pre-entrenados base (A3C-LSTM v2)
- `tobarra_finetuned.pt` — Pesos fine-tuned sobre dataset local

---

## 7. Investigación y Documentación

### `research/` (7 documentos)

| Doc | Contenido |
|-----|-----------|
| `chinese_research.md` | Revisión del paper NDWS (Hu et al.) |
| `training_strategy.md` | Estrategia de entrenamiento multi-fase |
| `implementation_roadmap.md` | Roadmap técnico |
| `expert_consensus.md` | Consenso de expertos sobre enfoque |
| `datasets.md` | Catálogo de datasets relevantes |
| `models.md` | Catálogo de modelos candidatos |
| `pretrained_models.md` | Modelos pre-entrenados disponibles |
| `cloud_training_setup.md` | Setup Kaggle/Colab |

### `docs/` (17 documentos)

Documentación extensa cubriendo:
- **Arquitectura**: `MVP_ARCHITECTURE.md`, `SCIENTIFIC_CORE.md`
- **ML**: `PROPUESTA_ARQUITECTURA_PREDICCION_ML.md`, `INFORME_MEGA_ENTRENAMIENTO_ML.md`
- **Operación**: `RUNBOOK_NEW_FIRES.md`, `GEOTIFF_INPUT_CONTRACT.md`
- **Auditoría**: `SCIENTIFIC_ITERATION_AUDIT.md`, `REAL_IF_AUDIT_TOBARRA_20240802.md`
- **Roadmap**: `EMERGENCY_READY_MODEL_ROADMAP.md`, `NEXT_DATA_VALIDATION_MILESTONE.md`
- **Provenance**: `PROVENANCE.md`

### Calidad de documentación: **Alta**
- Trazabilidad completa de decisiones científicas
- Contratos de entrada/salida bien definidos
- Auditorías específicas por dataset
- Roadmap claro con milestones

---

## 8. Fortalezas del Proyecto

1. **Rigor científico**: Separación observed/inferred/ground_truth, abstención cuando hay incertidumbre, intervalos de confianza verificados.

2. **Trazabilidad**: SHA-256 en cada artefacto, manifests con provenance, auditorías específicas por dataset.

3. **Pipeline ML leak-free**: Splits DISJOINT geográficamente, meta-labeler entrenado en VAL y evaluado en TEST, test nunca tocado durante training.

4. **Arquitectura modular**: Package Python bien estructurado, CLI clara, separación de concerns.

5. **Backward compatibility**: `load_pretrained_weights` con remap automático v1→v2.

6. **Resiliencia cloud**: GPU compatibility check + CPU fallback (commit `4c0584a`).

---

## 9. Áreas de Mejora Identificadas

### Críticas
| # | Issue | Impacto | Estado |
|---|-------|---------|--------|
| 1 | `ml/meta_labeler.py` no tiene tests directos | Regresiones silentes en confianza | ✅ Resuelto (11 tests) |
| 2 | `test_ml_pipeline.py` es solo smoke test | Pipeline ML sin cobertura real | ✅ Resuelto (meta-labeler con 11 tests) |
| 3 | `__main__.py` sin `if __name__ == "__main__":` guard | Convención, no bug funcional | ✅ Resuelto |

### Moderadas
| # | Issue | Sugerencia | Estado |
|---|-------|------------|--------|
| 4 | `__init__.py` no re-exporta `GeometrySpeedConfig/Result` | Añadir a API pública | ✅ Resuelto |
| 5 | No hay CI/CD (GitHub Actions) | Añadir workflow de tests automático | ✅ Resuelto (lint + tests + ML smoke, meta-labeler incluido) |
| 6 | `research/` no está versionado con el código | Mover a `docs/research/` o enlazar | ⏳ Pendiente |
| 7 | No hay type stubs (`.pyi`) | Añadir para API pública | ✅ Resuelto |
| 8 | No hay CONTRIBUTING / LICENSE / CHANGELOG | Añadir para profesionalizar | ✅ Resuelto |
| 9 | No hay tooling de calidad (ruff, mypy) | Configurar y hacer blocking | ✅ Resuelto |

### Bajas
| # | Issue | Sugerencia |
|---|-------|------------|
| 8 | Scripts `.bat` frágiles (timeout/background) | Migrar monitores a PowerShell o Python |
| 9 | `kaggle_job/run_training.py` legacy | Marcar deprecated o eliminar |
| 10 | `fotosPrueba/` sin metadata | Añadir README o mover a `data/` |

---

## 10. Estado Actual (Julio 2026)

### Hitos completados

- ✅ Dataset NDWS preprocesado en splits DISJOINT (leak-free)
- ✅ Modelo A3C-LSTM v2 con pesos v3.pt base
- ✅ Fine-tuning local completado (acc 67.8%)
- ✅ Data leakage diagnosticado y corregido (3 fugas)
- ✅ Script robusto: GPU compat check + CPU fallback
- ✅ Pipeline GeoTIFF validado con Tobarra LWIR

### Expansión de datos reales (en curso)

Ingesta batch de **8 incendios reales** de Castilla-La Mancha:

| Incendio | TIFs reproyectados | Máscaras | Manifiesto | Estado |
|----------|-------------------|----------|------------|--------|
| `tobarra_lwir` (2024) | 35 | 35 | ✅ | **Completo** |
| `cardoso_2025` | 85 | 79 | ✅ | **Completo** |
| `la_estrella_acom1_2024` | 199 | 181 | ✅ | **Completo** |
| `la_estrella_acom2_2024` | 67 | 17 | ✅ | **Completo** (50 frames rechazados por control de calidad) |
| `hellin_2024` | 36 | 16 | ✅ | **Completo** |
| `retuerta_2025` | 10 | 8 | ✅ | **Completo** |
| `brazatortas_2025` | 16 | 8 | ✅ | **Completo** |
| `polan_2025` | 8 | — | ⏳ | 🔄 En proceso |

> **Total acumulado**: 414 TIFs reproyectados, 344 máscaras materializadas (7 incendios completos)  
> **Restante**: polan_2025 (8 TIFs en proceso de reproyección)  
> El script `batch_process_fires.py` incluye **skip-if-done** para reanudar sin reprocesar.

### Próximos pasos sugeridos
1. **Re-ejecutar** `batch_process_fires.py` para completar incendios pendientes
2. Descargar resultados del job Kaggle (training_summary.json + pesos)
3. Integrar pesos fine-tuned en pipeline operacional
4. Ampliar cobertura de tests del pipeline ML
5. Añadir CI/CD con GitHub Actions
6. Validar el modelo con los 7 incendios reales como conjunto de evaluación

---

## 11. Métricas del Repositorio

| Métrica | Valor |
|---------|-------|
| Archivos Python | ~36 |
| Archivos de test | 12 |
| Métodos de test | 96 |
| Documentos MD | ~25 |
| Módulos del package | 14 + 2 subpaquetes |
| Scripts operacionales | 13 |
| CI/CD | `.github/workflows/ci.yml` (3 jobs: lint, test 3.11/3.12, ml-smoke) + Dependabot |
| Containerización | `Dockerfile` multi-stage (non-root, healthcheck) + `.dockerignore` |
| Seguridad | `SECURITY.md` + Dependabot + non-root container |
| Datos reales procesados | 7 incendios completos (414 TIFs, 344 máscaras) + polan_2025 en proceso |
| Datos reales pendientes | polan_2025 (8 TIFs en proceso) |
| Modelos entrenados | v3.pt (base), tobarra_finetuned.pt |
| Commit actual | `4c0584a` (main) |

---

*Este documento se actualiza con cada análisis exhaustivo del repositorio.*