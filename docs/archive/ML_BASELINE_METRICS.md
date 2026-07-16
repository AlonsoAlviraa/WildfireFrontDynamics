# ML Baseline Metrics Report

**Date:** 2026-07-09
**Weights:** `weights_pretrained_best.pt`
**Dataset:** `semireal_controlled_001`
**Samples evaluated:** 18

## Segmentation Metrics (Pixel-Level)

| Metric | Mean | Std | Micro (pooled) |
|--------|------|-----|----------------|
| IOU | 0.2183 | 0.1712 | 0.3378 |
| DICE | 0.3253 | 0.2367 | 0.5050 |
| PRECISION | 0.6759 | 0.3879 | 0.9208 |
| RECALL | 0.2384 | 0.1895 | 0.3479 |
| ACCURACY | 0.8663 | 0.1200 | — |
| SPECIFICITY | 0.9920 | 0.0136 | — |

## Interpretation

- **Valid samples** (with active fire): 18 / 18
- **Micro IoU** (pooled TP/FP/FN): `0.3378`
- **Micro F1/Dice**: `0.5050`

## Next Steps

1. If IoU < 0.3, the model is not learning front propagation effectively.
   Consider increasing data diversity or adjusting the RL reward.
2. If precision is low (many false positives), increase the action threshold or add a false-positive penalty.
3. If recall is low (missed ignitions), train longer or use focal loss.
4. Compare `weights_pretrained_best.pt` vs `weights_fine_tuned.pt` to quantify the fine-tuning gain.
