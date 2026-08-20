# WFIGS event-size decoder DEV result — 2026-08-20

## Scope and isolation

The fixed grid was evaluated on the 42-event WFIGS expansion DEV split using
the frozen equal-weight hybrid ensemble. No model weights were updated and no
confirmation/prospective TEST artifact was loaded or inspected.

## Result

The selected DEV rule uses thresholds `(0.30, 0.25, 0.40, 0.45)` for previous
fire areas `[0,100)`, `[100,500)`, `[500,2000)`, and `[2000,∞)` pixels,
respectively, plus a 12 px maximum t0-front distance.

| Decoder | Event-macro IoU | Pooled IoU | Precision | Recall |
|---|---:|---:|---:|---:|
| Frozen equal-weight ensemble, no size rule | 0.136178 | 0.149627 | 0.226176 | 0.306567 |
| Event-size thresholds + 12 px cap | 0.137478 | 0.147594 | 0.246673 | 0.268718 |

The event-macro gain is `+0.001299`, below the preregistered `+0.005`
promotion margin. The pooled IoU and recall decrease, despite a precision
increase. This is therefore a metric-specific DEV sensitivity and not a
confirmed model improvement.

## Decision

Reject promotion and do not open confirmation for this decoder. Keep the
frozen equal-weight ensemble as the paper control. The local aggregate ranking
is reproducible; raw WFIGS tensors, geometries, checkpoints and per-pixel
outputs remain private.

## Rights

WFIGS is used as a public source for internal/noncommercial training. No raw or
derived WFIGS data are redistributed in this PR.
