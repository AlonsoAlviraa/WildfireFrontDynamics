# Wildfire Front Dynamics — Development Makefile
# Usage: make <target>   (e.g., make verify)

PYTHON := python
PKG    := wildfire_front
TESTS  := tests

.PHONY: help install dev-install lint typecheck test test-cov test-spa verify clean format batch-fires smoke smoke-ops smoke-ml ml-lab-smoke ml-lab-freeze ml-lab-lofo ml-lab-next ml-lab-lofo-head-a demo industrial and-industrial-e2e demo-multi-ccaa pilot-honesty demo-third-party replay-third-party open-freshness dry-run-demo-third-party h3-dry-run metrics-hub operator operator-checklist operator-path operator-next ensayo

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

test-spa:  ## SPA industrial C2 pack (product_app + layout + plain_language + release flags + live ops)
	set PYTHONPATH=. && $(PYTHON) -m pytest tests/test_product_app.py tests/test_spa_layout.py tests/test_plain_language_app.py tests/test_check_release_flags.py tests/test_app_spa_security.py tests/test_spa_live_ops.py -q --tb=short

test-cov:  ## Run pytest with coverage report
	$(PYTHON) -m pytest $(TESTS) --cov=$(PKG) --cov-report=term-missing

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

ml-lab-freeze:  ## Lab freeze handoff card (not field promote)
	set PYTHONPATH=. && $(PYTHON) scripts/run_lab_ml_loop_v34_freeze.py

ml-lab-smoke:  ## Post-freeze lab smoke (CLI + rails + freeze; optional pytest via SMOKE_PYTEST=1)
	set PYTHONPATH=. && $(PYTHON) scripts/run_lab_ml_loop_v34_smoke.py $(if $(SMOKE_PYTEST),--pytest,)

ml-lab-lofo:  ## Multi-fire LOFO mask IoU scoreboard (not U1 ECE)
	set PYTHONPATH=. && $(PYTHON) scripts/run_lab_ml_loop_v34_lofo_board.py

ml-lab-next:  ## Next-signal readiness gate (W1 Head A LOFO; not metric retune)
	set PYTHONPATH=. && $(PYTHON) scripts/run_lab_ml_loop_v34_next_gate.py

ml-lab-lofo-head-a:  ## Build/eval LOFO Head A caches (W1/W2; needs ensemble weights)
	set PYTHONPATH=. && $(PYTHON) scripts/run_lab_ml_loop_v34_lofo_head_a.py --build

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

demo-third-party:  ## E1: build third-party evidence pack + zip (field_ops, no ML-live claim)
	set PYTHONPATH=. && $(PYTHON) scripts/build_demo_third_party_pack.py

replay-third-party:  ## E3: forensic replay (exit 0 iff replay_ok); pack under outputs/demo_third_party
	set PYTHONPATH=. && $(PYTHON) scripts/run_third_party_replay.py --bundle outputs/demo_third_party

open-freshness:  ## E5: audit open pack freshness_score + content_checksum (default emsr578)
	set PYTHONPATH=. && $(PYTHON) scripts/audit_open_pack_freshness.py --pack outputs/open_if/emsr578 --write

dry-run-demo-third-party:  ## H3 eng: rebuild pack + E3 replay + DRY_RUN_REPORT (human still required)
	set PYTHONPATH=. && $(PYTHON) scripts/dry_run_demo_third_party.py --no-zip

h3-dry-run:  ## H3 full path: teach → show → cheatsheet → demo-third-party → H3_DRY_RUN_REPORT
	set PYTHONPATH=. && $(PYTHON) scripts/run_h3_dry_run_path.py

operator:  ## Modo operario: semáforo + 4 actos + qué falta para GO_Q
	set PYTHONPATH=. && $(PYTHON) -m wildfire_front operator

operator-checklist:  ## Checklist operario (7 items; no cierra GO_Q)
	set PYTHONPATH=. && $(PYTHON) -m wildfire_front operator checklist

operator-path:  ## Ensayo 4 actos en secuencia (do --all; artefactos sin rebuild)
	set PYTHONPATH=. && $(PYTHON) -m wildfire_front operator do --all

ensayo: operator-path  ## Alias ES de operator-path (4 actos compactos)

operator-next:  ## Qué falta para GO_Q (humano H1; eng no cierra)
	set PYTHONPATH=. && $(PYTHON) -m wildfire_front operator next
