# Handoff 1M plan → Mes3 (eng note 2026-08-13)

**From:** `docs/PLAN_1M_GO_LATAM_2026-08-13.md` (13 ago–12 sep)  
**To:** `docs/PLAN_MES3_AGENTES_A_B_2026-09-12.md` · human tip `docs/HANDOFF_MES3_HUMANOS_2026-09-12.md`  
**Scorecard:** `docs/SCORECARD_1M_GO_LATAM_2026-08-13.md`  
**Exec status:** `docs/PLAN_1M_EXECUTION_STATUS.json`

## Corrected truths (do not regress)

| Topic | Truth at handoff | Common mistake |
|-------|------------------|----------------|
| field_ops fusion | **ON** (human 2026-08-13) | Older Mes3 draft said OFF — **correct to ON** |
| GO_Q | **partial** | Do not invent complete |
| GO_TOTAL | **false** | Needs real h1_acta |
| GO_MES+ | **false** | Prep checklist only |
| FREEZE | intact; KEEP reopen false | No Tobarra retrain |
| #39 sector ROS | **merged** eng default | Not field ROS |
| complete_proxy usable-pair mean ~0.737 (EMSR715 FEP excluded as incompatible) | lab proxy; model < copy | ≠ sealed transfer IoU · ≠ old dressed ~0.85 |

## Human residual into Mes3

1. **H1:** book tercero (`h1_slot=not_booked`); demo; signed acta; `record_h1_demo_complete`  
2. **CONAF:** folio OIRS / paste confirm if arrives; cesión before `lab_ok_conaf`  
3. **B4/B5:** scorecards + FOI — no invent grade A / national  
4. Alonso-only: promote Hellín, marketing, gate flips  

## Eng residual (optional)

- Re-run complete_proxy IoU after expanding real_proxy packs if product wants n>2 measured  
- Keep residual LATAM tests green  
- Mes3 W1 branches per human handoff (A V&V UI / B FREEZE CI)  

## Verify

```bash
python scripts/check_release_flags.py   # PASS; fusion ON; GO_Q partial
python -m wildfire_front operator checklist
```
