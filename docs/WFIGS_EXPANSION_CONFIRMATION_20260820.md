# WFIGS expansion confirmation (2026-08-20)

This report records the aggregate result of the preregistered WFIGS expansion
run. Raw WFIGS geometries, derived tensors, and model checkpoints are not
redistributed; they remain local under the project rights policy.

## Protocol

- Training material: 184 event-disjoint TRAIN events.
- Development selection: 42 event-disjoint DEV events.
- Confirmation: 16 event-disjoint events, opened once after the recipe freeze.
- Prospective cohort: 16 events, never loaded.
- Pilot recipes: 8; selection metric: event-macro IoU on DEV.
- Frozen winner: decoder-only adaptation with a light front-ring objective,
  RCDA TRAIN-only normalization, learning rate `1e-4`, and 18 maximum epochs.
- Replication seeds: 11, 29, and 47.

## Development evidence

The frozen pilot winner reached `0.131902` event-macro IoU on DEV. The three
replication runs selected their best DEV epochs at 10, 10, and 12, with event-
macro IoU values `0.132901`, `0.120745`, and `0.131902` respectively.

## One-time confirmation

The frozen three-seed ensemble was evaluated once on the 16-event confirmation
cohort and compared with the frozen geometry baseline:

| Metric | Candidate | Baseline |
| --- | ---: | ---: |
| Event-macro IoU | 0.067115 | 0.055010 |

The paired improvement is `+0.012105`; the event-level bootstrap 95% CI is
`[-0.001563, 0.029216]` over 10,000 resamples. The candidate improved on
56.25% of events. The preregistered confirmation gate therefore remains
**false** because the confidence interval includes zero.

This is useful directional evidence, not a confirmatory scientific claim.
The prospective cohort remains sealed for a future, separately authorized
evaluation.

## Reproducibility anchors

- Preregistration SHA-256:
  `ef26c7bcf3126018f5961124e9da23db0a8c4c7fc6d43ec944773b962e386879`
- Frozen recipe SHA-256:
  `bf185dc56183ab2853af0d06c1bcd95f2a3499de41818eb0af6704b269aa6467`
- Confirmation result SHA-256:
  `b724dfbea60894038d71ac702c1904323d69b5ab3492bc9d09f0172d86e69600`

