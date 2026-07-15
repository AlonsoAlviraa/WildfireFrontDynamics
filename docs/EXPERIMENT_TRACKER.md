# Experiment Tracker — WildfireFrontDynamics

> **Rule:** Update after every Kaggle kernel completes.

---

## Current Production Baseline

| Version | Date | IoU@0.5 | Δ vs copy (full) | Δ vs dilated (changed) | best_epoch | Status |
|---------|------|---------|------------------|------------------------|------------|--------|
| v14 | 2026-07-10 | 0.239* | -0.55* | — | 8 | Superseded |
| v21 | 2026-07-14 | **0.226** | **+0.076** | +0.041 | 6 | **PRODUCTION** |

\* v14 on original 619-patch test; cross-protocol on 979 patches: IoU **0.227**, Δ **+0.077**.

**Manifest:** `models/production/manifest.json`  
**Inference:** `wildfire_front/ml/spread_predictor.py`  
**Audit:** `docs/PRODUCTION_READINESS_AUDIT.md`

**Overnight mega v1:** ERROR — preprocess wrote to `/tmp/ndws_npz` but mega expected `/tmp/ndws_npz_*` (0 patches).

**Overnight mega v2:** relaunch after `--output-root` fix on `preprocess_ndws.py` + `kaggle_common.py`.

**Next manual check:** `kaggle_outputs_overnight/overnight_report.json` + `scripts/run_overnight_monitor.py`

---

## Experiment Log

### v22: Changed-Only Filter — NEUTRAL (better Δ changed)
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v22`
- **Parent:** v21 | **Change:** `--filter-mode changed`
- **IoU full:** 0.225 | **Δ full:** +0.075 | **Δ changed:** +0.081 (vs v21 +0.041)
- **Val peak IoU:** 0.255 (epoch 38) — test did not beat v21
- **Verdict:** Keep v21 production; v22 feeds overnight EMA/long experiments

### v21: Delta Target + Residual — PRODUCTION
- **Kernel:** `alonsoalviraaaa/wildfire-front-training-v21`
- **Parent:** v20
- **Change:** `--target-mode delta` (only variable vs v20)
- **IoU full @0.5:** 0.226 | **copy:** 0.150 | **Δ full:** +0.076
- **Δ vs dilated copy (changed):** +0.041 | legacy naive: +0.214
- **Early-stop:** `improvement_vs_copy_iou`
- **Verdict:** First model beating copy on full grid with honest protocol

### v20: Residual + Changed-Weighted — FAILED
- **IoU full:** 0.050 | **Δ full:** -0.100
- **Verdict:** Residual alone did not recover IoU; over-predicts (precision ~5%)

### v19: Changed-Weighted — DIAGNOSTIC ONLY
- **IoU full:** 0.052 | legacy Δ changed: +0.877 (metric was tautological)
- **Verdict:** Led to metrics fix; not production

### v14: U-Net Small — SUPERSEDED
- **IoU:** 0.239 on original test; still strong on cross-protocol (0.227)
- **Verdict:** Valid baseline until v21; keep for ablations

---

## Metric Definitions (v2 — honest)

| Metric | Meaning |
|--------|---------|
| `improvement_vs_copy_iou` | Model IoU − naive copy IoU (full grid) — **primary** |
| `improvement_vs_copy_iou_changed` | Model − **dilated** copy on changed pixels |
| `legacy_improvement_vs_naive_copy_iou_changed` | Inflated; equals `model_iou_changed` when naive copy changed = 0 |

---

## Failed Hypotheses (do not retry)

| Hypothesis | Evidence |
|------------|----------|
| changed_weighted alone fixes full IoU | v19/v20 IoU ~0.05 |
| residual without delta target | v20 failed |
| Tier-1 +0.87 = breakthrough | copy_changed always 0 |

---

## Accepted Hypotheses

| Hypothesis | Evidence |
|------------|----------|
| Delta target + residual beats copy (full) | v21 Δ +0.076 |
| Cross-protocol eval required | v14≈v21 only when aligned |
| Dilated-copy baseline for changed pixels | `ndws_metrics.py` fix |