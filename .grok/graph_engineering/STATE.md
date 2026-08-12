# Graph Engineering — Estado actual

| Campo | Valor |
|-------|--------|
| **Mode** | Graph Engineering **v6.1** — *evidence + third-parties + research-backed ops* |
| **As of** | 2026-08-05 |
| **Horizon** | 2026-08-04 → **2026-09-04** |
| **Last unlock** | GO_MES true · O1 PASS · research corpus fused · **ML W3 MET + Tobarra KILL** |
| **Primary (product)** | **Human demo + acta (M3.2 / H1)** → **GO_Q** |
| **Primary (eng stack)** | **E1 pack + E2 Reliability Report (+research §) + E3 replay** — **DONE** |
| **Primary (research on path)** | **R-UQ1 + R-STACK-L** (citas en E2; no retrain) — **DONE** |
| **ML lab mega** | W3 **CLOSED MET** · Tobarra KEEP-or-KILL **CLOSED KILL** — `docs/goals/README.md` |
| **Stretch eng** | **E7 · R-SIM1 · R-A1 · R-A3 · R-B4 · R-OSS1 · R-CN1 · I1–I4 · H3 eng** — **DONE this run** |
| **Primary (write)** | Informe M3.4 — **ENG_FILLED** (`docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md`); sello humano opcional |
| **GO_MES** | **true** (mínimo) — `docs/GO_MES_VERDICT.md` |
| **GO_MES+ / O5** | false / OPEN — Hellín B eng-blocked optional |
| **Research retrain** | **0 h this month** as primary (no Tobarra KEEP thrash) |
| **Season** | `wfd-fire-intel-scrape` |
| **Literature** | `wfd-literature-ingest` → update `RESEARCH_TO_GRAPH_V6_MAP.md` |
| **Hygiene** | `wfd-status-sync` · `wfd-autonomous-cycle` weekly |
| **Regression** | `wfd-pilot-regression` after E1/E3/E4/E6 |
| **External** | `wfd-external-unblock` — demo / pack / O2 |
| **Snapshot** | `docs/CURRENT_STATE.md` |

**v7 teach-cli overlay:** product CLI `teach` / `show` / `demo-third-party` + `decide --explain` + cheatsheet (`docs/CHEATSHEET_DEMO_12MIN.md`). Improves teachability of the v6.1 evidence stack (E1–E3). Mode remains **v6.1** with this eng hygiene overlay. **Does not claim GO_Q** — primary product gate is still H1/M3.2 human demo+acta.

**H3/H1 demo path (2026-08-04):** eng executed full H3 path (`scripts/run_h3_dry_run_path.py` / `wildfire-front dry-run-h3` / `make h3-dry-run`) → `H3_DRY_RUN_REPORT`; status **ENG_EXECUTED_HUMAN_ATTESTATION_PENDING**. H1 still **TODO** (prep kit: `docs/H1_GO_Q_RUNBOOK.md`, `prepare_h1_acta_draft.py`, strict `record_h1_demo_complete.py`). **GO_Q remains partial** — no fake third party.

## Topology v6.1

```
                         ┌─ H-PRIMARY ─ demo M3.2 + acta ──► GO_Q
                         ├─ H-WRITE ─── informe M3.4 + research cites
                         ├─ E-P0 ────── demo pack · Reliability Report · replay
                         ├─ E-P1 ────── thermal contract · open freshness · card UQ
                         ├─ R-P0 ────── Lampman + Orion paragraphs in E2
                         ├─ R-P1 ────── OSS catalog · sector ROS · EFFIS attempt
                         ├─ R-P2 ────── ELMFIRE spike · FIRMS · EO inventory
                         ├─ R-LAB ───── frozen: WFTS/Swin/CN-CA/RF-ROS promote
                         ├─ I-CAL ───── OWTRD · Red Sky · ICFFR · INTERSCHUTZ
                         ├─ X-WAIT ──── O2 · CyL · 3ª ancla formal
                         ├─ 2–3×/week ► wfd-external-unblock
Sense / research ────────┼─ weekly ───► wfd-status-sync
                         ├─ weekly ───► wfd-autonomous-cycle
                         ├─ season ───► wfd-fire-intel-scrape
                         ├─ on lit ───► wfd-literature-ingest → RESEARCH map
                         ├─ after open ► wfd-open-pack-audit
                         └─ on code ─► wfd-pilot-regression
```

**v5→v6:** human demo + eng evidence pack.  
**v6→v6.1:** track **R-*** + full research corpus map; research **on** critical path only as **citations/UQ rails**, never as retrain.

## Research corpus (registered)

| Doc | Graph role |
|-----|------------|
| `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md` | Mega A–E → R-A*/R-B*/R-C* freeze |
| `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` | Lampman, Orion UQ, RGB-TIR doctrine |
| `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md` | I* + ELMFIRE + ferias |
| `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` | fuel/hybrid cite; maintain code |
| `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` | **bridge research→IDs** |
| `docs/fire_intel/COMPLETION_MATRIX.md` · mega-fires | open intel / CEMS |
| `research/chinese_research.md` | R-CN1 lab-only |
| `docs/fire_intel/CN_RESEARCH_LAB_ONLY.md` | **R-CN1 flag written** |
| `docs/fire_intel/ELMFIRE_FOREFIRE_SPIKE_NOTE.md` | **R-SIM1** |
| `research/*` roadmaps históricos | archive; not primary |
| `docs/REUNION_RESUMEN_Y_ANALISIS_ACCIONES.md` | product fail mode |

