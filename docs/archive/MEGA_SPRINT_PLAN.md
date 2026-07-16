# Mega Sprint — WildfireFrontDynamics

> **Estado:** Borrador para revisión
> **Fecha:** 2026-07-07
> **Base:** Hallazgos de `docs/MEGA_AUDIT.md` + exploración de codebase
> **Objetivo:** Cerrar las 9 deudas técnicas restantes y elevar la calidad del repo a estándar production-ready

---

## 📊 Sprint Overview

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Tests | 80 | **100+** |
| Coverage de módulos core | ~65% | **≥90%** |
| CI/CD | ❌ None | ✅ GitHub Actions |
| Type stubs | ❌ None | ✅ API pública |
| Contract mismatches | 2 conocidos | **0** |
| Scripts frágiles (.bat) | 4 | **0** (migrados a PS1) |

**Duración estimada:** 6 fases, ejecutables en secuencia o paralelo donde se indique.

---

## Phase 1 — Contract Mismatches (CRÍTICO)

> **Bloqueante:** Estos bugs causan errores silenciosos en pipeline real.
> **Paralelizable:** Sí (1A y 1B son independientes)

### Task 1A: Unificar contract CRS `synthetic.py` ↔ `geometry_speed.py`

**Problema:**
- `synthetic.py:40` emite `coordinate_system="local_cartesian_m"` + `crs=None`
- `geometry_speed.py:181` exige `crs` no-None para ciertas operaciones
- Resultado: datos sintéticos pasan por synthetic pipeline pero fallan al entrar al estimator de geometría

**Archivos afectados:**
- `wildfire_front/synthetic.py`
- `wildfire_front/geometry_speed.py`
- `wildfire_front/models.py` (FrontObservation / ScenarioConfig)

**Acciones:**
1. Definir contract único: CRS opcional para synthetic, estimator debe manejar `crs=None` gracefully
2. En `geometry_speed.py:181`, añadir guard: si `crs is None`, asumir local cartesian y skip reprojection
3. Documentar el contract en docstring de `FrontObservation`
4. Añadir test cross-module: synthetic → geometry_speed end-to-end

**Criterio de aceptación:**
- [ ] `test_synthetic_to_geometry_pipeline()` pasa sin warnings de CRS
- [ ] `crs=None` no causa crash en `geometry_speed.py`
- [ ] Docstring de `FrontObservation` documenta el contract

---

### Task 1B: Eliminar `num_radial_samples` phantom de `reconstruction.py`

**Problema:**
- `reconstruction.py:63`: `num_samples = getattr(config, "num_radial_samples", 36)`
- `ScenarioConfig` NO tiene campo `num_radial_samples`
- Funciona por el fallback `36`, pero es código muerto/confuso

**Archivos afectados:**
- `wildfire_front/reconstruction.py`
- `wildfire_front/models.py`

**Acciones:**
1. **Opción A (preferida):** Añadir `num_radial_samples: int = 36` a `ScenarioConfig`
2. Reemplazar `getattr(config, ...)` por acceso directo `config.num_radial_samples`
3. Añadir test que verifique el campo existe y se respeta

**Criterio de aceptación:**
- [ ] `ScenarioConfig` tiene `num_radial_samples` con default `36`
- [ ] `reconstruction.py` usa acceso directo (no `getattr`)
- [ ] `test_reconstruction_custom_radial_samples()` pasa

---

## Phase 2 — Package & Imports Hardening

> **Paralelizable:** Sí (2A, 2B, 2C independientes)

### Task 2A: Añadir `models/__init__.py` explícito

**Problema:** El directorio `models/` funciona como PEP 420 namespace package pero es frágil — si algún tooling o editor no lo detecta, los imports fallan.

**Acciones:**
1. Crear `models/__init__.py` con exports de las clases públicas (`A3C_PerCellModel_LSTM`, etc.)
2. Actualizar `pyproject.toml` si es necesario
3. Verificar que `from models import A3C_PerCellModel_LSTM` funciona

**Archivos afectados:** `models/__init__.py` (nuevo)

---

### Task 2B: Añadir type stubs (`.pyi`) para API pública

**Problema:** No existen type stubs. IDEs y type checkers no pueden validar el uso de la API pública.

