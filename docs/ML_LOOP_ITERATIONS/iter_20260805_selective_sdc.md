# Lab loop — Selective SDC (deep research S1)

**UTC:** 2026-08-05T11:14:49.689930+00:00
**Verdict:** **KILL_SDC_PROMOTE**
**Recommended surface:** `iter1_reject_only`

## Kill bar

- VAL sel@80 lift SDC vs inv_entropy ≥ **+0.02**
- Observed lift: **-0.0056**
- VAL AURC SDC / entropy: 0.1000 / 0.0991

## VAL bake-off (sel@80 · AURC lower better)

| Score | sel@80 | lift vs full | AURC |
|-------|-------:|-------------:|-----:|
| inv_disagreement | 0.7934 | +0.0551 | 0.1007 |
| inv_entropy | 0.7993 | +0.0610 | 0.0991 |
| logistic_conf | 0.7973 | +0.0590 | 0.0988 |
| margin | 0.7936 | +0.0554 | 0.0998 |
| multi_signal | 0.7940 | +0.0557 | 0.0994 |
| soft_dice_proxy | 0.7936 | +0.0554 | 0.1000 |

## TEST report (one-shot, not for thrash)

| Score | sel@80 | lift vs full | AURC |
|-------|-------:|-------------:|-----:|
| inv_disagreement | 0.9117 | +0.0548 | 0.0425 |
| inv_entropy | 0.9159 | +0.0591 | 0.0441 |
| logistic_conf | 0.9034 | +0.0465 | 0.0457 |
| margin | 0.8965 | +0.0396 | 0.0480 |
| multi_signal | 0.9157 | +0.0589 | 0.0421 |
| soft_dice_proxy | 0.8965 | +0.0396 | 0.0480 |

## CRC-lite (VAL thr · TEST once)

- risk_alpha: **0.15**
- VAL thr: **0.7999999999999999** · risk 0.13503864319906433 · abstain 0.6025641025641026
- TEST @ thr: IoU_acc **0.9539900348261189** · risk 0.04600996517388112 · abstain 0.565

## Rails

- ml_product_go: **false**
- field_ops fusion: **OFF**
- IoU ≠ ROS · lab only

Machine: `C:/Users/Mariano/Documents/ALONSOO/WildfireFrontDynamics/outputs/ml_eval/lab_loop/lab_loop_v34_selective_sdc_latest.json`
