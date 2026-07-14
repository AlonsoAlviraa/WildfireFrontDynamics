# 📊 Experiment Tracker — WildfireFrontDynamics

> **Purpose:** Log every training experiment with metrics, hypothesis, and verdict
> **Format:** Follows `LOOP_ENGINEERING_PLAN.md` template
> **Rule:** Update this file AFTER every Kaggle kernel completes

---

## Current Baseline

| Version | Date | IoU@0.5 | Recall@0.5 | Precision@0.5 | F1 | best_epoch | val_loss | Status |
|---|---|---|---|---|---|---|---|---|
| v12 | 2026-07-10 | 0.002 | 0.002 | 0.161 | 0.004 | 2 | 0.2740 | Superseded |
| **v14** | 2026-07-10 | **0.239** | **0.564** | 0.293 | 0.385 | 8 | 0.1124 | **Production baseline** |
| v15 | 2026-07-10 | 0.235 | 0.548 | 0.292 | 0.381 | 6 | 0.1087 | Neutral |
| v16 | 2026-07-10 | 0.237 | 0.589 | 0.284 | 0.383 | 6 | 0.1079 | Neutral |

**NDWS acceptance threshold:** IoU > 0.15, Recall > 0.30 — **MET since v14**

**Scientific target (copy baseline):** IoU > 0.788 (naive PrevFireMask copy) — **NOT MET**

**Tier-1 baseline (changed pixels):** v19 — Δ vs copy **+0.877**  
**Tier-2 baseline (full grid):** v14 — IoU **0.239**  
**Next experiment:** v20 (Residual + changed-weighted)

---

## Experiment Log

### v14: U-Net Small + Composite Loss — ✅ BREAKTHROUGH
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v14`
- **Hypothesis:** U-Net + composite loss (BCE+Dice+Tversky) fixes v10-v12 architectural failure
- **Change:** 64×64 patches, batch=32, WildfireUNetSmall, composite loss, EMA, multi-threshold eval
- **IoU:** 0.239 (prev: 0.002, Δ: +0.237)
- **Recall:** 0.564 (prev: 0.002, Δ: +0.562)
- **Precision:** 0.293
- **F1:** 0.385
- **best_epoch:** 8
- **val_loss:** 0.1124
- **Copy baseline IoU:** 0.788 (model 3× worse — learns to copy poorly)
- **Verdict:** ✅ Better — new production baseline, all NDWS criteria met
- **Next:** Test SE attention (v15), then residual delta (v18)

---

### v15: U-Net Full + SE Attention — ⚖️ NEUTRAL
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v15`
- **Hypothesis:** SE attention improves multi-modal feature selection
- **Change:** WildfireUNet (4.3M params) + SE + composite loss
- **IoU:** 0.235 (prev: 0.239, Δ: -0.004)
- **Recall:** 0.548 (prev: 0.564, Δ: -0.016)
- **best_epoch:** 6
- **val_loss:** 0.1087 (lower, but IoU flat)
- **Verdict:** ⚖️ Neutral — SE + larger model does not improve IoU
- **Next:** Do not retry without architectural change

---

### v16: U-Net Full + SE + EMA — ⚖️ NEUTRAL
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v16`
- **Hypothesis:** Full model + EMA stabilizes training for higher IoU
- **Change:** Same as v15 with EMA decay=0.999
- **IoU:** 0.237 (prev: 0.235, Δ: +0.002)
- **Recall:** 0.589 (prev: 0.548, Δ: +0.041)
- **best_epoch:** 6
- **val_loss:** 0.1079
- **Verdict:** ⚖️ Neutral — recall up slightly, IoU still below v14
- **Next:** Pivot to residual delta learning

---

### v17: Autonomous Research Pipeline — ❌ FAILED
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-autonomous-research-v17`
- **Hypothesis:** 16h Optuna sweep finds config beating copy baseline
- **Change:** ResidualWildfireUNet + inline TFRecord preprocessor
- **Error:** Inline preprocessor required `downward_shortwave_radiation_flux` → 0 train/val/test samples → IndexError
- **Secondary:** PyTorch 2.1.2 install failed on P100 (ran 2.10 incompatible)
- **Verdict:** ❌ Failed — preprocessing broken
- **Fix applied (v17d):** Use `preprocess_ndws.py` via `kaggle_common.py`, P100 fix before import
- **Next:** Relaunch v17d OR run v18 first (simpler, higher priority)

