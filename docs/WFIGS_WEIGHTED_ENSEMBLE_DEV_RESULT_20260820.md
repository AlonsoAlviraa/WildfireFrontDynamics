# WFIGS weighted-ensemble DEV result — 2026-08-20

## Scope and isolation

The evaluator used only WFIGS expansion DEV (42 events) with frozen WFIGS
decoder checkpoints. No weights were updated, and confirmation/prospective TEST
were not loaded, selected on, or inspected.

## Result

The fixed grid selected weights `[0.25, 0.25, 0.50]` for seeds 11/29/47,
threshold `0.25`, and maximum t0-front distance `12` px.

| Decoder | Event-macro IoU | Pooled IoU | Precision | Recall |
|---|---:|---:|---:|---:|
| Frozen equal-weight ensemble, no distance cap | 0.136178 | 0.149627 | 0.226176 | 0.306567 |
| Frozen equal-weight ensemble, 12 px cap | 0.136554 | 0.149155 | 0.225898 | 0.305094 |
| Weighted `[.25,.25,.50]`, 12 px cap | 0.136771 | 0.147781 | 0.214854 | 0.321292 |

The weighted candidate improves event-macro IoU by `+0.000592` over the
equal-weight/no-cap ensemble and by `+0.000216` over the equal-weight/12 px
decoder. It does not meet the preregistered `+0.005` promotion criterion, and
its pooled IoU and precision are lower. This is a small DEV sensitivity result,
not evidence of a confirmed model improvement.

## Decision

Reject promotion and do not open confirmation for the weighted ensemble. Keep
the equal-weight ensemble and its previously frozen spatial decoder as the
paper control. The ranking JSON contains aggregate metrics only; checkpoints,
WFIGS tensors, geometries and per-pixel predictions remain private.

## Rights

WFIGS is used as a public source for internal/noncommercial training. This PR
does not redistribute raw or derived WFIGS data.