**Acciones:**
1. Crear `wildfire_front/py.typed` (marker PEP 561)
2. Crear stubs para:
   - `wildfire_front/models.pyi` — dataclasses públicas
   - `wildfire_front/geometry_speed.pyi` — `GeometrySpeedEstimator`, `GeometrySpeedConfig`, `GeometrySpeedResult`
   - `wildfire_front/reconstruction.pyi`
   - `wildfire_front/cli.pyi`
3. Ejecutar `mypy wildfire_front/` y fix warnings críticos

**Archivos afectados:** 4 archivos `.pyi` + `py.typed` (nuevos)

---

### Task 2C: Revisar entry points de `pyproject.toml`

**Acciones:**
1. Verificar que `[project.scripts]` declara todos los CLIs esperados
2. Añadir `wildfire-front` como entry point si no existe
3. Test: `pip install -e . && wildfire-front --help`

**Archivos afectados:** `pyproject.toml`

---

## Phase 3 — CI/CD Pipeline

> **Dependencia:** Ninguna (puede empezar en paralelo con Phase 1-2)

### Task 3A: GitHub Actions workflow

**Acciones:**
1. Crear `.github/workflows/tests.yml`:
   - Matrix: Python 3.10, 3.11, 3.12
   - OS: ubuntu-latest, windows-latest
   - Steps: checkout → setup-python → pip install -e .[dev] → pytest
   - Cache de pip
2. Añadir badge de status al `README.md`
3. Añadir step de coverage con `codecov` upload

**Archivos afectados:**
- `.github/workflows/tests.yml` (nuevo)
- `README.md` (badge)

---

### Task 3B: Quality gates en CI

**Acciones:**
1. En el mismo workflow, añadir jobs separados:
   - `lint`: `ruff check wildfire_front/`
   - `typecheck`: `mypy wildfire_front/`
   - `coverage`: `pytest --cov=wildfire_front --cov-report=xml`
2. Configurar `ruff` en `pyproject.toml` si no está
3. Fail-fast: el PR no se mergea si alguno falla

**Archivos afectados:** `.github/workflows/tests.yml`, `pyproject.toml`

---

## Phase 4 — Test Coverage Gap Closure

> **Dependencia:** Phase 1 debe estar completo (para testear los contracts unificados)

### Task 4A: Tests para módulos sin cobertura

**Módulos sin tests dedicados:**
| Módulo | Funciones a testear | Tests nuevos |
|--------|---------------------|--------------|
| `outputs.py` | `save_results()`, `save_manifest()`, formatos de salida | 3-4 |
| `weights.py` | `load_weights()`, `save_weights()`, paths/paths | 2-3 |
| `identity.py` | `sha256_of_file()`, determinismo, edge cases | 2-3 |
| `reconstruction.py` | `reconstruct_arrival_grid()`, `reconstruct_arrival_from_components()` | 3-4 |
| `synthetic.py` | generadores de escenarios, propiedades estadísticas | 2-3 |

**Acciones:**
1. Crear `tests/test_outputs.py`
2. Crear `tests/test_weights.py`
3. Expandir `tests/test_identity.py` (actualmente 1 test → 3-4)
4. Expandir `tests/test_pipeline.py` con tests de reconstruction
5. Crear `tests/test_synthetic_properties.py`

**Objetivo:** +15-20 tests nuevos, coverage de módulos core ≥90%

---

### Task 4B: Tests de integración end-to-end

**Acciones:**
1. `tests/test_e2e_synthetic_pipeline.py`:
   - Generar escenario sintético → reconstruction → geometry_speed → outputs
   - Verificar que todo el flujo funciona sin crashes
2. `tests/test_e2e_meta_labeler.py`:
   - Train primary model → generate predictions → train meta-labeler → predict trustworthiness

**Objetivo:** 2 test files nuevos, 4-6 tests cada uno

---

## Phase 5 — Scripts & Tooling Cleanup

> **Paralelizable:** Sí

### Task 5A: Migrar scripts `.bat` frágiles a PowerShell

**Scripts a migrar:**
- `scripts/run_mega_sprint.bat` (usa `timeout` y `start /b`)
- `scripts/run_mega_training_local.bat`
- Otros `.bat` que usen patrones frágiles

