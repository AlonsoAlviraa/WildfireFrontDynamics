# PR4 — Metrics lift promote checklist (human-gated)

**Do not promote without KEEP.** This checklist is the human gate only.

## When KEEP exists (T1)

1. Link kill JSON: `outputs/ml_eval/lab_loop/metrics_lift_{experiment_id}_kill.json`
2. Confirm profile L* all applicable pass; L4 SKIPPED only if `champion_candidate=false`
3. Update LOFO board latest from candidate eval root
4. Write iteration MD with core-3 mean/min vs baselines + `g1_met`/`g2_met`/`design_success_closed`
5. PR description must name **T1 board promote** (not T2 unless G1∧G2)

## When T2 (G1∧G2)

1. Core-3 mean ≥ 0.780 and min ≥ 0.720 on same protocol as baselines
2. G3 all beat copy
3. Rails OK (fusion OFF, IoU ≠ ROS)
4. Full close-out MD; recipe promote still needs L4 if champion path

## Champion recipe path

1. `champion_candidate=true` + L4 MEASURED pass (−0.01 only)
2. New recipe id under `models/clm_ensemble/` (never silent overwrite)
3. Human review; never auto-flip `ml_product_go` or field fusion

## Current ship (2026-08-06)

- KEEP: **none**
- Action: **no champion promote**; instrumentation only
