# ML lab loop — iter 9 LOFO multi-fire scoreboard

**UTC:** 2026-08-04T21:32:40.229852+00:00  
**Prior:** freeze + smoke (iters 7–8)  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| LOFO = U1 ECE | **never** |
| ECE thrash same TEST | **stopped** |

## Control: **YES**

- LOFO mean IoU: **0.7581** (n=3)
- spread: **0.1046**
- weakest: **LA_ESTRELLA_ACOM2** @ **0.6932**
- U1 gap: **0.0988**
- note: `holdout_u1_higher_than_lofo_mean — do not over-claim single-holdout IoU`

## Folds

| Fold | IoU | copy | Δ | changed |
|------|----:|-----:|--:|--------:|
| CARDOSO | 0.7978 | 0.6418 | 0.1560 | 0.9277 |
| LA_ESTRELLA_ACOM1 | 0.7832 | 0.3593 | 0.4238 | 0.8825 |
| LA_ESTRELLA_ACOM2 | 0.6932 | 0.3698 | 0.3233 | 0.8811 |

## CLI

```powershell
python -m wildfire_front ml lofo
python -m wildfire_front ml lofo --json
```

---
*Iteration 9 — multi-fire board; not field product; Head A LOFO ECE still blocked.*
