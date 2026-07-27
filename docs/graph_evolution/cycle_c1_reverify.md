# Cycle c1-reverify — complete

**HEAD during scan:** `60d4d55`  
**Confirmed:** 6 (2 bugs + 4 suggestions)

## Bugs fixed

1. **HR-catalog-holdout-conf-1** — holdout_quality no longer saturates to 1.0 in confidence_pred (research-only conf_zero path).
2. **HR-ml-only-legacy-holdout-ok** — `ml_ok` only from live actionable; catalog never enables HOLD.

## Suggestions fixed

3. Core docs VISION/MEMORY/ARCHITECTURE/RULES — U1 pitch + provenance catalog.
4. METRICS_HUB fusion note updated.
5. Lab-synthetic cannot `--apply-policy` (and refuses docs ML_PRODUCT path).

## Commit

Follow-up honesty commit on main after c1 (see git log).

## Pilot regression (parallel)

38/38 pytest + ruff format green (`wfd-pilot-regression`).
