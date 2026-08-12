# Mega Goal — Tobarra KEEP **or** KILL (fresh train, zero leak)

| Campo | Valor |
|-------|--------|
| **Status** | **CLOSED — process MET · scientific KILL** (2026-08-05) |
| **Prior** | W3 mega **MET** with Tobarra **INCONCLUSIVE** (v29 re-score only) |
| **Harness Rhai** | `.grok/workflows/wfd-ml-tobarra-keep-or-kill.rhai` |
| **Invoker PS1** | `scripts/run_mega_goal_tobarra_keep.ps1` |
| **Train fold** | `artifacts/clm_ndws_patches/lofo_v1/tobarra_20240802` |
| **Hub** | [docs/goals/README.md](./README.md) · [docs/CURRENT_STATE.md](../CURRENT_STATE.md) |

---

## Result (canonical)

| Field | Value |
|-------|------:|
| **Verdict** | **KILL** |
| model IoU (Tobarra test) | **0.4776** |
| copy baseline | 0.3284 |
| improvement_vs_copy | **+0.1492** |
| Head A baseline | 0.4894 |
| K1 lift | **−0.0118** (need ≥ +0.03) |
| n_leaked_train_val | **0** |
| init | `weights_v21_best.pt` |
| epochs / device | 12 / cpu · early stop 11 · best epoch 5 |
| attempt dir | `outputs/ml_eval/lofo_tobarra_keep_attempt_20260805T092936Z` |

### K1–K5

| ID | Pass | Note |
|----|:----:|------|
| K1 | **FAIL** | below Head A +0.03 bar |
| K2 | **PASS** | beats copy ≥ 0.05 |
| K3 | **PASS** | zero target leak |
| K4 | **PASS** | no thr/ECE fit on test |
| K5 | **PASS** | rails cold |

**KILL** = do not promote these weights over production ensemble Head A.  
Beats copy ≠ KEEP. v29 prior IoU ~0.494 still slightly better; neither clears K1.

### Process criteria T1–T6

All **met** (fresh train, leak audit, KEEP/KILL board, rails, tests, multi-fire note).  
`/goal` harness: `met: true` in 1 round.

### Boards

- Human: `docs/ML_LOOP_ITERATIONS/iter_tobarra_keep_or_kill_latest.md`
- Machine: `outputs/ml_eval/lab_loop/lab_loop_v34_tobarra_keep_latest.json`
- Scorecard: `outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json`  
  (alias: `tobarra_kill_scorecard.json` after re-score)

---

## Hard criterion (reference — already met)

**T1 FRESH_RUN** — New train under `lofo_tobarra_keep_attempt_*` with weights + evaluation_metrics on Tobarra test.

**T2 ZERO_LEAK** — `n_leaked_train_val == 0`.

**T3 KILL_BOARD** — Verdict **KEEP** or **KILL** after full train (not INCONCLUSIVE). K1–K5 on **this** run.

**T4 REGRESSION_GUARD** — Note Cardoso/Hellín; no silent multi-fire collapse claim on promote (KILL → no promote).

**T5 RAILS** — fusion false · `ml_product_go` false · IoU ≠ ROS.

**T6 TESTS + BOARD** — pytest kill/w3/align green; MD + JSON board.

---

## Kill criteria

| ID | Rule | On fail |
|----|------|---------|
| K1 | test_mean_iou − 0.489 ≥ **0.03** | KILL weights claim |
| K2 | improvement_vs_copy ≥ **0.05** | KILL |
| K3 | n_leaked_train_val = **0** | KILL protocol |
| K4 | no thr/ECE on Tobarra test / U1 TEST | KILL claim |
| K5 | rails cold | KILL claim |

**KEEP** only if K1∧K2∧K3∧K4∧K5.

---

## Re-audit only (do not thrash)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
# Re-score latest metrics as fresh-train path:
python scripts/score_tobarra_kill_criteria.py `
  --metrics outputs/ml_eval/lofo_tobarra_keep_attempt_latest/evaluation_metrics.json `
  --fresh-train `
  --out outputs/ml_eval/lab_loop/tobarra_keep_or_kill_scorecard.json
# Pipeline smoke (short train):
.\scripts\run_mega_goal_tobarra_keep.ps1 -Smoke
```

**Do not** re-open full 12-epoch KEEP hunt without new signal (data/features/protocol).

---

## Out of scope

- Flipping `ml_product_go` or field_ops fusion  
- ECE post-hoc on U1 TEST  
- Claiming KEEP from v29 re-score alone  
- H1 third-party demo  

## One-liner

**CLOSED:** fresh Tobarra LOFO train + zero leak → **KILL** under K1–K5 — lab only, rails locked.
