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

## 🔧 Loop Engineering Overhaul (Implemented)

All infrastructure for the experiment loop has been built and tested:

| Component | File | Status |
|---|---|---|
| **Improved U-Net** (3-level, 8×8 bottleneck) | `models/unet_model.py` | ✅ |
| **Composite Loss** (BCE+Dice+Tversky+Focal) | `models/unet_model.py` | ✅ |
| **SE Attention** module | `models/unet_model.py` | ✅ |
| **Preprocessor v2** (64×64 full grid) | `kaggle_job/preprocess_ndws.py` | ✅ |
| **Training v14** (multi-threshold, EMA, grad-accum) | `kaggle_job/run_unet_training_v14.py` | ✅ |
| **Local Smoke Test** | `kaggle_job/smoke_test_v14.py` | ✅ |
| **Automated Loop Runner** | `scripts/run_experiment_loop.py` | ✅ |
| **Experiment Queue** | `scripts/experiment_queue.json` | ✅ (auto-generated) |
| **Pytest Suite** (model + loss + gradient) | `tests/test_unet_model.py` | ✅ |

### Key Fixes Applied

1. **v13 Kaggle crash fixed** — `ModuleNotFoundError: models.unet_model` resolved with
   inline fallback + proper `sys.path` insertion in `run_unet_training_v14.py`.
2. **Bottleneck fixed** — 30×30 patches through 4 down-levels collapsed to 1×1 (zero spatial
   info). Now: 64×64 through 3 down-levels → 8×8 bottleneck.
3. **Fake temporal data fixed** — old preprocessor replicated the same frame 3× as a "sequence".
   Now uses `PrevFireMask` as real single-timestep input.
4. **Single-threshold eval fixed** — now sweeps 0.3/0.4/0.5/0.6 to find best recall point.
5. **No local validation** — now smoke test catches bugs before Kaggle.

## Experiment Queue (Ordered by Expected Impact)

### Phase 1: Architecture + Loss (v14-v18) — **READY TO RUN**

Managed by `scripts/run_experiment_loop.py`. See `scripts/experiment_queue.json`.

#### Experiment v14: U-Net + Composite Loss (BCE+Dice+Tversky) — **NEXT**
- **Hypothesis:** Composite loss with FN-heavy Tversky boosts recall over v13
- **Change:** `--model small --loss composite --epochs 50 --batch-size 32`
- **Expected:** IoU 0.10-0.20, Recall 0.15-0.30

#### Experiment v15: U-Net + SE Attention + Composite Loss
- **Hypothesis:** Channel attention improves feature selection on multi-modal input
- **Change:** Add `--se-attention` flag
- **Depends on:** v14
- **Expected:** IoU 0.12-0.22, Recall 0.20-0.35

#### Experiment v16: U-Net Full + Composite + EMA
- **Hypothesis:** Larger capacity + EMA stabilizes training for higher IoU
- **Change:** `--model full --ema-decay 0.999 --grad-accum 2`
- **Depends on:** v15
- **Expected:** IoU 0.15-0.25, Recall 0.25-0.40

#### Experiment v17: U-Net Small + Focal Loss (gamma=3)
- **Hypothesis:** Focal loss focuses on hardest fire pixels
- **Change:** `--loss focal --pos-weight 7.0`

#### Experiment v18: U-Net Small + Tversky Only (beta=0.7)
- **Hypothesis:** Pure Tversky loss maximizes recall without BCE interference
- **Change:** `--loss tversky`

### Phase 2: Temporal Enhancement (v19-v20)

#### Experiment v19: Real Temporal Sequences (3-timestep)
- **Hypothesis:** True temporal features from consecutive frames improve prediction
- **Change:** `preprocess_ndws.py --sequence-length 3` (now supported!)
- **Depends on:** Best of v14-v18

#### Experiment v20: ConvLSTM Encoder
- **Hypothesis:** Recurrent encoder captures temporal dynamics better than channel-stacking
- **Depends on:** v19

### Phase 3: Data Enhancement (v21-v22)

#### Experiment v21: Oversampling Fire-Heavy Patches
- **Hypothesis:** Weighted sampler increases fire exposure
- **Change:** WeightedRandomSampler in DataLoader

#### Experiment v22: Castilla-La Mancha Fine-Tuning
- **Hypothesis:** Real fire data improves domain adaptation
- **Change:** Fine-tune best model on Tobarra data

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