**Acciones:**
1. Crear equivalentes `.ps1` con:
   - Manejo de errores con `$ErrorActionPreference = "Stop"`
   - Logging estructurado
   - `try/catch` blocks
2. Mantener `.bat` como thin wrappers que llaman al `.ps1` (backward compat)
3. Documentar en `scripts/README.md`

**Archivos afectados:** `scripts/*.ps1` (nuevos), `scripts/*.bat` (simplificados)

---

### Task 5B: Organizar `fotosPrueba/`

**Problema:** 6 JPGs sin metadata ni README.

**Acciones:**
1. Mover a `data/reference_photos/`
2. Crear `data/reference_photos/README.md` documentando:
   - Origen de cada foto
   - Fecha de captura
   - Contexto (fuego real vs test)
3. (Opcional) Añadir `manifest.json` con metadata estructurada

**Archivos afectados:** `data/reference_photos/` (nuevo), `data/reference_photos/README.md`

---

## Phase 6 — Documentation & DX

> **Dependencia:** Todas las fases anteriores completas

### Task 6A: Actualizar `README.md` principal

**Acciones:**
1. Añadir sección "Quick Start" con ejemplo copy-pasteable
2. Añadir badges: CI status, coverage, Python versions
3. Añadir diagrama de arquitectura (ASCII o mermaid)
4. Enlazar a `docs/REPO_ANALYSIS.md` y `docs/MEGA_AUDIT.md`

---

### Task 6B: Añadir `CONTRIBUTING.md`

**Acciones:**
1. Guías de setup de dev (`pip install -e .[dev]`)
2. Cómo correr tests (`pytest`, `mypy`, `ruff`)
3. Convenciones de commit (Conventional Commits)
4. Cómo añadir nuevos tests
5. Cómo reportar bugs

---

## 🗓️ Cronograma Sugerido

```
Sprint 1 (Fase 1 + 2A):  Contract mismatches + models/__init__.py
Sprint 2 (Fase 3):        CI/CD pipeline
Sprint 3 (Fase 4):        Test coverage
Sprint 4 (Fase 2B + 2C):  Type stubs + entry points
Sprint 5 (Fase 5):        Scripts cleanup
Sprint 6 (Fase 6):        Documentation
```

Cada sprint termina con: **tests verdes + PR mergeable**.

---

## ✅ Definition of Done (todo el mega sprint)

- [ ] 100+ tests pasando en CI (Python 3.10/3.11/3.12, Ubuntu + Windows)
- [ ] `mypy wildfire_front/` sin errores críticos
- [ ] `ruff check wildfire_front/` limpio
- [ ] Coverage de módulos core ≥90%
- [ ] 0 contract mismatches
- [ ] CI/CD verde con badges en README
- [ ] Type stubs para API pública
- [ ] `CONTRIBUTING.md` publicado
- [ ] `fotosPrueba/` reorganizado con metadata

---

## ⚠️ Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Type stubs revelan bugs ocultos | Media | Medio | Fix incremental, no bloquear sprint |
| CI falla en Windows por paths | Alta | Bajo | Usar `pathlib.Path` en todos los tests |
| Migración de .bat rompe workflows existentes | Baja | Medio | Mantener wrappers .bat |
| Tests de integration son lentos | Media | Bajo | Marcar con `@pytest.mark.slow` |

---

## 🤖 ML SPRINT — Mejora del Modelo (POST-EVALUACIÓN 2026-07-09)

> **Trigger:** Resultados de `docs/ML_BASELINE_METRICS.md` muestran déficits críticos
> **Base:** Evaluación con 18 patches semireal → IoU 0.22, Recall 0.24, Precision 0.68

### Diagnóstico ML (Sprint 0 — COMPLETADO)

| Métrica | Valor Baseline | Objetivo | Diagnóstico |
|---------|---------------|----------|-------------|
| IoU (mean) | **0.2183** | ≥0.50 | 🔴 Crítico — modelo no captura bien el frente |
| IoU (micro) | 0.3378 | ≥0.55 | 🟡 Pooled algo mejor pero insuficiente |
| Dice/F1 (mean) | 0.3253 | ≥0.60 | 🔴 Bajo |
| Precision | **0.6759** | ≥0.70 | 🟡 Aceptable — pocas falsas alarmas |
| Recall | **0.2384** | ≥0.60 | 🔴 **Crítico** — se pierde 76% de fuegos reales |
| Specificity | ~0.95 | ≥0.90 | ✅ Bien — clasifica no-fuego correctamente |

