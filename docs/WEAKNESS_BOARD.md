# IF weakness / candidate board

> Fail-closed inventory. **Does not** invent Vp/ha, flip `infocam_anchors.json`,
> retrain `clm_ensemble_v34`, reopen Tobarra KEEP, or close GO_Q.
> Fusion SSOT stays **ON** (human 2026-08-13) ≠ despacho. IoU ≠ ROS.
> Schema `wfd_if_weakness_board_v1` · `2026-08-13T12:44:19.922415Z`.

## Rails

| Rail | Value |
|------|--------|
| FREEZE_ML | intact — no v34 retrain |
| Tobarra KEEP reopen | **false** |
| GO_Q | **partial** |
| field_ops ML fusion | **ON** (not despacho) |
| Hellín | `pending_external` until cite + Alonso |
| Catalog IoU 0.8963 | provenance only |

## Fires

| fire_id | status | honesty_class | R1 | R2 | R3 | R4 | R5 | R6 | H1 | H2 | H3 | H4 | H5 | H6 | H7 | tifs | dated | gap | owner |
|---------|--------|---------------|----|----|----|----|----|----|----|----|----|----|----|----|----|-----:|------:|-----|-------|
| `tobarra_20240802` | `confirmed` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 138 | 35 | rights | human |
| `cardoso_2025` | `pending_external` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 488 | 85 | cite | human |
| `hellin_2024` | `pending_external` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 152 | 36 | cite | human |
| `la_estrella_acom1_2024` | `pending_external` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 1065 | 199 | cite | human |
| `retuerta_2025` | `NO_USE` | `discard` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 48 | 10 | FOV | human |
| `la_estrella_acom2_2024` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 236 | 67 | cite | human |
| `brazatortas_2025` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 57 | 16 | cite | human |
| `polan_2025` | `NO_USE` | `discard` | 0 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 14 | 9 | >=3 frames | human |
| `AU_EMSR408_NSW` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 7 | 7 | cite | human |
| `AU_EMSR500_PERTH` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 20 | 6 | cite | human |
| `AU_NAFI_NT_SEASON_2023` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 9 | 6 | cite | human |
| `BR_PANTANAL_2020_MAPBIOMAS` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 9 | 6 | cite | human |
| `CL_EMSR647_NACIMIENTO` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 20 | 6 | cite | human |
| `CL_EMSR715_VALPARAISO` | `inventory_only` | `ml_weak` | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 6 | 6 | cite | human |
| `pt_firesprd` | `inventory_only` | `proxy` | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | cite | human |
| `extremadura_rai_2025` | `inventory_only` | `proxy` | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | cite | human |

- n_fires: **16** · confirmed: **1** · ml_strong: **0** · NO_USE: **2**
- Unknown R/H bits are **0**. Missing cite ⇒ not `confirmed`. Missing ≥3 dated scenes ⇒ not `ml_strong`.
- Open packs (PT-FireSprd, Perth, Nacimiento, …) stay `ml_weak` / `proxy` — not a 2nd INFOCAM grade A.

## Tobarra LOFO (sealed cites only)

- New IoU invented: `False` · KEEP reopened: `False` · retrained: `False`
- Sealed V29 (`docs/V29_LOFO_TOBARRA_VERDICT.json`): held `tobarra_20240802` test_iou **0.4938** vs copy 0.3284 (n_test=300).
- Sealed fold `CARDOSO`: test_iou **0.7978106779815259** (source `docs/CLM_LOFO_ALL_FOLDS_REPORT.json`).
- Sealed fold `LA_ESTRELLA_ACOM1`: test_iou **0.7831634770802975** (source `docs/CLM_LOFO_ALL_FOLDS_REPORT.json`).
- Sealed fold `LA_ESTRELLA_ACOM2`: test_iou **0.6931861844919686** (source `docs/CLM_LOFO_ALL_FOLDS_REPORT.json`).
- Sealed fold `tobarra_20240802`: test_iou **0.4938** (source `docs/CLM_LOFO_ALL_FOLDS_REPORT.json`).
- On-disk aligned `artifacts/aligned_spatial_v1/tobarra_20240802`: tifs=68 dated_scenes=34 present=True.
- `decide_tobarra_aligned` honesty_class=`ml_weak` (existing helper; not a new IoU).
- Blocker: domain gap: sealed Tobarra LOFO IoU is cited from docs/V29_LOFO_TOBARRA_VERDICT.json vs non-Tobarra folds in docs/CLM_LOFO_ALL_FOLDS_REPORT.json — not a 'need more epochs' problem

## How to run

```powershell
python scripts/score_if_weakness_board.py
python scripts/score_if_weakness_board.py --fire-id hellin_2024
```

Missing anchors or unknown `--fire-id` exit **1**. Does not write `data/infocam_anchors.json`.

Human leftovers (cite / 2nd grade A / H1 acta) stay in `docs/HANDOFF_HUMAN_P0_2026-08-13.md`.

