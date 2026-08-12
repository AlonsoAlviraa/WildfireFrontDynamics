# ML lab loop — iter 10 next-signal readiness gate

**UTC:** 2026-08-05T07:57:40.443364+00:00  
**Prior:** freeze + smoke + LOFO board (7–9)  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| ECE thrash same TEST | **stopped** |
| auto unfreeze | **false** |

## Control: **YES**

- recommended_next: **W3_new_features_or_data**
- primary_blocker: **None**
- LOFO folds/weights/head_a: **4/3/4**

## Work items

| ID | Status | Title |
|----|--------|-------|
| W1_lofo_head_a_caches | DONE | Build per-fire Head A feature caches for LOFO folds |
| W2_lofo_ece_reject_eval | DONE | Evaluate locked reject thr + ECE on LOFO Head A (frozen TEST-per-fire) |
| W3_new_features_or_data | OPEN | New features or fires before any same-holdout ECE post-hoc |
| W4_human_ml_product_go | BLOCKED | Human promote checklist for ml_product_go (separate from lab_usable) |
| W5_h1_third_party_demo | OUT_OF_SCOPE_ML_LAB | H1 third-party demo / GO_Q human track |

## CLI

```powershell
python -m wildfire_front ml next
python -m wildfire_front ml next --json
```

---
*Iteration 10 — readiness only; not a metric win; not field promote.*
