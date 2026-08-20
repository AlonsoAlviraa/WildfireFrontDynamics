# WFIGS follow-up DEV result — 2026-08-20

This report is a sanitized, directional development result. It does not
reopen the sealed one-time confirmation and does not constitute a new external
generalization claim.

## Frozen scope

- Dataset: the frozen WFIGS tuning cohort only (184 TRAIN events and 42 DEV
  events).
- Seed: 47; source RCDA architecture, source checkpoint, normalization, and
  decoder-only adaptation budget were fixed.
- Confirmation cohort: not loaded.
- Prospective holdout: not loaded.
- Selection: event-macro IoU and threshold selected on WFIGS DEV only.

## Aggregate result

| Recipe | Augmentation | DEV event-macro IoU | Threshold | Best epoch |
| --- | ---: | ---: | ---: | ---: |
| hybrid augmented control | yes | 0.131902 | 0.3 | 12 |
| growth-only | yes | 0.083614 | 0.4 | 18 |
| growth-only | no | 0.082554 | 0.4 | 18 |

Relative to the hybrid control, growth-only with augmentation was lower by
0.048288 IoU and growth-only without augmentation was lower by 0.049348 IoU on
DEV. Removing augmentation therefore did not rescue the growth-only objective
in this cohort.

## Decision

Keep the hybrid augmented control as the DEV development leader. Do not tune
or claim on the sealed confirmation from these results. A future fresh,
rights-cleared cohort is required before making a new external claim; the
original confirmation gate remains **false**.

Raw geometries, tensors, tiles, predictions, checkpoints, and per-event rows
remain local and are not included in this PR.