---

### v18: Residual Delta U-Net Small — ⚖️ NEUTRAL
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v18`
- **Hypothesis:** logit(prev_fire) + delta_logits forces model to learn propagation, not copy
- **Change:** `ResidualWildfireUNetSmall` + composite loss (absolute target, `both_fire` filter)
- **IoU:** 0.239 (same as v14)
- **Verdict:** ⚖️ Neutral — residual alone insufficient without changed-pixel loss
- **Next:** Combine with v19 formulation (v20)

---

### v19: Changed-Pixel Weighted U-Net — ✅ TIER-1 BREAKTHROUGH
- **Date:** 2026-07-14
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v19`
- **Parent:** v14
- **Hypothesis:** Upweight changed pixels + `any_fire` filter beats copy on dynamic cells
- **Change:** `changed_weighted` loss, WeightedRandomSampler, CLM merge (890 patches)
- **IoU full @0.5:** 0.052 (copy: 0.150)
- **Δ vs copy (changed px):** **+0.877** (copy changed IoU: 0.0)
- **model_iou_changed @0.5:** 0.877
- **best_epoch:** 9 | **train time:** 418s (T4)
- **Verdict:** ✅ Tier-1 target met; full-grid IoU sacrificed (over-predicts spread)
- **Next:** v20 — residual architecture + same changed-pixel setup

---

### v20: Residual + Changed-Pixel — 🔴 RUNNING
- **Date:** 2026-07-14
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v20`
- **Parent:** v19
- **Hypothesis:** Copy-anchored residual U-Net recovers full IoU while keeping Δ changed > 0.5
- **Change:** `--architecture residual` (only variable vs v19)
- **Go criteria:** Δ changed > 0.5 AND IoU full > 0.15
- **Status:** Pushed to Kaggle

---

## Failed Hypotheses (Do NOT Retry)

| # | Hypothesis | Why it failed | Evidence |
|---|---|---|---|
| 1 | "LR too high" | v11 halved LR, best_epoch went 3→1 | v11 |
| 2 | "pos_weight fixes recall" | v12 pos_weight 3→8, recall 4.2%→0.2% | v12 |
| 3 | "SE attention improves IoU" | v15/v16 IoU ≈ v14 | v15, v16 |
| 4 | "More params = better IoU" | v16 (4.3M) = v14 (1.08M) | v16 |
| 5 | "Inline TFRecord parser" | Wrong feature schema, 0 samples | v17 |

---

## Accepted Hypotheses (Validated)

| # | Hypothesis | Evidence |
|---|---|---|
| 1 | "U-Net >> A3C-LSTM" | IoU 0.002→0.239 | v12→v14 |
| 2 | "Composite loss >> BCE alone" | Convergence epoch 3 IoU 0.177 | v14 curves |
| 3 | "64×64 patches >> 30×30" | Bottleneck 8×8 preserves spatial info | v14 vs v13 |
| 4 | "Copy baseline is the real benchmark" | IoU 0.788 vs model 0.239 | leakage analysis |

---

## Resource Tracking

| Week | Experiments | GPU hours | Notes |
|---|---|---|---|
| 2026-W28 | v10-v17 (10 runs) | ~12h | v14-v16 success, v17 failed |
| 2026-W29 | v18 planned | ~4h est. | Residual delta |

---

## Metric Definitions

- **IoU:** `TP / (TP + FP + FN)` — primary NDWS metric
- **Copy baseline IoU:** IoU when prediction = PrevFireMask
- **improvement_vs_copy:** model IoU − copy baseline IoU (scientific target)
- **Recall:** `TP / (TP + FN)`
- **best_epoch:** Epoch with lowest val_loss