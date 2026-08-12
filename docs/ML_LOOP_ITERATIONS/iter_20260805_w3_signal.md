# ML lab loop — iter 13 W3 new signal (inventory + Tobarra diagnose)

**UTC:** 2026-08-05T08:06:29.922123+00:00  
**Label:** lab only · no ECE thrash same-holdout

## Control: **YES**

### In-pack sources (closed)

- n_sources: **4**
- hard fire: **tobarra_20240802**

### External candidates

- READY: **4** · first: **hellin_2024**

| id | priority | status | n_lwir | n_mask |
|----|----------|--------|-------:|-------:|
| hellin_2024 | P0 | READY | 36 | 16 |
| brazatortas_2025 | P1 | READY | 16 | 8 |
| retuerta_2025 | P1 | READY | 10 | 8 |
| polan_2025 | P2 | PARTIAL | 1 | 0 |
| cardoso_2025_lwir_extra | P2 | READY | 85 | 79 |

### Tobarra diagnose

- mean IoU: **0.48937716537707765** · bimodal: **True**
- frac IoU&lt;0.1: **0.3** · q25/q75: **0.04050847545199374** / **0.894789150060029**
- conf band: mean **0.781465507124868** [0.7400335559132966–0.8079320088350982]
- corr(conf, IoU): **0.7105692694972768**
- thr lock abstain: **0.68** · IoU acc: **0.840502906688746**
- reject helps: **True**

## Hellín probe (slice 2 dry-run)

**Status: BLOCKED** — `geotiff_to_training_patches` refused unaligned multi-frame shapes  
(H span≈5545 px · W span≈5438 px). See `outputs/ml_eval/lab_loop/w3_hellin_patch_probe.json`.

**Mitigation:** reproject/align LWIR to a common grid before patches. Do **not** use  
`allow_unaligned_crop` for product claims.

## Next

1. Align Hellín (or Brazatortas/Retuerta) grids → patches → Head A eval-only  
2. Tobarra finetune only with kill criteria (no U1 ECE thrash)

---
*Iteration 13 — W3 instrumented; not field product.*
