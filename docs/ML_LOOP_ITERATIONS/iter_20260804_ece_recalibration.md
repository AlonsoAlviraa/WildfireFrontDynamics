# ML lab loop — iter 2 ECE recalibration (clm_ensemble_v34)

**UTC:** 2026-08-04T14:33:55.254391+00:00  
**Continues from:** iter_20260804_reject_calibration (reject surface)  
**Label:** **lab / research_open only**

## Rails (unchanged)

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops ML live fusion | **OFF** |
| IoU as ROS | **never** |
| Tune split | **VAL only** |

## Prior iter 1 (reject) — locked results

| Metric | Value |
|--------|------:|
| abstain_rate (TEST) | 0.515 |
| IoU accepted | 0.9492 |
| thr | 0.795 |
| lab_reject_surface_improved | True |

## Friction this iteration

**Alta residual:** ECE full ~0.15 (overconfianza). Control question: **SÍ** (post-hoc VAL).

## Minimal change

Post-hoc on **confidence logits** after base calibrator:

- methods compared on **VAL ECE**: none · temperature · Platt  
- **Chosen:** `temperature`  
- TEST frozen only for reporting

## TEST frozen results (ECE)

| | Baseline | Tuned | Δ |
|--|--------:|------:|--:|
| ECE full | 0.1528 | 0.1744 | +0.0215 |
| mean conf | 0.7822 | 0.7606 | — |
| improved_on_test | | **False** | |

VAL: ECE 0.0987 → 0.0085

## Combined with reject (teaching surface)

| Metric | Baseline thr=0.35 | Combined |
|--------|------------------:|---------:|
| abstain_rate | 0.000 | 0.535 |
| mean_iou_accepted | 0.8569 | 0.9533 |
| ECE full | 0.1528 | 0.1744 |
| thr | 0.35 | 0.775 |

## Verdict

- ECE improved on TEST: **False**
- Reject surface still available: **True**
- Field product: **false**

## How to run

```powershell
$env:PYTHONPATH = "."
python scripts\run_lab_ml_loop_v34_ece.py --write-lab-calibrator
python -m wildfire_front ml show
```

Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_ece_latest.json`  
Latest pointer: `outputs/ml_eval/lab_loop/lab_loop_v34_latest.json`

## Next loop candidates

1. If ECE still high: feature-space re-fit logistic on VAL (heavier).  
2. LOFO ECE/reject tables.  
3. Teach fail_cases for rejected patches.

---
*Iteration 2 — not tactical dispatch.*
