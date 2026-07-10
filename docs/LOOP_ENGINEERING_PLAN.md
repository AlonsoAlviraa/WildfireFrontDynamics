# 🔄 Loop Engineering Plan — Until We Hit Acceptable Results

> **Goal:** Systematic iteration loop until we achieve **IoU > 0.15** and **Recall > 0.30** (NDWS minimum viable)
> **Method:** Each experiment is ONE change, measured against the previous baseline
> **Rule:** Never change 2 things at once — isolate variables

---

## Acceptance Criteria (The "Definition of Done")

| Metric | Current (v12) | Minimum Viable | Competitive | SOTA |
|---|---|---|---|---|
| **IoU** | 0.002 | **>0.15** | >0.30 | >0.42 |
| **Recall** | 0.002 | **>0.30** | >0.50 | >0.57 |
| **Precision** | 0.161 | **>0.30** | >0.50 | >0.60 |
| **F1 (Dice)** | 0.004 | **>0.25** | >0.40 | >0.50 |
| **best_epoch** | 2 | **>10** | >20 | >30 |
| **val_loss** | 0.274 | **<0.20** | <0.15 | <0.10 |

**We do NOT stop until ALL minimum viable criteria are met.**

---

## The Loop (Repeat Until Green)

```
┌──────────────────────────────────────────────────┐
│  1. HYPOTHESIS: Change ONE thing                 │
│  2. IMPLEMENT: Code the change                   │
│  3. TEST LOCAL: Unit tests pass?                 │
│  4. PUSH: Send to Kaggle (GPU)                   │
│  5. WAIT: Kernel runs (~2-4h)                    │
│  6. DOWNLOAD: Get results                        │
│  7. ANALYZE: Compare metrics to previous         │
│  8. DECISION: Better? → new baseline             │
│                 Worse? → revert, new hypothesis  │
│  9. DOCUMENT: Log in EXPERIMENT_TRACKER.md       │
│ 10. REPEAT                                       │
└──────────────────────────────────────────────────┘
```

---

## Experiment Queue (Ordered by Expected Impact)

### Phase 1: Architectural Overhaul (v13-v15)

**These experiments change the FUNDAMENTAL architecture.**

#### Experiment v13: U-Net Baseline (HIGHEST PRIORITY)
- **Hypothesis:** U-Net with batch_size=32 will dramatically improve IoU
- **Change:**
  - New model `WildfireUNet` in `models/unet_model.py`
  - Patch size 30×30 → 64×64
  - batch_size 1 → 32
  - Loss: Weighted BCE (weight=5, matching NDWS paper)
- **Expected:** IoU 0.10-0.20, Recall 0.15-0.30
- **Risk:** Medium (new code, but proven architecture)

#### Experiment v14: U-Net + Tversky Loss
- **Hypothesis:** Tversky loss (β=0.7) will boost recall
- **Change:** Replace weighted BCE with Tversky loss
- **Depends on:** v13 baseline
- **Expected:** Recall +15-20% over v13

#### Experiment v15: U-Net + Data Augmentation
- **Hypothesis:** Augmentation (flips, rotations) improves generalization
- **Change:** Add `Albumentations` or custom augmentation
- **Depends on:** v14
- **Expected:** IoU +5% over v14

### Phase 2: Temporal Enhancement (v16-v17)

#### Experiment v16: ConvLSTM Encoder
- **Hypothesis:** Temporal features from 3-timestep input improve prediction
- **Change:** Replace U-Net encoder with ConvLSTM
- **Depends on:** v15
- **Expected:** IoU +5-10% over v15

#### Experiment v17: Attention Mechanism (CBAM)
- **Hypothesis:** Channel + spatial attention improves feature selection
- **Change:** Add CBAM blocks to U-Net
- **Depends on:** v16
- **Expected:** IoU +3-5% over v16

### Phase 3: Data Enhancement (v18-v19)

#### Experiment v18: Oversampling Fire-Heavy Patches
- **Hypothesis:** Weighted sampler increases fire exposure
- **Change:** WeightedRandomSampler in DataLoader
- **Depends on:** v17
- **Expected:** Recall +5-10%

#### Experiment v19: Castilla-La Mancha Fine-Tuning
- **Hypothesis:** Real fire data improves domain adaptation
- **Change:** Fine-tune best model on Tobarra data
- **Depends on:** v18
- **Expected:** Better on real fire scenarios

---

## Revert Protocol

If an experiment makes things WORSE:
1. `git revert <commit>` to undo the change
2. Document WHY it failed in `EXPERIMENT_TRACKER.md`
3. Move to next hypothesis
4. Do NOT retry the same change without modification

---

## Kaggle Resource Budget

| Resource | Limit per kernel | Our usage |
|---|---|---|
| GPU time | 12h/week (free) / 30h (uni) | ~2-4h per experiment |
| CPU time | 12h | ~0.5h preprocessing |
| Disk | 20GB | ~5GB (dataset + repo) |
| RAM | 16GB | ~4GB |

**Expected:** We can run ~7-10 experiments per week with uni account.

---

## Decision Tree

```
v13 (U-Net baseline)
  ├── IoU > 0.15? → YES → v14 (Tversky) → v15 (augmentation) → ...
  │                 NO   → Check: batch_size actually 32?
  │                       Check: patch size actually 64?
  │                       Check: preprocessing correct?
  │
  └── val_loss still ~0.27? → Architecture not the issue
                               → Investigate data pipeline
```

---

## File Structure for Experiments

Each experiment needs:
1. **Model code:** `models/experiment_vXX.py` or modification of existing
2. **Training script:** Update `kaggle_job/run_mega_training.py` or new
3. **Results:** `kaggle_outputs_vXX/training_summary.json`
4. **Analysis:** Entry in `EXPERIMENT_TRACKER.md`
5. **Plots:** `docs/analysis_plots_vXX/`
6. **Weights:** `models/weights_vXX_best.pt`

---

## Success Metrics Per Experiment

After each experiment, fill this template:

```markdown
### vX: [Experiment Name]
- **Date:** YYYY-MM-DD
- **Hypothesis:** [What we expected]
- **Change:** [What we changed]
- **IoU:** [value] (prev: [value], Δ: [value])
- **Recall:** [value] (prev: [value], Δ: [value])
- **best_epoch:** [value]
- **val_loss:** [value]
- **Verdict:** ✅ Better / ❌ Worse / ⚖️ Neutral
- **Next:** [What to try next]