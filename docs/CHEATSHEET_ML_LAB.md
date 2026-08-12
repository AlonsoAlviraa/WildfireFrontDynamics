# Cheatsheet — ML lab (1 página)

**lab product · not field_ops fusion · IoU ≠ ROS**

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front ml list
python -m wildfire_front ml show
python -m wildfire_front ml show --json
python -m wildfire_front ml cases
python -m wildfire_front ml cases --bucket accepted_low_iou --rows
python -m wildfire_front ml curve
python -m wildfire_front ml curve --json
python -m wildfire_front ml freeze
python -m wildfire_front ml freeze --json
python -m wildfire_front ml smoke
python -m wildfire_front ml smoke --json
python -m wildfire_front ml lofo
python -m wildfire_front ml lofo --json
python -m wildfire_front ml next
python -m wildfire_front ml next --json
# LOFO Head A (needs weights; long first build):
# python scripts\build_lofo_head_a_caches.py
# python scripts\run_lab_ml_loop_v34_lofo_head_a.py
python -m wildfire_front ml doctor
python -m wildfire_front ml card --mode offline --scenario hold
python -m wildfire_front ml card --mode offline --scenario abstain
python -m wildfire_front ml predict --list-products
# live (needs .pt):
# python -m wildfire_front ml predict --product clm_ensemble_v34 --npz path\patch.npz
python -m wildfire_front decide --policy research_open --explain
python -m wildfire_front decide --policy field_ops --explain
pytest tests\test_cli_ml_product.py -q
```

| Product | Role |
|---------|------|
| `clm_ensemble_v34` | default |
| `clm_v28` | fallback |
| `ndws_v21` | research / G1 KILL primary |
| `front_dynamics_v1` | ops ROS — **not ML** |

| Gate | Value |
|------|-------|
| U1 mean IoU | ~0.86 lab holdout |
| LOFO mean IoU | ~0.76 (n=3 fires) — not same protocol |
| Tobarra Head A / fresh LOFO | ~0.49 / **0.478 KILL** (K1) |
| Lab reject thr | ~0.80 · abstain ~0.5 · IoU acc ~0.95 |
| Catalog IoU | 0.8963 provenance only |
| `ml_product_go` | **true** (lab; ≠ field fusion) |
| field_ops fusion | OFF |
| ECE thrash same TEST | **stopped** after iter2/3 |
| W3 mega / Tobarra KEEP | **MET** / **KILL** · `docs/goals/README.md` |

```powershell
# Lab loop iters (lab only; never flips field_ops)
python scripts\run_lab_ml_loop_v34_generalization.py
python scripts\run_lab_ml_loop_v34_teach_cases.py
python scripts\run_lab_ml_loop_v34_risk_curve.py
python scripts\run_lab_ml_loop_v34_freeze.py
python scripts\run_lab_ml_loop_v34_smoke.py
# make ml-lab-smoke
# make ml-lab-smoke SMOKE_PYTEST=1
pytest tests\test_lab_loop_generalization.py tests\test_lab_teach_cases.py tests\test_lab_risk_curve.py tests\test_lab_freeze.py tests\test_lab_smoke.py -q
```

Entry: `docs/ML_PRODUCT_START_HERE.md` · Plan: `docs/PLAN_ML_PRODUCT_USABLE.md` · Status: `docs/PLAN_ML_PRODUCT_STATUS.json`  
State: `docs/CURRENT_STATE.md` · Goals: `docs/goals/README.md` · Loop board: `docs/design/DESIGN_ML_LAB_LOOP_CONTINUOUS.md`

```powershell
# Closed mega goals — re-score / smoke only (no thrash KEEP)
python scripts\score_tobarra_kill_criteria.py --metrics outputs\ml_eval\lofo_tobarra_keep_attempt_latest\evaluation_metrics.json --fresh-train
# .\scripts\run_mega_goal_tobarra_keep.ps1 -Smoke

# Spatial_v1 + estrella LOFO on Kaggle T4 (no local CUDA)
python scripts\run_kaggle_spatial_v1_estrella.py
python scripts\run_kaggle_spatial_v1_estrella.py --watch-only
python scripts\run_kaggle_spatial_v1_estrella.py --score-only
```
