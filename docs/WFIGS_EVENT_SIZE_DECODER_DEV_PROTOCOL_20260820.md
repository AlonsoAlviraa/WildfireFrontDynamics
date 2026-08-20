# WFIGS event-size decoder DEV protocol — 2026-08-20

## Rationale

DEV diagnostics show that the frozen model produces disproportionately large
false-positive footprints on small observed t0 fires. This decoder-only study
tests a fixed, observable prior: use a higher probability threshold for smaller
t0 extents, without using t1 labels or changing model weights.

## Fixed grid

- Members: frozen equal-weight hybrid checkpoints from seeds 11, 29 and 47.
- Previous-fire area bins (pixels): `[0,100)`, `[100,500)`, `[500,2000)`,
  `[2000,∞)`; these boundaries are inherited from the TRAIN sampler strata.
- Per-bin thresholds: all combinations from `{0.25,0.30,0.35,0.40,0.45}`.
- Maximum t0-front distance: `None, 8, 12, 16, 24, 32` px.
- No dilation and no connectivity filter.
- Selection metric: event-macro growth IoU on the 42-event expansion DEV split.

## Isolation and decision

The runner only loads DEV validation tensors, validates the three frozen
WFIGS-DEV checkpoints, rejects roots containing `confirm`, `test` or
`prospective`, and writes aggregate ranking data only. The candidate is
promoted only if it exceeds the frozen equal-weight ensemble (`0.136178`) by
at least `0.005`; otherwise it is a sensitivity result and is not evaluated on
confirmation.

## Publication boundary

No WFIGS geometries, tensors, tiles, checkpoints or per-pixel predictions are
committed or redistributed. Only code, tests, protocol and sanitized aggregate
DEV metrics are publishable.
