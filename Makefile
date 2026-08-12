# Wildfire Front Dynamics — Development Makefile
# Usage: make <target>   (e.g., make verify)

PYTHON := python
PKG    := wildfire_front
TESTS  := tests

.PHONY: help install dev-install lint typecheck test test-cov test-spa verify clean format batch-fires smoke smoke-ops smoke-ml demo industrial and-industrial-e2e demo-multi-ccaa pilot-honesty

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package (basic)
	$(PYTHON) -m pip install -e .

dev-install:  ## Install package with dev dependencies
	$(PYTHON) -m pip install -e ".[dev]"

format:  ## Auto-format code with ruff
	$(PYTHON) -m ruff check $(PKG) $(TESTS) --fix
	$(PYTHON) -m ruff format $(PKG) $(TESTS)

lint:  ## Lint with ruff (check only)
	$(PYTHON) -m ruff check $(PKG) $(TESTS)

typecheck:  ## Type-check with mypy
	$(PYTHON) -m mypy $(PKG)

test:  ## Run pytest suite
	$(PYTHON) -m pytest $(TESTS) -q

test-cov:  ## Run pytest with coverage report
	$(PYTHON) -m pytest $(TESTS) --cov=$(PKG) --cov-report=term-missing


test-spa:  ## SPA industrial C2 pack (product_app + layout + plain_language + release flags + live ops + honesty UI)
	set PYTHONPATH=. && $(PYTHON) -m pytest tests/test_product_app.py tests/test_spa_layout.py tests/test_plain_language_app.py tests/test_check_release_flags.py tests/test_app_spa_security.py tests/test_spa_live_ops.py tests/test_spa_honesty_ui.py -q --tb=short

verify: lint typecheck test  ## Run all quality gates (lint + typecheck + test)

clean:  ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

batch-fires:  ## Process all real wildfire sequences through the ingest pipeline
	set PYTHONPATH=. && $(PYTHON) scripts/batch_process_fires.py

smoke: smoke-ml  ## Product ML smoke (alias for smoke-ml; not legacy A3C)

smoke-ops:  ## Incident runtime synthetic smoke
	set PYTHONPATH=. && $(PYTHON) scripts/smoke_incident_runtime.py

smoke-ml:  ## CLM v28 + ensemble v34 holdout smoke (product path)
	set PYTHONPATH=. && $(PYTHON) scripts/smoke_production_products.py --products clm_v28,clm_ensemble_v34 --max-patches 12

demo:  ## One-command dual product demo (ops + ML)
	set PYTHONPATH=. && $(PYTHON) scripts/demo_dual_product.py

industrial: test smoke-ops  ## Unit tests + ops smoke

metrics-hub:  ## Build full metrics hub + decision card + dashboard
	set PYTHONPATH=. && $(PYTHON) scripts/build_metrics_hub.py

reliability:  ## Reliability / abstention gate (system five-nines bound)
	set PYTHONPATH=. && $(PYTHON) scripts/reliability_gate.py

product-gate: reliability metrics-hub  ## Paid-value product gates

and-industrial-e2e:  ## Andalucía REDIAM industrial open E2E (fetch+inventory+pack+verify; no live WFS in verify by default)
	set PYTHONPATH=. && $(PYTHON) scripts/fetch_rediam_perimeters.py --years 2022,2023,2024,2025
	set PYTHONPATH=. && $(PYTHON) scripts/inventory_rediam_and.py --no-firms
	set PYTHONPATH=. && $(PYTHON) scripts/build_and_if_pack.py --selection data/open_if/rediam_andalucia/inventory/selection_gold.json --tier all --skip-dnbr
	set PYTHONPATH=. && $(PYTHON) scripts/verify_and_industrial_e2e.py

demo-multi-ccaa:  ## Build multi-CCAA demo hub (Tobarra OPS + Níjar AND + Caminomorisco EXT)
	$(PYTHON) scripts/build_demo_multi_ccaa.py

pilot-honesty:  ## Offline pilot honesty cards + docs report (fixtures; no weights)
	set PYTHONPATH=. && $(PYTHON) scripts/run_pilot_honesty_card.py --mode offline --fixture-root tests/fixtures/pilot --write-docs-report --generated-at 2026-07-24T00:00:00+00:00
