# WFIGS weighted-ensemble DEV protocol — 2026-08-20

## Purpose

The frozen equal-weight three-seed hybrid ensemble is the strongest current
DEV recipe. This small, explicitly bounded decoder study tests whether giving
the most stable seed more weight improves event-macro IoU without retraining
or touching sealed data.

## Fixed grid

- Members: the three frozen WFIGS hybrid decoder checkpoints from RCDA seeds
  11, 29 and 47; all selected on WFIGS DEV and marked `wfigs_test_evaluated=false`.
- Weight candidates (seed order 11/29/47):
  `[1/3,1/3,1/3]`, `[0.25,0.25,0.50]`, `[0.20,0.20,0.60]`,
  `[0.15,0.15,0.70]`.
- Thresholds: `0.20` through `0.50` in increments of `0.05`.
- Spatial decoder: no dilation, no t0-connectivity filter; maximum distance
  candidates `None, 4, 8, 12, 16, 24, 32` px.
- Selection metric: event-macro growth IoU on WFIGS DEV (42 events).

No model weights are updated. TRAIN is not used by this evaluator; only the
WFIGS expansion DEV manifest is loaded for selection.

## Isolation

The runner rejects roots containing `confirm`, `test` or `prospective`, checks
normalization was fitted on TRAIN, validates each checkpoint's WFIGS DEV-only
selection, and writes only a sanitized aggregate ranking. Confirmation and
prospective TEST remain sealed.

## Decision rule

The weighted candidate is promoted only if it exceeds the frozen equal-weight
ensemble (`0.136178`) by at least `0.005` event-macro IoU. A smaller gain is
reported as a sensitivity result and is not used to justify confirmation.

## Rights boundary

Raw WFIGS geometries, tensors, tiles, checkpoint files and per-pixel outputs are
not committed or redistributed. This PR publishes code, protocol and aggregate
metrics only.
