# ML Engineering Loop Rails

Three rails only for ML after 2026-07-15:

| Rail | Question | Example single_change |
|------|----------|------------------------|
| **Features** | New informative inputs? | `schema=physics14` |
| **Temporal** | Multi-timestep context? | `sequence_length=3` |
| **Transfer** | Real-fire holdout? | CLM test Δ copy |

## Gates

| Gate | Target |
|------|--------|
| G0 | v21 IoU 0.226, Δ +0.076 (any_fire 979) |
| G1 | IoU ≥ 0.25, Δ ≥ +0.09 same protocol |
| G2 | Δ copy > 0 on CLM **test** holdout |

## Queue

See `scripts/experiment_queue_features.json` (v25+).

## Kill list

filter-only · pos_weight-only · EMA/focal without new signal · train-CLM as transfer GO