**Conclusión:** El modelo es excesivamente conservador. Predice muy pocas celdas
como "fuego" y por eso pierde la mayoría de las igniciones reales (bajo recall).
La precision es decente porque cuando predice fuego, suele acertar.

**Artefactos creados en Sprint 0:**
- ✅ `wildfire_front/evaluation.py` — métricas segmentación + propagación
- ✅ `scripts/evaluate_current_model.py` — evaluación reproducible
- ✅ `scripts/package_real_data_for_kaggle.py` — empaquetar datos reales
- ✅ `docs/ML_BASELINE_METRICS.md` — reporte baseline

---

### ML-Sprint 1: Data Pipeline de Incendios Reales (ALTA PRIORIDAD)

> **Objetivo:** Convertir los 7 incendios reales (2,353 archivos) en patches
> entrenables compatibles con el modelo A3C-LSTM.

**Datos disponibles:**

| Incendio | Fotos | KMZ/KML | Total |
|----------|-------|---------|-------|
| RETUERTA | ~80 | ~26 | 106 |
| BRAZATORTAS | ~105 | ~34 | 139 |
| POLAN | ~67 | ~22 | 89 |
| CARDOSO (2 sesiones) | ~660 | ~213 | 873 |
| HELLIN | ~145 | ~112 | 415 |
| LA_ESTRELLA_ACOM2 | ~300 | ~175 | 475 |
| TOBARRA | ~60+ | ~30+ | ~100+ |

**Acciones:**

1. **Pipeline KMZ → GeoTIFF masks** (`scripts/kmz_to_geotiff_masks.py`):
   - Parsear KMZ → extraer polígonos de perímetro
   - Rasterizar a GeoTIFF con CRS consistente (EPSG:25830 para Albacete)
   - Generar máscaras binarias por timestamp

2. **Pipeline GeoTIFF → Patches 30×30** (`scripts/geotiff_to_patches.py`):
   - Recortar imágenes infrared/EO a grilla de 30×30 celdas
   - Construir secuencias temporales (3 frames por sample)
   - Generar 16 canales de entrada (NDWI, elevación, pendiente, etc.)

3. **Subida a Kaggle**:
   - Ejecutar `python scripts/package_real_data_for_kaggle.py`
   - Subir como Kaggle Dataset versionado
   - Configurar kernel para leer de ahí

4. **Augmentation**: flip horizontal/vertical, rotación 90°, variación temporal

**Criterio de aceptación:**
- [ ] ≥500 patches de datos reales listos para entrenamiento
- [ ] Manifest CSV con provenance (incendio, timestamp, coords)
- [ ] Subido a Kaggle y accesible desde kernel

---

### ML-Sprint 2: Reward Shaping & Fine-Tuning (CRÍTICO PARA RECALL) — ✅ COMPLETADO

> **Objetivo:** Corregir el bajo recall (0.24 → ≥0.60) mediante ajuste del
> reward y re-entrenamiento.
> **Estado:** Implementación de código completada (2026-07-09). Pendiente: lanzar
> mega-entrenamiento en Kaggle para validar métricas reales.

**Acciones implementadas:**

1. **Focal Loss + pos_weight** en `wildfire_front/ml/train.py`:
   - ✅ Focal loss con `gamma=2.0` que down-weighta ejemplos fáciles
   - ✅ `pos_weight=3.0` que penaliza false negatives 3× más que false positives
   - ✅ Spread-direction bonus (soft IoU) que recompensa capturar propagación correcta
   - ✅ Tests unitarios verifican que FN > FP loss y que gamma=0 reduce a BCE ponderado

2. **Smart initialization de capas v2** en `wildfire_front/ml/weights.py`:
   - ✅ `fusion_gate`: bias inicializado a -4.0 → sigmoid≈0 → passthrough espacial
   - ✅ `refine`: conv inicializada como identidad (kernel center=1) → no-op inicial
   - ✅ `temporal_projection`: Xavier con gain=0.1 → ruido temporal mínimo inicial
   - ✅ Test verifica que refine es near-identity y gate bias < -3.0

