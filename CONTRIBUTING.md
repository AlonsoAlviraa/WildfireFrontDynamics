# Contributing to Wildfire Front Dynamics

Thanks for your interest in contributing! This document covers the essentials for getting your local environment set up and your changes merged.

## Quick Start

```bash
# 1. Clone and install (editable)
git clone https://github.com/AlonsoAlviraa/WildfireFrontDynamics.git
cd WildfireFrontDynamics
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux
pip install -e ".[dev]"

# 2. Verify everything passes
make verify         # or: ruff check . && mypy wildfire_front && pytest -q
```

## Project Layout

```
wildfire_front/          # Library code (importable package)
  ingestion/             # GeoTIFF / LWIR ingest pipeline (leak-free)
  ml/                    # Model definitions, training, meta-labeler
scripts/                 # One-off and batch CLI entry points
tests/                   # Pytest suite (mirrors package structure)
docs/                    # Architecture, audit reports, runbooks
data/real_if/            # Raw + organized real wildfire sequences
artifacts/               # Generated masks, reprojected GeoTIFFs, manifests
```

## Development Workflow

1. **Create a branch** from `main`: `feat/<short-description>`.
2. **Make changes** with tests. Keep commits focused and atomic.
3. **Run quality gates locally** before pushing:
   ```bash
   make lint            # ruff
   make typecheck       # mypy
   make test            # pytest
   make verify          # all three
   ```
4. **Open a Pull Request** — CI runs the same gates on GitHub Actions.
5. **Ensure CI is green** before requesting review.

## Code Standards

| Aspect        | Tool      | Standard |
|---------------|-----------|----------|
| Style/Lint    | `ruff`    | Zero errors. Config in `pyproject.toml`. |
| Types         | `mypy`    | Strict on `wildfire_front/`. No `Any` leaks. |
| Tests         | `pytest`  | All tests pass. New code needs new tests. |
| Imports       | `ruff`    | Sorted automatically (`--fix`). |
| Line length   | 100       | Enforced by ruff. |

### Scientific Integrity Rules

This project enforces strict separation between observed, inferred, and ground-truth data. When contributing:

- **Never** mix `observed/` and `gt/` paths in the same pipeline stage.
- **Always** include SHA-256 hashes in manifests for traceability.
- **Never** modify provenance records after creation.
- **Always** document data sources in `docs/PROVENANCE.md`.

## Testing

```bash
# Full suite
pytest tests/ -q

# With coverage
pytest tests/ --cov=wildfire_front --cov-report=term-missing

# Single test file
pytest tests/test_ml_pipeline.py -q
```

Tests use lightweight fixtures and must pass without external data downloads.

## Data Handling

Real wildfire data lives under `data/real_if/` and is **not** committed to git (see `.gitignore`). To process new fires:

1. Download from the source (e.g., Dropbox transfer links).
2. Organize into `data/real_if/raw_dropbox/organized/<FIRE_NAME>/`.
3. Run: `python scripts/batch_process_fires.py`
4. Verify outputs in `artifacts/` and `outputs/`.

See `docs/RUNBOOK_NEW_FIRES.md` for the full protocol.

## Commit Messages

Use clear, imperative-mood messages:

```
Add meta-labeler temporal consistency check

Implements a robust outlier detector for temporal sequences
in the reconstruction pipeline. Closes #42.
```

Reference issues with `Closes #N` or `Refs #N`.

## Pull Request Checklist

- [ ] Branch is up to date with `main`
- [ ] `make verify` passes locally
- [ ] New code has tests
- [ ] No `data/real_if/raw_dropbox/` content committed
- [ ] `docs/` updated if architecture changed
- [ ] `CHANGELOG.md` updated (if applicable)

## Reporting Issues

Use GitHub Issues. Include:

- Python version and OS
- Steps to reproduce
- Expected vs. actual behavior
- Relevant logs (truncate if long)

## License

By contributing, you agree that your contributions are licensed under the project's license (see `LICENSE`).