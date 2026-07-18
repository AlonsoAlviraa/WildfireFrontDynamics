# Design / Audit: Auditoría exhaustiva del repositorio WildfireFrontDynamics

**Fecha:** 2026-07-18  
**Método:** loop-engineering (design-first) — exploración paralela de `wildfire_front/`, `scripts/`, `kaggle_job/`, `models/`, `tests/`, CI/Docker/docs  
**Alcance:** código, tests, CI, Docker, legacy, seguridad, honestidad de producto, drift documental  
**Estado de evidencia local:** pytest 2 FAIL / ~274 PASS; ruff CI-scope **167** errores; ruff format **35** ficheros; mypy **51** errores en 8 ficheros

---

## 1. Resumen ejecutivo

El repositorio tiene un **núcleo de producto serio y usable** (front geometry → ROS → Decision Card → incident runtime → ensemble CLM v34) superpuesto a una **capa sedimentaria legacy** (A3C-LSTM, dumps Kaggle, scripts de experimento, rutas a artefactos borrados en la limpieza de 2026-07).

### Veredicto

| Dimensión | Nota | Comentario |
|-----------|------|------------|
| Ops / geometría (ROS, ingest, incident) | **B+** | Código cuidadoso; tests sólidos en geo/ops |
| Producto decisión (card, policy, forensics) | **B-** | API útil; **claims de fiabilidad hard-coded** |
| ML producción (U-Net v21 + CLM ensemble) | **B** | Catalog + weights locales coherentes; CI smoke aún en A3C |
| ML legacy (A3C / fine-tune GeoTIFF) | **D** | FFMC doble-norm, physics sin denorm, tests rotos por `v3.pt` |
| Higiene repo / CI | **D** | ruff/mypy/format fallan; docs desactualizados |
| Seguridad | **C** | Sin secretos en árbol; pickle/torch.load/API sin auth |

**Conclusión:** no es un repo “roto de punta a punta”, pero **no es honesto en CI ni en claims de reliability**, y arrastra **legacy que contamina el mental model** de quien lo toca. La limpieza de dumps (CLEANUP_2026_07) no se propagó a tests, scripts ni ARCHITECTURE.

---

## 2. Superficie medida

| Área | Ficheros `.py` | ~LOC |
|------|----------------|------|
| `wildfire_front/` | 56 | ~13.3k |
| `scripts/` | 86 | ~14.9k |
| `tests/` | 40 módulos | ~4.7k |
| `kaggle_job/` (incl. archive) | 25 | ~6.9k |
| `models/` (NN) | 2 | ~0.7k |
| Tests `def test_*` | — | **276** funciones en 40 ficheros |

Ficheros más grandes (señal de God-object / deuda estructural):

| LOC aprox | Path |
|-----------|------|
| 42k B | `wildfire_front/cli.py` (~1050 líneas lógicas) |
| 38k B | `scripts/run_ml_loop_3way.py` |
| 34k B | `wildfire_front/incident/pipeline.py` |
| 29k B | `scripts/build_commander_app.py` |
| 28k B | `wildfire_front/ml/unet_train.py` |
| 28k B | `wildfire_front/ingestion/geotiff.py` |

---

## 3. Evidencia ejecutable (esta sesión)

### 3.1 Pytest

```
FAILED tests/test_ml_pipeline.py::MLPipelineTests::test_fine_tuning_execution_one_epoch
FAILED tests/test_ml_pipeline.py::MLPipelineTests::test_cloud_train_execution_one_epoch_without_upload
FileNotFoundError: models\v3.pt
```

Causa raíz: `docs/CLEANUP_2026_07.md` eliminó `models/v3.pt`; los tests A3C y `kaggle_job/run_training.py` siguen apuntando ahí. **Resto de la suite ~274 tests PASS.**

### 3.2 CI-equivalente local (mismas rutas que `.github/workflows/ci.yml`)