## Gates snapshot

| ID | Status |
|----|--------|
| **GO_MES** | **true** |
| **GO_Q** | partial (need **M3.2** / **H1** acta; M3.4 eng-filled) |
| **ml_product_go / field fusion** | **false / OFF** |
| **Tobarra LOFO KEEP** | **KILL** (fresh 0.4776) |
| **W3 multi-fire** | **MET** |
| **M3.2** | PENDING (templates ready) |
| **M3.4** | **ENG_FILLED_HUMAN_FINAL** — `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` |
| **H2 / H5** | H2 ENG_FILLED · H5 DONE (CyL silence note ~17 ago) |
| **O5 / O2** | OPEN / BLOCKED |
| **E1 E2 E3** | **DONE** eng (pack + report + replay) |
| **E7** | **DONE** hub abstention slice |
| **R-UQ1 R-STACK-L** | **DONE** (in E2) |
| **R-DATA1 / R-B1 / E4–E6 / E9 / E10** | **DONE** |
| **R-SIM1 R-A1 R-A3 R-B4 R-OSS1 R-CN1** | **DONE** eng this stretch |
| **I1–I5** | **DONE** eng notes/decisions (PDF OWTRD unread human) |
| **H3** | **ENG_EXECUTED_HUMAN_ATTESTATION_PENDING** (`make h3-dry-run` / `H3_DRY_RUN_REPORT`) |
| **H1** | **TODO** (runbook + acta draft prep; record script strict) |
| **ml_product_go / fusion** | false / OFF |

## Week focus (S1 now)

| P | Task | Owner |
|---|------|-------|
| **P0 eng** | E3→E1→E2 + R-UQ1 + R-STACK-L | **DONE** |
| **P0** | H1 schedule demo · H3 human dry-run | Human |
| **P1 eng** | R-DATA1 · E4–E6 · E9 · E10 · R-B1 · stretch R/I/E7 | **DONE** |
| **P1** | H2 informe | **ENG_FILLED** (human stamp optional) |
| **P1** | H5 CyL silence | **DONE** note · wait ~2026-08-17 |
| **KILL** | Hellín grids · ML retrain · invent anchors | all |

## Workflow registry

| Workflow | Cadence | v6.1 note |
|----------|---------|-----------|
| `wfd-external-unblock` | 2–3×/week | demo/pack/O2 |
| `wfd-status-sync` | weekly / after gates | |
| `wfd-autonomous-cycle` | weekly | not main |
| `wfd-literature-ingest` | on research | **→ RESEARCH_TO_GRAPH map** |
| `wfd-fire-intel-scrape` | season | no invent Vp |
| `wfd-open-pack-audit` | after E5/R-A1 | |
| `wfd-pilot-regression` | after product code | |

## Key paths

| Asset | Path |
|-------|------|
| Implement plan | `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md` |
| Research→IDs map | `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` |
| Status JSON | `docs/PLAN_1_MES_GRAPH_V6_STATUS.json` |
| Sub-window plan | `docs/PLAN_1_MES_POST_O1_UNLOCK.md` |
| Cycle c5 | `docs/graph_evolution/cycle_c5_graph_v6_implement.md` |
| Evolution log | `docs/graph_evolution/graph_evolution.md` |
| Dry-run H3 eng | `scripts/dry_run_demo_third_party.py` · `make dry-run-demo-third-party` |
| Metrics hub E7 | `scripts/build_metrics_hub.py` → `docs/METRICS_HUB.json` `abstention` |

## Rails (never auto-flip)

- No invented Vp / press / SITAC / Δha as confirmed  
- `field_ops.allow_ml_live_in_fusion` = false  
- `ml_product_go` = false  
- GO_MES true only as already verdicted; no silent GO_MES+  
- Catalog IoU provenance only  
- Holdout conf ≤ 0.75  
- Lampman MAE ≠ Tobarra SLA  
- Orion UQ → ABSTAIN rails, **not** EVACUATE product labels  
- ELMFIRE/ForeFire spike ≠ tactical  
- WFTS/Swin/CN-CA retrain **not** mes primary  
- research/* historical roadmaps **not** product primary  

## Next graph action (default)

1. **Human:** H3 walkthrough using `DRY_RUN_REPORT.md` · schedule H1 demo + acta (blocks full GO_Q).  
2. **Human (optional):** stamp/final author on `docs/INFORME_TRIMESTRE_2026_Q_PRODUCTO.md` (H2 eng-filled).  
3. **CyL (H5 DONE):** no re-spam until ~2026-08-17; then one follow-up or close — `docs/fire_intel/CYL_SILENCE_RULE_NOTE.md`.  
4. **Optional:** live FIRMS re-overlay; OWTRD PDF pass.  
5. **After lit scrape:** one row in RESEARCH_TO_GRAPH map.  
6. **Never:** Hellín param primary · ML retrain “because paper” · fusion flip · invent CyL perimeter.  
