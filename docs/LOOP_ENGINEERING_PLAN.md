# Loop Engineering Plan — Two-Tier Wildfire Spread Model

> **Updated:** 2026-07-14 after v19 Kaggle run  
> **Method:** One scientific variable per experiment, measured against copy baseline on **two tiers**.  
> **Rule:** Never change two variables at once.

---

## What v19 Proved

| Metric | v14 | v18 | **v19** | Copy baseline |
|---|---|---|---|---|
| IoU full @0.5 | 0.239 | 0.239 | **0.052** | 0.150 |
| Δ vs copy (full) | -0.55 | -0.55 | -0.10 | — |
| **Δ vs copy (changed px)** | negative | negative | **+0.877** | 0.0 |
| Train samples | 12k | 12k | **12,890** (+CLM) | — |
| best_epoch | 8 | 34 | 9 | — |

**Verdict:** The changed-pixel pivot works. The model now beats the copy baseline where fires actually move. Full-grid IoU collapsed because the standard U-Net over-predicts spread (recall 0.73, precision 0.05) while static pixels dominate the metric.

**New baseline:** v19 on `improvement_vs_copy_iou_changed`. Do not discard v14 for full-grid comparisons until v20+ recovers it.

---

## Acceptance Criteria (Realistic — Two Tiers)

### Tier 1 — Dynamic pixels (primary, achieved)

| Metric | Target | v19 |
|---|---|---|
| `improvement_vs_copy_iou_changed` @0.5 | **> 0** | **+0.877** |
| `model_iou_changed` @0.5 | > 0.70 | **0.877** |

### Tier 2 — Operational full grid (in progress)

| Metric | v14 | Target next | Stretch |
|---|---|---|---|
| IoU full @0.5 | 0.239 | **> 0.20** | > 0.35 |
| Δ vs copy (full) | -0.55 | **> -0.20** | > 0 |
| Recall @0.5 | 0.564 | 0.45–0.55 | > 0.55 |
| Precision @0.5 | 0.293 | **> 0.25** | > 0.35 |

Beating copy IoU ~0.79 on the **full grid** remains the long-term goal. Expect stepped gains (0.05–0.10 IoU per successful experiment), not a single jump.

---

## Root Cause (Updated)

1. **87% spatial correlation** — naive copy is strong; model must learn *corrections*, not redraw the map.
2. **Metric mismatch** — optimizing full IoU with a model that excels only on ~4% changed pixels misled v14–v18 early stopping.
3. **Architecture** — standard U-Net predicts absolute masks; v18 residual alone did not help without changed-pixel loss (v19).
4. **Preprocessing** — `both_fire` filter biased training; `any_fire` + CLM mix is now canonical.
5. **Infrastructure** — consolidated in `unet_train.py`; Kaggle clones fresh repo each run.

---

## Experiment Queue (Realistic)

Each row changes **one** variable relative to its parent.

| Ver | Parent | Single change | Hypothesis | Go if |
|---|---|---|---|---|
| **v19** | v14 | `changed_weighted` + `any_fire` + CLM | Beat copy on changed pixels | Δ changed > 0 |
| **v20** | v19 | `--architecture residual` | Copy-anchored logits recover full IoU while keeping Δ changed | Δ changed > 0.5 **and** IoU full > 0.15 |
| v21 | v20 | `--target-mode delta` | Growth-only target reduces false positives on static cells | IoU full > v20 |
| v22 | best | `--filter-mode changed` train only | Train exclusively on patches with fire movement | Δ changed ≥ v20 |
| v23 | best | 12-channel NDWS schema | Drop constant preprocessor channels | val_loss ↓, IoU ≥ parent |
| v24 | best | CLM fine-tune 10 epochs | Tobarra/Cardoso domain adaptation | real-fire eval ↑ |

**Active:** v20  
**Do not run:** v18-style residual without changed-pixel loss (already neutral).

---

## The Loop

```
┌─────────────────────────────────────────────────────────┐
│  1. HYPOTHESIS — one flag in unet_train / Kaggle script │
│  2. SMOKE — pytest + local smoke_test (optional)        │
│  3. PUSH — kernel to Kaggle (T4, fresh git clone)       │
│  4. WAIT — ~10 min preprocess + ~7 min train (v19)      │
│  5. PULL — training_summary.json + log                  │
│  6. SCORE — Tier-1 Δ changed, then Tier-2 IoU full     │
│  7. DECIDE — promote baseline / revert / queue next     │
│  8. LOG — EXPERIMENT_TRACKER.md + experiment_queue    │
│  9. REPEAT                                               │
└─────────────────────────────────────────────────────────┘
```

**Promotion rules**

- **New Tier-1 baseline:** `improvement_vs_copy_iou_changed` improves by ≥ 0.05.
- **New Tier-2 baseline:** full IoU improves by ≥ 0.03 without Tier-1 dropping below 0.
- **Revert:** Tier-1 < 0 or full IoU drops > 0.05 vs parent.

---

## Infrastructure (Stable — Do Not Fork)

| Purpose | Path |
|---|---|
| Trainer | `wildfire_front/ml/unet_train.py` |
| Metrics | `wildfire_front/ml/ndws_metrics.py` |
| Model | `models/unet_model.py` (`ResidualWildfireUNetSmall`) |
| Preprocess | `kaggle_job/preprocess_ndws.py` |
| Kaggle wrappers | `kaggle_job/run_unet_training_v19.py`, `v20.py` |
| Queue | `scripts/experiment_queue.json` |
| MCP monitor | Kaggle MCP / `kaggle kernels status` |

---

## Kaggle Checklist

- GPU: **T4** (`machine_shape: NvidiaTeslaT4`)
- Datasets: `fantineh/next-day-wildfire-spread`, `alonsoalviraaaa/clm-wildfire-patches`
- Output: `/kaggle/working/training_summary.json` only (no repo bloat in output)
- Auth: `KAGGLE_API_TOKEN` + GitHub MCP for CI

---

## Success Template

```markdown
### vX: [Name]
- **Date:** YYYY-MM-DD
- **Parent:** vY
- **Change:** [single variable]
- **Tier-1 Δ changed:** [value] (target > 0)
- **Tier-2 IoU full:** [value] (target > 0.20)
- **Verdict:** ✅ / ❌ / ⚖️
- **Next:** vZ
```