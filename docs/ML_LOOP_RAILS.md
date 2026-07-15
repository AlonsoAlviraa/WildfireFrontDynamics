# ML Engineering Loop Rails

Three rails only for ML after 2026-07-15:

| Rail | Question | Example single_change |
|------|----------|------------------------|
| **Features** | New informative inputs? | `schema=physics14` → `physics15` (+wind_upslope) |
| **Temporal** | Multi-timestep context? | `sequence_length=3` |
| **Transfer** | Real-fire holdout? | CLM test Δ copy |

## Gates

| Gate | Target | Status (2026-07-15) |
|------|--------|---------------------|
| G0 | v21 IoU 0.226, Δ +0.076 (any_fire 979) | **GO** product `ndws_v21` |
| G1 | IoU ≥ 0.25, Δ ≥ +0.09 same protocol | **OPEN** — v25 physics14 no-promote; **v26 physics15** queued |
| G2 | Δ copy > 0 on CLM **test** holdout | **GO** product `clm_v28` (IoU 0.838, Δ +0.196) |

## Queue

See `scripts/experiment_queue_features.json` (v25+). Active G1 attempt:

```bash
# after git push of physics15 schema + training script
cp kaggle_job/kernel-metadata-v26.json kaggle_job/kernel-metadata.json
kaggle kernels push -p kaggle_job
```

Kernel: `alonsoalviraaaa/wildfire-front-training-v26-physics15`

## Kill list

filter-only · pos_weight-only · EMA/focal without new signal · train-CLM as transfer GO · promote NDWS without G1
