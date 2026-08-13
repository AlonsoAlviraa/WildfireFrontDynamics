# ML live → ABSTAIN / ECE note (Sprint 1)

| Field | Value |
|-------|--------|
| **Status** | Lab note (no retrain) |
| **Date** | 2026-07-24 |
| **Product** | `clm_ensemble_v34` |
| **Policy for demos** | `research_open` (experimental live fusion) |
| **field_ops fusion** | **ON** (human 2026-08-13; cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho. This 2026-07-24 note predates that promote. |

## Why this note exists

Live Decision Cards must **refuse** (ABSTAIN) when patch reliability is weak.
Catalog holdout IoU **0.8963** is **provenance / research quality only** — never
live fire certainty, never ops ROS, never a substitute for Head A confidence.

## U1 TEST honest (claim surface for pitch)

Source: `docs/ML_PRODUCT_SCORECARD.json`, `docs/ML_U1_PROMOTE_RECORD.json`.

| Metric | Approx. value | Role |
|--------|---------------|------|
| mean IoU eval (TEST) | **~0.86** | Honest eval mean on frozen protocol |
| selective IoU @ 80% coverage | **~0.90** | Keep top-conf patches |
| ECE patch conf | **~0.15** | Calibration error of Head A confidence |
| catalog holdout TEST IoU | 0.8963 | Provenance only — **not** live certainty |

`gates.u1_test_honest == true` enabled **recommended** experimental fusion on
`research_open`. Field `field_ops.allow_ml_live_in_fusion` was later set **ON**
by human promote 2026-08-13 (not by this lab note). Fusion ON ≠ despacho.

## When the Card ABSTAINs

| Trigger | Product behavior |
|---------|------------------|
| `ml_live.abstain == true` | Live source not actionable; ML-only conf → 0 |
| conf &lt; policy `ml_live_abstain_below` | Treated as abstained |
| **Identity calibrator** (no VAL-fit artifact) | Force abstain on product path (`conf=0.5` is neutral, not a claim) |
| High lab ECE + weak live diags | Prefer ABSTAIN over overconfident HOLD/GO in demos |

No retrain in this sprint. ECE ~0.15 is **known residual**; lowering it is
Sprint/P2 work. Until then: **call silence when unreliable**.

## Dual product

- Ops ROS stays `front_dynamics_v1`.
- ML mask + live confidence fuse **only** at the Decision Card.
- Never train on fused labels.
- Never invent tactical Vp from open packs or ML IoU.

## Demo

```powershell
$env:PYTHONPATH = "."
python scripts/run_ml_live_card_demo.py --mode offline --scenario abstain
python scripts/run_ml_live_card_demo.py --mode offline --scenario identity
# outputs/ml_live_card_demo/abstain_ece_note.json
```

See also: `docs/design/ML_FOCUS_PRODUCT_V1.md` § uncertainty → Decision Card.
