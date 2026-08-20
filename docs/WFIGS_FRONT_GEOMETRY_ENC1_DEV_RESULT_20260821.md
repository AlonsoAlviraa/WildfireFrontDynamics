# WFIGS front-geometry + enc1 DEV result — 2026-08-21

## Scope

The RCDA VAL-selected residual hybrid seed 47 was adapted on WFIGS expansion
TRAIN (184 events), with epoch and threshold selection on DEV (42 events).
Inputs contained the 16-channel RCDA bridge plus signed front distance and two
normalized front derivatives. The full first residual encoder block and the
decoder were trainable; deeper encoder/context blocks remained frozen.

## Result

| Recipe | DEV event-macro growth IoU | Pooled IoU | Threshold | Best epoch | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| RCDA single-seed control, seed 47 | 0.131902 | — | 0.30 | 12 | 0.217028 | 0.307855 |
| Front geometry + full `enc1` | 0.133599 | 0.140359 | 0.25 | 4 | 0.266418 | 0.228775 |

The candidate improves the control by only `+0.001697`, well below the
preregistered `+0.005` promotion criterion. Its precision increase is offset by
a `0.079081` recall loss and a lower pooled IoU than the decoder-plus-input
geometry result (`0.148653`).

## Decision

Reject promotion and do not replicate or open confirmation. Retain the frozen
three-seed ensemble as the DEV reference. Unfreezing the complete first block
does not provide enough domain adaptation and makes the operating point more
conservative without improving event-level overlap.

## Reproducibility and rights

The report records `include_geometry_features=true`,
`trainable_scope=decoder_plus_enc1`, `wfigs_test_loaded=false`, and
`test_used_for_selection=false`; the source checkpoint was selected on RCDA VAL.
Only sanitized aggregate metrics are published. WFIGS raw geometries, tensors,
tiles and checkpoints remain private and are not redistributed.
