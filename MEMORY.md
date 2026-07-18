# MEMORY — Loop engineering short notes

Minimal working memory for the dual-product loop. Full experiment log: `docs/EXPERIMENT_TRACKER.md`.

## Current product baselines (do not regress without evidence)

| Layer | ID | Metric | Value |
|-------|-----|--------|------:|
| ML research | `ndws_v21` | NDWS test IoU / Δ copy | 0.226 / +0.076 |
| ML Spain single | `clm_v28` | CLM holdout IoU / Δ copy | 0.838 / +0.196 |
| ML Spain ensemble | `clm_ensemble_v34` | holdout IoU / Δ / growth | **0.8963** / **+0.2545** / 0.9071 |
| Ops | `front_dynamics_v1` | ROS from observed LWIR | geometry only (not IoU) |
| Decision | Decision Card | GO / HOLD / ABSTAIN | abstain if sources weak |

Catalog: `models/catalog.json`. Weights are local (`*.pt` gitignored).

## What works

- Residual U-Net train path: `kaggle_job/run_unet_training_v21.py` + `kernel-metadata-v21.json`
- CLM ensemble soft-vote with VAL-only temperature/mix calibration
- Incident runtime outbox + Decision Card fuse ops / open / ML without training on fused labels
- Open CEMS packs as optional Decision Card sources

## What does not (do not re-promote)

- A3C-LSTM product claims (legacy under `models/model.py`, archive mega scripts)
- Active paths to `run_mega_training.py` / `run_unet_training_v13.py` (archive only)
- Tuning ensemble mix on holdout test / LOFO-CARDOSO
- Claiming system reliability PASS without a real reliability gate result

## Failed hypotheses (high level)

See also `RULES.md` and early tracker entries:

1. Halving LR alone (v11 era) did not fix A3C collapse.
2. Extreme `pos_weight` hurt recall.
3. Freeze-conv variants that underperformed baseline stay archived.

## After each loop iteration

1. Log the experiment in `docs/EXPERIMENT_TRACKER.md` (one change, metrics, verdict).
2. Update this file only if **product baseline or active path** changed.
3. Do not invent metrics; cite manifests under `models/*/manifest.json`.
