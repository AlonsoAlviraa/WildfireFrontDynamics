# MEMORY — WildfireFrontDynamics

> Updated: 2026-07-14

---

## Current State

| Item | Value |
|------|-------|
| **Production model** | v21 — Residual + delta target |
| **IoU full @0.5** | 0.226 (test 979, any_fire + CLM) |
| **Δ vs copy (full)** | +0.076 — **beats copy baseline** |
| **Manifest** | `models/production/manifest.json` |
| **Next experiment** | v22 (filter-mode changed) |
| **Kaggle account** | `alonsoalviraaaa` |

---

## Critical learnings

1. **Copy baseline depends on protocol** — 0.788 (both_fire dense) vs 0.150 (any_fire test)
2. **Tier-1 +0.87 was a metric bug** — naive copy IoU on changed pixels is always 0
3. **v21 won with delta target** — growth-only loss + residual + early-stop on full Δ
4. **Cross-protocol eval is mandatory** — v14≈v21 only when test set aligned (979 patches)
5. **Kaggle bloat** — clone to `/tmp`, not `/kaggle/working`

---

## Production stack

- Inference: `SpreadPredictor` in `wildfire_front/ml/spread_predictor.py`
- CLI: `scripts/predict_spread.py`
- Weights: `scripts/install_production_weights.py` (from kaggle_outputs_v21)
- Audit: `docs/PRODUCTION_READINESS_AUDIT.md`

---

## Experiment timeline (recent)

| Ver | IoU | Δ full | Verdict |
|-----|-----|--------|---------|
| v19 | 0.052 | -0.10 | diagnostic |
| v20 | 0.050 | -0.10 | failed |
| **v21** | **0.226** | **+0.076** | **production** |

---

## Open questions

- [ ] v22 changed-filter improves Δ changed without losing IoU?
- [ ] TorchScript export for deployment?
- [ ] Tobarra/CLM real-fire validation of v21?