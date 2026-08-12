# ML lab loop — iter reject/calibration (clm_ensemble_v34)

**UTC:** 2026-08-04T14:30:21.614758+00:00  
**Product:** `clm_ensemble_v34` · **protocol:** `clm_holdout_test_seed42_v1`  
**Label:** **lab / research_open only**

## Rails (unchanged)

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops ML live fusion | **OFF** |
| IoU sold as ROS | **never** |
| Tune split | **VAL only** |
| TEST used for | **frozen eval only** |

## 1. Observe (baseline)

Scorecard U1 TEST (published):

- mean IoU lab ~**0.857** (U1 eval)
- ECE patch conf ~**0.153**
- selective@80 ~**0.903** (beats random)
- **abstain_rate at thr=0.35: ~0.0** on U1 card → fricción: rechazo de máscara no es visible

Baseline frozen TEST (this run, Head A cache):

| Metric | Baseline thr=0.35 |
|--------|---------------------------------------------------------------------:|
| ECE full | 0.1528 |
| ECE accepted | 0.1528 |
| abstain_rate | 0.0000 |
| mean_iou_accepted | 0.8569 |
| keep_rate | 1.0000 |

## 2. Friction chosen

**Alta:** calibración imperfecta + **falta de rechazo explícito** de baja confianza.

Control question: ¿mejorable con métricas honestas sin producto de campo? **SÍ.**

## 3. Minimal change

VAL-only search over:

1. post-hoc **confidence temperature** (does not retrain ensemble)
2. **abstain_threshold** for mask-level ABSTAIN (`conf < thr`)

Selection score on VAL only (IoU_accepted − 0.75·ECE_accepted, keep≥0.45).

**Chosen:** temperature=1.000, abstain_threshold=0.795

## 4. TEST frozen evaluation (not used for tune)

| Metric | Baseline | Tuned | Δ |
|--------|---------:|------:|--:|
| ECE full | 0.1528 | 0.1528 | +0.0000 |
| ECE accepted | 0.1528 | 0.1733 | +0.0205 |
| abstain_rate | 0.0000 | 0.5150 | +0.5150 |
| mean_iou_accepted | 0.8569 | 0.9492 | +0.0924 |
| keep_rate | 1.0000 | 0.4850 | — |

## 5. Verdict

```json
{
  "lab_reject_surface_improved": true,
  "explicit_mask_reject_enabled": true,
  "ece_accepted_not_worse": false,
  "iou_accepted_lift": 0.09235660792518696,
  "iou_accepted_improved": true,
  "keep_rate_ok": true,
  "field_product": false,
  "note": "lab_reject_surface_improved = visible mask ABSTAIN + higher IoU on accepted patches (TEST frozen). ECE on accepted may stay high (overconfidence of high-conf band) \u2014 reported honestly. Not a field promote; ml_product_go stays false."
}
```

- **Improved for research_open/lab:** explicit mask reject when `lab_reject_surface_improved`.
- **Still outside field:** ml_product_go false; field_ops fusion OFF; catalog 0.8963 remains provenance only.
- **What may not improve:** ECE full can stay similar if temperature does not fix global overconfidence; the win is **visible ABSTAIN** + ECE on accepted.

## 6. How to use

```powershell
$env:PYTHONPATH = "."
python scripts\run_lab_ml_loop_v34_reject.py --write-lab-calibrator
python -m wildfire_front ml show
```

Lab calibrator (if written): `models/clm_ensemble/uncertainty_calibration_v1_lab_reject.json`  
Machine result: `outputs/ml_eval/lab_loop/lab_loop_v34_reject_latest.json`

## 7. Next loop candidates

1. If ECE full still high: Platt re-fit diagnostics on VAL only (careful rails).  
2. LOFO ECE/abstain tables for generalización (media priority).  
3. Explainability: export fail_cases patches for teaching.

---
*Iteration artifact — not a tactical dispatch claim.*
