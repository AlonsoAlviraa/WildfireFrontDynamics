# Lab track — U-Net / larger-model kill criteria (PR11)

**Rail:** `lab_ml` only. **Zero field fusion** from this document or any experiment it authorizes.  
**Date:** 2026-08-06  
**Related:** `docs/design/PR_PLAN_MULTIHORIZON_FIELDOPS.md` (PR11), deep research claims 1–8, 42–45.

## Purpose

Keep the residual ~1M CLM ensemble as the **default lab product**. Larger backbones
(ResNet-50 encoder U-Nets, Swin, SegFormer, etc.) are **optional research** under
strict kill criteria — never the default field product, never a fusion unlock.

## Immutable rails

| Rail | Value |
|------|--------|
| Lab product default | `clm_ensemble_v34` (~ residual path) |
| Field fusion | **OFF** (`field_ops_allow_ml_live_in_fusion=False`) |
| IoU ≠ ROS | true |
| `ml_product_go` auto-flip | forbidden (human promote only) |
| Multihorizon field_ops | geometry / ops ROS — **not** ML next-day mask |
| Tobarra KEEP reopen | forbidden from this track |
| ECE thrash on same test | forbidden |

## Kill criteria (must all pass to promote a larger model)

1. **LOFO / LOYO:** mean IoU strictly beats locked champion residual on the same
   LOFO board protocol (not a single lucky fold).
2. **NDWS protocol clean:** holdout / NDWS evaluation uses the locked feature
   schema and VAL-only threshold protocol; no test-set thrash.
3. **No protocol inflation:** no silent change of reject thr, mix weights, or
   feature stack relative to the freeze iter1 surface without a new scorecard id.
4. **Domain-shift honesty:** year / site external stress must not collapse below
   documented floor without an explicit research-only flag.
5. **Cost/latency:** if larger model ties residual within noise, **keep residual**
   (capacity ≠ LOYO win; research claims 3, 8, 43, 46).
6. **Field path:** promoting a lab model **never** sets
   `field_ops_allow_ml_live_in_fusion=True`. Dual SKU remains dual.

## Allowed optional experiments

- Lightweight TD-Fusion-class residual heads **if** NDWS protocol is clean.
- Ablations recorded under `outputs/ml_eval/` with kill verdict stamped.
- Documentation / scorecard only — no retrain required to keep PR11 closed.

## Forbidden

- Larger U-Net / ViT as **primary field product**.
- ML multi-day heads sold as tactical 1 h multihorizon.
- Field fusion ON from lab `ml_product_go`.
- Claiming multihorizon isotropic/anisotropic improved lab IoU (impact audit: false).

## Verdict stamp (for experiment boards)

```json
{
  "schema": "wfd_lab_unet_scale_kill_v1",
  "product_rail": "lab_ml",
  "field_ops_allow_ml_live_in_fusion": false,
  "default_bet_larger_unet": false,
  "promote_if": ["lofo_beats_champion", "ndws_protocol_clean", "no_protocol_inflation"],
  "kill_if": ["tie_or_lose_lofo", "test_set_thrash", "field_fusion_attempt"]
}
```

## Code hooks (thin guardrails)

- `wildfire_front.ml.protocol_rails` — `LAB_LARGER_UNET_DEFAULT_BET = False`
- `wildfire_front.ml.product_catalog` — ops boundary refuses field fusion unlock
  from catalog loaders

**PR11 ships documentation + guardrail constants only. No retrain. No fusion path.**
