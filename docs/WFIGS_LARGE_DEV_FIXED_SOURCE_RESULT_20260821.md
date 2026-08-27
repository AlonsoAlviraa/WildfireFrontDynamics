# WFIGS large-DEV fixed-source ensemble result — 2026-08-21

## Scope

The preregistered corrected geometry + tile-EO recipe was adapted on the large
WFIGS TRAIN/DEV campaign (235 train events, 76 validation events). The RCDA
VAL-selected residual hybrid checkpoint with source seed 47 was held fixed.
Adaptation RNG seeds were 11, 29 and 47. Epoch and threshold were selected on
the **new** WFIGS validation split only.

Confirmation, prospective TEST and any `test.json` were not loaded or
inspected. The dataset root contained `train.json` and `validation.json` only;
those event IDs are disjoint.

Training wrote three best checkpoints and exited before the VAL-only summary.
This result reconstructs thresholds and the probability-average ensemble from
those checkpoints (`scripts/eval_wfigs_saved_checkpoints.py`).

## Result

| Recipe | DEV events | Event-macro growth IoU | Pooled IoU | Threshold / radius | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| Dilated-copy, TRAIN-selected radius 3 px (180 m) | 76 | 0.099155 | 0.102371 | 3 px | 0.217762 | 0.161912 |
| Dilated-copy, VAL-selected radius 6 px (360 m) | 76 | 0.099160 | 0.122080 | 6 px | 0.182948 | 0.268436 |
| Frozen 16-channel hybrid, transferred from 184/42 | 76 | 0.100220 | 0.096300 | 0.35 | 0.307950 | 0.122896 |
| Large-DEV fixed-source geometry+EO ensemble | 76 | **0.125428** | 0.151714 | 0.35 | 0.238060 | 0.294921 |
| Same recipe on the previous 42-event DEV | 42 | 0.140044 | 0.156678 | 0.25 | 0.240205 | 0.310616 |
| Preregistered paper control (42-event DEV) | 42 | 0.136178 | 0.149627 | 0.30 | 0.226176 | 0.306567 |
| Preregistered promotion gate (`+0.005`) | 42 | 0.141178 | — | — | — | — |

Individual large-DEV adaptation seeds: `0.124358` (seed 11, epoch 14),
`0.127798` (seed 29, epoch 10), `0.123424` (seed 47, epoch 12).

Versus dilated-copy on the **same** 76-event DEV the adapted ensemble is
`+0.026273` event-macro IoU (TRAIN-selected radius 3 px) and `+0.026268`
(VAL-selected radius 6 px). That is real growth skill against the official
persistence comparator, not a cross-cohort artefact.

Versus the transferred 16-channel control on the same DEV the adapted ensemble
is `+0.025208` and recovers recall (`0.123 → 0.295`). That control was trained
on the old 184-event TRAIN and only re-thresholded here.

Versus the preregistered 42-event gate the large-DEV ensemble is `-0.015750`
(`0.125428` vs `0.141178`). The new DEV is harder: dilated-copy itself only
reaches `0.099` here. The 42-event number is not a same-split comparison.

## Decision

**Reject confirmation.** Do not open confirmation or prospective TEST.

The preregistered promotion rule remains `+0.005` over `0.136178` on DEV
event-macro IoU. The large-DEV run does not meet that historical gate, and the
`+0.025` over a *transferred* 16-channel control is not a substitute for a
control retrained on the 235-event TRAIN.

Keep the large-DEV geometry+EO ensemble as a development result: it is stable
across three seeds, uses only TRAIN/DEV, and beats a transferred 16-channel
baseline on the new cohort. It is not a paper-confirmable improvement.

## Reproducibility and rights

- Recipe: 23 input channels (16 RCDA + 3 front geometry + 4 tile-standardized
  EO residuals), `trainable_scope=decoder_plus_input`, AdamW `1e-4`, batch 4,
  max 18 epochs, patience 5, front-ring BCE `0.05`.
- Source checkpoint selected on RCDA VAL; WFIGS epoch/threshold selected on
  WFIGS validation.
- `wfigs_test_loaded=false`, `test_used_for_selection=false`.
- `PUBLICATION_BLOCKED` includes `per_pixel_prediction`.
- Only sanitized aggregate metrics are published. WFIGS geometries, tensors,
  tiles, checkpoints and per-pixel predictions remain local and are not
  redistributed.
