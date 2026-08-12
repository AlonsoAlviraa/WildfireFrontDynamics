# Code health modernize pass — 2026-08-10

Engineering modernization only (typing, imports, ruff/pyupgrade idioms, test style, package surface).
**No ML retraining**, no scorecard threshold changes, no scientific semantics changes.

Scope: `wildfire_front/`, `tests/`, active `scripts/`, plus active package `models/` (setuptools include).
`kaggle_job/` inventory-only except noted; `*/archive/*` frozen.

---

## A. Inventory baseline (session start / post prior wave)

### Toolchain / environment

| Item | Value |
|------|--------|
| Python | 3.11.9 |
| ruff | 0.15.20 |
| pytest | 8.4.2 |
| `requires-python` | `>=3.11` (`pyproject.toml`) |
| ruff `target-version` | `py311` |
| Coverage gate | `fail_under = 60` (`tool.coverage.report`) |
| Dev extras | `pytest>=7`, `hypothesis>=6`, `ruff>=0.4`, `mypy>=1.10` |

### Dependencies (`pyproject.toml`)

| Group | Pins |
|-------|------|
| Core | `numpy>=2.0`, `rasterio>=1.4`, `affine`, `shapely>=2.0`, `pyproj>=3.6` |
| `ml` | `torch>=2.0`, `scikit-learn>=1.3` |
| `cloud` | `tensorflow>=2.15` |
| `viz` | `matplotlib>=3.7`, `Pillow>=10.0` |
| `dev` | pytest / hypothesis / ruff / mypy (see above) |

Notes:

- Core already targets NumPy 2.x and modern geospatial stack.
- Torch AMP in package code already uses **`torch.amp.autocast("cuda", …)`** and **`torch.amp.GradScaler("cuda", …)`** (`wildfire_front/ml/unet_train.py`) — not the deprecated `torch.cuda.amp` import path.
- Meta-labeler already prefers joblib with path allowlisting (pickle-class risk documented in code).

### Ruff (inventory waves)

| Wave | `wildfire_front` + `tests` + `scripts` | `models/` | Notes |
|------|----------------------------------------|-----------|--------|
| Pre first modernize | **~278** | — | I001, UP035, UP017, F541, F401, SIM*, W291 |
| Mid residual | **58** | 6 (E731/C408/SIM102) | mostly SIM + models lambdas |
| **Post prior pass** | **0** | 6 open | package/scripts clean |
| **Post this pass** | **0** | **0** | models cleaned; tests re-linted |

Format: **387 files** under migrate targets + models (`ruff format --check` clean).

### Pytest collection

| Metric | Value |
|--------|--------|
| Test modules | **104** |
| Tests collected | **1077** |
| Collection | clean (`python -m pytest --collect-only`) |
| `python_classes` | `["Test*", "*Tests"]` (added this pass so `*Tests` classes still collect after leaving `unittest.TestCase`) |

### Deprecated / legacy pattern greps (active tree)

| Pattern | Active `wildfire_front` / `tests` / `scripts` / `models` | Notes |
|---------|----------------------------------------------------------|--------|
| `Optional[...]` / `Union[...]` | **0** | Already `X \| None` + `from __future__ import annotations` |
| `typing.List/Dict/Tuple` | **0** | builtins `list`/`dict`/`tuple` |
| `typing.Mapping` / `Sequence` / `Callable` | **0** as typing imports | `collections.abc` used where needed |
| `np.float` / `np.int` / `np.bool` (bare aliases) | **0** | only `np.floating` / `np.integer` isinstance checks (valid) |
| `distutils` / `pkg_resources` | **0** | — |
| `assertEquals` | **0** | — |
| `datetime.utcnow` / `utcfromtimestamp` | **0** | — |
| `datetime.timezone.utc` | **0** | migrated to `datetime.UTC` (prior wave) |
| `torch.cuda.amp` | **0** in package; only `kaggle_job/archive/*` | archive out of scope |
| Old sklearn `cross_validation` / `grid_search` | **0** | — |
| `np.random.seed` in package | **1** (`unet_train` deterministic block) | residual; prefer `default_rng` later (may change shuffle) |
| `unittest.TestCase` style tests | **0** modules | full plain-pytest; `test_ml_pipeline.py` uses fixtures + `pytest.mark.skipif` |

