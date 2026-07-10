# 🧠 MEMORY — WildfireFrontDynamics

> **Purpose:** Accumulated knowledge from every loop iteration. Updated after each experiment.
> **Format:** Most recent entries at the top.

---

## Current State (2026-07-10)

| Metric | Value | Source |
|---|---|---|
| Best model IoU | **0.2548** | v14 (U-Net) @thresh=0.6 |
| Copy baseline IoU | **0.7881** | Leakage analysis (copy PrevFireMask) |
| Margin vs copy | **-0.5333** | ❌ Model does NOT beat naive copy |
| Best Recall | 0.6653 | v14 @thresh=0.3 |
| Best val_loss | 0.1079 | v16 (U-Net+SE) |
| Current experiment | v17 autonomous sweep | RUNNING on Kaggle |
| Kaggle account | `alonsoalviraaaa` (uni) | Migrated 2026-07-10 |

---

## 🚨 CRITICAL FINDING: Copy Baseline Problem

**The single most important discovery in this project:**

Simply copying `PrevFireMask` (the fire from yesterday) as prediction achieves **IoU = 0.7881**.
Our best model (v14, IoU=0.2548) is **3x WORSE** than copying.

**Root causes identified:**
1. `PrevFireMask` has r=0.8666 spatial correlation with target
2. 46% of samples are "stable" (fire doesn't change much day-to-day)
3. The model "learned" to copy but does it worse than identity
4. 14 of 17 input channels have near-zero correlation with target (noise)

**Solution (v17):** Residual Delta U-Net — predicts the CHANGE over copy baseline, not the absolute fire mask.

---

## Experiment History (Chronological)

### v17: Autonomous Research Pipeline — RUNNING
- **Date:** 2026-07-10
- **Change:** 16h Optuna sweep, residual delta U-Net, SOTA losses, feature pruning
- **Architecture:** ResidualWildfireUNet (predicts delta + copy_bias * prev_fire)
- **Loss:** Composite (Focal + Tversky + Lovasz + Weighted BCE)
- **Attention:** CBAM, SE, or none (swept)
- **Status:** Launched on Kaggle (alonsoalviraaaa/wildfire-autonomous-research-v17)
- **Fixes:** P100 sm_60 (PyTorch 2.1.2 before import)

### v16: U-Net + SE Attention — NO IMPROVEMENT
- **Date:** 2026-07-10
- **Result:** IoU=0.2367, Recall=0.6399 (same as v14)
- **Lesson:** More capacity (4.3M vs 1.08M params) doesn't help. Bottleneck is NOT model size.
- **Early stopping:** epoch 16, best at epoch 6

### v14: U-Net Small — ✅ BREAKTHROUGH
- **Date:** 2026-07-10
- **Result:** IoU=0.2548, Recall=0.6653, val_loss=0.1124
- **Architecture:** WildfireUNetSmall (1.08M params, batch=32)
- **Lesson:** U-Net dramatically improved from A3C (IoU 0.035→0.255)
- **But:** Still 3x below copy baseline

### v13c: U-Net Small + P100 fix — COMPLETED
- **Date:** 2026-07-10
- **Fix:** PyTorch 2.1.2 install before import torch (P100 sm_60)

### v13b: CUDA sm_60 error — FAILED
- v13: ModuleNotFoundError — FAILED

### v12: pos_weight=8 — FAILED (recall dropped)
### v11: LR reduction — MIXED (val_loss improved, recall stayed low)
### v10: A3C baseline — IoU 0.035

---

## Key Learnings

1. **Copy baseline is the real enemy** — IoU 0.7881, not 0.0 as assumed
2. **Architecture matters** — U-Net (0.255) >> A3C-LSTM (0.035)
3. **More params ≠ better** — v16 (4.3M) = v14 (1.08M) in IoU
4. **Feature noise is massive** — 14/17 channels are near-zero correlation
5. **P100 GPU needs PyTorch ≤2.1.x** — sm_60 not supported by 2.3+
6. **Inline models in Kaggle scripts** — External imports fail on cloned repos
7. **pos_weight higher = recall LOWER** — Counterintuitive but confirmed
8. **Meta-labeler works** — RandomForest 90.1% accuracy with 12 features

---

## Open Questions

- [ ] Will residual delta learning (v17) finally beat copy baseline?
- [ ] Which loss function will Optuna select as optimal?
- [ ] Does feature pruning (keeping <95% importance) help or hurt?

---

## Environment Notes

- **OS:** Windows 11, cmd.exe
- **Python:** 3.11 (local), 3.12 (Kaggle)
- **GPU:** Tesla P100 16GB (sm_60 — needs PyTorch ≤2.1.x)
- **Kaggle:** 30 GPU-h/week (uni account)
- **Kaggle auth:** Token in `~/.kaggle/access_token`
- **Git:** Push to `origin/main` directly