# Metrics lift — Kaggle retrain results (2026-08-06)

| Campo | Valor |
|-------|--------|
| **Design** | `docs/design/DESIGN_ML_METRICS_LIFT_20260806.md` |
| **Deep research** | residual ~1M default; multi-fire EV; capacity ≠ LOYO win |
| **GPU** | Kaggle T4 (`alonsoalviraaaa/wfd-metrics-lift-*`) |
| **Local CUDA** | none — all full LOFO trains on Kaggle |

## Locked baselines (core-3 LOFO)

| Metric | Value |
|--------|------:|
| mean | **0.7581** |
| min (ACOM2) | **0.6932** |
| G1 / G2 targets | 0.780 / 0.720 |

## Experiments (honest)

| ID | Data | Init | mean | min | Δmean | Δmin | Kill |
|----|------|------|-----:|----:|------:|-----:|------|
| **E3a** Hellín train-pool | lofo_v2 (+hellin) | v21 | 0.7516 | 0.6650 | **−0.0064** | **−0.0281** | **KILL** (E3) |
| **E4** curriculum on v2 pack | same | v21 | 0.7511 | 0.6631 | **−0.0069** | **−0.0301** | **KILL** (E4) |
| **E_recover** sealed + multi_if | lofo_v1 core-3 | multi_if | **0.7665** | **0.7011** | **+0.0084** | **+0.0079** | **KILL** E2 (L1 needs +0.010; got +0.0084) · **L2_pass true** (min≥0.700) |
| **E_recover_v2** sealed longer/lower-LR | lofo_v1 core-3 | multi_if | **0.7816** | **0.7023** | **+0.0235** | **+0.0091** | **KEEP** E2 (L1+L2 pass) · G1 **true** · G2 **false** · **not champion** |

### Per-fold

| Fold | Baseline | E3a | E4 | Recover | **Recover_v2** |
|------|--------:|----:|---:|--------:|---------------:|
| CARDOSO | 0.7978 | 0.7977 | 0.7981 | 0.8085 | **0.8518** |
| ACOM1 | 0.7832 | 0.7921 | 0.7921 | 0.7898 | **0.7906** |
| ACOM2 | 0.6932 | 0.6650 | 0.6631 | 0.7011 | **0.7023** |

## Interpretation (deep research aligned)

1. **Hellín multi-fire into train pool hurt ACOM2** (domain shift / year-fire heterogeneity). Primary EV E3a **failed**.
2. **Curriculum alone on Hellín-contaminated packs** did not recover the floor.
3. **Sealed LOFO + Spain multi_if init** (E_recover) produced first real lift: mean +0.84 pt, ACOM2 crosses **0.700**.
4. **E_recover_v2** (epochs 28, lr 1e-4, patience 10, ACOM2 change_w=10 / pos_w=8) cleared E2 KEEP: mean **0.7816** (Δ+0.0235), min **0.7023**. G1 (mean≥0.780) **met**; G2 (min≥0.720) **not met** (gap −0.0177 on ACOM2).
5. CARDOSO drove most of the mean lift (0.8085 → 0.8518); VAL early-stop selected epoch-1 checkpoint under lower LR (honest LOFO: VAL-best → TEST).
6. **No larger U-Net**. Fusion remains **OFF**. Tobarra KEEP not reopened. **Champion recipe not auto-promoted** (needs PR4 human gate + L4 MEASURED U1 for champion path).

## Artifacts

| Path | Role |
|------|------|
| `outputs/kaggle_metrics_lift_e3a/` | E3a fold metrics + weights |
| `outputs/kaggle_metrics_lift_e4/` | E4 fold metrics + weights |
| `outputs/kaggle_metrics_lift_recover/` | E_recover metrics + weights |
| `outputs/kaggle_metrics_lift_recover_v2/` | **T1 KEEP** recover_v2 metrics + weights |
| `outputs/ml_eval/lofo_v1_recover_kaggle/` | scorer candidate root (recover) |
| `outputs/ml_eval/lofo_v1_recover_v2_kaggle/` | scorer candidate root (recover_v2) |
| `outputs/ml_eval/lab_loop/metrics_lift_E_recover_v2_sealed_multi_if_kill.json` | E2 KEEP kill board |
| `outputs/ml_eval/lab_loop/weights_recover_v2/` | fold best weights |
| `artifacts/clm_ndws_patches/lofo_v2/` | Hellín-expanded packs (0 leak) |
| Kaggle dataset | `alonsoalviraaaa/wfd-lofo-v2-e3a`, `wfd-lofo-v1-core3` |
| Kaggle kernel | `alonsoalviraaaa/wfd-metrics-lift-lofo-recover-v2` (COMPLETE) |

## Verdict stamps

- `design_success_closed` = **false** (G1 true ∧ G2 false → not closed)
- T1 KEEP under E2 = **YES** — `E_recover_v2_sealed_multi_if`
- `north_star_g1_met` = **true** (mean 0.7816 ≥ 0.780)
- `north_star_g2_met` = **false** (min 0.7023 < 0.720)
- Best research candidate = **E_recover_v2_sealed_multi_if** (T1 KEEP member)
- Champion recipe = **unchanged** (no auto-promote; L4 U1 SKIPPED; PR4 human gate required)

## PR4 promote checklist (T1 only — human gate)

- [x] Kill JSON `verdict=KEEP` with E2 L1–L3, L5–L9 pass (L4 SKIPPED OK for research T1)
- [x] Board stamps `north_star_g1_met=true` / `north_star_g2_met=false` honestly
- [x] Tier named: **T1 board KEEP member** (not T2 north-star closeout)
- [ ] Champion path: requires `champion_candidate=true` + L4 MEASURED U1 ≥ 0.8469 + new recipe id — **not done**
- [x] Fusion OFF; Tobarra KEEP not reopened; no ECE same-TEST thrash
- [ ] Human sign-off before any champion recipe file update

## Next EV (post T1 KEEP)

1. Optional G2 push: raise ACOM2 floor toward 0.720 without losing mean ≥0.780 (VAL-only ensemble / mild ACOM2 curriculum — no Hellín primary).
2. Champion path only with formal L4 MEASURED U1 + PR4 checklist.
3. **Do not** re-add Hellín for ACOM2 LOFO without fire-level reweighting.
4. Still no Tobarra KEEP reopen; no ECE same-TEST thrash; no Res50 / larger U-Net default.

---

*Real Kaggle trains. No invented IoU. T1 KEEP = board member only; champion unchanged until PR4 human gate.*