| Check | Resultado |
|-------|-----------|
| `ruff check wildfire_front tests scripts` | **167 errors** |
| `ruff format --check wildfire_front tests` | **35 files would reformat** |
| `mypy wildfire_front --ignore-missing-imports` | **51 errors / 8 files** |

**Implicación:** un push a `main` con CI actual debería fallar en el job `lint` (salvo que CI no se haya corrido en los 31 commits locales ahead of origin).

### 3.3 Pesos de producto vs git

- En disco: `models/production/*.pt`, `clm_specialist/*.pt`, `clm_ensemble/*.pt` **existen**.
- En git (`git ls-files models/`): solo manifests/JSON/código — **ningún `.pt` trackeado** (gitignore `*.pt`).
- CI sin bootstrap de pesos → `test_product_catalog` (assert paths exist) y smoke real **dependen del workspace del runner**, no del clone limpio.

### 3.4 Ruff global (incluye archive)

~**360** issues en `kaggle_job/archive` + resto; la mayoría del archive es ruido histórico.

---

## 4. Hallazgos por severidad

### CRITICAL

#### C1 — Decision Card: “system reliability” hard-coded PASS

**Archivo:** `wildfire_front/product/confidence.py` ~299–305

```python
sys_rep = system_reliability_report(
    gates_ok=True,
    determinism_ok=True,
    abstention_enforced=decision == Decision.ABSTAIN or conf >= 0.0,  # always True
    provenance_ok=True,
)
```

**Impacto:** toda tarjeta reporta fiabilidad de sistema “ok” y residual risk ~1e-6 aunque gates reales no se midan. **Mentira de producto** frente a operadores / scorecards de industrial readiness.

**Fix:** inyectar resultado de `scripts/reliability_gate.py` o marcar `gates_ok=None` / `unknown` y fallar a ABSTAIN en field_ops si no hay gate.

---

#### C2 — FFMC doble normalización en `WildfireDataset`

**Archivo:** `wildfire_front/ml/dataset.py` ~226–232

1. Escribe `ffmc_raw / 101` en canal 16.  
2. Llama `normalize_channels_inplace` que aplica `(x - 50) / 51` (`normalization.py` ch16).

**Resultado:** FFMC 85 → 0.84 → `(0.84-50)/51 ≈ -0.96` en vez de `(85-50)/51 ≈ 0.69`.

**Impacto:** fine-tune A3C / dataset GeoTIFF ve FFMC basura; física que asume 0–101 se rompe en cascada con C3.

**Fix:** escribir FFMC crudo 0–101; una sola pasada de normalize.

---

#### C3 — Physics loss legacy sin denormalizar wind/slope/FFMC

**Archivo:** `wildfire_front/ml/train.py` `calculate_local_spread_loss` ~141–148

La ruta vectorizada denormaliza; el bucle por celda (aún usado por `fine_tune_model` / `cloud_train`) pasa valores ya normalizados a `physics_loss_cell` como si fueran m/s y radianes.

**Impacto:** Rothermel penalty numéricamente absurdo en el path de fine-tune legacy.

---

#### C4 — Tests ML rotos + `models/v3.pt` fantasma

- Tests: `test_ml_pipeline` carga `models/v3.pt` → FAIL.
- `kaggle_job/run_training.py` hardcodea `--weights models/v3.pt`.
- Cleanup documentó el borrado; **código no migró**.

---

#### C5 — Docker runtime incompleto

**Archivo:** `Dockerfile`

```dockerfile
pip wheel . --no-deps -w /wheels && \
pip wheel numpy rasterio affine -w /wheels
...
pip install --no-index --find-links=/wheels wildfire-front-dynamics
```

Faltan wheels de **`shapely` y `pyproj`** (deps de `pyproject.toml`). Install con `--no-index` no puede resolverlas. **No hay job CI de `docker build`.**

---

#### C6 — Metadata Kaggle raíz apunta a script archivado

**Archivo:** `kaggle_job/kernel-metadata.json`

