# Archived one-off scripts

Historical experiment helpers, closed-eval verdicts, and superseded finalize
scripts. Kept for forensic reproducibility only — **not** part of the product
path.

| File | Why archived |
|------|----------------|
| `evaluate_current_model.py` | Legacy A3C + deleted `kaggle_output` paths |
| `compare_base_vs_finetuned.py` | Legacy A3C fine-tune comparison |
| `analyze_training_curves.py` | v10/v11 dump analysis |
| `analyze_leakage_and_shap.py` | Synthetic silent fallback; not production SHAP |
| `eval_kaggle_v27_verdict.py` / `eval_kaggle_v27b_verdict.py` | Closed G1 temporal experiments |
| `finalize_observatorio_v2.py` / `v3.py` | Superseded by v4+ |
| `_count_artifacts.py` / `_fix_la_estrella_acom2_masks.py` | One-off data repairs |
| `run_overnight_monitor.py` | Overnight mega kernel (failed / obsolete) |
| `experiment_queue*.json` | Historical queues (terminal / forensic); **do not write here** |

**Live experiment queue** (mutable): `scripts/experiment_queue.json`  
(`run_experiment_loop.py` / `run_production_loop.py` read and write that path only.)

This directory is **read-only history**. Copy a historical queue into
`scripts/experiment_queue.json` if you need to re-drive a past experiment.

**Production ML:** `models/unet_model.py` + `models/catalog.json` +
`models/production/` / `models/clm_ensemble/`.

Do not retrain from these scripts without first updating paths and weights.
