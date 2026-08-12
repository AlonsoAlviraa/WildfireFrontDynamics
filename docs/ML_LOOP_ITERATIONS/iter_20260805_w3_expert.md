# ML lab loop — iter 14 W3 expert (align → patches → Head A + Tobarra recipe)

**UTC:** 2026-08-05T08:55:58.354653+00:00  
**Label:** lab only · no ECE/thr thrash same-holdout · field_ops OFF

## Control: **YES**

### Align + patches

- align_patch_ok: **True**
- head_a_ok: **True**

| fire | patches | mean IoU | copy IoU | Δ vs copy | ECE | abs@lock |
|------|--------:|---------:|---------:|----------:|----:|---------:|
| retuerta_2025 | 300 | 0.46576538084800384 | 0.465765380859375 | -1.137118177396701e-11 | 0.3329320088350983 | 0.0 |

Honesty: patches use `min_change_fraction=0.02` (drop copy-easy short-Δt).
Do **not** sell Hellín IoU without Δ vs copy.

### Tobarra recipe

- recommendation: **OPTIONAL_lofo_finetune_with_kill**
- zero_target_leak_ok: **True**
- baseline mean IoU: **0.48937716537707765**
- kill criteria: **5** (K1–K5)
- recipe JSON: `outputs/ml_eval/lab_loop/tobarra_finetune_recipe.json`

### Rails (unchanged)

- `ml_product_go`: **false**
- `field_ops.allow_ml_live_in_fusion`: **false**
- no ECE / reject thr fit on holdout TEST

## Next

1. Hellín beats copy (Δ>0) on filtered patches — lab new-fire signal usable
2. Brazatortas weak Δ vs copy — treat as hard transfer, not GO
3. Tobarra LOFO finetune only if recipe recommendation is OPTIONAL and K1–K5 pass
4. W4 human `ml_product_go` — not this loop

---
*Iteration 14 — W3 expert path; not field product.*
