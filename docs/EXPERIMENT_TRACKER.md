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

**Priority stack (2026-07-15, `ebdc9a0`):** Dual product `ndws_v21`+`clm_v28` shipped (`docs/PRODUCTO_DUAL.md`). Anchors tooling → O1 PARTIAL / O5 NO_GO (only Tobarra confirmed). Hausdorff official BLOCKED; temporal proxy 5 IF.

### v26_physics15: Features rail — NO PROMOTE vs v21
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v26-physics15` COMPLETE
- **Single change:** `schema=physics15` (physics14 + wind_upslope)
- **Test IoU:** **0.221** | copy **0.150** | **Δ +0.071** | best_epoch **23** | n=979
- **vs v21:** IoU −0.005, Δ −0.005 — does **not** beat production
- **G1:** FAIL (need IoU≥0.25 and Δ≥+0.09)
- **Verdict:** **NO_PROMOTE**; next rail = temporal T=2 (`v27`)

### v27_temporal_t2: Temporal rail — RUNNING (S1)
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v27-temporal-t2`
- **Single change:** `sequence_length=2` on legacy17 residual+delta any_fire
- **Eval script:** `python scripts/eval_kaggle_v27_verdict.py` → `docs/V27_TEMPORAL_VERDICT.json`
- **Loop 1M:** `docs/LOOP_1M_MEJORA_CONTINUA.md` (S1 D0 started 2026-07-16)

### Loop 1M — S1 inventory
- **IF inventory:** `docs/IF_INVENTORY_S1.json` — 5 packs, 3 missing (ACOM2, Brazatortas, Polán)
- **Retuerta:** QA flag area ~4209 ha — `docs/RETUERTA_QA_FLAG.md` (exclude from O1)
- **Scorecard mes:** `python scripts/finalize_loop_1m_scorecard.py`

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

### v29_lofo_tobarra: Transfer LOFO — GO
- Held-out: Tobarra patches (n=300); train Cardoso+Estrella ACOM1/2
- Test IoU **0.494** | copy **0.328** | **Δ +0.165**
- Verdict: **GO_TRANSFER_LOFO** (industrial G2+)

### v30 batch (2026-07-17) — CLM transfer only (G1 NDWS killed)
Protocol: `clm_holdout_test_seed42_v1` (test=CARDOSO, n=200). Baseline **clm_v28** IoU **0.838** Δ **+0.196**.

| Exp | Single change | IoU | Δ copy | Growth IoU | Verdict |
|-----|---------------|-----|--------|------------|---------|
| **v30 ensemble honest** | soft-vote v28 + LOFO-CARDOSO | **0.868** | **+0.226** | 0.886 | **GO_PROMOTE** → `clm_ensemble_v30` |
| **v30_ema** | `ema_decay=0.999` FT | **0.846** | **+0.204** | 0.991 | **GO_PROMOTE** (runner-up) |
| v30_growth_es | early-stop `model_iou_growth` | 0.798 | +0.156 | 0.999 | **NO_PROMOTE** |
| LOFO4-only ensemble | mean of 4 LOFO | 0.806 | +0.165 | ~1.0 | **NO_PROMOTE** |
| leaky LOFO+v28 | includes train-on-Cardoso folds | 0.85–0.88 | +0.21–0.24 | high | **REJECTED_LEAKAGE** |

**Scorecard:** `docs/V30_ML_SCORECARD.json` · **Ensemble verdict:** `docs/V30_ENSEMBLE_VERDICT.json`  
**Scripts:** `scripts/eval_clm_ensemble.py`, `scripts/run_clm_v30_experiments.py`, `wildfire_front/ml/clm_eval.py`  
**Product:** `models/clm_ensemble/manifest.json` + catalog `clm_ensemble_v30`

### v31 metric push (2026-07-17)
Protocol: same holdout test (CARDOSO). Champion v30 pair equal IoU **0.8683** Δ **+0.2265**.

| Exp | Single change | Test IoU | Δ | Verdict |
|-----|---------------|----------|---|--------|
| weighted pair | mix w on VAL | 0.8683 | +0.2265 | NO (equal already best) |
| threshold | thr on VAL | 0.8579 | +0.216 | NO |
| **triple weighted** | v28+EMA+LOFO mix 0.4/0.3/0.3 | **0.8702** | **+0.2284** | **GO_SOFT → product** |
| continue FT v28 | lr=1e-4 from v28 | 0.788 | +0.146 | NO_PROMOTE |

**Scorecard:** `docs/V31_ML_SCORECARD.json` · **Script:** `scripts/run_clm_v31_metric_push.py`

### ML loop 3-way (2026-07-17) — continuous iteration
Script: `python scripts/run_ml_loop_3way.py --rounds N`  
Tracks (cycle each round):

1. **multi_if** — FT multi-fire LOFO-CARDOSO train  
2. **source_mix** — per-source soft-vote mix (LOFO tests → Cardoso recipe)  
3. **multi_obj** — early-stop `multi_full_growth*` = fullΔ + λ·growth IoU  

| Round | multi_if holdout IoU | source_mix Cardoso Δ | multi_obj holdout IoU | Promote? |
|-------|----------------------|----------------------|------------------------|----------|
| 1 | 0.799 (v21 init) | Δ 0.228 (mix 0.4/0.3/0.3) | 0.788 | No |
| 2 | 0.802 (v28 init) | Δ 0.225 (mix 0.4/0.4/0.2) | 0.823 (λ=0.25) | No |

**Champion after round 4 (honest):** `r4_v28_plus_multi_if` IoU **0.8709** Δ **+0.2291**  
= soft-vote **v28 + multi_if** (0.5/0.5); multi_if trained on LOFO-CARDOSO train only.  

**Champion after round 8 (honest, promoted):** `source_mix_transfer_non_cardoso`  
IoU **0.8952** Δ **+0.2534** · mix ≈ **0.30 / 0.27 / 0.43** (v28 + EMA + multi_if)  
Mix = average of best mixes on **non-Cardoso** LOFO folds; multi_if snapshotted.  
Product: `models/clm_ensemble/manifest.json` version **`clm_ensemble_v33`**.  

**Leakage rejected:**
- `source_mix_cardoso_recipe` IoU 0.888 — LOFO CARDOSO/test ≡ holdout test.
- **v34 Tobarra/LA as 4th member** IoU ~0.90 — LOFO-tobarra / LOFO-LA trains **include Cardoso**; not eligible for holdout GO.

**v34 loop upgrades (in progress):**
- Growth-prob **cache** for mix×threshold sweeps (no U-Net re-inference per mix).
- Denser mix grid + VAL-only threshold sweep (thr=0.4 overfits VAL; thr=0.5 keeps champion).
- multi_if: rotate init (freeze / best-holdout / v28 / v21) + EMA + clw/pw variants.
- multi_obj triple uses **frozen** multi_if, not live mid-train weights.

Scorecard: `docs/ML_LOOP_3WAY_SCORECARD.json`

### O3 temporal Tobarra
- Strict band 2/3 GO; late ratio 0.478; wide band 3/3

### v27_temporal_t2: COMPLETE — NO_PROMOTE
- Test IoU **0.2253** | Δ **+0.0755** | best_epoch 30 | flat vs v21 (0.2256/+0.076)
- G1: FAIL | next: v27b T=3 last temporal shot then KILL if fail

