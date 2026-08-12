# ML lab loop — iter 6 risk–coverage curve

**UTC:** 2026-08-04T14:50:49.502384+00:00  
**Prior:** iter1 reject YES · 2/3 ECE NO · 4 LOFO · 5 teach cases  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| IoU as ROS | **never** |
| ECE re-tune same TEST | **stopped** |

## Why this iteration

Reject thr is one operating point. Productize the **coverage→IoU** selective curve (ranking by conf) and place default thr vs locked thr on the map — without retuning ECE.

Control: **YES**

## Conf band (TEST)

mean 0.7822 · p05 0.7428 · p50 0.7929 · p95 0.8079 · max 0.8079

Note: Tight conf band (~0.74–0.81) explains thr=0.35 never rejects; lab thr~0.80 sits inside the band.

## Selective curve TEST (rank by conf)

| coverage | n_keep | selective IoU | lift vs full |
|---------:|-------:|--------------:|-------------:|
| 1.0000 | 200 | 0.8569 | 0.0000 |
| 0.9000 | 180 | 0.8742 | 0.0173 |
| 0.8000 | 160 | 0.9034 | 0.0465 |
| 0.7000 | 140 | 0.9268 | 0.0699 |
| 0.6000 | 120 | 0.9379 | 0.0810 |
| 0.5000 | 100 | 0.9448 | 0.0879 |
| 0.4850 | 97 | 0.9492 | 0.0924 |
| 0.4000 | 80 | 0.9535 | 0.0966 |

**Highlights:** full IoU 0.8569 · sel@80 0.9034 · lift 0.0465 · ranking_useful=True

## Thr operating points TEST (frozen)

| thr | keep | abstain | IoU accepted | ECE full |
|----:|-----:|--------:|-------------:|---------:|
| 0.3500 | 1.0000 | 0.0000 | 0.8569 | 0.1528 |
| 0.7950 | 0.4850 | 0.5150 | 0.9492 | 0.1528 |
| 0.7500 | 0.7500 | 0.2500 | 0.9234 | 0.1528 |
| 0.7800 | 0.6000 | 0.4000 | 0.9379 | 0.1528 |
| 0.8000 | 0.4350 | 0.5650 | 0.9540 | 0.1528 |
| 0.8200 | 0.0000 | 1.0000 | nan | 0.1528 |

## Verdict

```json
{
  "risk_coverage_curve_built": true,
  "ranking_useful_selective_80": true,
  "default_thr_never_rejects": true,
  "locked_reject_has_visible_abstain": true,
  "recommended_lab_surface": "iter1_reject_only",
  "ece_holdout_still_unfixed": true,
  "field_product": false,
  "stop_ece_thrash_on_same_test": true,
  "note": "Iter6 productizes the coverage\u2192IoU tradeoff and places locked thr on the operating map. Does not claim ECE fixed. Does not change thr."
}
```

## CLI

```powershell
python -m wildfire_front ml curve
python -m wildfire_front ml curve --json
```

---
*Iteration 6 — not field product. Surface stays iter1 reject only.*
