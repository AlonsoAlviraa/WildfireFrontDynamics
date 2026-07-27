# Limpieza de repositorio (2026-07-16)

## Borrado local (~1.5+ GB residual + dumps)

| Eliminado | Motivo |
|-----------|--------|
| `kaggle_output/`, `kaggle_outputs_v*` (todas las versiones) | Dumps de entrenamiento; regenerables; no producto |
| `_vendor_cn/` | Clones de análisis externos (re-descargables; ver VENDOR_CN_INVENTORY) |
| `WildfireFrontDynamics/` (anidado) | Copia accidental del propio repo |
| `_cross_eval_npz/`, `_kaggle_weights_bundle/` | Cachés de evaluación / pesos intermedios |
| `build/`, `*.egg-info/`, `__pycache__/`, `.mypy_cache/`, `.pytest_cache/`, `.ruff_cache/` | Artefactos de build/test |
| `node_modules/`, `ci_logs*`, `terminals/`, `mcps/` | Dependencias regenerables / logs IDE |
| `models/v3.pt`, `weights_v10–v12*`, meta_labelers viejos | Pesos intermedios; producto = `production/` + `clm_specialist/` |
| `1.10`, `cross_protocol_report.json` | Basura residual raíz |

## Conservado a propósito

- `data/`, `artifacts/`, `outputs/` — datos de trabajo y demos ops (gitignored)
- `models/production/`, `models/clm_specialist/`, `models/catalog.json`
- `wildfire_front/`, `scripts/`, `tests/`, `kaggle_job/` (código de jobs, sin dumps)
- Docs activos de producto en `docs/` (no archive)

## Docs

~35 documentos de sesión / V8–V16 / sprints viejos → `docs/archive/`

## .gitignore

Reforzado para que no vuelvan dumps kaggle, vendor, nest, pesos intermedios.

---

## Pass 2 — implement cleanup 2026-07-21

Goal: tidy root / scripts / docs without touching product, La Mierla open-if,
decide service, production weights, or `data/` / `artifacts/` bulk data.

### Inventory (candidates reviewed)

| Candidate | Decision |
|-----------|----------|
| Root `*.ps1` Dropbox one-offs | **Archive** → `scripts/archive/` (not in START_HERE / RUNBOOK) |
| `scripts/_probe_cems_candidates.py` | **Archive** (temp probe; product has `cems_watch` + gold e2e) |
| `scripts/smoke_test_finetune.py` | **Archive** (A3C legacy; RUNBOOK updated) |
| `scripts/smoke_test_physics_loss.py` | **Archive** (v9 historical smoke) |
| `scripts/reeval_cross_protocol.py` | **Archive** (v14–v20 cross-eval; pre-product) |
| `docs/V10–V12_TRAINING_RESULTS.json` + `analysis_plots*` | **Archive** under `docs/archive/` |
| Closed G1 JSON (`V26`/`V27`/`V27B`/`G1_KILL_*`) | **Archive**; scorecard loader paths updated |
| `kaggle_job/archive/run_autonomous_research_v` (no ext.) | **Rename** → `run_autonomous_research_v_incomplete.py` |
| `__pycache__/` under package/scripts/tests/models | **Deleted** (regenerable; already gitignored) |
| Active product scripts (La Mierla, open_if, decide, smokes ops) | **Kept** |
| `models/production`, `clm_specialist`, `clm_ensemble` | **Kept** |
| `data/`, `artifacts/`, `outputs/` | **Not bulk-wiped** |
| `research/`, `package.json` (entrega_cma docx) | **Kept** |
| Live ML scorecards `V30_*` / `V31_*` / hubs / PORTAL | **Kept** in `docs/` |

### Moved / deleted (this pass)

**→ `scripts/archive/`**

| Path | Why |
|------|-----|
| `inspect_zips.ps1` | Root Dropbox zip inspect one-off |
| `parse_dropbox.ps1` | Root Dropbox HTML parse one-off |
| `move_transfers.ps1` | Root transfer file mover one-off |
| `extract_and_organize.ps1` | Root extract/organize one-off |
| `scripts/_probe_cems_candidates.py` | Temporary CEMS probe |
| `scripts/smoke_test_finetune.py` | Legacy A3C fine-tune smoke |
| `scripts/smoke_test_physics_loss.py` | Legacy v9 physics smoke |
| `scripts/reeval_cross_protocol.py` | Legacy v14/v19/v20 re-eval |

**→ `docs/archive/`**

| Path | Why |
|------|-----|
| `docs/V10_TRAINING_RESULTS.json` | Superseded training dump |
| `docs/V11_TRAINING_RESULTS.json` | Superseded training dump |
| `docs/V12_TRAINING_RESULTS.json` | Superseded training dump |
| `docs/analysis_plots/*` | V10/V11 analysis PNGs |
| `docs/analysis_plots_v12/*` | V12 analysis PNGs |
| `docs/V26_PHYSICS15_VERDICT.json` | Closed G1 physics verdict |
| `docs/V27_TEMPORAL_VERDICT.json` | Closed G1 T=2 verdict |
| `docs/V27B_TEMPORAL_VERDICT.json` | Closed G1 T=3 verdict |
| `docs/G1_KILL_FEATURES_TEMPORAL.json` | G1 kill record |

**Renamed**

| Path | Why |
|------|-----|
| `kaggle_job/archive/run_autonomous_research_v` → `…_incomplete.py` | Extensionless orphan next to v17 |

**Deleted (regenerable)**

| Path | Why |
|------|-----|
| `models/__pycache__/`, `scripts/__pycache__/`, `tests/__pycache__/`, `wildfire_front/**/__pycache__/` | Bytecode caches |

### Reference fixes

- `scripts/finalize_loop_1m_scorecard.py` — loads V26/V27 from `docs/archive/`
- `scripts/archive/eval_kaggle_v27*.py`, `analyze_training_curves.py` — archive output paths
- `docs/RUNBOOK_NEW_FIRES.md` — A3C finetune marked archived; product path preferred
- `docs/EMERGENCY_PRODUCT_STATUS.md`, `EXPERIMENT_TRACKER.md`, `LOOP_1M_MEJORA_CONTINUA.md` — G1 JSON paths
- `pyproject.toml` — drop ruff override for moved `smoke_test_finetune.py`
- `scripts/archive/README.md`, `docs/archive/README.md` — inventory tables

### Tests run (pass 2)

```text
pytest tests/test_la_mierla_week.py tests/test_decide_cli.py tests/test_pipeline.py tests/test_open_if_pack.py -q
# → 51 passed
```