### High-complexity / high-NLOC modules (`wildfire_front`)

Heuristic branch-node count (If/For/While/Except/With/Assert/BoolOp/comprehension) — **module totals**:

| Branch nodes | Lines | Module |
|-------------:|------:|--------|
| 317 | 2143 | `cli_ml.py` |
| 279 | 1175 | `product/decide_service.py` |
| 230 | 1538 | `multihorizon_fieldops.py` |
| 207 | 1372 | `incident/pipeline.py` |
| 152 | 979 | `ml/lab_metrics_lift.py` |

Package-wide: **114** `.py` files, **~49.7k** lines. These mega-modules remain **refactor backlog** (behavior risk if split without pure-helper extraction).

Approximate McCabe-style top functions (from prior inventory; still valid):

| Est. CC | Function | Module |
|--------:|----------|--------|
| ~81 | `build_next_gate` | `ml/lab_next.py` |
| ~76 | `operational_files_to_ops_metrics` | `product/decide_service.py` |
| ~75 | `run_ml_predict` | `cli_ml.py` |
| ~70 | `main` | `cli.py` |
| ~68 | `print_incident_report` | `cli_report.py` |

### “Crops” interpretation

Two meanings used in this audit:

1. **Code-quality / coverage-style metrics** — ruff counts, format drift, pytest collection volume, complexity ranking, dep freshness (tables above). Coverage numeric run not re-baselined here; gate remains **60%** in `pyproject.toml`.
2. **Silent spatial crop / dataset alignment risk** — `wildfire_front/ml/dataset.py`:

| Mechanism | Default | Risk |
|-----------|---------|------|
| `allow_unaligned_crop` | **`False`** | Hard-fail on H/W span beyond `shape_align_tolerance_px` (default **0**) |
| Geotransform drift check | on when crop opt-in is off | Fail if affine components differ by `> 0.5 * px` |
| Common grid size | `height/width = min(...)` | When crop is **opt-in**, still top-left truncates to min H/W |
| Mask cache slice | `full[:height, :width]` | Same top-left convention |
| Training patch crop | intentional `[:, row:row+ps, col:col+ps]` | Not misalignment; normal patching |

**Residual dataset risk (documented, not changed):**

- Opt-in `allow_unaligned_crop=True` still **silently top-left crops** misaligned stacks (research-only; docstring already warns).
- DEM/NDVI/FSM loaders use `out_shape=(height, width)` resampling — different semantics from frame stack crop; alignment honesty depends on callers reprojecting first (`align_geotiff_stack`, spatial_v1 pipelines).
- No change to crop defaults or scorecards in this pass.

---

## B. Changes applied (this session + prior wave summary)

### Prior wave (already on tree at session start)

On `wildfire_front/`, `tests/`, `scripts/`:

- ruff UP/I/F/SIM/W clean (~278 → 0)
- `datetime.UTC`, `collections.abc`, `zip(..., strict=True)`, `contextlib.suppress`, format

### This session

#### 1. `models/` ruff hygiene (active package)

| File | Change |
|------|--------|
| `models/unet_model.py` | E731: lambda norm factories → nested `_make_norm`; C408: `dict(...)` → `{...}` literals |
| `models/model.py` | SIM102: nested neighbor-bound check → single `if` with `and` |

Semantics of U-Net norms and A3C neighbor labels unchanged.

#### 2. unittest → plain pytest style (mechanical)

Converted **all** former `unittest.TestCase` modules to plain pytest (`assert` / `pytest.raises` / `pytest.approx` / fixtures / `pytest.mark.skipif`), including:

