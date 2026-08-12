# ML lab loop — iter 4 generalization + teaching lock

**UTC:** 2026-08-04T14:42:34.002374+00:00  
**Prior:** iter1 reject YES · iter2/3 ECE NO  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| IoU as ROS | **never** |
| ECE re-tune same TEST | **stopped** |

## Why this iteration

After two failed ECE improvements on the same holdout, change friction to **generalization visibility** + **lock teaching surface** (not more post-hoc).

Control question: **YES** — measurable LOFO table + recipe without field product.

## Holdout reference (labels)

- U1 TEST mean IoU (lab): **0.8568865373678947**
- U1 ECE (lab): **0.15280955026564416**
- Catalog holdout IoU: **0.8963** (provenance only)

## LOFO mask IoU (existing evals — different protocol from U1 ECE)

| Fold | model_iou | copy_iou | Δ vs copy |
|------|----------:|---------:|----------:|
| CARDOSO | 0.7978 | 0.6418 | 0.1560 |
| LA_ESTRELLA_ACOM1 | 0.7832 | 0.3593 | 0.4238 |
| LA_ESTRELLA_ACOM2 | 0.6932 | 0.3698 | 0.3233 |

**n_folds:** 3 · **mean IoU:** 0.7581 · **std:** 0.0463 · **min–max spread:** 0.1046

**Generalization note:** `holdout_u1_higher_than_lofo_mean — do not over-claim single-holdout IoU`

**Honesty:** LOFO rows are leave-one-fire mask IoU from existing training evals — not the same protocol as U1 Head A ECE. Do not mix as one number.

## Locked lab reject surface (iter1 — still recommended)

| thr | 0.7949999999999999 |
| TEST abstain_rate | 0.515 |
| TEST IoU accepted | 0.9492431452930816 |

## Teach recipe

1. `python -m wildfire_front ml list`
1. `python -m wildfire_front ml show`
1. `python -m wildfire_front ml card --mode offline --scenario abstain`
1. Explain: thr~0.80 enables mask ABSTAIN; thr=0.35 never rejects
1. Explain: LOFO IoU varies by fire — single holdout is not universal
1. Never: IoU as ROS; never field_ops fusion ON; ml_product_go false

## Verdict

```json
{
  "generalization_table_built": true,
  "lofo_spread_material": true,
  "ece_holdout_still_unfixed": true,
  "recommended_lab_surface": "iter1_reject_only",
  "field_product": false,
  "stop_ece_thrash_on_same_test": true,
  "note": "Iter4 productizes multi-fire visibility + teaching recipe. Does not claim ECE fixed. LOFO IoU \u2260 U1 ECE protocol."
}
```

## Next

1. Optional: build per-fire Head A caches for true LOFO ECE/reject (needs inference).
2. Keep using reject thr for research_open demos.
3. Do not re-open ECE post-hoc on the same TEST without new features/data.

---
*Iteration 4 — not field product.*
