# WFIGS combined geometry + tile-EO DEV result — 2026-08-21

## Scope

The RCDA VAL-selected residual hybrid seed 47 was adapted on WFIGS expansion
TRAIN (184 events), with epoch and threshold selection on DEV (42 events).
Inputs appended both target-independent feature families: signed front distance
and two normalized front derivatives, plus four valid-pixel median/IQR residuals
for blue/green/red/NDVI. Confirmation and prospective TEST were not loaded or
inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 12 | 0.217028 | 0.307855 |
| Combined geometry + tile EO, seed 47 | 0.141378 | 0.154920 | 0.20 | 5 | 0.238660 | 0.306291 |
| Frozen three-seed hybrid ensemble | 0.136178 | 0.149627 | 0.30 | — | 0.226176 | 0.306567 |

The combined candidate improves the single-seed control by `+0.009476`,
clearing the preregistered `+0.005` promotion gate. It also exceeds the frozen
ensemble by `+0.005200` on event-macro IoU and improves pooled IoU by `+0.005293`
while preserving recall. This is a meaningful DEV result, but it is still a
single-seed adaptation and requires seed replication before any confirmation
decision.

## Decision

Advance the combined feature recipe to a preregistered three-seed DEV
replication. Do not open confirmation or inspect prospective TEST yet; the
candidate must show stable event-level gains across seeds first.

## Reproducibility and rights

The report records `include_geometry_features=true`,
`include_tile_standardized_features=true`, `trainable_scope=decoder_plus_input`,
`wfigs_test_loaded=false`, and `test_used_for_selection=false`; the source
checkpoint was selected on RCDA VAL. Only sanitized aggregate metrics are
published. WFIGS raw geometries, tensors, tiles and checkpoints remain private
and are not redistributed.
