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
