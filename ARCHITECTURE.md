# ARCHITECTURE — WildfireFrontDynamics

Dual-product system: **ops geometry** (observed front / ROS) and **ML next-day masks** (U-Net v21 / CLM ensemble v34), fused only at the Decision Card. Ops is not ML; ML is not drone ROS.

## System overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PRODUCT SURFACE                                  │
│  Decision Card (GO / HOLD / ABSTAIN)  ·  incident outbox  ·  open packs  │
│  wildfire_front/product/   ·   wildfire_front/incident/   ·   open_if/   │
└───────────────────────────────┬──────────────────────────────────────────┘
                                │ fuse (never train on fused labels)
          ┌─────────────────────┴─────────────────────┐
          │                                           │
┌─────────▼─────────┐                     ┌───────────▼───────────┐
│  OPS (geometry)   │                     │  ML (next-day mask)   │
│  front_dynamics   │                     │  Residual U-Net       │
│  geometry_speed   │                     │  product_catalog      │
│  incident runtime │                     │  ndws_v21 · clm_v28   │
│  emergency_products                     │  clm_ensemble_v34     │
└─────────┬─────────┘                     └───────────┬───────────┘
          │                                           │
┌─────────▼───────────────────────────────────────────▼───────────┐
│  INGEST / DATA                                                   │
│  GeoTIFF LWIR (real_if) · NDWS npz · CLM holdout patches         │
│  open CEMS/EFFIS packs · STAC dNBR (open_if)                     │
└──────────────────────────────────────────────────────────────────┘
```

**Hard rule:** do not mix drone ROS with ML IoU claims. Catalog `ops_product` is `front_dynamics_v1`; ML defaults to `clm_ensemble_v34`.

## Product map

| Product ID | Role | Entry points |
|------------|------|--------------|
| `front_dynamics_v1` | Observed front, multi-estimator ROS, envelope | `wildfire_front/front_dynamics.py`, `scripts/smoke_emergency_products.py` |
| `incident_runtime_v1` | Inbox LWIR → state/outbox + Decision Card | `wildfire_front/incident/`, `python -m wildfire_front incident` |
| open CEMS packs | Public multi-day perimeters (no NDA) | `wildfire_front/open_if/`, `outputs/open_if/*` |
| `ndws_v21` | NDWS research baseline (Residual U-Net) | `models/production/`, `scripts/predict_spread.py --product ndws_v21` |
| `clm_v28` | CLM Spain single-checkpoint specialist | `models/clm_specialist/` |
| `clm_ensemble_v34` | **Emergency ML default** — soft-vote ensemble | `models/clm_ensemble/`, catalog default |
| Decision Card | GO / HOLD / ABSTAIN + confidence + forensics | `wildfire_front/product/`, `python -m wildfire_front decide` |

Catalog source of truth: `models/catalog.json` + `wildfire_front/ml/product_catalog.py`.

### Published ML metrics (honest)

| Product | Domain | IoU | Notes |
|---------|--------|-----|-------|
| `ndws_v21` | NDWS test | **0.226** | Δ vs copy **+0.076**; research / NDWS-like only |
| `clm_v28` | CLM holdout test | **0.838** | Δ vs copy **+0.196** |
| `clm_ensemble_v34` | CLM holdout ensemble | U1 ~**0.86** · catalog **0.8963** | Catalog = provenance only; U1 TEST honest is lab pitch; mix/temps on VAL only |

Weights (`*.pt`) are gitignored; install via `scripts/install_dual_weights.py` (local workspace). CI without weights cannot assert real product paths.

## Package layout

```
wildfire_front/
├── front_dynamics.py      # Coreg, front geometry, ROS estimators
├── geometry_speed.py      # Perimeter / speed helpers
├── geometry / scientific  # scientific_ops, sector_ros_local, evaluation
├── incident/              # Live runtime: doctor, update, watch, state
│   ├── pipeline.py
│   ├── watch.py
│   ├── doctor.py
│   └── state.py
├── product/               # Decision surface
│   ├── confidence.py      # Decision Card + reliability report
│   ├── policy.py
│   ├── decide_service.py
│   ├── forensics.py
│   └── api_server.py      # POST /v1/decide
├── open_if/               # Public perimeter / STAC dNBR helpers
│   ├── dnbr.py
│   └── stac_s2.py
├── ml/                    # Training, eval, product catalog, predictors
│   ├── product_catalog.py
│   ├── spread_predictor.py
│   ├── unet_train.py
│   ├── clm_eval.py
│   ├── dataset.py
│   ├── train.py           # Legacy A3C / fine-tune paths
│   └── ...
├── ingestion/geotiff.py   # GeoTIFF contract
├── emergency_products.py
└── cli.py                 # CLI: decide, incident, serve-decide, ...
```

Supporting trees:

```
models/
├── catalog.json                 # Product registry
├── unet_model.py                # Residual U-Net (production architecture)
├── model.py                     # A3C-LSTM LEGACY (not production)
├── production/                  # ndws_v21 manifests (+ local weights)
├── clm_specialist/              # clm_v28
└── clm_ensemble/                # clm_ensemble_v34

kaggle_job/
├── run_unet_training_v21.py     # Active NDWS / production train script
├── kernel-metadata-v21.json     # Canonical Kaggle kernel metadata
├── preprocess_ndws.py
├── kaggle_common.py
└── archive/                     # Historical kernels (mega, v13–v27, …)
    ├── run_mega_training.py     # Archived A3C pipeline — not active
    ├── run_unet_training_v13.py # Archived — superseded by v21
    └── run_unet_training_v*.py  # Older U-Net experiments

scripts/                         # Ops/ML demos, smokes, scorecards, loops
tests/                           # ~270+ test functions across ~40 modules
docs/                            # Product docs, scorecards, design, archive
data/                            # real_if, candidates (not fully git-tracked)
```

## Data paths

### Ops / incident

```
LWIR GeoTIFF inbox
  → incident doctor (timestamps, CRS, masks)
  → front_dynamics + geometry_speed
  → outbox: ROS, sectors, envelope, fire_decision_card.json
```

Contract: `docs/GEOTIFF_INPUT_CONTRACT.md`, runbook `docs/FIELD_KIT_INCIDENT.md`.

### ML training (NDWS)

```
NDWS TFRecords
  → kaggle_job/preprocess_ndws.py → .npz patches
  → NpzWildfireDataset / U-Net train (kaggle_job/run_unet_training_v21.py)
  → models/production (v21)
```

### ML transfer (CLM Spain)

```
CLM GeoTIFF / patches
  → holdout splits (scripts/build_clm_holdout_splits.py, LOFO helpers)
  → fine-tune / ensemble members
  → models/clm_specialist (v28) + models/clm_ensemble (v34)
```

### Open perimeter

```
CEMS / EFFIS / STAC
  → scripts/build_open_if_*.py
  → outputs/open_if/<pack>
  → Decision Card via --open-pack
```

## Model comparison (current)

| Aspect | Residual U-Net (production) | A3C-LSTM |
|--------|----------------------------|----------|
| Status | **Active** (`ndws_v21`, CLM products) | **Legacy** (`models/model.py`) |
| Code | `models/unet_model.py`, `wildfire_front/ml/unet_train.py` | `models/model.py`, `wildfire_front/ml/train.py` |
| Kaggle entry | `kaggle_job/run_unet_training_v21.py` | `kaggle_job/archive/run_mega_training.py` |
| Patch / channels | 64×64, residual delta target | Historical 30×30 per-cell |
| Product metrics | v21 IoU 0.226; ensemble v34 0.8963 | Obsolete for product claims |

Do not cite mega/v13 paths as active training. Older scripts live under `kaggle_job/archive/` for reproducibility only.

## Inference and decision flow

```
1. Ops path (optional): incident update / emergency products → ROS + quality
2. ML path (optional): predict_spread --product clm_ensemble_v34 (or v21/v28)
3. Open path (optional): load open_if pack
4. product.decide_service / CLI `decide`
     → policy + confidence → GO | HOLD | ABSTAIN
     → forensics / provenance hashes
```

CLI examples:

```powershell
python scripts/predict_spread.py --list-products
python -m wildfire_front decide
python -m wildfire_front decide --use-ml-v34 --open-pack outputs\open_if\emsr578 --require-ops-for-go
python -m wildfire_front serve-decide --port 8765
python -m wildfire_front incident doctor --inbox path/to/inbox
```

## Evaluation protocol (leak-free)

1. NDWS: train [0–11], val [12–13], single test [14] (or documented re-export).
2. CLM: holdout protocol `clm_holdout_test_seed42_v1`; ensemble mix/temperatures **VAL only**.
3. Never tune ensemble weights on LOFO-CARDOSO / holdout test.
4. Meta-labeler: fit on VAL predictions, evaluate on TEST when used.
5. Ops metrics (ROS, Hausdorff) stay separate from ML IoU scorecards.

## Kaggle training (active)

- Canonical kernel metadata: `kaggle_job/kernel-metadata-v21.json` → `run_unet_training_v21.py`
- Root `kaggle_job/kernel-metadata.json` may lag; prefer the v21 file for pushes
- Historical A3C / U-Net v13–v27 scripts: `kaggle_job/archive/` only
- GPU constraints and account notes: see `RULES.md` and experiment tracker

## Tests and quality gates

| Check | Scope (matches CI) |
|-------|--------------------|
| Suite size | **~270+** `test_*` functions in **~40** modules under `tests/` |
| Lint | `ruff check wildfire_front tests scripts` |
| Format | `ruff format --check wildfire_front tests` |
| Types | `mypy wildfire_front --ignore-missing-imports` |
| Tests | `pytest tests/` (weights-dependent tests need local `*.pt`) |

See `CONTRIBUTING.md` and `.github/workflows/ci.yml`.

## Dependencies

- Python 3.11+
- Core: numpy, rasterio, shapely, pyproj, affine
- ML extras: torch (Kaggle P100/sm_60 historically needed ≤2.1.x for some kernels)
- Dev: ruff, mypy, pytest (see `pyproject.toml` extras)

## Related docs

| Doc | Role |
|-----|------|
| `docs/PRODUCTO_DUAL.md` | Dual-product CLI and gates |
| `docs/INCIDENT_RUNTIME_V1.md` | Incident field runtime |
| `docs/GEOTIFF_INPUT_CONTRACT.md` | Ingest contract |
| `docs/design/DECISION_POLICY.md` | GO / HOLD / ABSTAIN policy |
| `VISION.md` | Product north star |
| `RULES.md` | Loop engineering rules |
| `MEMORY.md` | Short loop memory (current baselines) |
| `docs/EXPERIMENT_TRACKER.md` | Experiment log |
| `docs/CLEANUP_2026_07.md` | Removed dumps / path cleanup |
