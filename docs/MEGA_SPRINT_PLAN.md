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

## 📋 Orden de Ejecución Recomendado

```
1. Phase 1A (CRS contract)     ← bloqueante, hace primero
2. Phase 1B (radial samples)   ← rápido, junto con 1A
3. Phase 2A (models/__init__)  ← rápido
4. Phase 3A (CI básico)        ← para tener feedback loop
5. Phase 4A (tests gap)        ← aprovechar CI
6. Phase 2B (type stubs)       ← con tests de respaldo
7. Phase 5A (scripts)          ← no bloqueante
8. Phase 6 (docs)              ← al final