# Mega Goal — W3 Finetune + new fires + zero target leak

| Campo | Valor |
|-------|--------|
| **Status** | **CLOSED — MET** (2026-08-05) |
| **Scientific follow-up** | Tobarra weights later **KILL** via [MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md](./MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md) |
| **Harness (project)** | `.grok/workflows/wfd-ml-w3-mega-goal.rhai` |
| **Harness (goal CLI)** | `scripts/run_mega_goal_w3.ps1` → grok-workflows `goal` |
| **Hub** | [docs/goals/README.md](./README.md) · [docs/CURRENT_STATE.md](../CURRENT_STATE.md) |

---

## Result (canonical)

| Criterion | Result |
|-----------|--------|
| **C1 NEW_FIRE** | **PASS** — Hellín / Brazatortas / Retuerta: align + NPZ + Head A thr=0.795 frozen |
| **C2 TOBARRA_KILL** | **PASS (process)** — protocol applied; at W3 close: v29 re-score **INCONCLUSIVE**; later fresh train → **KILL** |
| **C3 RAILS** | **PASS** — fusion OFF · `ml_product_go` false · no ECE thrash |
| **C4 BOARD** | **PASS** — multi-fire MD + JSON |
| **C5 TESTS** | **PASS** — pytest w3/align/kill green |

### Head A multi-fire (frozen thr 0.795)

| Fire | mean IoU | n | ECE (full) |
|------|---------:|--:|-----------:|
| hellin_2024 | **0.789** | 60 | 0.077 |
| brazatortas_2025 | **0.544** | 60 | 0.224 |
| retuerta_2025 | **0.466** | 40 | 0.333 |

IoU = mask lab quality, **not ROS**.

### Boards

- `docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md`
- `outputs/ml_eval/lab_loop/lab_loop_v34_w3_mega_latest.json`
- Expert: `outputs/ml_eval/lab_loop/lab_loop_v34_w3_expert_latest.json`

---

## Hard criterion (reference — already met)

**C1 NEW_FIRE** — ≥1 fire **not** in `{CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2, tobarra_20240802}` has aligned LWIR chains, NPZ patches, and frozen Head A eval (production cal + thr lock ~0.795, **no thr/ECE fit on that fire**).

**C2 TOBARRA_KILL** — K1–K5 scorecard on fresh LOFO **or** honest re-score of v29, with `n_leaked_train_val == 0`. Verdict KEEP | KILL | INCONCLUSIVE (INCONCLUSIVE only valid for re-score / train-blocked).

**C3 RAILS** — `field_ops.allow_ml_live_in_fusion == false` · `ml_product_go == false`.

**C4 BOARD** — Iteration MD + lab_loop JSON with multi-fire table + honesty.

**C5 TESTS** — pytest green for W3/align modules.

---

## How to re-audit (not re-open)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
.\scripts\run_mega_goal_w3.ps1
# expert path:
$env:PYTHONPATH = "."
python scripts/run_lab_ml_loop_v34_w3_expert.py --fires hellin_2024 brazatortas_2025 retuerta_2025
```

## Out of scope (still)

- Flipping `ml_product_go` or field_ops fusion  
- ECE post-hoc on U1 holdout TEST  
- Claiming IoU = ROS  
- Replacing H1 third-party demo  

## One-liner

**MET:** new-fire Head A signal + Tobarra protocol with zero leak and rails locked — lab only. Tobarra weight claim later settled as **KILL**.
