# ML lab loop — iter 7 freeze / handoff

**UTC:** 2026-08-04T14:55:08.524620+00:00  
**Prior:** iters 1–6 (reject YES · ECE NO · LOFO · teach · curve)  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| recommended surface | **iter1_reject_only** |
| locked thr | **0.7949999999999999** |
| ECE thrash same TEST | **stopped** |

## Control: **YES**

- lab_usable_freeze: **True**
- field_product: **false**
- note: Freeze means lab teaching/demo surface is complete and honest. It is NOT field promote and does NOT fix ECE.

## Loop board

| Iter | Name | Lab promote? | Headline |
|-----:|------|:------------:|----------|
| 1 | reject | YES | thr~0.795 abstain=0.515 IoU_acc=0.9492431452930816 |
| 2 | ece_posthoc | NO | TEST ECE did not improve (no ECE promote) |
| 3 | refit | NO | TEST ECE did not improve after logistic refit |
| 4 | generalization | YES | LOFO mean IoU=0.7580534465179306 n=3 vs U1=0.8568865373678947 |
| 5 | teach_cases | YES | fail rows=10 buckets={'accepted_low_iou': 5, 'rejected_high_iou': 5} |
| 6 | risk_curve | YES | full=0.8568865373678947 sel@80=0.903428533834858 lift=0.04654199646696333 |

## Checks

- [x] `artifacts_complete`
- [x] `iterations_1_to_6_present`
- [x] `ml_product_go_false`
- [x] `field_ops_fusion_off`
- [x] `recommended_surface_iter1_reject`
- [x] `stop_ece_thrash`
- [x] `reject_surface_improved`
- [x] `ece_not_claimed_improved`
- [x] `lofo_table_present`
- [x] `risk_curve_present`
- [x] `cli_surfaces_documented`

## CLI

```powershell
python -m wildfire_front ml freeze
python -m wildfire_front ml freeze --json
```

## Do not

- Claim ml_product_go true without human promote checklist
- Turn field_ops.allow_ml_live_in_fusion ON
- Say IoU = ROS / m·min⁻¹
- Sell U1 ~0.86 as multi-fire universal (LOFO ~0.76)
- Claim ECE improved (iters 2–3 failed on TEST)
- Re-tune ECE post-hoc on the same TEST without new data/features
- Treat thr=0.35 as a working mask reject

---
*Iteration 7 — freeze ≠ field promote. ECE not fixed.*
