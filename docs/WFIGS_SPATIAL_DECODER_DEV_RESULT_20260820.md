# WFIGS spatial decoder DEV result — 2026-08-20

This is a sanitized, directional DEV result. It is not a new external
generalization or confirmation claim.

## Frozen evaluation

- 42 expansion DEV events only; the runner loaded no confirmation or
  prospective manifest.
- Frozen hybrid ensemble, seeds `11/29/47`, selected before confirmation.
- Grid: 630 combinations of threshold, distance cap, dilation, and t0
  connectivity; all choices selected by event-macro IoU on DEV.

## Result

| Decoder | Event-macro IoU | Pooled IoU | Precision | Recall |
| --- | ---: | ---: | ---: | ---: |
| Frozen ensemble, no distance cap | 0.136178 | 0.149627 | 0.226176 | 0.306567 |
| DEV-selected 12 px distance cap | **0.136554** | 0.149155 | 0.225898 | 0.305094 |

Selected parameters: probability threshold `0.30`, maximum distance `12 px`,
zero dilation, and no t0-connectivity requirement. The event-macro gain is
`+0.000376` (about `+0.28%` relative), while pooled IoU decreases slightly;
this is therefore a metric-specific, modest improvement rather than evidence
that the model is ready for deployment.

## Scientific decision

Carry the 12 px decoder as a pre-registered candidate for a future fresh,
rights-cleared cohort. Do not apply it retroactively to the sealed
confirmation, and do not claim external improvement from this DEV-only sweep.
The original confirmation gate remains **false**.

Raw geometries, tensors, predictions, checkpoints, and per-event rows remain
local and are not included in this PR.

