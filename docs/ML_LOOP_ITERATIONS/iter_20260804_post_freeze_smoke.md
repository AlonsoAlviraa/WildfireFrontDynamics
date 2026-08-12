# ML lab loop — iter 8 post-freeze smoke

**UTC:** 2026-08-04T21:29:27.317305+00:00  
**Prior:** freeze lab_usable (iter7)  
**Label:** lab / research_open only

## Rails

| Rail | Value |
|------|--------|
| ml_product_go | **false** |
| field_ops fusion | **OFF** |
| recommended surface | **iter1_reject_only** |
| ECE thrash same TEST | **stopped** |

## Control: **YES**

- smoke_pass: **True**
- steps: **22/22**
- lab_usable_freeze: **True**
- note: Post-freeze smoke green — lab surface still honest and offline-usable.

## Steps

- [x] `freeze_usable` — lab_usable_freeze=True
- [x] `freeze_check_artifacts_complete` — True
- [x] `freeze_check_iterations_1_to_6_present` — True
- [x] `freeze_check_ml_product_go_false` — True
- [x] `freeze_check_field_ops_fusion_off` — True
- [x] `freeze_check_recommended_surface_iter1_reject` — True
- [x] `freeze_check_stop_ece_thrash` — True
- [x] `freeze_check_reject_surface_improved` — True
- [x] `freeze_check_ece_not_claimed_improved` — True
- [x] `freeze_check_lofo_table_present` — True
- [x] `freeze_check_risk_curve_present` — True
- [x] `freeze_check_cli_surfaces_documented` — True
- [x] `field_ops_fusion_off` — allow_ml_live_in_fusion=False
- [x] `ml_product_go_false` — ml_product_go=False
- [x] `cli_list` — exit=0 out_len=1303 err_len=0
- [x] `cli_show` — exit=0 out_len=2308 err_len=0
- [x] `cli_doctor` — exit=0 out_len=2917 err_len=0
- [x] `cli_cases` — exit=0 out_len=2277 err_len=0
- [x] `cli_curve` — exit=0 out_len=1453 err_len=0
- [x] `cli_freeze` — exit=0 out_len=2690 err_len=0
- [x] `cli_card_offline` — exit=0 out_len=318 err_len=0
- [x] `cli_show_json_rails` — exit=0

## CLI

```powershell
python -m wildfire_front ml smoke
python scripts/run_lab_ml_loop_v34_smoke.py --pytest
make ml-lab-smoke
```

---
*Iteration 8 — regression gate; not field promote; ECE not fixed.*
