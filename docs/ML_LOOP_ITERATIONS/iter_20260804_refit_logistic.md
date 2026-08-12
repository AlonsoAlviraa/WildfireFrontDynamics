# ML lab loop — iter 3 re-fit logistic Head A (clm_ensemble_v34)

**UTC:** 2026-08-04T14:37:11.855653+00:00  
**Prior:** iter1 reject **YES** · iter2 ECE post-hoc **NO**  
**Label:** **lab / research_open only**

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| Fit split | **VAL only** |
| TEST | frozen eval only |

## Friction

Residual **ECE ~0.15** after post-hoc conf temperature failed on TEST.  
Control: re-fit full logistic on VAL Head A features — **YES attempted**.

## Change

1. `fit_logistic_calibrator` on VAL features/labels (L2=0.05)  
2. Optional second stage on VAL 20% outer: **platt**  
3. VAL-only reject thr search on new confidences  
4. Fail-case export for teaching (accepted low IoU / rejected high IoU)

## TEST frozen results

| Metric | Prod cal thr=0.35 | Refit thr=0.35 | Refit+reject |
|--------|------------------:|---------------:|-------------:|
| ECE full | 0.1528 | 0.1782 | 0.1782 |
| abstain_rate | 0.000 | 0.000 | 0.535 |
| mean_iou_accepted | 0.8569 | 0.8569 | 0.9533 |

Δ TEST ECE (refit vs prod): **+0.0254**

Compare to iter1 reject on prod cal (thr≈0.80):  
iou_accepted=0.9492,  
abstain=0.515

## Verdict

```json
{
  "ece_improved_on_test": false,
  "reject_surface_available": true,
  "iou_accepted_lift_vs_baseline_full": 0.09643602461177325,
  "lab_refit_recommended": false,
  "field_product": false,
  "note": "Recommend lab_refit only if TEST ECE drops and reject still works. Production uncertainty_calibration_v1.json unchanged unless human promotes lab artifact."
}
```

- **lab_refit_recommended:** False  
- If false: keep **iter1 reject surface** as primary lab teaching path; do not replace prod calibrator.

## Commands

```powershell
$env:PYTHONPATH = "."
python scripts\run_lab_ml_loop_v34_refit.py --write-lab-calibrator
python -m wildfire_front ml show
```

Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_refit_latest.json`  
Latest: `outputs/ml_eval/lab_loop/lab_loop_v34_latest.json`

## Next candidates

1. LOFO / multi-fire generalization tables  
2. If refit helps: human review lab_refit artifact  
3. Course section: fail_cases JSON

---
*Iteration 3 — not field product.*
