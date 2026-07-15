# Experiment Tracker — WildfireFrontDynamics

> **Rule:** Update after every Kaggle kernel completes.

---

## Current Production Baseline

| Version | Date | IoU@0.5 | Δ vs copy (full) | Δ vs dilated (changed) | best_epoch | Status |
|---------|------|---------|------------------|------------------------|------------|--------|
| v14 | 2026-07-10 | 0.239* | -0.55* | — | 8 | Superseded |
| v21 | 2026-07-14 | **0.226** | **+0.076** | +0.041 | 6 | **PRODUCTION** |

\* v14 on original 619-patch test; cross-protocol on 979 patches: IoU **0.227**, Δ **+0.077**.

**Manifest:** `models/production/manifest.json`  
**Inference:** `wildfire_front/ml/spread_predictor.py`  
**Audit:** `docs/PRODUCTION_READINESS_AUDIT.md`

**Overnight mega v1:** ERROR — preprocess path mismatch (0 patches).  
**Overnight mega v2:** COMPLETE but still 0 patches (root-cause: silent empty preprocess; fail-fast added in `kaggle_common`).

**Observatorio packs (2026-07-15):** Tobarra + Cardoso + Hellín en `outputs/observatorio/` — gates A1/A2/A5 PASS (scorecard).

---

## Experiment Log

### Feature methodology foundation (2026-07-15)
- **Docs:** `ML_FEATURE_METHODOLOGY.md`, `ML_TRANSFER_PROTOCOL.md`, `ML_LOOP_RAILS.md`
- **Schema:** `physics14` in `feature_schema.py` (tmin/tmax + drought/FFMC)
- **CLM holdout v1:** `artifacts/clm_ndws_patches/holdout_v1/` (event split 70/15/15)
- **G2 v21 on CLM test:** IoU 0.798, copy 0.642, **Δ +0.157 → GO** (protocol `clm_holdout_test_seed42_v1`)
- **Signal analysis:** `outputs/ml_eval/feature_signal_report.json` (CLM train sample)

### v28_clm_ft: Transfer rail — BEST CLM result so far
- **Script:** `scripts/run_clm_finetune_v28.py` (local CPU, 12 ep early-stop @6)
- **Single change:** fine-tune v21 on CLM `holdout_v1/train`; eval **test**
- **Test IoU:** **0.838** | copy **0.642** | **Δ +0.196**
- **Zero-shot v21 same test:** IoU 0.798 | **Δ +0.157**
- **Beats zero-shot:** yes (+0.039 Δ, +0.040 IoU)
- **G2:** PASS | **Verdict:** promote as **CLM specialist weights** (not NDWS production)

### v25_physics14: Features rail — NO PROMOTE vs v21
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v25-physics14` COMPLETE
- **Single change:** `--schema physics14` (tmin/tmax + drought/FFMC), residual+delta, any_fire
- **IoU full:** 0.224 | **Δ full:** +0.074 | copy 0.150 | best_epoch 18 | test 979
- **vs v21:** IoU −0.002, Δ −0.002 — does **not** beat production
- **G1:** FAIL | **Verdict:** physics14 alone is not the leap; try interactions / temporal / keep v21

### v24: clean12 + changed train / any_fire eval — MARGINAL vs v21, NO M1
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v24` COMPLETE
- **Change:** hybrid data — train `changed` + val/test `any_fire`; schema clean12; residual+delta; change_loss_weight=8
- **IoU full:** **0.230** | **Δ full:** **+0.080** | **Δ changed:** +0.072
- **copy:** 0.150 | **best_epoch:** 18 | train 11964 / test 979
- **vs v21:** IoU +0.004, Δ +0.004 (slightly better)
- **M1 gate (IoU≥0.25, Δ≥0.09):** **FAIL** (not a leap)
- **Verdict:** Optional experimental checkpoint; **keep v21 production**. No promote.

### v23_clean12: Clean 12-channel schema — NO PROMOTE
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v23-clean12` (v2)
- **Parent:** v21 | **Change:** `--schema clean12` (elevation, wind sin/cos, no constant channels); **no CLM merge** (17ch mismatch)
- **IoU full:** 0.215 | **Δ full:** +0.065 | **Δ changed:** **+0.074**
- **copy:** 0.150 | **best_epoch:** 20 | train 12000 (NDWS only)
- **vs v21:** IoU −0.011, Δ full −0.011, Δ changed **+0.033**
- **Verdict:** Keep **v21** production. clean12 improves changed-pixels but not full-grid IoU; do not promote.

### v22: Changed-Only Filter — NEUTRAL (better Δ changed)
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v22`
- **Parent:** v21 | **Change:** `--filter-mode changed`
- **IoU full:** 0.225 | **Δ full:** +0.075 | **Δ changed:** +0.081 (vs v21 +0.041)
- **Val peak IoU:** 0.255 (epoch 38) — test did not beat v21
- **Verdict:** Keep v21 production; v22 feeds overnight EMA/long experiments

### v21: Delta Target + Residual — PRODUCTION
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v21`
- **Parent:** v20
- **Change:** `--target-mode delta` (only variable vs v20)
- **IoU full @0.5:** 0.226 | **copy:** 0.150 | **Δ full:** +0.076
- **Δ vs dilated copy (changed):** +0.041 | legacy naive: +0.214
- **Early-stop:** `improvement_vs_copy_iou`
- **Verdict:** First model beating copy on full grid with honest protocol

### v20: Residual + Changed-Weighted — FAILED
- **IoU full:** 0.050 | **Δ full:** -0.100
- **Verdict:** Residual alone did not recover IoU; over-predicts (precision ~5%)

### v19: Changed-Weighted — DIAGNOSTIC ONLY
- **IoU full:** 0.052 | legacy Δ changed: +0.877 (metric was tautological)
- **Verdict:** Led to metrics fix; not production

### v14: U-Net Small — SUPERSEDED
- **IoU:** 0.239 on original test; still strong on cross-protocol (0.227)
- **Verdict:** Valid baseline until v21; keep for ablations

---

## Metric Definitions (v2 — honest)

| Metric | Meaning |
|--------|---------|
| `improvement_vs_copy_iou` | Model IoU − naive copy IoU (full grid) — **primary** |
| `improvement_vs_copy_iou_changed` | Model − **dilated** copy on changed pixels |
| `legacy_improvement_vs_naive_copy_iou_changed` | Inflated; equals `model_iou_changed` when naive copy changed = 0 |

---

## Failed Hypotheses (do not retry)

| Hypothesis | Evidence |
|------------|----------|
| changed_weighted alone fixes full IoU | v19/v20 IoU ~0.05 |
| residual without delta target | v20 failed |
| Tier-1 +0.87 = breakthrough | copy_changed always 0 |

---

## Accepted Hypotheses

| Hypothesis | Evidence |
|------------|----------|
| Delta target + residual beats copy (full) | v21 Δ +0.076 |
| Cross-protocol eval required | v14≈v21 only when aligned |
| Dilated-copy baseline for changed pixels | `ndws_metrics.py` fix |