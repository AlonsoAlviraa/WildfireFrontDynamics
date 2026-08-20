# WFIGS spatial decoder DEV protocol — 2026-08-20

This is a post-confirmation, directional development experiment. It does not
reopen or reinterpret the sealed one-time confirmation.

## Scope and invariants

- Use only the frozen expansion tuning cohort: 184 TRAIN events and 42 DEV
  events. The runner loads the DEV manifest for inference and uses the frozen
  three-seed hybrid ensemble selected before any confirmation data was opened.
- Refuse confirmation, test, and prospective dataset paths.
- Select every spatial-decoder parameter on DEV only. No parameter from this
  sweep may be reported as an external generalization result.
- Do not publish raw tensors, geometries, predictions, checkpoints, or
  per-event rows.

## Frozen model and grid

The model is the three-seed (`11, 29, 47`) decoder-only hybrid ensemble from
the expansion development freeze. The spatial decoder grid is fixed before
execution:

- probability threshold: `0.10` through `0.80` in steps of `0.05`;
- maximum distance from the observed t0 front: none, `4`, `8`, `12`, `16`,
  `24`, or `32` pixels;
- binary dilation radius: `0`, `1`, or `2` pixels;
- t0-connectivity filter: disabled or enabled.

The ranking metric is event-macro IoU. The selected row is a DEV hypothesis
for a future fresh, rights-cleared cohort; it is not a new confirmation claim.

