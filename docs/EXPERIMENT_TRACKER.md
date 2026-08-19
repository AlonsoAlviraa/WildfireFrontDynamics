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

### rcda_sealed_v1: event-disjoint U-Net/RCDA — KERNEL v4 RUNNING
- **Hypothesis:** A VAL-selected U-Net/RCDA with train-only norm, sin/cos wind, distance-to-front, horizon and focal-Tversky beats dilated-copy on the sealed TEST without touching TEST during selection.
- **Change:** new sealed trainer (`wildfire_front/ml/rcda_sealed.py`) + Caldor ERC/HRRR valid-time contract.
- **Kernel:** `alonsoalvira/wfd-rcda-sealed-v1` version 4 (GPU T4, **no internet**).
- **Inputs:** `alonsoalvira/wfd-rcda-archive` (26.2 GB extracted tree, 6501 train npy) + `alonsoalvira/wfd-rcda-sealed` + embedded protocol blobs.
- **Protocol:** TRAIN 5552 / VAL 928 / TEST 1651, event-disjoint
- **Honest sealed baseline:** dilated-copy TEST IoU **0.1108** (radius selected on VAL=3 px).
- **Not results:** published RCDA IoU 0.308 (contaminated TEST protocol); local smoke IoU 0.059 (8/4 samples, 1 epoch).
- **v1/v3:** ERROR before any TRAIN step (missing module; then missing protocol after Zenodo).
- **Verdict:** pending kernel completion; do not promote until TEST-once vs 0.1108

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
- **Eval script:** `python scripts/archive/eval_kaggle_v27_verdict.py` → `docs/archive/V27_TEMPORAL_VERDICT.json` (archived G1)
- **Loop 1M:** `docs/LOOP_1M_MEJORA_CONTINUA.md` (S1 D0 started 2026-07-16)

### Loop 1M — S1 inventory
- **IF inventory:** `docs/IF_INVENTORY_S1.json` — 5 packs, 3 missing (ACOM2, Brazatortas, Polán)
- **Retuerta:** QA flag area ~4209 ha — `docs/RETUERTA_QA_FLAG.md` (exclude from O1)
- **Scorecard mes:** `python scripts/finalize_loop_1m_scorecard.py`

---

## Experiment Log

### RCDA sealed paper campaign (2026-08-19) — RUNNING, TEST SEALED

- **Protocol:** 886 fires / 8,131 samples; TRAIN 596/5,552, VAL 106/928,
  TEST 184/1,651; event-disjoint and TRAIN-only normalization.
- **Frozen VAL winner:** `resunet_hybrid_event_balanced_v1`, event-macro
  growth IoU 0.20867 at epoch 28 and threshold 0.45; event-bootstrap 95% CI
  [0.18047, 0.24000]. Its paired delta over the previous low-LR leader is
  +0.01456 (95% CI [-0.00111, 0.03307]; wins on 50.94% of fires). This is
  model-selection evidence on VALIDATION, not TEST.
- **Independent reproducibility:** a second private T4 execution produced a
  byte-identical checkpoint (`2bd3729438de...`), identical selected metrics,
  and exactly the same 106 per-fire IoUs (maximum absolute difference 0).
- **Corrected geometric TEST comparator:** dilation radius 6 selected on VAL
  event-macro IoU, TEST 0.12724. Legacy pooled-selection radius 3 is retained
  but superseded.
- **VAL ensemble audit:** equal-weight combinations were rejected. A bounded
  low-LR-weight search found `low3_phase1_growth` (weights 3:1:1),
  event-macro IoU 0.19736 at threshold 0.40, delta +0.00325 versus `low_lr`.
  Paired event-bootstrap 95% CI [-0.00004, 0.00681], wins 49.06%; descriptive,
  not confirmatory. It was excluded from the frozen recipe after the
  event-balanced run became the winner; the only retained ensemble is the
  preregistered mean probability across the winner's three seeds.
- **VAL spatial decoder:** fixed threshold 0.80, one-pixel dilation, and t0
  connectivity reached 0.19839 (delta +0.00428; paired 95% CI
  [-0.00126, 0.00991]). It was excluded from the frozen recipe because the
  low-LR run did not remain the winner; applying it to the event-balanced model
  would be an unregistered cross-run transfer.
- **TRAIN sampler audit:** 15/5,552 zero-growth samples; default event-mass
  CV 0.647 versus approximately 0 for `uniform_events`; all 5,552 transitions
  retain every t0-positive pixel. The two sampler candidates now match the
  low-LR leader in architecture, target, LR, epoch cap, patience, loss and seed;
  only event-mass exponent or sampler changes.
- **GCP long run recovered:** `resunet_hybrid_long_v2` reached a finite best at
  epoch 13, VAL event-macro IoU 0.16766 (threshold 0.20), then produced a
  non-finite loss at epoch 16. A full scan found 0/13,002 non-finite TRAIN NPY
  files. The finite checkpoint was re-evaluated on VAL only and the run is
  explicitly marked truncated; TEST remained sealed.
