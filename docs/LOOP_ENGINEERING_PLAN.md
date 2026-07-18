# Loop Engineering Plan — Production Track (v21+)

> **Updated:** 2026-07-14 after v21 + production audit  
> **Production model:** v21 — `ResidualWildfireUNetSmall` + `target_mode=delta`

---

## Current state

| Metric | v14 (cross) | v21 | Copy |
|--------|-------------|-----|------|
| IoU full @0.5 | 0.227 | **0.226** | 0.150 |
| Δ vs copy (full) | +0.077 | **+0.076** | — |
| Δ vs dilated (changed) | +0.098 | +0.041 | — |

**Verdict:** v21 matches v14 IoU and beats copy. Promoted to production manifest.

---

## Acceptance criteria (production)

| Tier | Metric | Target | v21 |
|------|--------|--------|-----|
| P0 | IoU full @0.5 | > 0.15 | 0.226 |
| P0 | Δ vs copy (full) | > 0 | +0.076 |
| P1 | Δ vs dilated (changed) | > 0 | +0.041 |
| P2 | Real-fire eval (CLM/Tobarra) | TBD | not run |

---

## Experiment queue

| Ver | Parent | Single change | Go if |
|-----|--------|---------------|-------|
| **v21** | v20 | `--target-mode delta` | **PRODUCTION** |
| v22–v24 | — | filter / clean12 hybrid | no leap (see EXPERIMENT_TRACKER) |
| **v25+** | — | Features / Temporal / Transfer only | `docs/ML_LOOP_RAILS.md` |

**Active queue (mutable):** `scripts/experiment_queue.json`  
**Historical features queue:** `scripts/archive/experiment_queue_features.json`  
**Docs:** `docs/ML_FEATURE_METHODOLOGY.md`, `docs/ML_TRANSFER_PROTOCOL.md`

---

## Infrastructure rules

1. Clone repo to `/tmp`, never `/kaggle/working`
2. Early-stop on `improvement_vs_copy_iou` (full grid)
3. Cross-protocol re-eval before promoting baseline
4. Update `EXPERIMENT_TRACKER.md` + `PRODUCTION_READINESS_AUDIT.md` after each run

---

## The loop

```
HYPOTHESIS → smoke (pytest) → push Kaggle → wait → pull summary
→ cross-protocol if baseline candidate → update manifest → queue next
```

---

## Canonical paths

| Purpose | Path |
|---------|------|
| Trainer | `wildfire_front/ml/unet_train.py` |
| Production inference | `wildfire_front/ml/spread_predictor.py` |
| Manifest | `models/production/manifest.json` |
| Metrics | `wildfire_front/ml/ndws_metrics.py` |
| Audit | `docs/PRODUCTION_READINESS_AUDIT.md` |
| Kaggle shared | `kaggle_job/kaggle_common.py` |