3. **Learning rate warmup + cosine decay** en `kaggle_job/run_mega_training.py`:
   - ✅ 2 epochs de warmup lineal (start_factor=0.1)
   - ✅ Cosine decay sobre 13 epochs restantes hasta lr_min=1e-6
   - ✅ Epochs aumentados de 12 → 15 para aprovechar focal loss

**Acciones pendientes (futuras iteraciones):**

4. **Curriculum learning** (ML-Sprint 2b):
   - Fase 1 (5 epochs): synthetic puro — aprender dinámica básica
   - Fase 2 (5 epochs): mixto 50/50 synthetic + real
   - Fase 3 (5 epochs): real puro — adaptación a dominio real

5. **Entropy bonus tuning** (ML-Sprint 2b):
   - Aumentar entropy coefficient de 0.01 → 0.05 para forzar más exploración

**Criterio de aceptación:**
- [x] Código de Focal Loss + pos_weight implementado y testeado
- [x] Smart init de capas v2 implementado y testeado
- [x] LR warmup + cosine decay configurado en mega training
- [x] 83/83 tests pasando (3 tests nuevos añadidos)
- [ ] Recall ≥ 0.50 en datos semireal (requiere lanzar Kaggle)
- [ ] IoU ≥ 0.35 (requiere lanzar Kaggle)

---

### ML-Sprint 3: Arquitectura — Attention + Multi-Scale (MEDIANA PRIORIDAD)

> **Objetivo:** Mejorar captura de patrones espaciales multi-escala del fuego.

**Acciones:**

1. **Spatial attention module** en `models/model.py`:
   - Añadir bloque self-attention después del CNN encoder
   - Permite al modelo enfocar en bordes del frente

2. **Multi-scale feature pyramid**:
   - FPN-style con skips a múltiples resoluciones
   - Captura tanto fuegos pequeños (1-2 celdas) como grandes frentes

3. **Temporal attention en LSTM**:
   - Attention sobre los 3 timesteps de la secuencia
   - Ponderar frames más recientes con más peso

**Criterio de aceptación:**
- [ ] Nuevo modelo supera baseline en IoU por ≥5 puntos
- [ ] Misma latencia de inferencia (<50ms/patch en CPU)

---

### ML-Sprint 4: Meteodatos y Physics-Informed Loss (BAJA PRIORIDAD)

> **Objetivo:** Integrar datos meteorológicos como canales adicionales y
> añadir restricciones físicas al loss.

**Acciones:**

1. **Canales de meteorología** (de AEMET/OpenMeteo):
   - Velocidad y dirección del viento (2 canales)
   - Temperatura y humedad relativa
   - Esto eleva in_channels de 16 → 20

2. **Physics-informed loss term**:
   - Penalizar predicciones que violen la ecuación de propagación de Rothermel
   - vmax = f(fuel, wind, slope) → restricción de velocidad máxima

3. **Topografía** (de MDT5 de IGN):
   - Pendiente y orientación (ya parcialmente en canal 14-15)

**Criterio de aceptación:**
- [ ] Modelo con 20 canales entrena sin errores de dimensionalidad
- [ ] Physics loss mejora velocidad de propagación predicha vs observada

---

## 📋 Orden de Ejecución Recomendado (ACTUALIZADO)

```
 Prioridad ALTA (impacta ML directamente):
 1. ML-Sprint 1  (data pipeline reales)    ← desbloquea entrenamiento real
 2. ML-Sprint 2  (reward + fine-tuning)    ← corrige recall crítico
 3. Phase 1A     (CRS contract)            ← bloqueante para pipeline real

 Prioridad MEDIA (calidad e infraestructura):
 4. Phase 3A     (CI básico)               ← feedback loop para todo
 5. Phase 2A     (models/__init__)         ← rápido
 6. Phase 4A     (tests gap)               ← aprovechar CI
 7. ML-Sprint 3  (attention multi-scale)   ← mejora incremental

 Prioridad BAJA (pulido):
 8. Phase 2B     (type stubs)              ← con tests de respaldo
 9. ML-Sprint 4  (meteo + physics loss)    ← enrichment
10. Phase 5A     (scripts cleanup)         ← no bloqueante
11. Phase 6      (docs)                    ← al final
