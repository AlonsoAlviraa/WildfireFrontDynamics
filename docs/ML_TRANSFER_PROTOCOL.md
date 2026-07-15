# ML Transfer Protocol (CLM holdout)

> **Freeze date:** 2026-07-15  
> **Gate G2:** Δ vs copy on **CLM test only** > 0, or explicit NO-GO with numbers  
> **Forbidden:** go/no-go on `train` split

---

## 1. Data source

- Raw pool: `artifacts/clm_ndws_patches/train/*.npz` (legacy 17-ch sequences)
- After split: `artifacts/clm_ndws_patches/{train,val,test}/` + `holdout_manifest.json`

## 2. Split rule (frozen)

1. Content hash (SHA-256 of `sequence`+`current_fire`+`target_fire` bytes) for dedup.
2. Sort unique hashes; seed **42**; assign 70% train / 15% val / 15% test.
3. Prefer grouping by filename prefix `clm_<EVENT>_` when present so an event does not leak across splits.
4. Manifest stores counts, seed, rule version `v1`.

```bash
python scripts/build_clm_holdout_splits.py --seed 42
```

## 3. Eval command

```bash
python scripts/eval_clm_transfer.py --split test --weights <pt>
```

- Refuses `--split train` for gate reporting (use `--allow-train-debug` only for debug).
- Metrics: `ndws_metrics.aggregate_ndws_evaluation` (IoU full, copy, Δ, dilated-changed).
- Protocol tag: `clm_holdout_test_seed42_v1`.

## 4. Schema note

CLM NPZ are **legacy17** `(1,17,64,64)`.  
- Evaluate v21-class weights as-is.  
- physics14 models require re-export or conversion before G2.

## 5. Promote rule

Transfer fine-tune (v28+) may train on CLM **train**, select on **val**, report G2 on **test** only.
