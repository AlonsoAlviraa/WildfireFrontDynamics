# WFIGS combined-feature three-seed DEV replication — 2026-08-21

## Motivation

The seed-47 combined geometry + tile-EO recipe cleared the promotion gate with
event-macro IoU `0.141378` versus `0.131902` control. This replication tests
stability across the three RCDA paper seeds before any confirmation access.

## Fixed recipe

- Sources: RCDA-VAL-selected residual hybrid checkpoints, seeds 11, 29 and 47.
- Features: 16 RCDA channels + three signed front-distance/normal channels +
  four valid-pixel median/IQR EO residual channels.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; augmentation enabled.
- Trainable scope: decoder plus both residual input projections; deeper encoder
  and context remain frozen.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5; focal-Tversky `(0.3, 0.7, 0.75)` and front-ring BCE `0.05`.
- Seed aggregation: mean probability over the three adapted models.
- Selection metric: event-macro growth IoU on DEV.

## Isolation and decision

The runner requires RCDA final-summary proof of VAL-only source selection,
refuses roots containing `confirm`, `test` or `prospective`, and asserts WFIGS
TEST is not loaded. Promotion requires the replicated ensemble to preserve the
`+0.005` event-macro improvement over the frozen three-seed reference (`0.136178`);
otherwise no confirmation is opened.

## Publication boundary

Only code, tests, protocol and sanitized aggregate DEV metrics may be published.
WFIGS geometries, tensors, tiles, checkpoints and per-pixel outputs remain
private.