- **Kaggle T4 precision result:** `resunet_hybrid_precision_v3` reached its
  finite best at epoch 13, VAL event-macro IoU 0.17056 (threshold 0.05), then
  encountered a non-finite loss at epoch 21. Its finite checkpoint was
  re-evaluated on all 928 VAL samples and is explicitly marked truncated; it
  did not beat the phase-1 leader and never accessed TEST.
- **Completed growth-only run:** `resunet_growth_v1` finished normally at epoch
  18 with VAL event-macro IoU 0.17395, pooled IoU 0.16184, threshold 0.95 and
  far-front recall 0.06850. It did not beat the low-LR hybrid leader; TEST was
  not evaluated. The leader's paired advantage was +0.02016 across 106 fires
  (event-bootstrap 95% CI [0.00786, 0.03310]; wins on 57.55%).
- **Matched growth-only low-LR run:** `resunet_growth_low_lr_v1` recovered to
  0.18804 event-macro IoU (95% CI [0.16821, 0.20843]), pooled IoU 0.14030,
  epoch 25 and threshold 0.95. It ranks third. Against the then-matched hybrid
  low-LR run, the hybrid advantage was +0.00607 (95% CI [-0.00502, 0.01720]);
  against the frozen event-balanced winner the paired delta is +0.02063 (95%
  CI [-0.00076, 0.04444]). These target-mode contrasts remain descriptive.
- **Completed event-balanced run:** `resunet_hybrid_event_balanced_v1` crossed
  the preregistered 0.20 stopping threshold at 0.20867. Therefore the later
  `uniform_events` and FiLM candidates were not launched. The source datasets
  remained private and shared read-only on the alternate Kaggle account.
- **Frozen final contract:** one raw primary recipe and the mean-seed
  probability ensemble were frozen for seeds 11/29/47. The old low-LR spatial
  decoder and weighted checkpoint ensemble were excluded as run-mismatched.
  WFIGS zero-shot and adaptation may proceed only from this frozen recipe.
- **Final execution audit:** the first final Kaggle kernel failed after 7.7 s
  while importing the generated script because JSON `false` had been embedded
  as a Python name. It produced no seed report or checkpoint and did not load
  or evaluate TEST. The serializer and an AST-level regression test were fixed
  in PR #65; TEST therefore remains sealed for the corrected execution.
- **Pre-TEST registry:** `PRETEST_DECISION_LOG.json` records evidence, numerical
  recovery, gradient-safety amendment and code/runtime hashes; the future
  frozen recipe must carry its SHA-256.
- **Engineering verification:** 1,365 tests collected; the full `not slow`
  suite passed 1,363 with 1 skip after deselecting exactly one known live-data
  assertion whose locally modified NDWS report contains one ready pack instead
  of the required two. The RCDA/WFIGS/UI focused suite passes 130/130.
- **Artifacts:** `outputs/ml_eval/rcda_paper_nightwatch_20260819/` and
  `docs/RCDA_PAPER_PROTOCOL_2026.md`.

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
Product was **`clm_ensemble_v33`**.

**Champion v34 (honest, promoted — CLOSED):** `source_mix_val_temp_calibrated`  
IoU **0.8963** Δ **+0.2545** · growth **0.9071**  
mix **0.28 / 0.32 / 0.40** · temperatures **0.7 / 0.7 / 1.3** (v28, EMA, multi_if)  
Selection on holdout **VAL only** (no Cardoso). Gain vs v33: IoU/Δ **+0.0010**, growth **+0.018**.  
Product: `models/clm_ensemble/manifest.json` version **`clm_ensemble_v34`**.

**Loop close-out:** 3-way infinite loop stopped after **30 rounds** at plateau (temps reaffirm champion; multi_if / multi_obj no GO). Status `STOPPED_PLATEAU`.

**Leakage rejected:**
- `source_mix_cardoso_recipe` IoU 0.888 — LOFO CARDOSO/test ≡ holdout test.
- **Tobarra/LA as 4th member** IoU ~0.90 — LOFO trains **include Cardoso**; not eligible for holdout GO.

**Loop upgrades (landed):**
- Growth-prob **cache** for mix×threshold/temp sweeps.
- multi_if: rotate init + EMA + clw/pw; freeze-protected members.
- Production inference supports `member_temperatures` (logit / T).
- Scorecard save never demotes a stronger external champion.

Scorecard: `docs/ML_LOOP_3WAY_SCORECARD.json`

### O3 temporal Tobarra
- Strict band 2/3 GO; late ratio 0.478; wide band 3/3

### v27_temporal_t2: COMPLETE — NO_PROMOTE
- Test IoU **0.2253** | Δ **+0.0755** | best_epoch 30 | flat vs v21 (0.2256/+0.076)
- G1: FAIL | next: v27b T=3 last temporal shot then KILL if fail

