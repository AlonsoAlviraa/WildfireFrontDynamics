# Tobarra KEEP-or-KILL mega goal — result

**UTC:** 2026-08-05  
**Status:** **CLOSED** · process **MET** · scientific **KILL**  
**Hub:** `docs/goals/README.md` · snapshot `docs/CURRENT_STATE.md`

## Fresh train

| Field | Value |
|-------|------:|
| model_iou (Tobarra test) | **0.4776** |
| copy_baseline | 0.3284 |
| improvement_vs_copy | **+0.1492** |
| Head A baseline | 0.4894 |
| K1 lift | **−0.0118** (need ≥ +0.03) |

- Dir: `outputs/ml_eval/lofo_tobarra_keep_attempt_20260805T092936Z`  
  (pointer: `lofo_tobarra_keep_attempt_latest`)
- Init: `weights_v21_best.pt` · early stop epoch 11 · best epoch 5 · CPU ~8 min
- Fold: train/val/test **531 / 59 / 300** · **leak = 0**
- Early-stop on **fold val** only (non-Tobarra) · primary thr **0.5** (no thr/ECE on test)

## K1–K5

| ID | Pass |
|----|:----:|
| K1 lift vs 0.489 | **FAIL** |
| K2 beats copy | **PASS** |
| K3 zero leak | **PASS** |
| K4 no thr/ECE on test | **PASS** |
| K5 rails | **PASS** |

**KILL** = do not promote these weights over production ensemble Head A.

## Comparison

| Run | Tobarra IoU | vs copy | K1 vs 0.489 |
|-----|------------:|--------:|-------------|
| Ensemble Head A baseline | 0.489 | — | — |
| v29 LOFO (prior) | 0.494 | +0.165 | FAIL (Δ+0.004) |
| **This attempt** | **0.478** | **+0.149** | **FAIL (Δ−0.012)** |

## T4 regression guard

- Keep-attempt weights **not** re-scored on Cardoso / multi-fire (KILL → no promote).
- Prior frozen Head A: Hellín ~0.79 · Brazatortas ~0.54 · Retuerta ~0.47 (W3 pack).
- No silent multi-fire collapse claimed.

## Rails

- `ml_product_go`: **false**
- `field_ops` fusion: **OFF**
- no ECE thrash holdout TEST · IoU ≠ ROS · weights **lab-only**

## Honesty

- Beats copy ≠ KEEP under K1.
- Fresh init-from-v21 underperformed v29 slightly on test IoU.
- v29 `GO_TRANSFER_LOFO` is copy-relative, not this KEEP bar.
- Do **not** re-open same recipe without new signal.

## Artifacts

| Path | Role |
|------|------|
| `outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json` | KILL scorecard |
| `outputs/ml_eval/lab_loop/lab_loop_v34_tobarra_keep_latest.json` | machine board |
| `outputs/ml_eval/lab_loop/tobarra_leak_audit_latest.json` | leak = 0 |
| `docs/goals/MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md` | goal doc (closed) |

## Tests

```text
pytest tests/test_tobarra_kill_score.py tests/test_w3_signal.py tests/test_align_geotiff_stack.py -q
# 11 passed
```
