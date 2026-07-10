# 📊 Experiment Tracker — WildfireFrontDynamics

> **Purpose:** Log every training experiment with metrics, hypothesis, and verdict
> **Format:** Follows `LOOP_ENGINEERING_PLAN.md` template
> **Rule:** Update this file AFTER every Kaggle kernel completes

---

## Current Baseline

| Version | Date | IoU | Recall | Precision | F1 | best_epoch | val_loss | Status |
|---|---|---|---|---|---|---|---|---|
| v10 | 2026-07-09 | N/A | N/A | N/A | N/A | 3 | 0.2849 | Superseded |
| v11 | 2026-07-09 | 0.035 | 0.042 | 0.183 | 0.058 | 1 | 0.2712 | Superseded |
| v12 | 2026-07-10 | 0.002 | 0.002 | 0.161 | 0.004 | 2 | 0.2740 | **Current** |

**Acceptance threshold:** IoU > 0.15, Recall > 0.30

---

## Experiment Log

### v10: Baseline A3C-LSTM (Original)
- **Date:** 2026-07-09
- **Kernel:** `alonsoalvira/wildfire-front-training-v10`
- **Hypothesis:** A3C-LSTM with focal BCE + physics loss would learn fire spread
- **Architecture:** A3C_PerCellModel_LSTM (per-cell iteration, batch_size=1)
- **Config:** LR=1e-4, pos_weight=3.0, warmup=3, patience=8
- **IoU:** N/A (not computed)
- **Recall:** N/A (not computed)
- **best_epoch:** 3
- **val_loss:** 0.2849
- **test_loss:** 0.2771
- **Verdict:** ⚖️ Baseline — no segmentation metrics computed
- **Key finding:** Model peaks at epoch 3, then degrades. Focal loss is stable.
- **Next:** Reduce LR, add segmentation metrics

---

### v11: LR Reduction + Segmentation Metrics
- **Date:** 2026-07-09
- **Kernel:** `alonsoalvira/wildfire-front-training-v11`
- **Hypothesis:** Lower LR (1e-4 → 5e-5) + longer warmup (3→5) would extend training
- **Change:** LR halved, warmup extended, patience increased, added IoU/Recall/Precision eval
- **IoU:** 0.035 (first measurement)
- **Recall:** 0.042 (catastrophic — model predicts "no fire" 96% of time)
- **Precision:** 0.183
- **F1:** 0.058
- **best_epoch:** 1 (WORSE than v10's epoch 3)
- **val_loss:** 0.2712 (best ever)
- **test_loss:** 0.2726
- **meta_labeler_acc:** 90.1% (excellent)
- **Verdict:** ⚖️ Mixed — val_loss improved but best_epoch regressed to 1
- **Key finding:** LR was NOT the problem. The model peaks BEFORE learning starts (v3.pt weights are better than fine-tuning).
- **Root cause identified:** batch_size=1 creates noisy gradients; training destroys pre-trained features
- **Next:** Freeze conv layers, increase pos_weight

---

### v12: Freeze Conv + pos_weight=8 + Clipping 0.3
- **Date:** 2026-07-10
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v12` (NEW UNI ACCOUNT)
- **Hypothesis:** Freeze conv during warmup + higher pos_weight would protect features and boost recall
- **Change:**
  - pos_weight 3.0 → 8.0
  - Freeze conv1/conv2/conv3 during warmup (5 epochs)
  - start_factor 0.1 → 0.01
  - Gradient clipping 0.5 → 0.3
- **IoU:** 0.002 (75x below minimum viable threshold)
- **Recall:** 0.002 (WORSE than v11's 0.042)
- **Precision:** 0.161
- **F1:** 0.004
- **best_epoch:** 2 (marginal improvement over v11's epoch 1)
- **val_loss:** 0.2740 (slightly worse than v11's 0.2712)
- **test_loss:** 0.3016 (WORSE — overfitting)
- **meta_labeler_acc:** 63.6% (much worse than v11's 90.1%)
- **Verdict:** ❌ WORSE — pos_weight=8 paradoxically reduced recall further
- **Key finding:** Higher pos_weight does NOT help — it makes the model MORE conservative. The problem is NOT class imbalance, it's the architecture.
- **Conclusion:** 3 experiments confirm the problem is architectural (per-cell, batch_size=1)
- **Next:** U-Net architecture overhaul (v13)

---

## Failed Hypotheses (Do NOT Retry)

| # | Hypothesis | Why it failed | Evidence |
|---|---|---|---|
| 1 | "LR too high" | v11 halved LR, best_epoch went from 3→1 | v11 results |
| 2 | "Class imbalance causes low recall" | v12 increased pos_weight 3→8, recall went 4.2%→0.2% | v12 results |
| 3 | "Freeze conv protects features" | v12 froze conv for 5 epochs, result was worse than v11 | v12 results |

---

## Accepted Hypotheses (Validated)

| # | Hypothesis | Evidence |
|---|---|---|
| 1 | "Meta-labeler works well with 12 features" | v11 achieved 90.1% accuracy | v11 results |
| 2 | "Problem is architectural (batch_size=1)" | 3 experiments all peak at epoch 1-3 | v10-v12 pattern |

---

## Next Experiments (Queue)

| Version | Experiment | Priority | Expected IoU |
|---|---|---|---|
| **v13** | **U-Net baseline (batch=32, patch=64, weighted BCE)** | 🔴 CRITICAL | 0.10-0.20 |
| v14 | U-Net + Tversky loss | High | +0.05 |
| v15 | U-Net + data augmentation | High | +0.03 |
| v16 | ConvLSTM temporal encoder | Medium | +0.05 |
| v17 | CBAM attention | Medium | +0.03 |
| v18 | Oversampling fire-heavy patches | Medium | +0.03 |
| v19 | Castilla-La Mancha fine-tuning | Low | Domain-specific |

---

## Resource Tracking

| Week | Experiments run | GPU hours used | GPU hours remaining |
|---|---|---|---|
| 2026-W28 (Jul 8-14) | v10, v11, v12 (3 runs) | ~8h | ~22h (uni: 30h/week) |
| 2026-W29 (Jul 15-21) | v13 planned | ~4h estimated | — |

---

## Metric Definitions

- **IoU (Intersection over Union):** `TP / (TP + FP + FN)` — primary metric
- **Recall (Sensitivity):** `TP / (TP + FN)` — ability to detect fire
- **Precision:** `TP / (TP + FP)` — accuracy of fire predictions
- **F1 (Dice):** `2*P*R / (P+R)` — harmonic mean
- **best_epoch:** Epoch with lowest val_loss (indicator of learning capacity)