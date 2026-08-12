# Mapa del repositorio (profesional)

> **Autoridad:** este mapa + `docs/CURRENT_STATE.md` + `docs/START_HERE.md`.  
> **Última actualización:** 2026-08-12 (SPA Live Ops + demo-day ship; Grok Bot org doc).

---

## Raíz (solo producto / ingeniería)

| Entrada | Rol |
|---------|-----|
| `README.md` | Entrada humana |
| `ARCHITECTURE.md` · `VISION.md` · `RULES.md` · `MEMORY.md` | Diseño y memoria de proyecto |
| `wildfire_front/` | **Código de producto** (paquete Python) |
| `scripts/` | CLI operativas y lab (no basura de agent) |
| `tests/` | Tests (`test_spa_*`, live ops, product) |
| `kaggle_job/` | Kernels Kaggle (código de train remoto) |
| `docs/` | Documentación |
| `data/` | Datos locales (tif/raw gitignored en gran parte) |
| `artifacts/` | Parches/train regenerables (**gitignored**) |
| `outputs/` | Resultados de runs (**gitignored**; canónicos bajo `outputs/ml_eval/canonical/`) |
| `models/` | Pesos locales (**gitignored** `*.pt`) |
| `config/` | Config |
| `Makefile` · `pyproject.toml` · `Dockerfile` | Build / CI (`make test-spa`) |

**No debe haber** en raíz: `_FINAL_*`, `_OUT_*`, diffs de migration, JSON de agent, etc. (ver `.gitignore`).

---

## Producto SPA / Live Ops (código)

| Ruta | Rol |
|------|-----|
| `wildfire_front/cli_app.py` | CLI `app` / `spa` / `console` · `--serve` · `--demo-day` |
| `wildfire_front/product/app_spa.py` | Payload `wfd_product_app_v1` |
| `wildfire_front/product/app_spa_html.py` | HTML industrial C2 |
| `wildfire_front/product/live_ops.py` | Live Ops Kernel handlers |
| `wildfire_front/product/fire_catalog.py` | Catálogo IF + product_actions |
| `wildfire_front/product/operator_ux.py` | Brief / gates / next |
| `wildfire_front/map_status/` | Mapa Leaflet layers + FIRMS |
| `tests/test_spa_live_ops.py` · `test_product_app.py` · `test_app_spa_security.py` | SPA / live / security |

---

## Documentación (`docs/`)

| Ruta | Contenido |
|------|-----------|
| `docs/START_HERE.md` | Onboarding 2 min |
| `docs/CURRENT_STATE.md` | **Snapshot canónico** gates + freeze + Live Ops |
| `docs/APP.md` | SPA + Live Ops API/flags |
| `docs/design/LIVE_OPS_DEMO_KERNEL.md` | Diseño Live Ops |
| `docs/EMPRESA_BOTS_TRABAJADORES.md` | Grok Bot teammates (empresa) |
| `docs/PLAN_PR_POST_LIVE_OPS.md` | PRs land + residual |
| `docs/REPO_MAP.md` | Este mapa |
| `docs/GOAL_ML_CLOSEOUT.md` | Criterio de cierre ML |
| `docs/ml/README.md` | ML lab: qué está probado |
| `docs/H1_*` · `docs/CHEATSHEET_DEMO_12MIN.md` | Demo H1 |
| `docs/goals/` | Mega-goals cerrados |
| `docs/commander/` | App sala de mando (**legacy** vs SPA) |
| `docs/archive/` | Docs históricos |

---

## ML — qué está probado (lectura obligada)

Ver **`docs/ml/README.md`**.

Resumen de cierre (2026-08-10):

| Rol | Config | Mean / min | Dónde |
|-----|--------|------------|-------|
| Product LOFO sealed | `exact_force_ema_long` | 0.788 / 0.707 | `outputs/ml_eval/canonical/CHAMPION_SEALED_*.json` |
| Weather spatial | `era5_long` | 0.576 / 0.526 (ΔW0 +0.019) | `…/CHAMPION_WEATHER_era5_long_board.json` |
| Decisión de cierre | `FREEZE_ML_AND_REQUEST_DATA` | — | `…/ML_CLOSEOUT_DECISION.json` |

---

## `outputs/` (resultados locales)

Todo es regenerable / local; **gitignored**. Organización:

| Prefijo / carpeta | Significado |
|-------------------|-------------|
| `outputs/ml_eval/canonical/` | **Stamps canónicos** (copias pequeñas JSON/MD) |
| `outputs/ml_eval/lab_loop/` | Stamps y scorecards del lab loop |
| `outputs/kaggle_*` | Downloads de kernels (boards + pesos) |
| `outputs/open_if/` | Packs open perimeter |
| `outputs/*_lwir/` | Demos / runs incidentales por fuego |
| `outputs/observatorio*` | Packs observatorio |

No uses `outputs/kaggle_*` como “verdad de producto” sin el stamp canónico.

---

## `kaggle_job/`

| Contenido | Rol |
|-----------|-----|
| `run_*.py` | Scripts de train en Kaggle |
| `kernel-metadata-*.json` | Metadatos de kernel |
| `datasets/` | Metadata local; **zips LOFO spatial grandes gitignored** (límite GitHub 100 MB) |
| `archive/` | Kernels viejos archivados |

No reintroducir carpetas `_push_*` (staging efímero).  
No commitear `data/real_if/pablo_geacam_20260803_drop/` (~159 MB raw).

---

## Qué se borra / no se reintroduce

- Prefijos de agent en raíz: `_FINAL_*`, `_OUT_*`, `_emit_*`, `*_migration_*`
- Diffs `.migration_*`
- `_json_parts/`, staging `_push_*`
- Scripts `_poll_*` / `_parse_*` efímeros

Ver patrones en `.gitignore`.

---

## Comandos de higiene

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
# No deben quedar archivos _* en raíz:
Get-ChildItem -File | Where-Object { $_.Name -match '^_' }
# Canónico ML:
Get-ChildItem outputs\ml_eval\canonical
```