- `code_file: run_unet_training_v20.py` (solo existe en `kaggle_job/archive/`)
- Canonical: `kernel-metadata-v21.json` → `run_unet_training_v21.py`

Riesgo: `kaggle kernels push` accidental falla o usa layout obsoleto.

---

### HIGH

#### H1 — Coreg “mask IoU” no rellena el bbox

**Archivo:** `wildfire_front/front_dynamics.py` `_rasterize_main` ~116–119

```python
grid[r0:r1, c0:c1] = np.maximum(grid[r0:r1, c0:c1], 0)  # no-op
```

Solo stamps de vértices + vecindario del centroide. Comentarios hablan de soft bbox fill / IoU estructural.

**Impacto:** coregistration shifts engañosos → ROS sesgado.

---

#### H2 — `apply_weighted_loss` ignora `pos_weight` de config

**Archivo:** `wildfire_front/ml/unet_train.py` ~119–120

`pw = torch.tensor(5.0, ...)` hard-coded. Rompe aislamiento de variables de `RULES.md` para experimentos `changed_weighted`.

---

#### H3 — GeoTIFF patches: crop top-left sin realineación CRS

**Archivo:** `wildfire_front/ml/dataset.py` — `height/width = min` y crop sin reproject.

Frames de dron con footprints distintos → secuencias espacialmente incoherentes.

---

#### H4 — Decide HTTP API sin auth / path resolution abierta

**Archivos:** `product/api_server.py`, `product/decide_service.py`

- Sin autenticación, sin cap de body más allá de Content-Length.
- `work_dir` / `open_pack` resuelven cualquier path legible por el proceso.
- Default bind 127.0.0.1 (bien); riesgo si se expone a 0.0.0.0.

---

#### H5 — `torch.load` inseguro / inconsistente

- `ml/weights.py`: `weights_only=False`
- `ml/unet_train.py`: load sin `weights_only`
- `ml/meta_labeler.py`: **`pickle.load` completo** (RCE si el `.pkl` no es de confianza)

---

#### H6 — Scripts de “análisis” con fallback sintético silencioso

| Script | Comportamiento |
|--------|----------------|
| `scripts/reeval_cross_protocol.py` | Sin data → NPZ aleatorios; métricas plausibles en ruido |
| `scripts/analyze_leakage_and_shap.py` | Sin data → fires sintéticos sin seed; “SHAP/leakage” fake |

**Fix:** fallar hard en modo real; smoke debe marcar `"synthetic": true` y no escribir a scorecards de producción.

---

#### H7 — ARCHITECTURE.md y reglas desactualizados

| Claim | Realidad |
|-------|----------|
| `run_mega_training.py` / `run_unet_training_v13.py` en raíz kaggle | Solo en `archive/` |
| “38 tests” | **276** funciones / 40 ficheros |
| U-Net “Pending v13b” | Producto **v21 + CLM v34** |
| Diagrama sin incident/product/open_if | Producto dual ya shipped |
| `RULES.md` → `MEMORY.md` | **No existe** MEMORY.md |
| CI smoke → A3C | Producto es Residual U-Net |

---

#### H8 — Paths a dumps borrados

Defaults rotos en: `evaluate_current_model.py`, `install_production_weights.py`, `analyze_training_curves.py`, `reeval_cross_protocol.py`, `experiment_queue.json` (scripts en archive sin prefijo `archive/`), `monitor_job.bat` (path absoluto Windows + slug viejo).

---

#### H9 — Paths absolutos de máquina local embebidos

- `scripts/build_commander_app.py`, `build_portal.py`, `show_all.py`
- `kaggle_job/monitor_job.bat`
- Snapshots JSON en `docs/DEMO_*` con `C:\Users\Mariano\...`

---

#### H10 — Tests opcionales con `return` silencioso

`test_open_if_pack`, stream Tobarra, holdouts reales: si no hay artefactos (gitignore), **pasan sin validar nada**. CI verde ≠ producto validado.

---

### MEDIUM

