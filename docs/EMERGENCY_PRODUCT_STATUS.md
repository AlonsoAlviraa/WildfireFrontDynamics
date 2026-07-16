# Emergency product status (lives first)

**Updated:** 2026-07-16  
**Smoke:** `python scripts/smoke_emergency_products.py`  
**Briefing:** `python scripts/emergency_briefing.py --fire tobarra_20240802`

## G1 / NDWS closed

| Run | IoU | Δ copy | Verdict |
|-----|-----|--------|---------|
| v21 production | 0.226 | +0.076 | **FREEZE research baseline** |
| v25/v26 features | ≤0.224 | ≤+0.074 | NO_PROMOTE |
| v27 T=2 | 0.2253 | +0.0755 | NO_PROMOTE |
| **v27b T=3** | **0.2249** | **+0.0751** | **NO_PROMOTE → KILL features+temporal** |

Evidence: `docs/V27B_TEMPORAL_VERDICT.json`, `docs/G1_KILL_FEATURES_TEMPORAL.json`  
**Emergency ML primary remains `clm_v28`.** NDWS is research-only.

## Shippable for emergencies

| Product | What it does |
|---------|--------------|
| **front_dynamics_v1** | Observed ROS, grade A/B/C, sector head/flank/rear + IQR |
| **short_horizon_envelope_v2_sector** | 15/30/60 min **head/flank/rear radii** from observed ROS |
| **emergency_briefing.md** | One-command human brief (grade, ROS, sectors, envelope, blocked items) |
| **clm_v28** | Spain-like next-day ML (holdout + LOFO validated) |
| **ndws_v21** | Research baseline only |

## How to run

```bash
python scripts/enrich_emergency_ops.py
python scripts/emergency_briefing.py --fire tobarra_20240802
python scripts/smoke_emergency_products.py
```

## Explicitly blocked / not claimed

- Multi-IF anchors without external Vp/ha  
- Official Hausdorff without official GeoJSON (path BLOCKS honestly)  
- Validated tactical 15/30/60 dispatch  
- NDWS G1 “best model for emergencies”
