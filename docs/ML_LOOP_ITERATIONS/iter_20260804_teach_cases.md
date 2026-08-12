# ML lab loop — iter 5 teach-cases productization

**UTC:** 2026-08-04T14:46:18.474377+00:00  
**Prior:** iter1 reject YES · iter2/3 ECE NO · iter4 LOFO YES  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| IoU as ROS | **never** |
| ECE re-tune same TEST | **stopped** |

## Why this iteration

Fail cases + LOFO board existed as files but were not a first-class CLI/course surface. Productize teaching without metric thrash.

Control question: **YES**

## Locked reject + holdout/LOFO

- reject thr: **0.7949999999999999**
- abstain / IoU acc: **0.515** / **0.9492431452930816**
- U1 IoU / ECE: **0.8568865373678947** / **0.15280955026564416**
- LOFO mean IoU (n=3): **0.7580534465179306**
- note: `holdout_u1_higher_than_lofo_mean — do not over-claim single-holdout IoU`

## Fail-case buckets

- n_rows: **10**
- buckets: `{'accepted_low_iou': 5, 'rejected_high_iou': 5}`

- **accepted_low_iou:** High conf accepted the patch but IoU is weak — overconfidence risk (why thr alone is not enough; ECE residual ~0.15).
- **rejected_high_iou:** Rejected (conf below thr) despite high IoU — conservative false reject trade-off of thr~0.80 reject surface.

## CLI

```powershell
python -m wildfire_front ml cases
python -m wildfire_front ml cases --json
python -m wildfire_front ml cases --bucket accepted_low_iou
```

## Verdict

```json
{
  "fail_cases_productized": true,
  "cli_surface": "wildfire-front ml cases",
  "n_fail_rows": 10,
  "buckets": {
    "accepted_low_iou": 5,
    "rejected_high_iou": 5
  },
  "lofo_n_folds": 3,
  "lofo_iou_mean": 0.7580534465179306,
  "recommended_lab_surface": "iter1_reject_only",
  "ece_holdout_still_unfixed": true,
  "field_product": false,
  "stop_ece_thrash_on_same_test": true,
  "note": "Iter5 wires teaching product surface around locked iter1 reject + iter4 LOFO honesty + fail buckets. No metric retune."
}
```

## Next

1. Optional: per-fire Head A caches for LOFO ECE/reject (inference).
2. New data/features before any same-TEST ECE post-hoc.
3. H1 human demo remains outside this ML track.

---
*Iteration 5 — not field product.*
