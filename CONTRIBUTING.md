# Contributing to Wildfire Front Dynamics

Thanks for your interest in contributing. This document covers local setup, product layout, and the quality gates that must match CI.

## Quick Start

```bash
# 1. Clone and install (editable)
git clone https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git
cd WildfireFrontDynamics
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"
# Optional ML + geo extras used in product paths:
# pip install -e ".[ml,viz,dev]"
# pip install shapely pyproj

# 2. Optional dual-product weights (gitignored *.pt)
python scripts/install_dual_weights.py

# 3. Verify (local; see CI scope below)
make verify
# or match CI explicitly:
#   ruff check wildfire_front tests scripts
#   ruff format --check wildfire_front tests
#   mypy wildfire_front --ignore-missing-imports
#   pytest tests/ -q
```

## Project Layout

```
wildfire_front/          # Library code (importable package)
  incident/              # Live LWIR runtime (doctor / update / watch)
  product/               # Decision Card, policy, forensics, decide API
  open_if/               # Public perimeter / STAC helpers
  ml/                    # U-Net train/eval, product catalog, predictors
  ingestion/             # GeoTIFF / LWIR ingest (leak-free contract)
  front_dynamics.py      # Observed front + ROS (ops, not ML)
models/                  # Catalog, U-Net definition, product manifests
  catalog.json           # ndws_v21 · clm_v28 · clm_ensemble_v34
  production/            # NDWS v21
  clm_specialist/        # CLM v28
  clm_ensemble/          # CLM ensemble v34 (default emergency ML)
kaggle_job/              # Active v21 train + archive/ historical kernels
scripts/                 # Smokes, demos, scorecards, data helpers
tests/                   # Pytest suite (~270+ test functions / ~40 modules)
docs/                    # Architecture, product docs, scorecards, design
data/real_if/            # Real sequences (not fully committed)
```

Ops product ID: `front_dynamics_v1`. Default ML product: `clm_ensemble_v34`. Details: `ARCHITECTURE.md`, `docs/PRODUCTO_DUAL.md`.

## Development Workflow

1. **Create a branch** from `main`: `feat/<short-description>` (or `fix/`, `docs/`).
2. **Make changes** with tests. Keep commits focused and atomic.
3. **Run quality gates locally** before pushing (same scopes as CI):
   ```bash
   ruff check wildfire_front tests scripts
   ruff format --check wildfire_front tests
   mypy wildfire_front --ignore-missing-imports
   pytest tests/ -q
   # Makefile helpers (note: make lint currently scopes package+tests only):
   make lint && make typecheck && make test
   make verify
   ```
4. **Open a Pull Request** — CI runs lint + tests on GitHub Actions.
5. **Ensure CI is green** before requesting review.

## Code Standards

| Aspect        | Tool      | Standard |
|---------------|-----------|----------|
| Style/Lint    | `ruff`    | Zero errors on `wildfire_front tests scripts` (CI). Config in `pyproject.toml`. |
| Format        | `ruff`    | `ruff format --check wildfire_front tests` |
| Types         | `mypy`    | `mypy wildfire_front --ignore-missing-imports` |
| Tests         | `pytest`  | All unit tests pass. New code needs new tests. |
| Line length   | 100       | Enforced by ruff. |
| Python code   | —         | No emojis in Python sources. |

### Scientific Integrity Rules

This project enforces strict separation between observed, inferred, and ground-truth data. When contributing:

- **Never** mix `observed/` and `gt/` paths in the same pipeline stage.
- **Always** include SHA-256 hashes in manifests for traceability.
- **Never** modify provenance records after creation.
- **Always** document data sources in `docs/PROVENANCE.md` when relevant.
- **Never** claim Decision Card system reliability PASS without a real gate result.
- **Never** tune ensemble mix/temperatures on holdout test / LOFO-CARDOSO (VAL only).

## Model weights (`.pt`)

**`.pt` / `.pth` files are gitignored** and are not present in a clean clone.

| Location | Role |
|----------|------|
| `models/production/` | NDWS v21 weights + TorchScript (research baseline) |
| `models/clm_specialist/` | CLM Spain single-model specialist |
| `models/clm_ensemble/` | CLM ensemble members (emergency ML product) |

Manifests/JSON under those dirs **are** tracked; only binary checkpoints are not.

