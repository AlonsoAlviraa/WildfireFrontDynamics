# Metrics lift — large LOFO grid on Kaggle (2026-08-06)

## Goal

Use **more GPU compute** than single-recipe runs: one multi-config residual LOFO grid
on sealed core-3 packs (no Hellín primary), multi-init, multi-lr / growth / warm-start.

## What was launched

| Item | Value |
|------|--------|
| Dataset | `alonsoalviraaaa/wfd-lofo-grid-inits` (~41 MB zip: sealed packs + multi_if/v28/v30/v21 + recover_v2 fold weights) |
| Full grid kernel | [wfd-metrics-lift-lofo-grid-sealed](https://www.kaggle.com/code/alonsoalviraaaa/wfd-metrics-lift-lofo-grid-sealed) |
| Script | `kaggle_job/run_metrics_lift_lofo_grid.py` |
| Configs | **14** full core-3 trainings (see GRID in script) |
| Shards (optional parallel) | `scripts/push_kaggle_lofo_grid_shards.py` → grid-a/b/c (push blocked while Kaggle API 500) |

### Grid axes

- **Inits:** multi_if, multi_if_r8, v30_ema, v28_clm_ft, v21, warm recover_v2 per-fold
- **LR:** 3e-5 … 2e-4
- **Epochs:** 24–40, patience 8–20
- **ACOM2 growth:** change_w 8–16, pos_w 7–14
- **Batch:** 8 / 16
- **Architecture:** residual small only (deep-research: no larger U-Net default)

### Expected wall time

~14 configs × 3 folds × multi-epoch residual on T4 ≈ **hours** (session-length). Intermediate `metrics_lift_grid_board.json` is rewritten after each config.

## Rails

- fusion OFF · IoU ≠ ROS · no Tobarra KEEP reopen · no Hellín primary · no champion auto-promote

## Results (downloaded — 14/14 configs, ~28 min T4)

| Rank | Config | mean | min | Δmean | Δmin | E2 KEEP | G1 | G2 |
|-----:|--------|-----:|----:|------:|-----:|:-------:|:--:|:--:|
| 1 | **force_train_multi_if** | **0.7857** | **0.7071** | +0.0277 | +0.0139 | YES | YES | no |
| 2 | v2_anchor | 0.7853 | 0.7033 | +0.0273 | +0.0101 | YES | YES | no |
| 3 | mild_growth_balanced | 0.7848 | 0.7039 | +0.0268 | +0.0107 | YES | YES | no |
| 4 | long_lowlr_multi_if | 0.7843 | 0.7062 | +0.0262 | +0.0130 | YES | YES | no |
| 5 | growth_extreme_acom2 | 0.7827 | 0.7007 | +0.0246 | +0.0075 | YES | YES | no |
| 6 | batch16_lr1e4 | 0.7805 | 0.7049 | +0.0224 | +0.0117 | YES | YES | no |
| 7 | long_lowlr_acom2_heavy | 0.7800 | 0.7060 | +0.0220 | +0.0128 | YES | YES | no |
| 8 | warm_recover_v2 | 0.7764 | 0.7003 | +0.0183 | +0.0071 | YES | no | no |
| 9–14 | other inits / high lr | ≤0.7767 | ≤0.6996 | — | — | no | no | no |

### vs prior E_recover_v2 (0.7816 / 0.7023)

- Best grid **force_train_multi_if**: mean **+0.0041**, min **+0.0048** vs v2
- **G2 still open** (min 0.707 ≪ 0.720; gap ~−0.013)
- Many runs early-stop at epoch 1 on multi_if VAL peak — low-lr/high-patience still helps slightly

### Artifacts

- Board: `outputs/kaggle_metrics_lift_grid/metrics_lift_grid_board.json`
- Best folds: `outputs/kaggle_metrics_lift_grid/grid/force_train_multi_if/`
- Kill scores: `outputs/ml_eval/lab_loop/grid_scores/`
- Best promoted board candidate: `E_grid_force_train_multi_if`

## After download

1. Score all configs with `score_metrics_lift_grid_board.py`
2. Compare leaderboard vs E_recover_v2
3. Promote only if E2 KEEP and (optionally) G2 for T2; PR4 human for champion

## Re-push parallel shards (when API healthy)

```powershell
python scripts/push_kaggle_lofo_grid_shards.py
```
