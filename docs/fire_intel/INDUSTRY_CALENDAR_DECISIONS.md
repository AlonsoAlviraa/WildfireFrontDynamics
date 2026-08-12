# Industry calendar decisions (I3 + I4)

**As of:** 2026-08-04  
**Graph IDs:** I3 (Red Sky) · I4 (INTERSCHUTZ)  
**Sources:** `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md`  
**Rule:** decision flags only — no fabricated registrations or budgets.

## Decision table

| Event | When / where | Decision | Pack readiness | Rationale | Next action |
|-------|--------------|----------|----------------|-----------|-------------|
| **Red Sky Summit** | **4 Nov 2026 · San Francisco, CA** · [redskysummit.com](https://redskysummit.com/) | **WAIT → prepare apply** | **READY eng** (`outputs/demo_third_party/`, Reliability Report, dry-run target) | Best CA firetech networking; audience = adoption not papers. Apply window TBD by organizers; human owns registration. | Human: monitor apply form; eng: keep pack + dry-run green; do **not** pitch IoU-as-ROS |
| **INTERSCHUTZ 2026** + WildfireCamp | **1–6 Jun 2026 · Hannover** | **SKIP visit 2026** (budget/default) · **flag 2027 revisit** | Pack ready for EU narrative, but **no booth budget locked** | Strongest EU wildland product-fit fair; Jun 2026 may be too soon for travel/booth without H1 acta. | Human: if sponsor appears, flip to **VISIT-lite** (walking pass); eng: no new fair software |
| **ICFFR Coimbra** | **31 Oct – 6 Nov 2026** | **WAIT abstract** | Abstract **draft** exists (`ICFFR_ABSTRACT_DRAFT.md`) | Scientific peer audience for multi-ancla + ABSTAIN | Human: author list + submit decision before deadline |
| **IDGA Wildfire Tech Summit** | **21–22 Apr 2027 · San Diego** | **WAIT** | Same pack family | Institutional CA/US buyers; after Red Sky learnings | Calendar only |
| **OWTRD (not a fair)** | ongoing CA | **READ** | Notes skeleton `OWTRD_NOTES.md` | Language/procurement channel | Human PDF pass |

### Decision legend

| Tag | Meaning |
|-----|---------|
| **APPLY** | Submit attendance/sponsor application now |
| **WAIT → prepare apply** | Materials ready; human timing for form |
| **SKIP** | No spend this cycle |
| **VISIT-lite** | No booth; walk + meetings only |
| **WAIT** | Reassess next quarter |

## Pack readiness checklist (shared)

| Asset | Path | Status |
|-------|------|--------|
| Third-party pack | `outputs/demo_third_party/` | eng DONE (E1) |
| Replay one-cmd | `scripts/run_third_party_replay.py` | eng DONE (E3) |
| Dry-run report | `make dry-run-demo-third-party` → `DRY_RUN_REPORT.md` | eng support (H3 human still required) |
| Reliability narrative | `docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md` | DONE |
| Honesty IoU≠ROS | `docs/METRICS_HONESTY_IOU_NE_ROS.md` | DONE |
| Signed acta H1 | `docs/actas/` | **HUMAN TODO** |
| Travel/booth budget | — | **HUMAN TODO** |

## Rails for any fair pitch

- fusion ML-live **OFF**  
- no invented anchors / Vp  
- no GO_Q claim without M3.2 acta  
- CEMS open ≠ national O2  
- ELMFIRE/ForeFire = lab compare only  

## Related

- I1 `OWTRD_NOTES.md`  
- I2 `ICFFR_ABSTRACT_DRAFT.md`  
- I5 / R-DATA1 OSS catalog  
