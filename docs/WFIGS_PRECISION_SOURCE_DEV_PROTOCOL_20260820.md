# WFIGS precision-tuned source DEV protocol — 2026-08-20

## Question

The WFIGS DEV error profile is dominated by false positives on small fires.
This candidate transfers an independently RCDA-VAL-selected hybrid residual
source trained with precision-oriented Tversky weights (alpha `0.7`, beta
`0.3`) instead of the recall-oriented source used by the control.

## Fixed recipe

- Source: `resunet_hybrid_precision_v3_seed0_best.pt`, selected on RCDA VAL.
- Data: WFIGS expansion TRAIN (184 events), selection on DEV (42 events).
- RCDA TRAIN normalization; hybrid target; decoder-only adaptation.
- AdamW `lr=1e-4`, weight decay `1e-4`, batch 4, maximum 18 epochs, patience 5,
  gradient cap 5; augmentation enabled.
- Precision-oriented Tversky source weights alpha `0.7`, beta `0.3`, gamma
  `0.75`; front-ring BCE `0.05`, radius 16 px.
- Selection metric: event-macro growth IoU on DEV only.

## Isolation and decision

The runner rejects roots containing `confirm`, `test` or `prospective`, checks
source selection on RCDA VAL, and asserts WFIGS TEST is not loaded. Promotion
requires `+0.005` event-macro IoU over the frozen residual control (`0.131902`);
otherwise the source is rejected without replication or confirmation.

## Publication boundary

Only code, tests, protocol and aggregate DEV metrics may be published. Raw
WFIGS geometries, tensors, tiles, checkpoints and per-pixel predictions remain
private.
