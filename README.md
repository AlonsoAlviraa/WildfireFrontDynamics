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

## Empieza aquí (1 comando)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics"
python scripts\show_all.py
```

Abre la **app de sala de mando** (`docs/commander/index.html`) + portal.  
Solo la app:

```powershell
python scripts\build_commander_app.py
start docs\commander\index.html
```

Lectura corta: **[`docs/START_HERE.md`](docs/START_HERE.md)**  
Venta: **[`docs/ONEPAGER_COMERCIAL_ES.md`](docs/ONEPAGER_COMERCIAL_ES.md)**  
Comandos largos: **[`docs/GUIA_COMANDOS_RECREAR_TODO.md`](docs/GUIA_COMANDOS_RECREAR_TODO.md)**  
Sueños máximos (techo del producto): **[`docs/SUENOS_MAXIMOS.md`](docs/SUENOS_MAXIMOS.md)**

---

## Números clave (no eslóganes)

| Métrica | Valor |
|---------|------:|
| ML U1 TEST honest (lab) | mean IoU ~**0.86** · sel@80 ~**0.90** · ECE ~**0.15** |
| Catalog holdout IoU (provenance only) | **0.8963** — not live certainty · not ROS |
| Mejora vs copy (catálogo) | **+0.2545** |
| Packs open CEMS | **4** (hasta ~**5300 ha**) |
| Decision Card | GO / HOLD / **ABSTAIN** según fuentes |
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
| ML v34, ops incident, 4 packs CEMS | 2ª ancla INFOCAM |
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