| ID | Hallazgo |
|----|----------|
| M1 | Bearing dominante: indexación sospechosa `top[:len(bearings)]` en `scientific_ops.py` |
| M2 | `physics_loss()` ignora prediction/fire mask (API muerta / engañosa) |
| M3 | Augment flips sin rotar wind_dir/aspect |
| M4 | `reconstruction.estimate_observed_speeds` asume origen (0,0) — inútil en UTM |
| M5 | Meta-labeler “spatial features” son globales (mean/std del grid) |
| M6 | Sector ROS por cuartiles, no por bearing real (parcialmente documentado) |
| M7 | Amplio `except Exception: pass` en pack builders, front_dynamics enrich, real_if geotiff |
| M8 | PID lock Windows (`os.kill`) imperfecto; race en steal |
| M9 | `sys.path.insert` en ~55 scripts (no package-install-only) |
| M10 | Duplicación: IoU, speed stats, decision loaders, channel stats (normalization vs feature_schema) |
| M11 | God files: `cli.py`, `incident/pipeline.py`, `run_ml_loop_3way.py` |
| M12 | NaN loss → 0 con grad en train legacy (oculta fallos) |
| M13 | `SECURITY.md` email `security@example.org`; CodeQL reclamado pero no hay workflow |
| M14 | package.json solo `docx`; lockfile gitignored |
| M15 | Makefile lint ≠ CI (scripts solo en CI); Unix `rm` en Windows |
| M16 | Version sprawl: package 0.1.0 vs product v21/v34 |
| M17 | Augment/dataset sin seed en training salvo `deterministic=True` (default False) |
| M18 | `torch.jit.trace` deprecado (warnings en tests) |
| M19 | CI ML smoke valida A3C, no ensemble v34 |
| M20 | Cobertura medida, sin `--cov-fail-under` |

### LOW / NIT

- Imports sin usar / UP017 datetime.UTC / trailing newlines (ruff bulk).
- Docstrings 16ch vs código 17ch en `models/model.py`.
- `geo_crs` zona UTM 30 hard-coded (España).
- PR template “96 tests” vs realidad 276.
- `.gitignore` duplicado en bloques cleanup.
- Emojis en ARCHITECTURE vs RULES “no emojis in Python”.
- `hypothesis` en dev deps casi sin uso real en tests.
- Colisión de nombres: paquete `models` (NN) vs `wildfire_front.models` (dataclasses).

---

## 5. Inventario LEGACY (acción recomendada)

### Eliminar o mover YA a archive

| Path | Motivo |
|------|--------|
| `kaggle_job/run_training.py` | A3C + `v3.pt` muerto |
| `kaggle_job/kernel-metadata.json` | Apunta a v20 archivado; o reescribir = v21 |
| `kaggle_job/monitor_job.bat` | Path absoluto + slug obsoleto |
| `scripts/evaluate_current_model.py` | A3C + kaggle_output |
| `scripts/compare_base_vs_finetuned.py` | A3C |
| `scripts/analyze_training_curves.py` | dumps v10/v11 |
| `scripts/analyze_leakage_and_shap.py` | sintético silencioso |
| `scripts/eval_kaggle_v27*.py` | experimento G1 cerrado |
| `scripts/finalize_observatorio_v2.py`, `v3.py` | superados por v4/v5 |
| `scripts/_count_artifacts.py`, `_fix_la_estrella_acom2_masks.py` | one-offs |
| `scripts/experiment_queue*.json` | paths a archive incorrectos |

### Marcar LEGACY / no usar en producto (mantener por reproducibilidad)

| Path | Nota |
|------|------|
| `models/model.py` | A3C-LSTM |
| `models/config.json` | hiperparams A3C |
| `wildfire_front/ml/train.py` (fine_tune A3C) | hasta reescritura o delete |
| `wildfire_front/ml/cloud_train.py` | HF + A3C |
| `wildfire_front/ml/weights.py` | remap A3C |
| `wildfire_front/ml/meta_labeler.py` | no en decide path; pickle |
| `wildfire_front/cn_cellular_ca.py` | research demo |
| `kaggle_job/archive/**` | OK archivado |
| `docs/archive/**` | OK archivado |

