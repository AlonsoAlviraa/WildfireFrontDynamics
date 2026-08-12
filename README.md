# WildfireFrontDynamics

[![CI](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/workflows/ci.yml/badge.svg)](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Qué es (30 segundos)

**Apoyo a la decisión en incendios** con tres piezas:

| Pieza | Qué hace | Cuando no hay… |
|-------|----------|----------------|
| **Ops térmico** | ROS y brief desde LWIR de dron | No inventa frente |
| **Open CEMS** | Perímetros satélite multi-día (sin NDA) | No sustituye cadastro nacional |
| **Decision Card** | **GO / HOLD / ABSTAIN** + confianza + auditoría | Se calla si faltan datos |

**No es:** un visor más de mapas gratis de Copernicus.  
**Sí es:** cuándo confiar, cuándo no, y con qué métricas.

---

## Empieza aquí

### Demo terceros / presentador H1 (superficie primaria)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front app --demo-day
```

SPA industrial C2 + **Live Ops** (Estado · Decidir · Acta en loopback) · fusion **OFF** · GO_Q **partial** (humano).  
Doc: **[`docs/APP.md`](docs/APP.md)** · cheatsheet: **[`docs/CHEATSHEET_DEMO_12MIN.md`](docs/CHEATSHEET_DEMO_12MIN.md)**

### Modo operario (tablero)

```powershell
python -m wildfire_front operator
python -m wildfire_front operator do --act 1   # … 2, 3, 4
python -m wildfire_front operator checklist
python -m wildfire_front operator explain-abstain   # ABSTAIN ≠ bug
```

Semáforo **VERDE / AMARILLO / ROJO** · 4 actos · residual **H1**.

Lectura: **[`docs/START_HERE.md`](docs/START_HERE.md)** · Estado: **[`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)** ·  
Mapa: **[`docs/REPO_MAP.md`](docs/REPO_MAP.md)** · ML: **[`docs/ml/README.md`](docs/ml/README.md)** ·  
Grok Bot equipo: **[`docs/EMPRESA_BOTS_TRABAJADORES.md`](docs/EMPRESA_BOTS_TRABAJADORES.md)**

### Portal / sala de mando (legacy eng, no primary)

```powershell
python scripts\show_all.py
python scripts\build_commander_app.py
```

Venta: **[`docs/ONEPAGER_COMERCIAL_ES.md`](docs/ONEPAGER_COMERCIAL_ES.md)** · H1: **[`docs/H1_GO_Q_RUNBOOK.md`](docs/H1_GO_Q_RUNBOOK.md)**

---

## Números clave (no eslóganes)

| Métrica | Valor |
|---------|------:|
| ML U1 TEST honest (lab) | mean IoU ~**0.86** · sel@80 ~**0.90** · ECE ~**0.15** |
| Catalog holdout IoU (provenance only) | **0.8963** — not live certainty · not ROS |
| Mejora vs copy (catálogo) | **+0.2545** |
| Tobarra LOFO fresh (2026-08-05) | IoU **0.478** · **KILL** vs Head A 0.489 (K1) · lab only |
| Packs open CEMS (emsr*) | **11** (inventario local `outputs/open_if/`; + AND/EXT/open packs aparte) |
| Decision Card | GO / HOLD / **ABSTAIN** según fuentes |
| Gates | GO_MES **true** · GO_Q **partial** · `ml_product_go` **true** · fusion **OFF** · ML **FREEZE+DATA** |
| SPA / Live Ops | eng **OK** · `app --demo-day` · residual = **H1 human** |
| Sealed LOFO (lab) | mean IoU **0.788** · min **0.707** (`exact_force_ema_long`) |
| Weather spatial (lab) | ERA5 long mean **0.576** · ΔW0 **+0.019** |
| “99.9999%” | Solo: no emitir GO silencioso bajo tests — **no** acierto del fuego |

---

## Tres productos (claro)

```text
1) Thermal Front (CLM / Heligrafics)  →  incident_runtime_v1
2) Open Perimeter (Copernicus EMS)    →  outputs/open_if/*
3) ML next-day España                 →  clm_ensemble_v34  (separado del ROS)
```

```powershell
# Listar ML
python scripts\predict_spread.py --list-products

# Decisión (vacío = ABSTAIN)
python -m wildfire_front decide

# Decisión con open pack
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\open_if\emsr578 --require-ops-for-go

# API mínima local (POST /v1/decide)
python -m wildfire_front serve-decide --port 8765
```

---

## Instalación

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
python -m pip install -e ".[dev]"
python -m pip install shapely pyproj
python scripts\install_dual_weights.py
```

---

## Documentos (solo 5 al empezar)

| Archivo | Uso |
|---------|-----|
| [`docs/PORTAL.html`](docs/PORTAL.html) | **Ver todo** (generado) |
| [`docs/START_HERE.md`](docs/START_HERE.md) | 2 minutos de texto |
| [`docs/ONEPAGER_COMERCIAL_ES.md`](docs/ONEPAGER_COMERCIAL_ES.md) | Venta |
| [`docs/GUIA_COMANDOS_RECREAR_TODO.md`](docs/GUIA_COMANDOS_RECREAR_TODO.md) | Todos los comandos |
| [`docs/PLAN_3_MESES.md`](docs/PLAN_3_MESES.md) | Roadmap |

Arquitectura dual (ops + ML v21/v34): [`ARCHITECTURE.md`](ARCHITECTURE.md) · producto: [`docs/PRODUCTO_DUAL.md`](docs/PRODUCTO_DUAL.md) · contribuir: [`CONTRIBUTING.md`](CONTRIBUTING.md)

El resto de `docs/` es archivo técnico (scorecards, FIRE-RES, experimentos). No hace falta para la primera demo.

---

## Trabajo hecho vs bloqueado

| Hecho | Bloqueado (hace falta gente/datos) |
|-------|-------------------------------------|
| ML v34, ops incident, 11 packs CEMS open | 2ª ancla / H1 demo tercero |
| Decision Card + Metrics Hub + portal | Perímetro nacional oficial |
| Demo 1 comando | Piloto con cliente real |

---

## Desarrollo

```powershell
# Slice de producto (rápido)
pytest tests\test_confidence_product.py tests\test_decide_cli.py tests\test_product_catalog.py -q

# Suite completa (~270+ tests / ~40 módulos)
pytest tests\ -q

# Lint como CI
ruff check wildfire_front tests scripts
ruff format --check wildfire_front tests
```

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`RULES.md`](RULES.md). Pesos locales: `python scripts\install_dual_weights.py`.

## License

MIT — see [LICENSE](LICENSE).
