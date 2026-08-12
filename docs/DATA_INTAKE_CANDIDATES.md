# DATA_INTAKE_CANDIDATES — V1 High-EV Fire Ledger

**As-of:** 2026-08-07 · **work_class:** `data_intake_ledger_v1` · **lab only**  
**Rails:** no press ha as official · no invented Vp · `press_only` never enters ML train/test IoU product  
**Machine CSV:** [`docs/DATA_INTAKE_CANDIDATES.csv`](DATA_INTAKE_CANDIDATES.csv)

## Honesty classes

| Class | Meaning | ML use |
|-------|---------|--------|
| `chain_honest` | LWIR + masks multi-step aligned | LOFO train/test OK |
| `perimeter_only` | Multi-hora ops perimeter (KMZ), no full LWIR chain | lab perimeter eval only; not sealed T1 IoU |
| `partial_masks` | LWIR yes, masks << frames | train only if QA B+; document n_masks |
| `press_only` | Press/EFFIS/CEMS ha only | **never** ML train/test |
| `blocked` | Rights/silence/insufficient material | wait / drop |

## Candidate ledger (≥8)

| pri | fire_id | honesty_class | n_lwir | n_masks | legacy17_patches | spatial_patches | ML queue | next_action | risk |
|----:|---------|---------------|-------:|--------:|-----------------:|----------------:|----------|-------------|------|
| 1 | `hellin_2024` | `chain_honest` | 36 | 16 | ~320 (w3 holdout) | 120 | **PROMOTE LOFO held/train** | LOFO v2 redesign + leak audit | ancla confirmed Vp=50; masks &lt; lwir |
| 2 | `brazatortas_2025` | `partial_masks` | 16 | 8 | 0 sealed | 40 | train-cap external | emit legacy17 if missing; cap ≤0.28 | sin ancla |
| 3 | `la_estrella_acom2_2024` | `partial_masks` | 67 | 17 | in lofo_v1 | 120 | keep stress fold | complete masks if possible | min IoU bottleneck |
| 4 | `retuerta_2025` | `partial_masks` + QA_FLAG | 10 | 8 | 0 sealed | 80 | **exclude train** until clean | QA re-open only | FOV/area flag |
| 5 | `polan_2025` | `blocked` | 1 | 0 | 0 | 0 | no | need masks or drop | insufficient |
| 6 | `cardoso_2025` | `chain_honest` | 85 | 79 | in lofo_v1 | 1120 | core LOFO | request INFOCAM Vp | pending_external anchor |
| 7 | `pablo_geacam_tobarra_ops` | `perimeter_only` | n/a | n/a | n/a | n/a | ops O2 partial | multi-IF KMZ request | ops≠cadastre |
| 8 | `es_gu_la_mierla_20260716` | `press_only` | 0 | 0 | 0 | 0 | **blocked ML** | EGIF+LWIR only | press ~32k ≠ EGIF |
| 9 | `es_av_burgohondo_202607` | `press_only` | 0 | 0 | 0 | 0 | **blocked ML** | CEMS perimeter research only | press ~50k |
| 10 | `es_md_sierra_oeste_202607` | `press_only` | 0 | 0 | 0 | 0 | **blocked ML** | same | press ~19k |
| 11 | `cems_open_perimeter` | `perimeter_only` | 0 | 0 | 0 | 0 | open demo not T1 | `build_open_if_pack` | no Vp |
| 12 | `nijar_rediam_and` | `perimeter_only` | 0 | 0 | open packs | — | O2 AND demo | keep industrial demo | no LWIR chain |

## ML queue (press_only excluded)

1. **Hellín** → LOFO redesign (highest EV local).  
2. **Brazatortas** → external train cap if legacy17 emit OK.  
3. **ACOM2 masks** → complete if material exists (regime min).  
4. External: Cardoso Vp, GEACAM multi-IF, CyL silence rule (no re-spam).

## Sprint S1 exit (this execution)

- [x] Ledger ≥8 with honesty_class  
- [ ] Hellín in LOFO pack leak-0  
- [ ] Brazatortas decision stamp  
- [ ] External blocked/press documented (not in train)

## Rails stamp

```json
{
  "ml_product_go": false,
  "field_ops_allow_ml_live_in_fusion": false,
  "press_only_in_ml_train": false,
  "tobarra_keep_reopen": false
}
```