- `test_data_validation_milestone.py`, `test_dataset_candidate_audit.py`
- `test_evaluation_quality.py`, `test_geometry_speed.py`
- `test_geotiff_ingestion.py`, `test_geotiff_to_patches.py`
- `test_identity.py`, `test_inventory_real_if_material.py`
- `test_meta_labeler.py`, `test_multihorizon_fieldops.py`
- `test_pipeline.py`, `test_prepare_real_if_geotiffs.py`
- `test_real_if_manifest.py`, `test_tobarra_multipass_s4.py`
- `test_ml_pipeline.py` (fixtures + `pytest.mark.skipif` for torch/sklearn)

**Collection fix:** after dropping `TestCase`, classes named `*Tests` (not `Test*`) were no longer collected by pytest defaults. Added to `pyproject.toml`:

```toml
python_classes = ["Test*", "*Tests"]
```

Restores **1077** collected tests.

**pytest.raises API:** `ctx.exception` → `ctx.value` (meta_labeler, geotiff_ingestion CLI exit).

**Operator-precedence fix:** `assert (out / "GAP.json").is_file()` in tobarramultipass (regex migration had dropped parens).

#### 3. Intentionally **not** changed

- Training hyperparameters, thresholds, scorecard gates, promote rails.
- Scientific formulas (Rothermel lite, envelope geometry, ROS caps).
- Dataset `allow_unaligned_crop` default or tolerance.
- Intentional late imports after `sys.path` bootstrap (`# noqa: E402` / per-file ignores).
- `kaggle_job/` bulk modernize (still has I001/F541/W292 outside archive).
- `np.random.seed(42)` in `unet_train.run_training` (deterministic train bootstrap; RNG modernization deferred as experiment-affecting).
- Complexity splits of mega-functions.

---

## C. Post-pass metrics

| Metric | Before first wave | After prior pass | **Close-out (harness resume)** |
|--------|-------------------|------------------|--------------------------------|
| Ruff (`wildfire_front`+`tests`+`scripts`+`models`) | ~278 | **0** | **0** (All checks passed) |
| Format (scope) | drift | 385–387 clean | **387 files already formatted** |
| Pytest collection | 1077 / 104 | 1077 / 104 | **1078** / 104 (+1 crop-default freeze test) |
| `unittest.TestCase` modules | ~15 | **0** | **0** |
| Legacy patterns (Optional/Union/np.float/torch.cuda.amp/timezone.utc/TestCase) | mixed | **0** | **0** |
| Focused modernize smoke (+ `test_ml_pipeline`) | — | pass | **pass** (exit 0) |
| `allow_unaligned_crop` default | False | False | **False** (asserted in tests) |
| `field_ops_allow_ml_live_in_fusion` default | False | False | **False** (`ProductRails`) |

---

## Verification commands

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics

# Lint / format (migrate scope + models) — expect 0 errors
python -m ruff check wildfire_front tests scripts models
python -m ruff format --check wildfire_front tests scripts models

# Collection — expect 104 modules, 1078 tests
python -m pytest --collect-only
# Last line: "1078 tests collected …"

# Smoke (post-modernize; no GPU required)
python -m pytest `
  tests/test_identity.py `
  tests/test_pipeline.py `
  tests/test_evaluation_quality.py `
  tests/test_geometry_speed.py `
  tests/test_dataset_candidate_audit.py `
  tests/test_data_validation_milestone.py `
  tests/test_prepare_real_if_geotiffs.py `
  tests/test_inventory_real_if_material.py `
  tests/test_geotiff_to_patches.py `
  tests/test_tobarra_multipass_s4.py `
  tests/test_unet_model.py `
  tests/test_meta_labeler.py `
  tests/test_real_if_manifest.py `
  tests/test_geotiff_ingestion.py `
  tests/test_multihorizon_fieldops.py `
  tests/test_dataset_dem_align.py `
  tests/test_feature_schema.py `
  tests/test_geo_crs.py `
  tests/test_normalization.py `
  tests/test_metrics_protocol.py `
  tests/test_ml_pipeline.py `
  -q --tb=line

