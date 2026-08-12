# Goals hub — WildfireFrontDynamics

> **As of:** 2026-08-10  
> **Live snapshot:** `docs/CURRENT_STATE.md`  
> **ML proven path:** `docs/ml/README.md` · **Repo map:** `docs/REPO_MAP.md`  
> Mega goals are **closed** unless re-opened with new signal. Do not thrash closed KILL/MET.

---

## ML closeout (2026-08-10) — MET

| Item | Value |
|------|--------|
| Decision | **`FREEZE_ML_AND_REQUEST_DATA`** |
| Spec | [`docs/GOAL_ML_CLOSEOUT.md`](../GOAL_ML_CLOSEOUT.md) |
| Stamp | `outputs/ml_eval/canonical/ML_CLOSEOUT_DECISION.json` |
| Sealed champion | exact_force_ema_long mean **0.788** / min **0.707** |
| Weather champion | era5_long mean **0.576** (ΔW0 **+0.019**) |
| Next queue | **DATA_INTAKE** chain_honest — not sealed hparam thrash |

---

## Closed mega goals (ML lab)

| ID | Doc | Process | Scientific result | Artifacts |
|----|-----|---------|-------------------|-----------|
| **W3** new fires + zero leak | [MEGA_GOAL_W3_FINETUNE_NO_LEAK.md](./MEGA_GOAL_W3_FINETUNE_NO_LEAK.md) | **MET** | Multi-fire Head A on disk; Tobarra protocol scored (then superseded) | `iter_w3_mega_goal_latest.md` · `lab_loop_v34_w3_mega_latest.json` |
| **Tobarra KEEP-or-KILL** | [MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md](./MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md) | **MET** | Fresh LOFO → **KILL** (K1 fail) | `iter_tobarra_keep_or_kill_latest.md` · `tobarra_keep_or_kill_scorecard.json` |

### Tobarra KILL (canonical numbers)

| Metric | Value |
|--------|------:|
| Fresh test IoU | **0.4776** |
| Copy Δ | **+0.149** |
| Head A baseline | **0.4894** |
| K1 lift | **−0.012** (need ≥ +0.03) |
| Leak | **0** |
| Verdict | **KILL** — no promote over ensemble Head A |

Train dir: `outputs/ml_eval/lofo_tobarra_keep_attempt_20260805T092936Z`  
(latest pointer: `outputs/ml_eval/lofo_tobarra_keep_attempt_latest/`)

### Rails (locked)

- `field_ops.allow_ml_live_in_fusion` = **false**  
- `ml_product_go` = **true** (lab GO ≠ field fusion; 2026-08-05 promote)  
- No thr/ECE fit on U1 TEST or Tobarra test  
- IoU ≠ ROS · weights lab-only · Tobarra KEEP reopen forbidden  

---

## How they were run

| Goal | Rhai | Goal CLI PS1 |
|------|------|--------------|
| W3 | `.grok/workflows/wfd-ml-w3-mega-goal.rhai` | `scripts/run_mega_goal_w3.ps1` |
| Tobarra | `.grok/workflows/wfd-ml-tobarra-keep-or-kill.rhai` | `scripts/run_mega_goal_tobarra_keep.ps1` |

Re-run only for **audit / smoke**, not to “try again” without new data:

```powershell
# Smoke pipeline only
.\scripts\run_mega_goal_tobarra_keep.ps1 -Smoke
# Re-score existing latest metrics (no train)
$env:PYTHONPATH = "."
python scripts/score_tobarra_kill_criteria.py --metrics outputs/ml_eval/lofo_tobarra_keep_attempt_latest/evaluation_metrics.json --fresh-train
```

---

## Active product goals (not ML mega)

| Track | Status | Next |
|-------|--------|------|
| **H1 / GO_Q** | open (human) | Third-party demo + acta · `docs/H1_GO_Q_RUNBOOK.md` |
| **E1–E3 evidence** | eng | Demo pack + Reliability Report + replay |
| **O2 / O5** | external | Nacional perimeter / 2º grade A |
| **Graph v6.1** | active | Primary = H1 + evidence; research R\* 0 h retrain |

Workflows (ops/status): `wfd-status-sync`, `wfd-external-unblock`, `wfd-pilot-regression`, `wfd-open-pack-audit`, `wfd-autonomous-cycle` (weekly honesty only).

---

## Optional next ML goals (only if new signal)

Do **not** re-open Tobarra KEEP with same init/recipe. Candidates:

1. **New fire patches** (non-pack) with align + Head A frozen thr — extend W3 table  
2. **Feature / architecture experiment** with pre-registered kill bar (K1-style)  
3. **Uncertainty honesty** on hard fires (Tobarra ECE high) without thrash same-TEST  

**Deep research shortlist (2026-08-05):** selective SDC + conformal mask · EFFIS open geometry · arrival-time ROS ops · **not** GFM full retrain.  
→ `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md`

Any new mega goal needs: hard criterion doc under `docs/goals/`, scorer, board path, rails immutable.

---

## Lab loop map (v34)

| Iters | Theme | Status |
|-------|--------|--------|
| 1–8 | reject / ECE / refit / teach / curve / freeze / smoke | DONE (surface = iter1 reject) |
| 9–12 | LOFO board + Head A + Tobarra hard | DONE |
| 13–14 | W3 inventory + expert align | DONE |
| 15–16 | W3 mega harness + board | **MET** |
| 17 | Tobarra fresh KEEP-or-KILL | **KILL** |

Plan status machine: `docs/PLAN_ML_PRODUCT_STATUS.json`  
Entry: `docs/ML_PRODUCT_START_HERE.md`