### Install weights locally

```bash
# v21 production only
python scripts/install_production_weights.py

# Full dual-product catalog (NDWS + CLM + ensemble)
python scripts/install_dual_weights.py
```

Search order prefers already-present files under `models/production/` (and other
catalog paths), then optional Kaggle output dirs / training exports. The
historical `kaggle_outputs_v21/` tree is **not** required if weights already
live under `models/`.

For CI or release packaging, attach weights as release assets or restore them
via a private cache — never commit large checkpoints.

### Docker inference image

`.pt` files are **not** baked into CI-built images (gitignored; clean clone has
manifests/JSON only). The `inference` Docker target still builds and import-
smokes without weights; CI does **not** fail when `.pt` are missing.

Inject checkpoints at runtime with bind-mounts:

```bash
docker run --rm \
  -v "$PWD/models/production/weights_v21_best.pt:/app/models/production/weights_v21_best.pt:ro" \
  -v "$PWD/models/production/spread_model_v21.pt:/app/models/production/spread_model_v21.pt:ro" \
  wildfire-front-dynamics:inference --help
```

Or place files under `models/production/` before `docker build --target inference`.

Env defaults inside the image:

- `WILDFIRE_MANIFEST=/app/models/production/manifest.json`
- `WILDFIRE_TORCHSCRIPT=/app/models/production/spread_model_v21.pt`

### Tests that need weights

Tests that assert on real checkpoints **skip** with a clear reason when artifacts
are missing (`pytest.skip("requires_weights: ...")`, marker `requires_weights`).
The default suite must stay green on a clean clone without downloading weights.

```bash
# Full suite (skips weight-gated cases when .pt missing)
pytest tests/ -q

# Only weight-gated tests (need local .pt install first)
pytest tests/ -m requires_weights -q
```

## Testing

Suite size (approx.): **~270+** `test_*` functions across **~40** modules under `tests/`.

```bash
# Full suite
pytest tests/ -q

# With coverage
pytest tests/ --cov=wildfire_front --cov-report=term-missing

# Product / ML-focused slices (also used in CI ml-smoke)
pytest tests/test_product_catalog.py tests/test_clm_eval_ensemble.py tests/test_spread_predictor.py -q
pytest tests/test_incident_watch.py tests/test_confidence_product.py tests/test_decide_cli.py -q
```

Tests use lightweight fixtures and must pass without external data downloads
(except weight-gated tests; see **Model weights** above). Tests that require
production `*.pt` weights or large holdout packs may skip on a clean clone
without `scripts/install_dual_weights.py` / `install_production_weights.py` —
call that out in the PR if relevant.

## Data Handling

Real wildfire data lives under `data/real_if/` and is **not** fully committed to git (see `.gitignore`). To process new fires:

1. Download from the source (e.g., Dropbox transfer links).
2. Organize into `data/real_if/raw_dropbox/organized/<FIRE_NAME>/`.
3. Run: `python scripts/batch_process_fires.py`
4. Verify outputs in `artifacts/` and `outputs/`.

See `docs/RUNBOOK_NEW_FIRES.md` for the full protocol. Open packs: `docs/PISTA_B_OPEN_IF.md` / `scripts/build_open_if_*.py`.

## Commit Messages

Use conventional commits (imperative mood):

```
feat(product): add open-pack source to decide CLI

docs: rewrite ARCHITECTURE for dual-product v21/v34

fix(incident): preserve CRS when writing outbox envelope
```

Reference issues with `Closes #N` or `Refs #N`.

## Pull Request Checklist

- [ ] Branch is up to date with `main`
- [ ] Lint/format/mypy scopes match CI (see above)
- [ ] `pytest tests/ -q` passes (or failures explained + marked)
- [ ] New code has tests
- [ ] No `data/real_if/raw_dropbox/` content committed
- [ ] No secrets or large `*.pt` weights committed
- [ ] `docs/` / `ARCHITECTURE.md` updated if architecture or product surface changed
- [ ] `CHANGELOG.md` updated (if applicable)

## Reporting Issues

Use GitHub Issues. Include:

- Python version and OS
- Steps to reproduce
- Expected vs. actual behavior
- Relevant logs (truncate if long)

## License

By contributing, you agree that your contributions are licensed under the project's license (see `LICENSE`).
