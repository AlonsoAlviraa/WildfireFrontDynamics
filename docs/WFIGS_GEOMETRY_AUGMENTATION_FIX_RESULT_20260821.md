# WFIGS physically consistent geometry augmentation DEV result — 2026-08-21

## Scope

The combined geometry + tile-EO recipe was rerun with a corrected augmentation
implementation: horizontal/vertical flips and quarter-turns transform
`front_normal_x/y` as a vector. RCDA VAL-selected seed 47 was adapted on WFIGS
TRAIN (184 events), selecting on DEV (42 events). Confirmation and prospective
TEST were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 12 | 0.217028 | 0.307855 |
| Combined features, corrected normal augmentation | 0.138828 | 0.151691 | 0.20 | 5 | 0.235699 | 0.298537 |

The corrected candidate improves the control by `+0.006926`, clearing the
single-seed `+0.005` gate, but is below the previous (buggy) implementation's
`0.141378`. The decrease demonstrates why the vector-transform fix is required;
the corrected recipe must be replicated across seeds before any holdout claim.

## Decision

Advance only the corrected implementation to a three-seed DEV replication. Do
not use the earlier uncorrected checkpoint for promotion or confirmation, and
do not inspect TEST.

## Reproducibility and rights

The report records `include_geometry_features=true`,
`include_tile_standardized_features=true`, `trainable_scope=decoder_plus_input`,
`wfigs_test_loaded=false`, and `test_used_for_selection=false`; the source
checkpoint was selected on RCDA VAL. Only sanitized aggregate metrics are
published. WFIGS raw geometries, tensors, tiles and checkpoints remain private
and are not redistributed.
