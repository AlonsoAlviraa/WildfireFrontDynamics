# Wildfire Front Dynamics

[![CI](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/workflows/ci.yml/badge.svg)](https://github.com/AlonsoAlviraa/WildfireFrontDynamics/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)

> MVP reproducible y auditable para reconstruir la dinámica observada de un frente de incendio a partir de secuencias térmicas georreferenciadas (LWIR/GeoTIFF).

## Overview

El pipeline genera quemas sintéticas con verdad conocida, simula observaciones con error, reconstruye tiempos de llegada, estima velocidades locales y produce informes visuales auditables. También acepta secuencias GeoTIFF reales y máscaras binarias para generar geometrías observadas, campos de llegada y estimaciones conservadoras de velocidad local **sin inventar ground truth**.

### Key Features

- **Scientific rigor**: strict separation between `observed`, `inferred`, and `ground-truth` data (leak-free pipeline).
- **SHA-256 traceability**: every artifact has content hashes for full reproducibility.
- **Modular architecture**: ingestion → reconstruction → evaluation → ML, each independently testable.
- **Adaptive segmentation**: MAD-based (Median Absolute Deviation) thermal thresholding for robust hotspot detection.
- **Meta-labeler**: temporal consistency validation for reconstructed fire fronts.

## Quick Start

```bash
# Install (editable, with dev tools)
pip install -e ".[dev]"

# Run the synthetic demo
python -m wildfire_front demo --output outputs/demo

# Run the test suite
pytest tests/ -q

# Open the report
start outputs/demo/report.html      # Windows
# open outputs/demo/report.html     # macOS
```

### One-step MVP (Windows)

```powershell
.\scripts\run_mvp.cmd
```

Generates both `outputs/demo/report.html` and `outputs/geotiff-demo/report.html`.

## Installation

### Prerequisites

- Python ≥ 3.11
- GDAL system libraries (for rasterio): `gdal-bin libgdal-dev` (Ubuntu) or [OSGeo4W](https://trac.osgeo.org/osgeo4w/) (Windows)

### Setup

```bash
python -m venv .venv
.venv\Scripts\activate              # Windows
# source .venv/bin/activate         # macOS/Linux
pip install -e ".[dev]"

# For ML experiments:
pip install -e ".[ml]"

# For everything:
pip install -e ".[all]"
```

## Usage

### Dual ML products (NDWS + CLM)

| Product | CLI id | When |
|---------|--------|------|
| NDWS global v21 | `ndws_v21` | Next-day spread on NDWS-like patches |
| CLM Spain specialist v28 | `clm_v28` | CLM holdout-style Spain patches |

```bash
python scripts/install_dual_weights.py
python scripts/predict_spread.py --list-products
python scripts/predict_spread.py --product clm_v28 --npz path/to/patches --eval
```

See `docs/PRODUCTO_DUAL.md`. Ops ROS (drone fronts) is **not** ML — use `scripts/build_observatory_pack.py`.

### Synthetic Demo

```bash
python -m wildfire_front demo --output outputs/demo
```

### GeoTIFF Ingest (Real Data)

With pre-supplied masks:
```powershell
python -m wildfire_front ingest-geotiff `
  --images data\sample\images `
  --masks data\sample\masks `
  --output outputs\geotiff-demo `
  --event-id burn_001 `
  --sensor-id thermal_demo `
  --estimated-error-m 2.0
```

Adaptive MAD-based segmentation (no masks needed):
```powershell
python -m wildfire_front ingest-geotiff `
  --images data\sample\images `
  --mad-z 6 `
  --output outputs\mad-demo `
  --sensor-id thermal_demo `
  --estimated-error-m 2.0
```

### Batch Processing (Multiple Fires)

```bash
python scripts/batch_process_fires.py
```

Processes all organized wildfire sequences: reprojection → ingest → mask materialization → audit.

## Outputs

| File | Description |
|------|-------------|
| `fronts.geojson` | True and observed fire fronts |
| `observations_manifest.csv` | Observation traceability with declared error |
| `ingest_manifest.csv` | Accepted/reviewed/rejected records with reasons |
| `arrival_time.csv` | Rasterized arrival time field |
| `local_speeds.csv` | Local speed, uncertainty, and abstentions |
| `summary.json` | Metrics and reproducible configuration |
| `fronts.svg` | Vector visualization |
| `report.html` | Self-contained dashboard |

## Development

```bash
make verify    # lint + typecheck + test
make help      # see all targets
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development workflow.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/MVP_ARCHITECTURE.md](docs/MVP_ARCHITECTURE.md) | Architecture overview |
| [docs/SCIENTIFIC_CORE.md](docs/SCIENTIFIC_CORE.md) | Scientific method, quality gates, and limits |
| [docs/GEOTIFF_INPUT_CONTRACT.md](docs/GEOTIFF_INPUT_CONTRACT.md) | GeoTIFF input specification |
| [docs/PROVENANCE.md](docs/PROVENANCE.md) | Data provenance and traceability |
| [docs/REPO_ANALYSIS.md](docs/REPO_ANALYSIS.md) | Repository analysis and improvement areas |
| [docs/RUNBOOK_NEW_FIRES.md](docs/RUNBOOK_NEW_FIRES.md) | Protocol for ingesting new fires |
| [docs/MEGA_SPRINT_PLAN.md](docs/MEGA_SPRINT_PLAN.md) | Sprint plan and roadmap |

## Project Status

This MVP validates the geometric core with synthetic data and accepts the real GeoTIFF contract. It is **not** an operational tool and does not predict real wildfires. Non-radial speed estimation still requires validation against independent annotations from a real thermal sequence.

## License

[MIT](LICENSE) — © 2026 Alonso Alviraa