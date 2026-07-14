# Production Readiness Audit — WildfireFrontDynamics

> **Date:** 2026-07-14  
> **Production candidate:** v21 (`ResidualWildfireUNetSmall` + `target_mode=delta`)  
> **Auditor:** loop engineering session post cross-protocol re-eval

---

## Executive summary

v21 is the first model that **beats the copy baseline on the full grid** (IoU 0.226, Δ +0.076) under the honest v19 test protocol. It is promoted to `models/production/manifest.json`. The repo is **not** yet an operational wildfire service — it is a research pipeline with a clear production inference path.

---

## What works (keep)

| Area | Status |
|------|--------|
| v21 metrics | IoU 0.226, beats copy +0.076 on 979 test patches |
| Trainer | Consolidated `wildfire_front/ml/unet_train.py` |
| Metrics | Fixed `ndws_metrics.py` (dilated-copy baseline, legacy field) |
| CI | pytest + ruff + mypy on `wildfire_front` |
| No leakage | Splits disjuntos verificados |
| Production inference | `wildfire_front/ml/spread_predictor.py` + `scripts/predict_spread.py` |
| Kaggle weights dataset | `alonsoalviraaaa/wildfire-checkpoint-weights` |

---

## Critical issues (fix before calling it “operational”)

### 1. Kaggle output bloat — **PARTIALLY FIXED**

**Problem:** v19–v21 cloned the repo into `/kaggle/working/WildfireFrontDynamics`, polluting kernel outputs with the entire git tree (~300 MB).

**Fix:** v22+ clones to `/tmp/WildfireFrontDynamics`; artifacts only in `/kaggle/working`.

**Still bad:** v19–v21 scripts not retrofitted; cross-protocol re-eval had same issue.

### 2. Weights not in git — **BY DESIGN, needs process**

**Problem:** `*.pt` is gitignored. Fresh clone has no model.

**Mitigation:**
- `models/production/manifest.json` — config contract
- `scripts/install_production_weights.py` — copy from `kaggle_outputs_v21`
- Kaggle dataset `wildfire-checkpoint-weights`

### 3. Stale documentation — **FIXED in this commit**

| File | Was | Now |
|------|-----|-----|
| `EXPERIMENT_TRACKER.md` | v20 “RUNNING”, v14 production | v21 production |
| `LOOP_ENGINEERING_PLAN.md` | Tier-1 “breakthrough” +0.87 | Honest metrics + v21 |
| `MEMORY.md` | 2026-07-10, v18 next | v21 production state |

### 4. Tier-1 metric was tautological — **FIXED**

`copy_baseline_iou_changed` was always 0.0. Use `improvement_vs_copy_iou_changed` (vs dilated copy) or `legacy_improvement_vs_naive_copy_iou_changed` for audit only.

### 5. Apples-to-oranges comparisons — **FIXED via cross-protocol**

v14 IoU 0.239 and v19 IoU 0.052 used different test sets. Cross-protocol re-eval (`alonsoalviraaaa/wildfire-cross-protocol-reeval`) aligned all models on 979 patches.

### 6. No unified Kaggle entrypoint — **IN PROGRESS**

`kaggle_job/kaggle_common.py` exists but v19–v21 duplicate 200+ lines each. v22 uses common helpers after clone.

### 7. A3C-LSTM vs U-Net confusion — **DOCUMENTATION**

- `scripts/evaluate_current_model.py` — legacy A3C, not production U-Net
- CI smoke test still imports `A3C_PerCellModel_LSTM`
- README says “not operational” — still true for GeoTIFF MVP; NDWS spread is separate track

### 8. `ResidualWildfireUNetSmall` + `delta` double residual — **WATCH**

Residual architecture anchors logits to prev_fire; delta target predicts growth then adds prev at eval. Worked in v21 but is redundant — monitor v22 for instability.

### 9. Copy baseline 0.788 vs 0.150 — **NOT A BUG**

0.788 = `both_fire` dense patches (leakage analysis). 0.150 = `any_fire` test protocol. Always label which protocol when citing copy IoU.

### 10. MCP config — **OK, orthogonal**

`.vscode/mcp.json` GitHub + Kaggle MCP is for monitoring/CI, not model quality.

---

## Production deployment checklist

- [x] Manifest with version, architecture, metrics
- [x] `SpreadPredictor` class with delta decode
- [x] CLI `scripts/predict_spread.py`
- [x] Install script for weights
- [ ] TorchScript export for edge deployment
- [ ] Docker image with pinned torch + weights
- [ ] Real-fire validation (Tobarra/CLM) separate from NDWS test
- [ ] Meta-labeler gate on production predictions
- [ ] Monitoring: precision/recall drift vs copy baseline

---

## Experiment queue (post-audit)

| Ver | Status | Notes |
|-----|--------|-------|
| v21 | **PRODUCTION** | IoU 0.226, Δ full +0.076 |
| v22 | RUNNING | `--filter-mode changed`, parent v21 |
| v23 | queued | 12-channel schema |
| v24 | queued | CLM fine-tune |

---

## Files canonical for production

| Purpose | Path |
|---------|------|
| Inference | `wildfire_front/ml/spread_predictor.py` |
| Manifest | `models/production/manifest.json` |
| Predict CLI | `scripts/predict_spread.py` |
| Install weights | `scripts/install_production_weights.py` |
| Trainer | `wildfire_front/ml/unet_train.py` |
| Metrics | `wildfire_front/ml/ndws_metrics.py` |
| Cross-eval | `wildfire_front/ml/cross_protocol_eval.py` |

---

## Honest verdict

**Ship v21 for NDWS patch inference and loop iteration.** Do not claim operational wildfire forecasting for real incidents until real-fire eval and deployment checklist are complete.