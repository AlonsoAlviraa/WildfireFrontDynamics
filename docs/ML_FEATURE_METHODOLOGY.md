# ML Feature Methodology

> **Status:** canonical  
> **Baseline models:** v21 (legacy17+prev, production), v24 (clean12 hybrid, experimental)  
> **Rails for new experiments:** Features · Temporal · Transfer only

---

## 1. Principles

1. **No constant channels** in production schemas (dead signal).
2. Measure channel usefulness vs **growth** `(target−prev)+`, not only absolute fire.
3. One schema version per training run; name it in `training_summary.json`.
4. Trainer always appends `prev_fire` → `in_channels = C × T + 1`.
5. Promote only under gates G0–G2 (see transfer protocol + loop plan).

---

## 2. Schema registry

Implemented in `wildfire_front/ml/feature_schema.py`.

| Schema | C | Use |
|--------|---|-----|
| `legacy17` | 17 | v10–v22 checkpoints; includes constant padding |
| `clean12` | 12 | elevation, terrain, mean temp, meteo, wind sin/cos, veg, erc |
| **`physics14`** | 14 | **preferred for v25+**: tmin/tmax split + drought/FFMC slot |

### physics14 channel order

| Idx | Name | Notes |
|-----|------|-------|
| 0 | elevation | meters |
| 1 | slope | radians |
| 2 | aspect_sin | from DEM |
| 3 | aspect_cos | |
| 4 | tmin | °C |
| 5 | tmax | °C |
| 6 | humidity | % |
| 7 | wind_speed | m/s |
| 8 | wind_sin | from direction |
| 9 | wind_cos | |
| 10 | precipitation | mm |
| 11 | vegetation | NDVI proxy |
| 12 | erc | /100 |
| 13 | drought_or_ffmc | PDSI if varying else FFMC Van Wagner |

Preprocess: `python kaggle_job/preprocess_ndws.py --schema physics14 ...`

---

## 3. Analysis protocol (before new schemas)

```bash
python scripts/analyze_feature_signal.py --data-dir <npz_root/train> --max-patches 500
```

Reports per channel: std, fraction constant, Pearson vs target / growth / change.  
Output: `outputs/ml_eval/feature_signal_report.json`.

**Must / maybe / never** labels:

- **never:** std ≈ 0 or corr_growth & corr_change both ~0 and not physics-required
- **must:** high |corr| with growth or paper-required meteo
- **maybe:** weak corr but interactions planned

---

## 4. Forbidden experiment types

- Filter-only, pos_weight-only, EMA/focal-only without new input
- Train-CLM eval as transfer GO
- Tier-1 “changed” Δ vs naive copy (tautological)

---

## 5. Loop template (mandatory)

```
hypothesis | single_change | schema | T | train_filter | eval_protocol | primary_metric | go_if
```

Queue: `scripts/experiment_queue_features.json`