# Optional broader (slow / weights-gated may skip)
python -m pytest -m "not slow and not requires_weights" -q
```

**Executed on harness close-out (2026-08-10 resume):**

- `python -m ruff check wildfire_front tests scripts models` → **All checks passed** (exit 0).
- `python -m ruff format --check …` → **387 files already formatted** (exit 0).
- Collection → **1078 tests collected** / 104 modules (exit 0).
- Smoke set above (incl. `test_ml_pipeline` + `test_dataset_dem_align`) → **exit 0**.
- Legacy grep on active migrate scope → **TOTAL_HITS 0**.
- Freeze guard: modernize did **not** retune scorecard thresholds; scorecard JSON dirt in the working tree is **pre-existing WIP** on the branch. `ProductRails.field_ops_allow_ml_live_in_fusion is False`; crop default remains False.
- Durable test: `tests/test_dataset_dem_align.py::test_allow_unaligned_crop_default_is_false` asserts the shipped keyword-only default.

---

## Residual backlog (ordered)

1. **Complexity splits** — peel `cli_ml.run_ml_predict`, `decide_service.operational_files_to_ops_metrics`, `lab_next.build_next_gate`, `cli.main` into pure helpers + thin CLI (no behavior change; enables unit tests).
2. **E402 hygiene** — replace ad-hoc `sys.path` bootstrap with package install / `python -m` entrypoints; drop per-file ruff ignores gradually.
3. **Text I/O encoding** — audit non-binary `open`/`Path.write_text` for explicit `encoding="utf-8"` (binary GIS paths stay binary).
4. **RNG modernization** — replace remaining `np.random.seed` in `unet_train` with `np.random.default_rng` **only if** bit-identical policy is waived (may change shuffle → experiment-affecting).
5. **Coverage climb** — raise `fail_under` from 60 toward measured line coverage in CI; add `pytest-cov` to `dev` extras if CI does not already install it separately.
6. **kaggle_job modernize** — separate pass for kernel scripts (I001, F541, W292); archives frozen. Old `torch.cuda.amp` only in archive kernels.
7. **Dep pins** — consider upper-bound smoke on `torch` 2.4+/2.5 and sklearn 1.5+ in CI matrix; no pin change required for this pass.
8. **Class rename optional** — rename `*Tests` → `Test*` over time and drop custom `python_classes` once complete.

*(Crop telemetry for opt-in `allow_unaligned_crop=True` already ships: warning + `crop_telemetry` counters; default remains hard-fail.)*

---

## Out of scope (explicit)

- Retrain / re-eval LOFO, U1 promote, metrics-lift kill criteria.
- Changing scorecard JSON claims or `ML_PRODUCT_GO`.
- Geospatial reproject pipeline redesign (only documented alignment defaults).
- Committing git; working tree may contain unrelated WIP — this doc describes the **modernize** delta class only.

---

## Summary

| Goal | Status |
|------|--------|
| Inventory metrics + deprecated greps + complexity | Done |
| Safe modernize of package / tests / active scripts / models | Done (ruff **0** on scope; models cleaned; **0** unittest.TestCase left) |
| Dataset silent-crop risk assessed | Done (default **False**; opt-in telemetry; freeze test added) |
| Collection parity after unittest migration | Done (`python_classes`; **1078** tests) |
| Harness close-out verification | Done (ruff/format/collect/smoke/legacy/freeze) |
| Report + verification commands + backlog | This file |

**Bottom line:** active Python surface is on **Py3.11 idioms** (`datetime.UTC`, `collections.abc`, `X | None`, modern `torch.amp`, NumPy 2-ready deps). Configured ruff on migrate targets **and** `models/` is **clean**. All tests are plain pytest style. Field fusion stays **OFF**; silent unaligned crop stays **OFF**. Remaining debt is **complexity concentration**, optional **coverage climb**, **kaggle_job**, and experiment-affecting **RNG** — not legacy stdlib/sklearn/torch AMP breakage in the package.
