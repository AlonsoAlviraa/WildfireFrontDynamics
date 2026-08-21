# WFIGS robust per-tile EO features DEV result — 2026-08-21

## Scope

The RCDA VAL-selected residual hybrid seed 47 was adapted on WFIGS expansion
TRAIN (184 events), with selection on DEV (42 events). Four clipped median/IQR
EO residual channels (blue, green, red and NDVI) were appended to the 16-channel
RCDA bridge. Statistics used only valid pixels from the current input tile;
future targets and perimeters were not read. Confirmation and prospective TEST
were not loaded or inspected.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Precision | Recall |
|---|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 0.217028 | 0.307855 |
| Tile-standardized EO features, global threshold | 0.135831 | 0.154225 | 0.25 | 0.240225 | 0.301091 |
| Same checkpoint + fixed prior event-size decoder | 0.136407 | 0.149237 | fixed | 0.270176 | 0.250035 |

The learned feature improves pooled IoU substantially, but its primary
event-macro gain is only `+0.003929`, below the preregistered `+0.005` gate.
Applying the already-fixed event-size rule (`(0.30, 0.25, 0.40, 0.45)` by
previous-fire area and 12 px distance cap) raises event-macro IoU to `0.136407`
but still reaches only `+0.004505` over control while lowering pooled IoU and
recall. This is a calibration sensitivity, not a robust promotion.

## Decision

Reject promotion and do not replicate or open confirmation. Retain the frozen
three-seed ensemble as the paper reference. The result confirms that EO domain
shift is real and that tile residuals help pooled overlap, but the event-level
criterion remains below the scientific promotion gate.

## Reproducibility and rights

The report records `include_tile_standardized_features=true`,
`trainable_scope=decoder_plus_input`, `wfigs_test_loaded=false`, and
`test_used_for_selection=false`; the source checkpoint was selected on RCDA VAL.
Only sanitized aggregate metrics are published. WFIGS raw geometries, tensors,
tiles and checkpoints remain private and are not redistributed.
