# Archived one-off scripts

Historical experiment helpers, closed-eval verdicts, and superseded finalize
scripts. Kept for forensic reproducibility only — **not** part of the product
path.

| File | Why archived |
|------|----------------|
| `evaluate_current_model.py` | Legacy A3C + deleted `kaggle_output` paths |
| `compare_base_vs_finetuned.py` | Legacy A3C fine-tune comparison |
| `analyze_training_curves.py` | v10/v11 dump analysis |
| `analyze_leakage_and_shap.py` | Forensic SHAP/leakage helper; hard-fails without data unless `--smoke` (tags `synthetic:true`; never writes product docs/scorecards) |
| `eval_kaggle_v27_verdict.py` / `eval_kaggle_v27b_verdict.py` | Closed G1 temporal experiments |
| `finalize_observatorio_v2.py` / `v3.py` | Superseded by v4+ |
| `_count_artifacts.py` / `_fix_la_estrella_acom2_masks.py` | One-off data repairs |
| `run_overnight_monitor.py` | Overnight mega kernel (failed / obsolete) |
| `experiment_queue*.json` | Historical queues (terminal / forensic); **do not write here** |
| `smoke_test_finetune.py` | Legacy A3C fine-tune smoke (not product U-Net/CLM) |
| `smoke_test_physics_loss.py` | v9 physics-loss regression smoke (historical) |
| `reeval_cross_protocol.py` | v14/v19/v20 cross-protocol re-eval (pre-v21 product) |
| `_probe_cems_candidates.py` | One-off CEMS zip probe; product uses `open_if/cems_watch` + gold e2e |
| `inspect_zips.ps1` / `parse_dropbox.ps1` / `move_transfers.ps1` / `extract_and_organize.ps1` | 2026-07 Dropbox intake one-offs (root clutter) |

**Live experiment queue** (mutable): `scripts/experiment_queue.json`  
(`run_experiment_loop.py` / `run_production_loop.py` read and write that path only.)

This directory is **read-only history**. Copy a historical queue into
`scripts/experiment_queue.json` if you need to re-drive a past experiment.

**Production ML:** `models/unet_model.py` + `models/catalog.json` +
`models/production/` / `models/clm_ensemble/`.

Do not retrain from these scripts without first updating paths and weights.
