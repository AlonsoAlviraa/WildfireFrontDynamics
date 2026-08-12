# Schema Bridge A/B Fix v2 (loop-engineering)

**Date:** 2026-08-07  
**Status:** **GATE PASS** on Kaggle v2 (kernel v4)  

### v2 result (evidence)

| Arm | mean | min |
|-----|------|-----|
| scratch | 0.438 | 0.373 |
| **partial_init** | **0.669** | **0.621** |
| **Δ mean** | **+0.231** | gate ≥0.02 **PASS** |

Board: `outputs/kaggle_schema_bridge_ab_v2/schema_bridge_ab_board.json`  
Stamp: `outputs/ml_eval/lab_loop/schema_bridge_ab_v2_result.json`

## v1 failure (evidence)

From `outputs/kaggle_schema_bridge_ab/schema_bridge_ab_board.json`:

* scratch mean = partial mean = **0.438** (identical folds)
* `improvement_vs_copy_iou = 0` all folds
* VAL log: IoU@0.5 stuck at **copy** every epoch; early-stop saved ep.1 with delta=0

### Root causes

1. **Early-stop metric** `improvement_vs_copy_iou` never rises above 0 on weak projected packs → checkpoint is ep.1 random/near-copy.  
2. **Partial init path** relied on monkeypatching `build_model` after git clone; no durable full spatial `state_dict` passed via `init_weights_path`.  
3. `init_weights_path` only supported **strict** same-shape loads (17+1 vs 14+1 mismatch).

## v2 design

| Change | Where |
|--------|--------|
| `export_spatial_init_from_multi_if` → full 15ch state_dict | `wildfire_front/ml/schema_bridge.py` |
| `init_weights_strict` + unwrap wrappers | `wildfire_front/ml/unet_train.py` |
| A/B kernel: pre-export adapted.pt; load strict; **early_stop=`model_iou`** | `kaggle_job/run_schema_bridge_ab.py` |
| Tests: export + real multi_if if present | `tests/test_schema_bridge.py` |

### Gate (unchanged honesty)

`mean(partial) − mean(scratch) ≥ 0.02` **and** `min(partial) ≥ min(scratch)`.

### Not claimed

* Not sealed T1 recipe beat  
* Not field fusion  
* Elev GAP / temp_split_proxy remain stamped  

## PR plan (single increment)

1. schema_bridge export + unet strict flag + tests  
2. Kaggle A/B v2 push + score  
3. If gate FAIL: elev_override re-project + full pack size (next loop)
