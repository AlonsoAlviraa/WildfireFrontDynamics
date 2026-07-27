# Archived Kaggle job experiments

Old training kernels (v13–v20, v22–v27b, overnight/mega), plus:

- `run_training.py` — legacy A3C / `v3.pt` entrypoint (removed from active job dir)
- `monitor_job.bat` — absolute Windows paths + obsolete kernel slug
- `run_autonomous_research_v_incomplete.py` — extensionless orphan renamed (2026-07-21);
  prefer `run_autonomous_research_v17.py` if replaying v17 research pipeline

Active kernel metadata lives in `kaggle_job/kernel-metadata.json` and
`kernel-metadata-v21.json` (v21 / `run_unet_training_v21.py`). Product weights
are under `models/production/`, `models/clm_specialist/`, and `models/clm_ensemble/`.

Re-run only if you need to reproduce a historical Kaggle job.
