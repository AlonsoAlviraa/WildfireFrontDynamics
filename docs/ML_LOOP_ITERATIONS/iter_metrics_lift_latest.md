# ML lab loop — metrics lift (PR1–PR3a instrumentation + harness)

| Campo | Valor |
|-------|--------|
| **Date** | 2026-08-06 |
| **Product rail** | `lab_ml` only (`clm_ensemble_v34`) |
| **Design** | `docs/design/DESIGN_ML_METRICS_LIFT_20260806.md` (rev 2026-08-06c) |
| **Status** | PR1–PR3a + **PR3b Kaggle reals** · **T1 KEEP** = `E_recover_v2_sealed_multi_if` (mean 0.7816 / min 0.7023, Δmean +0.0235) · G1 true · G2 false · champion **not** auto-promoted · see `iter_metrics_lift_kaggle_20260806.md` |

## Rails (immutable)

- field fusion **OFF**; IoU ≠ ROS
- no ECE thrash same TEST; no Tobarra KEEP reopen; no larger U-Net default
- thr VAL-locked; no test-set thr fit
- T1 KEEP ≠ T2 north-star (G1 ∧ G2)

## Locked baselines (honest — not invented)

| Metric | Value |
|--------|------:|
| LOFO mean (core-3) | **0.7581** |
| LOFO min (ACOM2) | **0.6932** |
| U1 TEST mean IoU | **0.8569** |
| G1 target | 0.780 |
| G2 target | 0.720 |
| L2_pass KEEP floor | 0.700 (E4 uses 0.720) |

## Metric status (honest)

| Claim | Status |
|-------|--------|
| T1 KEEP member | **YES** — `E_recover_v2_sealed_multi_if` (E2 profile, L1+L2 pass) |
| T2 design_success_closed | **false** (G1 true, G2 false; min 0.7023 &lt; 0.720) |
| Baseline reference board | YES — sealed baseline still reference; recover_v2 is T1 KEEP candidate board |
| Champion promote | **blocked** — T1 KEEP ≠ champion; L4 U1 SKIPPED; PR4 human gate required |

Do **not** invent IoU lifts. If only baseline eval exists, stamp `BASELINE_REFERENCE` / `NO_RUN` / `PENDING`.

## PR mapping shipped

| PR | Content |
|----|---------|
| **PR1** | `wildfire_front/ml/lab_metrics_lift.py`, `scripts/run_lab_ml_loop_v34_metrics_lift.py`, `ml lift` CLI, W3 sub-items E0–E4 in `lab_next`, `tests/test_lab_metrics_lift.py` |
| **PR2** | E2-P1 projector (`feature_schema` map + `scripts/project_lofo_schema_packs.py`), `audit_lofo_pack_leak.py`, `build_holdout_v1_plus_w3.py`, `build_clm_lofo_splits.py --src-root/--out-root`, tests |
| **PR3a** | `score_metrics_lift_kill_criteria.py` (E2–E5, L1–L9, D3 SKIPPED), `run_clm_lofo_all_folds.py` harness + `--smoke`, kill profile tests |
| **PR3b** | This note + offline command below; score baseline into board as **BASELINE_REFERENCE** (not KEEP) |
| **PR4** | Promote checklist only — **no false champion** |

## Offline full LOFO commands (PR3b — local GPU/CPU)

```powershell
$env:PYTHONPATH = "."

# E0 seal baselines
python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only

# L5 leak audit (sealed pack)
python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v1

# E2-P1 project clean12_subset (does not mutate sealed packs)
python scripts/project_lofo_schema_packs.py `
  --src-lofo artifacts/clm_ndws_patches/lofo_v1 `
  --out-root outputs/ml_eval/lofo_schema_clean12_subset

# E2a train (full — not CI)
python scripts/run_clm_lofo_all_folds.py `
  --lofo-root outputs/ml_eval/lofo_schema_clean12_subset `
  --out-root outputs/ml_eval/lofo_schema_clean12_subset_eval `
  --feature-schema clean12_subset --schema-path-id E2-P1 --epochs 12

# Score E2 kill
python scripts/score_metrics_lift_kill_criteria.py --profile E2 `
  --candidate-root outputs/ml_eval/lofo_schema_clean12_subset_eval `
  --experiment-id E2a_clean12_subset --write-board

# E3a: stage Hellín train-pool (never mutate holdout_v1)
python scripts/build_holdout_v1_plus_w3.py
python scripts/build_clm_lofo_splits.py `
  --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 `
  --out-root artifacts/clm_ndws_patches/lofo_v2
python scripts/audit_lofo_pack_leak.py --lofo-root artifacts/clm_ndws_patches/lofo_v2
python scripts/run_clm_lofo_all_folds.py `
  --lofo-root artifacts/clm_ndws_patches/lofo_v2 `
  --out-root outputs/ml_eval/lofo_v2 `
  --feature-schema legacy17 --schema-path-id E3a --epochs 12
python scripts/score_metrics_lift_kill_criteria.py --profile E3 `
  --candidate-root outputs/ml_eval/lofo_v2 `
  --experiment-id E3a_hellin_train_pool --write-board
```

## CI smoke (PR3a)

```powershell
$env:PYTHONPATH = "."
pytest tests/test_lab_metrics_lift.py tests/test_lab_metrics_lift_kill_profiles.py `
  tests/test_lab_lofo_board.py tests/test_lab_next.py tests/test_lofo_pack_leak.py `
  tests/test_project_lofo_schema.py -q
python scripts/score_metrics_lift_kill_criteria.py --profile E3 --smoke
python scripts/run_clm_lofo_all_folds.py --smoke
python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only
```

## PR4 promote checklist (human gate — T1 KEEP exists)

- [x] Kill JSON `verdict=KEEP` with E2 L1–L3, L5–L9 pass (L4 SKIPPED OK for research T1)
- [x] Board stamps `north_star_g1_met=true` / `north_star_g2_met=false` honestly
- [x] Tier named: **T1 board KEEP member** (`E_recover_v2_sealed_multi_if`) — not T2 closeout
- [ ] Champion path: `champion_candidate=true` + L4 MEASURED U1 ≥ 0.8469 + new recipe id — **not done**
- [x] Never flip field fusion; never reopen Tobarra KEEP; never ECE same-TEST thrash
- [x] Champion recipe file **not** updated (no false auto-promote)

### T1 KEEP numbers (real Kaggle)

| Metric | Baseline | E_recover_v2 | Δ |
|--------|--------:|-------------:|--:|
| mean | 0.7581 | **0.7816** | **+0.0235** |
| min (ACOM2) | 0.6932 | **0.7023** | **+0.0091** |

Kernel: `alonsoalviraaaa/wfd-metrics-lift-lofo-recover-v2` · dataset: `alonsoalviraaaa/wfd-lofo-v1-core3`

---

*Real Kaggle trains. No invented lifts. T1 KEEP documented; champion unchanged until human PR4.*
