# WFIGS combined-feature three-seed DEV replication — 2026-08-21

## Scope

Seeds 11, 29 and 47 were adapted independently from RCDA VAL-selected residual
hybrid checkpoints using the combined geometry + tile-EO feature recipe. WFIGS
expansion TRAIN (184 events) was used for updates and DEV (42 events) for epoch
and threshold selection. Confirmation and prospective TEST were not loaded or
inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | 0.226176 | 0.306567 |
| Combined-feature adapted ensemble | 0.138581 | 0.152349 | 0.40 | 0.262019 | 0.266854 |
| Fixed weighted grid best `(0.2,0.2,0.6)`, cap 12 px | 0.140649 | 0.152208 | 0.35 | 0.258433 | 0.270236 |

The equal-weight replication improves the frozen ensemble by `+0.002403`,
below the preregistered `+0.005` stability gate. A fixed, previously used
weight/threshold/distance grid raises the DEV event-macro score to `0.140649`,
but its gain is still only `+0.004471`; the grid also lowers recall relative to
the strongest seed and is a DEV sensitivity, not a confirmed improvement.

Per-seed event-macro scores were `0.131221` (seed 11), `0.132894` (seed 29),
and `0.141378` (seed 47), showing that most of the single-seed gain is not
stable across initializations.

## Decision

Reject promotion of the combined recipe for confirmation. Retain the frozen
three-seed ensemble as the paper reference and do not inspect TEST. The result
is scientifically useful: the feature combination improves pooled overlap and
one seed substantially, but replication variance prevents a defensible claim.

## Reproducibility and rights

The report records `source_seeds=[11,29,47]`,
`include_geometry_features=true`, `include_tile_standardized_features=true`,
`trainable_scope=decoder_plus_input`, `wfigs_test_loaded=false`, and
`test_used_for_selection=false`. Only sanitized aggregate metrics are
published; WFIGS raw geometries, tensors, tiles and checkpoints remain private
and are not redistributed.
