# WFIGS front-geometry three-seed ensemble DEV protocol — 2026-08-21

## Motivation

The single-seed explicit-front-geometry adapter was a near miss: it reached
`0.136740` event-macro IoU versus the `0.131902` control, but narrowly missed
the fixed `+0.005` gate. This preregistered follow-up tests whether that gain
survives the three RCDA seeds used by the paper recipe, with no new threshold
sweep or confirmation access.

## Fixed recipe

- Sources: RCDA-VAL-selected residual hybrid checkpoints, seeds 11, 29 and 47.
- Features: existing 16 encoded channels plus signed front distance and its
  normalized horizontal/vertical derivatives, all derived from `previous_fire`.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: decoder plus both residual `enc1` input projections;
  deeper encoder and context remain frozen.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5; focal-Tversky `(alpha=0.3, beta=0.7, gamma=0.75)` and
  front-ring BCE `0.05`.
- Seed aggregation: mean probability over the three adapted models.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner requires the RCDA final summary to prove VAL-only source selection,
refuses roots containing `confirm`, `test` or `prospective`, and asserts that
WFIGS TEST is not loaded. Promotion requires the resulting ensemble to beat the
frozen ensemble reference (`0.136178`) by `+0.005` event-macro IoU; otherwise
the candidate is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
