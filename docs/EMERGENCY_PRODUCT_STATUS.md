# Emergency product status (lives first)

**Updated:** 2026-07-16  
**Smoke:** `python scripts/smoke_emergency_products.py`

## Shippable for emergencies (defendable)

| Product | What it does | Gate |
|---------|--------------|------|
| **front_dynamics_v1** | Observed ROS (m/min), grade A/B/C, **sector head/flank/rear**, uncertainty IQR | Tobarra A; multi-IF packs |
| **short_horizon_envelope** | 15/30/60 min **extrapolated** distance from observed ROS | Labeled NOT tactical dispatch |
| **clm_v28** | Spain-like next-day mask (ML) | Holdout Δ>0 + LOFO 4/4 Δ>0 |
| **ndws_v21** | Global research baseline only | **Not** emergency primary |

## Explicitly blocked / not claimed

| Need | Status |
|------|--------|
| Multi-IF INFOCAM anchors (O1/O5) | BLOCKED without external Vp/ha |
| Official perimeter Hausdorff (O2) | Path wired; BLOCKED until GeoJSON/EFFIS vector |
| NDWS G1 (IoU≥0.25) | Features/temporal NO_PROMOTE; not emergency path |
| Validated 15/30/60 tactical dispatch | **Never claimed** without independent anchors |

## How to run (ops)

```bash
python scripts/enrich_emergency_ops.py --packs tobarra_20240802,cardoso_2025,hellin_2024,brazatortas_2025
python scripts/smoke_emergency_products.py
# Official O2 without reference → BLOCKED
python scripts/eval_perimeter_hausdorff.py --observed outputs/observatorio/tobarra_20240802/main_front.geojson --mode official
```

## Monetization / emergency value (honest)

- **Value now:** multi-estimator observed front speed + quality + sector guidance + envelope radius for **planning awareness**, plus CLM transfer model for Spain-like patch prediction.
- **Not sold as:** autonomous dispatch AI or guaranteed perimeter forecast.
