# 🧠 MEMORY — WildfireFrontDynamics

> **Purpose:** Accumulated knowledge from every loop iteration. Updated after each experiment.
> **Format:** Most recent entries at the top.

---

## Current State

| Metric | Value | Source |
|---|---|---|
| Best IoU | 0.035 | v11 (A3C-LSTM) |
| Best Recall | 0.042 | v11 |
| Best val_loss | 0.2712 | v11 |
| Current model | U-Net Small (v13b) | Pending results |
| Kaggle account | `alonsoalviraaaa` (uni) | Migrated 2026-07-10 |

---

## Experiment History (Chronological)

### v13b: U-Net Small — PENDING
- **Date:** 2026-07-10
- **Change:** New architecture (U-Net), batch_size=32, PyTorch downgrade for P100
- **Status:** Launched, awaiting results
- **Fixes applied:** Inlined model (v13 ModuleNotFoundError), PyTorch 2.1.2 install (sm_60 CUDA error)

### v12: Freeze Conv + pos_weight=8 — FAILED
- **Date:** 2026-07-10
- **Result:** IoU=0.002, Recall=0.002 (WORSE than v11)
- **Lesson:** pos_weight=8 paradoxically reduced recall. Problem is NOT class imbalance.
- **Action:** Reverted pos_weight to 3.0

### v11: LR Reduction + Segmentation Metrics — MIXED
- **Date:** 2026-07-09
- **Result:** val_loss=0.2712 (best ever), but best_epoch=1, recall=4.2%
- **Lesson:** LR was NOT the problem. Model peaks before learning starts.
- **Meta-labeler:** 90.1% accuracy (excellent with 12 features)

### v10: Baseline A3C-LSTM
- **Date:** 2026-07-09
- **Result:** val_loss=0.2849, best_epoch=3
- **Lesson:** Model degrades after epoch 3. Focal loss stable.

---

## Key Learnings

1. **Architecture > Hiperparámetros** — 3 experiments (v10-v12) proved that tuning A3C-LSTM is futile
2. **batch_size=1 is the bottleneck** — Per-cell iteration prevents stable gradients
3. **Meta-labeler works** — RandomForest with 12 features achieves 90% accuracy
4. **P100 GPU needs PyTorch ≤2.1.x** — sm_60 not supported by newer versions
5. **Inline models in Kaggle scripts** — External imports fail on cloned repos
6. **pos_weight higher = recall LOWER** — Counterintuitive but confirmed

---

## Open Questions

- [ ] Will U-Net achieve IoU > 0.10 on first try? (v13b pending)
- [ ] Does PyTorch 2.1.2 install correctly at runtime on Kaggle?
- [ ] Is 30×30 patch size sufficient for U-Net, or do we need 64×64?

---

## Environment Notes

- **OS:** Windows 11, cmd.exe
- **Python:** 3.11 (local), 3.12 (Kaggle)
- **Encoding:** Use `python -X utf8` for scripts with Spanish characters
- **Kaggle auth:** Token in `~/.kaggle/access_token` (not kaggle.json OAuth)
- **Git:** Push to `origin/main` directly (no branches)