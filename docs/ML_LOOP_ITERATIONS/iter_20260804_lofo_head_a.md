# ML lab loop — iter 11 LOFO Head A (W1/W2)

**UTC:** 2026-08-05T07:57:38.369161+00:00  
**Prior:** next-gate said W1 BLOCKED  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| fit on LOFO | **false** |
| thr retune | **false** (locked from iter1) |

## Control: **YES**

- locked thr: **0.7949999999999999**
- LOFO ECE mean: **0.1732** (holdout 0.1528)
- locked abstain mean: **0.5236**
- locked IoU accepted mean: **0.8710**

## Per-fold

| Fold | n | mean IoU | ECE | abstain@lock | IoU acc@lock |
|------|--:|---------:|----:|-------------:|-------------:|
| CARDOSO | 200 | 0.8569 | 0.1528 | 0.5150 | 0.9492 |
| LA_ESTRELLA_ACOM1 | 200 | 0.7830 | 0.1249 | 0.2100 | 0.8505 |
| LA_ESTRELLA_ACOM2 | 190 | 0.6912 | 0.0730 | 0.6895 | 0.8436 |
| tobarra_20240802 | 300 | 0.4894 | 0.3421 | 0.6800 | 0.8405 |

## CLI

```powershell
python scripts/build_lofo_head_a_caches.py
python scripts/run_lab_ml_loop_v34_lofo_head_a.py --build
```

---
*Iteration 11 — multi-fire Head A; not field promote.*