### Source of truth de producto (NO tocar a la ligera)

- `models/catalog.json` + `production/` + `clm_specialist/` + `clm_ensemble/`
- `wildfire_front/front_dynamics.py`, `geometry_speed.py`, `ingestion/`, `incident/`, `product/`
- `wildfire_front/ml/unet_train.py`, `spread_predictor.py`, `ndws_metrics.py`
- `kaggle_job/run_unet_training_v21.py`, `preprocess_ndws.py`, `kaggle_common.py`

---

## 6. Mapa de duplicación

| Preocupación | Ubicaciones |
|--------------|-------------|
| IoU/F1 | `evaluation.py` ↔ `ndws_metrics.py` |
| Speed stats | `geometry_speed` ↔ `scientific_ops` ↔ `front_dynamics` |
| Decision metrics load | `decide_service` ↔ `incident/pipeline` |
| Channel stats | `normalization._CHANNEL_STATS` ↔ `feature_schema.LEGACY17_*` |
| Physics loss | 3 APIs, 2 políticas de denorm |
| Mask find | `ingestion` ↔ `incident` ↔ dataset |
| Kaggle bootstrap | `run_unet_training_v21` ↔ `kaggle_common` ↔ archive copies |
| Observatorio finalize | v2 → v3 → v4 |

---

## 7. Gaps de tests (críticos)

| Path | Gap |
|------|-----|
| reliability hard-code | Ningún test que falle si gates son siempre True |
| FFMC double-norm | Sin assert ch16 post-normalize |
| pos_weight config | Sin assert en weighted loss |
| coreg fill | Sin recovery de shift conocido con máscara llena |
| normalization.py | **Cero tests** |
| metrics_protocol.py | **Cero tests** |
| cross_protocol_eval.py | **Cero tests** |
| outputs.py | **Cero tests** |
| decide golden matrix policy×inputs | Parcial / enums amplios |
| Docker / industrial smoke | No en CI |
| Windows lock race | Débil |

---

## 8. PR Plan de remediación (DAG)

Orden recomendado. Cada PR debe dejar CI verde en su scope.

### PR-1 — Stop the bleeding (tests + CI honesty) `[P0]`

**Deps:** ninguna  
**Incluye:**
1. Arreglar o skip-with-reason tests A3C: fixture de pesos mínimos generados en `tmp_path` **o** `@pytest.mark.skip(reason="v3.pt removed; A3C legacy")`.
2. `ruff format` + `ruff check --fix` en `wildfire_front tests scripts`.
3. Corregir errores mypy bloqueantes (cli_report, forensics, emergency_products, scientific_ops, clm_eval, pipeline redef, spread_predictor).
4. `pytest.skip(...)` en lugar de `return` silencioso.

**DoD:** `ruff check/format` y `mypy wildfire_front` y `pytest tests/` verdes en clone limpio (salvo markers requires_weights).

### PR-2 — Product honesty: reliability + decide API `[P0]`

**Deps:** PR-1  
**Incluye:** C1 (no hard-code gates); H4 path allowlist; tests adversariales de reliability.

### PR-3 — ML data correctness (FFMC, physics, pos_weight) `[P0]`

**Deps:** PR-1  
**Incluye:** C2, C3, H2; tests unitarios de canal 16 y denorm parity; opcional H3 documentar “requires reprojected inputs”.

### PR-4 — Legacy quarantine `[P1]`

**Deps:** PR-1  
**Incluye:** mover scripts/kaggle dead a `scripts/archive/` y `kaggle_job/archive/`; reescribir o borrar `kernel-metadata.json`; marcar `models/model.py` LEGACY en docstring + README pointer.

### PR-5 — ARCHITECTURE / RULES / MEMORY rewrite `[P1]`

