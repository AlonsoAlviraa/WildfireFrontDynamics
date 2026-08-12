# Design — continuous ML lab loop (v34)

| Campo | Valor |
|-------|--------|
| **Status** | **FROZEN + W3 MET + Tobarra KILL** — 2026-08-05 |
| **Product** | `clm_ensemble_v34` lab only |
| **Rails** | ml_product_go **false** · field_ops OFF · IoU ≠ ROS · catalog 0.8963 provenance only |
| **Surface** | iter1 reject thr~0.80 (locked ~0.795) |
| **Mega goals** | W3 **MET** · Tobarra fresh LOFO **KILL** (IoU 0.4776 · K1 fail) · `docs/goals/README.md` |
| **recommended_next** | **idle lab** unless new signal · product primary = **H1 GO_Q** · no Tobarra KEEP thrash |

## Multi-fire Head A (frozen thr ~0.795)

### In-pack LOFO — Tobarra / Cardoso / Estrella

| Fold | n | IoU | ECE | abs@lock | IoU acc | honesty |
|------|--:|----:|----:|---------:|--------:|---------|
| **CARDOSO** | 200 | 0.857 | 0.153 | 0.515 | 0.949 | **CARDOSO≈U1** — easy; LOFO CARDOSO ≈ holdout TEST family; not independent multi-fire gen |
| ACOM1 | 200 | 0.783 | 0.125 | 0.210 | 0.851 | in-pack Estrella |
| ACOM2 | 190 | 0.691 | 0.073 | 0.689 | 0.844 | weakest in-pack |
| **Tobarra** | 300 | **0.489** | **0.342** | **0.680** | **0.841** | **hard** transfer; reject helps; IoU ≠ ROS |
| **mean** | 890 | **0.705** | **0.173** | **0.524** | **0.871** | — |

### External W3 — Hellín + Brazatortas + Retuerta (present)

| Fire | n_disk | n_HeadA | IoU | Δ vs copy | ECE | abs@lock | IoU acc | honesty |
|------|-------:|--------:|----:|----------:|----:|---------:|--------:|---------|
| **Hellín 2024** | 320 | 60 | 0.789 | **+0.114** | 0.077 | 0.517 | 0.978 | primary new-fire signal; lab only |
| **Brazatortas 2025** | 57 | 60 | 0.544 | ~0 | 0.224 | 0.017 | 0.553 | ≈ copy / hard growth — report Δ |
| **Retuerta 2025** | 92 | 32 | 0.465 | +0.010 | 0.308 | 0.000 | 0.465 | hard probe; present in C1 |

**Board law:** never thr/ECE fit on U1 TEST or held-out fire TEST · never flip field_ops / ml_product_go · catalog **0.8963** provenance only.

Board MD: `docs/ML_LOOP_ITERATIONS/iter_20260805_w3_mega.md` · latest `iter_w3_mega_goal_latest.md`.

## Commands

```powershell
python scripts/build_lofo_head_a_caches.py
python scripts/run_lab_ml_loop_v34_lofo_head_a.py
python -m wildfire_front ml next
```

## W3 status (2026-08-05) — mega goal MET (C1–C5)

| Item | Status |
|------|--------|
| Inventory external fires | DONE (`w3_fire_inventory.json`) — READY: Hellín, Brazatortas, Retuerta (+ Cardoso extra) |
| Tobarra diagnose | DONE — bimodal IoU, reject helps |
| Hellín / Brazatortas / Retuerta align | **DONE** chain-local (`align_geotiff_stack`) |
| Patches + Head A frozen | **DONE** (min_change≥0.02; thr/cal frozen) |
| Hellín Head A | IoU ~0.79 · Δ vs copy **+0.11** |
| Brazatortas Head A | IoU ~0.54 · Δ vs copy **~0** (hard) |
| Retuerta Head A | IoU ~0.47 · Δ vs copy **~0.01** (hard) |
| Tobarra finetune (v29 re-score) | K1–K5 → **INCONCLUSIVE** (historical W3 close) |
| Tobarra **fresh** LOFO train | **KILL** — IoU **0.4776** · K1 −0.012 · leak 0 · board `iter_tobarra_keep_or_kill_latest.md` |
| ECE same-holdout thrash | **forbidden** |
| field_ops / ml_product_go | **false** |

## Commands (W3 expert path)

```powershell
$env:PYTHONPATH = "."
python scripts/align_lwir_common_grid.py --images-dir artifacts/hellin_2024_reprojected_lwir --masks-dir artifacts/hellin_2024_lwir_masks --out-root outputs/ml_eval/w3/hellin_2024/aligned
python scripts/run_lab_ml_loop_v34_w3_expert.py --fires hellin_2024 brazatortas_2025 retuerta_2025
```

## Mega goals

### W3 process — **MET**

| Piece | Path |
|-------|------|
| Doc | `docs/goals/MEGA_GOAL_W3_FINETUNE_NO_LEAK.md` |
| Rhai | `.grok/workflows/wfd-ml-w3-mega-goal.rhai` |
| PS1 | `scripts/run_mega_goal_w3.ps1` |
| Board | `docs/ML_LOOP_ITERATIONS/iter_w3_mega_goal_latest.md` |

### Tobarra KEEP-or-KILL — **next harness (READY)**

| Piece | Path |
|-------|------|
| Doc | `docs/goals/MEGA_GOAL_TOBARRA_KEEP_OR_KILL.md` |
| Rhai | `.grok/workflows/wfd-ml-tobarra-keep-or-kill.rhai` |
| PS1 | `scripts/run_mega_goal_tobarra_keep.ps1` |
| Train | `scripts/run_tobarra_lofo_keep_attempt.py` |
| Score | `scripts/score_tobarra_kill_criteria.py` |

```powershell
python scripts/score_tobarra_kill_criteria.py          # prior: INCONCLUSIVE (v29)
# /workflow wfd-ml-tobarra-keep-or-kill
.\scripts\run_mega_goal_tobarra_keep.ps1
.\scripts\run_mega_goal_tobarra_keep.ps1 -Smoke
python scripts/run_tobarra_lofo_keep_attempt.py --epochs 15
```

Success = **KEEP or KILL** after **fresh** LOFO train (not v29 re-score alone). Rails stay cold.

## Next

1. **Run Tobarra KEEP-or-KILL mega goal**  
2. More external fires if needed  
3. W4/W5 human tracks — **not** auto flip go rails  

**Do not:** thrash ECE same-TEST; sell Hellín IoU without Δ vs copy; field_ops ON; claim catalog 0.8963 as live certainty; treat CARDOSO LOFO as independent of U1.
