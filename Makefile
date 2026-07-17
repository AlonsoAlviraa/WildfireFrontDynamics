# Wildfire Front Dynamics — Development Makefile
# Usage: make <target>   (e.g., make verify)

PYTHON := python
PKG    := wildfire_front
TESTS  := tests

.PHONY: help install dev-install lint typecheck test test-cov verify clean format batch-fires smoke smoke-ops smoke-ml demo industrial

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

verify: lint typecheck test  ## Run all quality gates (lint + typecheck + test)

clean:  ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

batch-fires:  ## Process all real wildfire sequences through the ingest pipeline
	set PYTHONPATH=. && $(PYTHON) scripts/batch_process_fires.py

smoke:  ## Quick smoke test of the ML pipeline
	$(PYTHON) scripts/smoke_test_finetune.py

smoke-ops:  ## Incident runtime synthetic smoke
	set PYTHONPATH=. && $(PYTHON) scripts/smoke_incident_runtime.py

smoke-ml:  ## CLM v28 + ensemble v34 holdout smoke
	set PYTHONPATH=. && $(PYTHON) scripts/smoke_production_products.py --products clm_v28,clm_ensemble_v34 --max-patches 12

demo:  ## One-command dual product demo (ops + ML)
	set PYTHONPATH=. && $(PYTHON) scripts/demo_dual_product.py

industrial: test smoke-ops  ## Unit tests + ops smoke

metrics-hub:  ## Build full metrics hub + decision card + dashboard
	set PYTHONPATH=. && $(PYTHON) scripts/build_metrics_hub.py

reliability:  ## Reliability / abstention gate (system five-nines bound)
	set PYTHONPATH=. && $(PYTHON) scripts/reliability_gate.py

product-gate: reliability metrics-hub  ## Paid-value product gates
