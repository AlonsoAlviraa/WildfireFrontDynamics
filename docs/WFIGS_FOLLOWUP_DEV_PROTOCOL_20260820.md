# WFIGS follow-up DEV protocol — 2026-08-20

This is a directional, post-confirmation development experiment. It does not
repair, reopen, or reinterpret the sealed one-time confirmation in
`WFIGS_EXPANSION_CONFIRMATION_20260820.md`.

## Scope

- Read only the frozen tuning cohort: 184 TRAIN events and 42 DEV events.
- Do not load the 16-event confirmation cohort or the 16-event prospective
  holdout. The runner accepts a DEV dataset path explicitly and rejects paths
  whose name indicates confirmation, test, or prospective data.
- Keep the RCDA source architecture, source checkpoints, and TRAIN-only
  normalization fixed.
- Select epochs and thresholds only on WFIGS DEV. No claim about held-out
  generalization is made by this follow-up.

## Pre-registered controls

All recipes use decoder-only adaptation, the same learning-rate schedule,
front-ring BCE weight (0.05), batch size (4), 18-epoch ceiling, patience 5,
and pilot seed 47:

1. `hybrid_augmented_control`: existing hybrid objective with augmentation.
2. `growth_only_augmented`: growth objective with augmentation.
3. `growth_only_no_augmentation`: growth objective without spatial augmentation.

The script writes one private report per recipe and a sanitized aggregate
ranking. It must not be used to inspect or publish raw geometries, tensors,
tiles, checkpoints, or per-pixel predictions.

## Interpretation rule

The best DEV recipe is a hypothesis for a future fresh external cohort, not a
new confirmatory result. The original confirmation gate remains **false**:
the candidate improved the point estimate but its paired bootstrap interval
crossed zero.