**Deps:** PR-4 (o paralelo si solo docs)  
**Incluye:** diagrama dual-product (ops + ML v21/v34); borrar refs a mega/v13; test count real; quitar MEMORY.md o crearlo; alinear CONTRIBUTING y PR template.

### PR-6 — Docker + weights policy `[P1]`

**Deps:** PR-1  
**Incluye:** C5 wheels completas; job `docker build`; política de pesos (Git LFS / release assets / CI install script / mark tests `requires_weights`).

### PR-7 — Silent synthetic analysis hard-fail `[P1]`

**Deps:** PR-4  
**Incluye:** H6; `--smoke` etiqueta explícita; nunca sobrescribir scorecards de producto.

### PR-8 — Security harden `[P2]`

**Deps:** PR-2  
**Incluye:** meta_labeler sin pickle RCE (joblib+whitelist o JSON+sklearn export); `torch.load(weights_only=True)`; SECURITY contact real; CodeQL opcional.

### PR-9 — Structural split (god files) `[P2]`

**Deps:** PR-1  
**Incluye:** partir `cli.py` (incident/decide submodules), extraer coreg raster de `front_dynamics`, unificar loaders decide/incident.

### PR-10 — Coverage gate + CI product smoke `[P2]`

**Deps:** PR-1, PR-6  
**Incluye:** smoke U-Net/ensemble no solo A3C; `--cov-fail-under` inicial 55–65%; tests `normalization` + `metrics_protocol`.

---

## 9. Qué NO hacer

- No reentrenar modelos “para arreglar la auditoría”.
- No borrar `kaggle_job/archive` ni `docs/archive` sin inventario de reproducibilidad.
- No mezclar en un solo PR: ruff format + rewrite de physics + archive de 40 scripts.
- No hardcodear más paths `C:\Users\Mariano\...` en generadores de portal.

---

## 10. Criterios de aceptación globales (Definition of Done de la auditoría ejecutada)

1. `pytest tests/ -q` PASS en máquina limpia con markers claros para datos pesados.  
2. Jobs CI lint + test verdes.  
3. Decision Card no reporta `system_reliability_pass` sin evidencia.  
4. Ningún script “product” escribe métricas desde sintéticos sin flag.  
5. ARCHITECTURE describe v21/v34 + incident/product.  
6. Docker build del target `runtime` e `inference` funciona.  
7. Lista legacy archivada; defaults no apuntan a `kaggle_output/` ni `v3.pt`.

---

## 11. Anexos de evidencia rápida

### A. Fallo confirmado v3.pt

```
FileNotFoundError: models\v3.pt
  wildfire_front/ml/weights.py:103 torch.load(...)
  tests/test_ml_pipeline.py fine_tune + cloud_train
```

### B. Pesos trackeados

```
git ls-files models/  → solo *.json, model.py, unet_model.py
*.pt gitignored y presentes solo en working tree local
```

### C. Mypy hotspots

`cli_report.py`, `product/forensics.py`, `emergency_products.py`, `scientific_ops.py`, `front_dynamics.py` (unused ignores), `incident/pipeline.py` (redef summary), `ml/clm_eval.py`, `ml/spread_predictor.py`.

### D. Ruff top categories (CI scope)

UP017 (datetime.UTC), F401 unused imports, I001 import order, F841 unused vars, UP035 typing imports, W292 EOF, E402 script path hacks, B023 loop var in nested def (firms — note: nested def capturing xs/ys is intentional pattern but ruff flags B023 in other sites).

---

## 12. Siguiente paso (loop-engineering)

Esta auditoría **es el design doc**. Ejecución:

```
/execute-plan docs/design/REPO_CODE_AUDIT_2026_07.md
```

o incremental:

```
/implement --effort 3 "PR-1 Stop the bleeding: fix v3.pt tests, ruff, mypy, silent skips"
```

Tras cada PR: `/check-work`.

---

*Auditoría generada 2026-07-18. Hallazgos verificados con lectura de código + pytest + ruff + mypy + git ls-files + 3 agentes explore en paralelo.*
