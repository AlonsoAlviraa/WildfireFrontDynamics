# MEMORY — Loop engineering short notes

Minimal working memory for the dual-product loop.  
Full experiment log: `docs/EXPERIMENT_TRACKER.md`.  
**Canonical snapshot:** `docs/CURRENT_STATE.md` (2026-08-05).  
**Long form:** `docs/PROJECT_STATUS.md`. **Goals:** `docs/goals/README.md`.

## Current product baselines (do not regress without evidence)

| Layer | ID | Metric | Value |
|-------|-----|--------|------:|
| ML research | `ndws_v21` | NDWS test IoU / Δ copy | 0.226 / +0.076 |
| ML Spain single | `clm_v28` | CLM holdout IoU / Δ copy | 0.838 / +0.196 |
| ML Spain ensemble | `clm_ensemble_v34` | U1 TEST honest IoU / ECE (lab) | ~**0.86** / ~**0.15** |
| ML Spain catalog | `clm_ensemble_v34` | holdout IoU provenance only | **0.8963** / +0.2545 — not live certainty |
| ML lab surface | same | reject thr ~0.80 | **iter1 reject only** (ECE thrash stopped) |
| ML multi-fire | Head A / LOFO | pack LOFO ~0.76; Tobarra Head A ~0.49 | hard fire honesty |
| Ops | `front_dynamics_v1` | ROS from observed LWIR | geometry only (not IoU) |
| Decision | Decision Card | GO / HOLD / ABSTAIN | holdout conf cap **0.75**; field_ops fusion **OFF** |

Catalog: `models/catalog.json`. Weights are local (`*.pt` gitignored).

## Gates (2026-08-05)

- **GO_ENG** true · **GO_MES** true (mínimo; O1 Tobarra+Hellín; P1 two-real smoke)
- **GO_Q** partial (**H1** demo+acta tercero pending — primary product residual)
- `ml_product_go` **true** (lab; U1 TEST honest + promote 2026-08-07) · `u1_test_honest` true · field_ops fusion **OFF** · GO_MES still H1-blocked
- Graph **v6.1**: primary = human demo + E1–E3; research R\* (**0 h retrain** as main)
- **ML mega goals CLOSED:** W3 **MET** · Tobarra KEEP-or-KILL → **KILL** (fresh IoU 0.4776, K1 fail)

## What works

- Residual U-Net train path: `kaggle_job/run_unet_training_v21.py` + `kernel-metadata-v21.json`
- CLM ensemble soft-vote with VAL-only temperature/mix calibration
- Incident runtime outbox + Decision Card fuse ops / open / ML without training on fused labels
- Open CEMS + REDIAM AND + RAI EXT packs; demo multi-CCAA + piloto honesty
- Integrity graph c0–c2 shipped holdout/fusion honesty rails
- **Operator UX PLATEAU** (iters 1–17): bare CLI → operator; residual = H1 human. Log: `docs/OPERATOR_UX_LOOP_LOG.md`
- **ML lab product CLI** + loop freeze/smoke/lofo/next · W3 multi-fire Head A · Tobarra kill protocol
- Entry: `docs/ML_PRODUCT_START_HERE.md` · status: `docs/PLAN_ML_PRODUCT_STATUS.json`

## What does not (do not re-promote)

- A3C-LSTM product claims (legacy under `models/model.py`, archive mega scripts)
- Active paths to `run_mega_training.py` / `run_unet_training_v13.py` (archive only)
- Tuning ensemble mix on holdout test / LOFO-CARDOSO
- Claiming system reliability PASS without a real reliability gate result
- Using holdout quality as live certainty or ML-only HOLD under field_ops
- More autonomous honesty cycles as substitute for H1 / third-party demo
- **Tobarra LOFO KEEP** after fresh train KILL (K1 vs Head A 0.489) — do not thrash same recipe
- Beats-copy alone as KEEP; IoU as ROS

## Failed hypotheses (high level)

See also `RULES.md` and early tracker entries:

1. Halving LR alone (v11 era) did not fix A3C collapse.
2. Extreme `pos_weight` hurt recall.
3. Freeze-conv variants that underperformed baseline stay archived.
4. ECE post-hoc / refit on same U1 TEST did not improve ECE (iter2–3) — stop thrash.
5. Fresh Tobarra LOFO init-v21 (2026-08-05) IoU 0.477 < Head A 0.489 → KILL under K1.

## After each loop iteration

1. Log the experiment in `docs/EXPERIMENT_TRACKER.md` (one change, metrics, verdict).
2. Update this file only if **product baseline or active path** changed.
3. Refresh `docs/CURRENT_STATE.md` + `docs/PROJECT_STATUS.md` / `scripts/run_plan_cycle.py` when gates move.
4. Do not invent metrics; cite manifests under `models/*/manifest.json`.
5. Closed mega goals: only re-audit, do not re-open without new signal (`docs/goals/README.md`).
