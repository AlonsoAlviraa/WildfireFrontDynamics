# Graph cycle c4 — post O1 unlock (2026-08-03)

| Field | Value |
|-------|--------|
| **Cycle** | c4 |
| **Graph version** | v4 → **v5** |
| **Trigger** | Pablo pack 0308 + Hellín confirmed + fuel PR-α/β on main + O1/GO_MES recompute |
| **HEAD fuel stack** | `eb95049` |
| **Authority** | `data/infocam_anchors.json` · `docs/O1_GOMES_RECOMPUTE_20260803.json` |

---

## Sense snapshot

### Product / gates

| Gate | Value |
|------|--------|
| GO_ENG | true |
| GO_MES | **false** (P1 partial) |
| O1 | **PASS** (n_confirmed=2) |
| O2 national | BLOCKED |
| ml_product_go | false |
| field_ops fusion | OFF |

### Confirmed anchors

1. **Tobarra** — Vp 7 m/min · 39 ha · parte INFOCAM  
2. **Hellín** — Vp **50** m/min · 100 ha* · boletín UNAP 20/07/2024  

### Shipped eng (not blockers)

- Fuel terrain stack + WorldCover + spatial sectors + k recipe  
- AEMET weather path + hybrid envelope v3 + scorecard weight 0  
- Pablo Tobarra + multi-IF 0308 (Hellín/Estrella/Cardoso)  
- Cardoso Δha timeline proxy; Estrella map readings (non-confirmed)  

---

## Decision: evolve graph to v5

**Stop** treating “email for second anchor” as the primary external node.

**New primary eng node:** Hellín front_dynamics vs Vp 50 → close P1/O5.  
**New primary human node:** third-party demo (M3.2).  
**Hygiene nodes:** status-sync, autonomous-cycle, fire-intel — unchanged cadence.  

### Topology change

| Before (v4) | After (v5) |
|-------------|------------|
| O1 human top | Demo human top |
| Cardoso email unlock | Hellín ops eng unlock |
| Literature + fuel build primary science | Fuel **maintain**; ops **close GO_MES** |

---

## Track A executed (2026-08-03)

| Field | Result |
|-------|--------|
| Pack | `outputs/observatorio/hellin_2024/` |
| Grade | **B** (muestra corta) |
| Primary ROS | **15.96 m/min** (area_isotropic, n=1 pair usable) |
| Vp | **50 m/min** |
| Ratio | **0.32** — underestimate / out of [0.5, 2] |
| Grade A | **NO** |
| GO_MES | **NO** (P1 still partial) |
| Scorecard | `docs/HELLIN_TRACK_A_SCORECARD.md` · `scripts/score_hellin_track_a.py` |

## Next actions (ordered)

1. **eng optional:** re-run Hellín with fuller mask set / better FOV to try grade A — or document P1 eng BLOCKED  
2. **human:** schedule 30 min third-party demo + 1-page acta  
3. **sync:** after 1 or 2, `wfd-status-sync` + SCORECARD  
4. **external:** O2 SHP; CyL wait ~17 Aug  

## Explicit non-actions

- Do not invent Cardoso Vp  
- Do not promote Estrella SITAC 20–25 m/min to confirmed without formal parte  
- Do not single-k calibrate 7 vs 50  
- Do not claim GO_MES until P1 true  

---

## Artifacts written this cycle

| Path | Role |
|------|------|
| `.grok/graph_engineering/STATE.md` | v5 state |
| `docs/PLAN_1_MES_POST_O1_UNLOCK.md` | 1-month overlay |
| `docs/graph_evolution/cycle_c4_post_o1_20260803.md` | this log |
| `docs/O1_GOMES_RECOMPUTE_20260803.json` | machine O1/GO_MES |
| `docs/SCORECARD_MES_1.md` | human scorecard |

---

## Success metrics for next cycle (c5)

| Metric | Target |
|--------|--------|
| P1 | GO or documented eng BLOCKED with evidence |
| GO_MES | true if P1 GO |
| M3.2 | scheduled or done |
| Honesty | still no invented Vp; fusion OFF |
