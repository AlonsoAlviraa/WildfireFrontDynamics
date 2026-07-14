# Loop Engineering Plan — Beat the Copy Baseline

> **Goal:** Beat the naive copy baseline (PrevFireMask → FireMask, IoU ~0.79) on **changed pixels**, not just hit NDWS minimum viable thresholds.
> **Method:** Each experiment changes ONE scientific variable, measured against v14 baseline AND copy baseline.
> **Rule:** Never change 2 things at once — isolate variables.

---

## Acceptance Criteria (Revised — Post-Audit)

| Metric | v14 | v18 | **Primary Target** | NDWS Minimum |
|---|---|---|---|---|
| **IoU (full grid)** | 0.239 | 0.239 | >0.30 | >0.15 |
| **Recall@0.5** | 0.564 | 0.534 | >0.50 | >0.30 |
| **Copy baseline IoU** | ~0.79 | ~0.79 | — | — |
| **Δ vs copy (full)** | -0.55 | -0.55 | **>0** | — |
| **Δ vs copy (changed px)** | negative | negative | **>0** | — |
| **best_epoch** | 8 | 34 | >10 | >10 |

**NDWS minimum viable: MET since v14.** Architecture tweaks (v15/v16/v18 residual) did not move the needle because the bottleneck is **problem formulation**, not model capacity.

---

## Root Cause (Why We Were Stuck)

1. **87% spatial correlation** — model learns to copy yesterday's fire mask
2. **Biased preprocessing** — `prev_fire>0 AND fire>0` filter oversamples active-fire patches
3. **Wrong optimization target** — early stopping on `val_loss` (BCE), not vs copy baseline
4. **5 constant channels** in preprocessor (pressure, cloud, etc.) add noise, not signal
5. **Script duplication** — v14–v18 are ~3000 lines of copy-paste, hard to iterate

---

## Scientific Pivot (v19+)

```
OLD: predict absolute fire mask, optimize val_loss
NEW: upweight changed pixels, optimize improvement_vs_copy_iou_changed
```

### Phase 1: Problem Reformulation (v19–v21) — **ACTIVE**

| Version | Hypothesis | Change | Status |
|---|---|---|---|
| **v19** | Changed-pixel loss beats copy on dynamic pixels | `changed_weighted` loss + `any_fire` filter + WeightedRandomSampler | **NEXT** |
| v20 | Delta target (growth mask only) | `--target-mode delta` | queued |
| v21 | Official 12-channel NDWS schema | Remove constant channels from preprocess | queued |

### Phase 2: Infrastructure Consolidation — **DONE**

| Component | File | Status |
|---|---|---|
| Consolidated trainer | `wildfire_front/ml/unet_train.py` | ✅ |
| NDWS metrics (copy + changed) | `wildfire_front/ml/ndws_metrics.py` | ✅ |
| Preprocess filter modes | `kaggle_job/preprocess_ndws.py --filter-mode` | ✅ |
| v19 Kaggle kernel | `kaggle_job/run_unet_training_v19.py` | ✅ |

### Phase 3: Temporal Enhancement (v22–v23)

- v22: Real 3-timestep sequences (`--sequence-length 3`)
- v23: ConvLSTM encoder

### Phase 4: Domain Adaptation (v24)

- Fine-tune best NDWS model on Castilla-La Mancha (Tobarra) data

---

## The Loop

```
┌──────────────────────────────────────────────────┐
│  1. HYPOTHESIS: Change ONE scientific variable     │
│  2. IMPLEMENT: unet_train.py config flag         │
│  3. TEST LOCAL: pytest + smoke_test              │
│  4. PUSH: Kaggle kernel (T4 GPU)                 │
│  5. WAIT: ~10 min preprocess + ~2h train         │
│  6. DOWNLOAD: training_summary.json              │
│  7. ANALYZE: Δ vs copy (changed pixels)        │
│  8. DECISION: Better? → new baseline             │
│                 Worse? → revert, next hypothesis │
│  9. DOCUMENT: EXPERIMENT_TRACKER.md              │
│ 10. REPEAT                                       │
└──────────────────────────────────────────────────┘
```

---

## Completed Experiments (v14–v18)

| Ver | Result | Verdict |
|---|---|---|
| v14 | IoU 0.239, Recall 0.564 | ✅ Baseline breakthrough |
| v15 | IoU 0.235 (SE attention) | ⚖️ Neutral |
| v16 | IoU 0.237 (full + EMA) | ⚖️ Neutral |
| v17 | ERROR (0 samples) | ❌ Fixed in v17d |
| v18 | IoU 0.239 (residual delta) | ⚖️ Neutral — same as v14 |

---

## Revert Protocol

1. `git revert <commit>` to undo the change
2. Document WHY it failed in `EXPERIMENT_TRACKER.md`
3. Move to next hypothesis
4. Do NOT retry the same change without modification

---

## Kaggle Resource Budget

| Resource | Limit | Our usage |
|---|---|---|
| GPU time | 12–30h/week | ~2–4h per experiment |
| Disk | 20GB | ~5GB |
| **GPU type** | T4 required | P100 incompatible with PyTorch 2.10 |

---

## File Structure

| Purpose | Path |
|---|---|
| Canonical trainer | `wildfire_front/ml/unet_train.py` |
| NDWS metrics | `wildfire_front/ml/ndws_metrics.py` |
| Model | `models/unet_model.py` |
| Preprocess | `kaggle_job/preprocess_ndws.py` |
| Kaggle wrapper | `kaggle_job/run_unet_training_v19.py` |
| Experiment queue | `scripts/experiment_queue.json` |
| Results | `kaggle_outputs_vXX/training_summary.json` |

---

## Success Template

```markdown
### vX: [Name]
- **Date:** YYYY-MM-DD
- **Hypothesis:** [What we expected]
- **Change:** [Single variable changed]
- **IoU:** [value] (copy: [value], Δchanged: [value])
- **Verdict:** ✅ / ❌ / ⚖️
- **Next:** [Next experiment]
```