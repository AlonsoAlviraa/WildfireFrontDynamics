# Deep research — nuevas estrategias producto WFD (2024–2026)

> **Generated:** 2026-08-05 via `/deep-research` harness + product synthesis  
> **Corpus prior:** `MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md`, `SOTA_STACK_ADOPTION_2026.md`, `LITERATURE_CORPUS_ROS_FUEL.md`, `RESEARCH_TO_GRAPH_V6_MAP.md`  
> **Product rails:** `ml_product_go=false` · field_ops fusion **OFF** · IoU ≠ ROS · Tobarra LOFO KEEP **KILL**  
> **Snapshot:** `docs/CURRENT_STATE.md`  
> **Machine claims:** `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026_claims.json`

## Verification stats

| Metric | Value |
|--------|------:|
| Sub-queries | 6 |
| Claims survived | **75** |
| Dropped | **0** |
| Dropped breakdown | duplicates 0 · refuted 0 · verifierFailed 0 |
| Wall time | ~50 min |

## Sub-queries (fan-out)

1. Selective prediction / reject / conformal / abstention (segmentation + wildfire)  
2. LOFO / LOIO / domain generalization / hard-fire transfer  
3. Multi-pass thermal UAV ROS beyond Lampman (geometry ≠ IoU)  
4. Hybrid physics-ML fuel/ROS Mediterranean + digital-twin light  
5. Open datasets + EFFIS/CEMS/FIRMS validation geometry  
6. Geospatial foundation models + SAR–optical / RGB–TIR fusion  

---

## Executive message (post Tobarra KILL)

El corpus interno de julio–agosto ya cubría U-Net, Lampman TIR-ROS, Orion UQ, fuel Med y EFFIS A1.  
La ampliación 2024–2026 **no** pide “otra U-Net en Tobarra”. Señala cinco frentes con ROI de producto:

1. **Selective prediction + conformal risk** → endurecer ABSTAIN en Decision Card / `ml reject` (lab) sin thrash ECE same-TEST  
2. **LOFO/LOIO protocol honesty** → formalizar transfer penalty (ya medimos Tobarra hard)  
3. **ROS geométrico multi-pass** (O’Neill arrival-time, FLAME 3, FireCast-Fusion) → ops, no ML IoU  
4. **Open perimeter geometry** (EFFIS WFS, FireSpread_MedEU, TS-SatFire) → O2-lite / demo honesty  
5. **GFM + LoRA burn scar** (Prithvi-EO-2.0, TerraMind) → lab exploratorio; **no** field fusion  

**Deprioritizado (explícito):** ECE thrash same U1 TEST · IoU=ROS · reabrir Tobarra KEEP misma receta · `ml_product_go` flip.

---

## Strategy shortlist (ranked by product ROI)

### S1 — Soft Dice Confidence + risk–coverage on lab reject (P0 · 1 semana)

| | |
|--|--|
| **Paper** | Soft Dice Confidence (SDC) — Borges et al., arXiv [2402.10665](https://arxiv.org/abs/2402.10665) (ML 2026) |
| **Claim** | Post-hoc image-level confidence near-optimal for selective prediction when Dice/IoU is the metric; risk–coverage curves |
| **Also** | SHRUG-FM ([2511.10370](https://arxiv.org/abs/2511.10370), CVPR EarthVision 2026) — multi-signal accept/abstain on **burn scar** EO; UnCoL entropy risk–coverage |
| **WFD map** | ML lab: `ml curve` / reject thr ~0.80 already; Decision Card ABSTAIN language |
| **Experiment (1 week)** | Implement SDC (or Dice-aligned score) on U1 TEST **frozen** model; plot risk–coverage vs entropy/margin; compare AURC on accepted IoU |
| **Kill** | No lift in selective@80 IoU **or** AURC worse than entropy by >5% relative → **KILL SDC**, keep iter1 reject |
| **Rails** | Fit thr/score on **VAL only**; never retune on Tobarra test / U1 thrash loop |

### S2 — Morphological / pixel conformal sets for mask ABSTAIN (P0–P1 · 1–2 semanas)

| | |
|--|--|
| **Paper** | Morphological conformal prediction sets — Mossina & Friedrich [2503.05618](https://arxiv.org/abs/2503.05618) (MICCAI 2025); CRC segmentation [2405.05145](https://arxiv.org/abs/2405.05145); Kandinsky CP CVPR 2024 |
| **Claim** | Finite-sample coverage on dilated mask sets; model-agnostic if only masks available |
| **WFD map** | Decision Card / Reliability Report visual “uncertainty band”; lab envelope of mask |
| **Experiment** | Calibrate dilation radius on VAL so empirical coverage ≥ 1−α (e.g. 0.9) on held VAL fold; report coverage on U1 TEST once |
| **Kill** | Test coverage < target−0.05 **or** average dilated area > 2× mask → **KILL** (too loose) |
| **Rails** | One-shot TEST report; no iterative thrash |

### S3 — Dual LOFO protocol board (within-fire vs across-fire) (P0 · ya casi hecho)

| | |
|--|--|
| **Paper** | Van & Lee LOCO+LOFO burn severity — Remote Sensing 2025 [17/22/3756](https://www.mdpi.com/2072-4292/17/22/3756); Wong et al. LOFO trees California [IOP 2025](https://iopscience.iop.org/article/10.1088/2752-664X/add5fd); LOIO Huang et al. [2607.07951](https://arxiv.org/abs/2607.07951) |
| **Claim** | Explicit **transfer penalty** LOCO→LOFO; hard fires dominate failures (Dixie-like); no literature kill bar standard — **we invent K1** |
| **WFD map** | Head A LOFO board + W3 Hellín/Brazatortas/Retuerta + Tobarra KILL already |
| **Experiment** | Publish dual table: pack LOFO mean vs external W3 mean + Δ vs copy; freeze as **demo honesty slide** |
| **Kill** | N/A product — science already KILL on Tobarra KEEP; do not retrain |
| **Rails** | No thr retune per fire |

### S4 — Arrival-time ROS geometry (ops · beyond Lampman MAE claims) (P0 · ops)

| | |
|--|--|
| **Paper** | O’Neill et al. IJWF 2024 — arrival-time raster → ROS = tan(slope)×60 m/min ([PDF](https://www.nwfirescience.org/sites/default/files/publications/WF24067.pdf)); FLAME 3 radiometric TIR ([2412.02831](https://arxiv.org/html/2412.02831v2)); FireCast-Fusion 2026 multi-obj arrival-time ([SRS](https://www.sciencedirect.com/science/article/pii/S2666017226000672)); McFadden FRED multi-pass ([Fire 2024](https://www.mdpi.com/2571-6255/7/6/179)) |
| **Claim** | ROS is **geometry of progression**, not mask IoU; GSD &lt;~2.3 m recommended; revisit ~1 min for slow prescribed ROS |
| **WFD map** | `front_dynamics_v1` / envelope v3 — strengthen arrival-time / normal-ray narrative in demo |
| **Experiment** | On one Tobarra chain with ≥2 timestamps: export arrival-time field + ROS map; compare headline ROS to Vp 7 / AEMET hybrid **without** ML IoU |
| **Kill** | If multi-pass coreg fails (shift &gt; 1 cell) or only 1 usable frame → **document BLOCKED**, not fake ROS |
| **Rails** | Never quote Lampman MAE as Tobarra SLA |

### S5 — EFFIS / FireSpread_MedEU open perimeter benchmark (P0 eng · O2-lite)

| | |
|--|--|
| **Sources** | EFFIS RDA + WFS burnt areas ([data-and-services](https://forest-fire.emergency.copernicus.eu/applications/data-and-services)); FireSpread_MedEU Scientific Data 2026 ([s41597-026-06965-2](https://www.nature.com/articles/s41597-026-06965-2)); TS-SatFire ([s41597-025-06271-3](https://www.nature.com/articles/s41597-025-06271-3)); CFSDS OSF 2025 update |
| **Claim** | Open European multi-day BA progressions + near-RT polygons; caveats (mixed fire types, islands, dates ≠ ignition) |
| **WFD map** | Open perimeter product · Hausdorff-lite · demo third-party honesty |
| **Experiment** | For 1 IF with CEMS pack (e.g. large 2025 ES): pull EFFIS poly + compute area/Hausdorff vs open pack; write scorecard row |
| **Kill** | No temporal overlap or area ratio outside [0.5, 2.0] without note → **INCONCLUSIVE**, not “official validated” |
| **Rails** | Do not claim national cadastre O2 closed |

### S6 — Mediterranean fuel / LFMC hybrid (P1 · physics track)

| | |
|--|--|
| **Paper** | LFMC-SFX Portugal hybrid LSM+RF 2025 ([Springer](https://link.springer.com/article/10.1007/s40808-025-02561-2)); McNorton fuel model ([BG 2024](https://bg.copernicus.org/articles/21/279/2024/)); Mesogeos Med datacube ([Orion](https://orionlab.space.noa.gr/mesogeos/)); FIRE-RES pan-EU fuel map; Di Giuseppe NatComm 2025 fuel &gt; architecture |
| **Claim** | Fuel moisture/load dominates; hybrid &gt; pure DL architecture thrash |
| **WFD map** | `rothermel_lite` / `hybrid_ros_prior` / fuel stack already |
| **Experiment** | Plug AEMET RH/T into FMC proxy for Tobarra envelope; report sensitivity table |
| **Kill** | Envelope head ROS changes &lt;5% vs current with realistic FMC range → **low priority**, no more modules |

### S7 — Uncertainty-aware wildfire danger Med (lab parallel · not mask U-Net)

| | |
|--|--|
| **Paper** | Kondylatos et al. uncertainty-aware Med danger 2025 ([2509.25017](https://arxiv.org/html/2509.25017v1)) — +2.3% F1, −2.1% ECE, reject low-conf |
| **WFD map** | Optional risk layer; **not** substitute for ROS ops |
| **Experiment** | Only if Mesogeos/Iberia grids available offline; 1 fold ECE+reject |
| **Kill** | No local data in 1 week → **SKIP** |

### S8 — Geospatial FM LoRA burn scar (P2 lab · high cost)

| | |
|--|--|
| **Paper** | Prithvi-EO-2.0 ([2412.02732](https://arxiv.org/html/2412.02732v3)); Shibli et al. LoRA GFM wildfire BA ([2605.04989](https://arxiv.org/html/2605.04989v1)) IoU 78.8 with LoRA &lt;1% params; TerraMind ESA Φ-lab 2025 |
| **Claim** | PEFT on GFM beats full FT for continental BA; multi-temporal HLS |
| **WFD map** | Open BA / CEMS complement — **not** CLM drone mask, **not** ROS |
| **Experiment** | Smoke: load Prithvi-EO-2.0 tiny path + 1 Iberian fire S2 pair if GPU; else paper-only citation in Reliability Report |
| **Kill** | No GPU / &gt;2 days setup → **cite only**, no train thrash |

### S9 — RGB–TIR dual-stream detection (P2 · only if RGB exists)

| | |
|--|--|
| **Paper** | Fire-YOLO26 Frontiers 2026 ([fenvs](https://www.frontiersin.org/journals/environmental-science/articles/10.3389/fenvs.2026.1824597/full)); RGBT-3M MDPI 2025; Rajagopal SAR+UAV dual SciRep 2025 |
| **Claim** | Thermal-guided fusion under smoke; Jetson real-time |
| **WFD map** | Upstream mask quality **if** Heligrafics RGB aligned; else skip |
| **Kill** | No paired RGB-TIR in ops packs → **SKIP** |

### S10 — Digital twin light (demo narrative · not retrain)

| | |
|--|--|
| **Sources** | NASA Wildfire DT ([NASA](https://science.nasa.gov/science-research/science-enabling-technology/nasa-wildfire-digital-twin-pioneers-new-ai-models-and-streaming-data-techniques-for-forecasting-fire-and-smoke/)); TEMA Sardinia EU CP; FIRETWIN arXiv 2025 ([2510.18879](https://arxiv.org/html/2510.18879v1)); PiNN Vogiatzoglou ([2406.14591](https://arxiv.org/html/2406.14591v3)) |
| **WFD map** | Commander + Decision Card + envelope = “DT light” pitch for **H1 demo** |
| **Experiment** | 0 code: one-pager mapping our modules to NASA DT minimum (obs state + meteo + short forecast + UQ + GIS) |
| **Kill** | N/A eng — copy only |

---

## Top 4 experiments — **implemented 2026-08-05**

| # | Experiment | Status | Artifact |
|---|------------|--------|----------|
| **1 S1** | SDC proxy ranking bake-off + CRC-lite | **KILL_SDC_PROMOTE** (VAL lift −0.006 &lt; +0.02) → keep **iter1 reject** | `lab_loop_v34_selective_sdc_latest.json` · `iter_20260805_selective_sdc.md` |
| **2 S2** | CRC-lite reject thr (patch, VAL→TEST once) | shipped inside S1 board | same |
| **3 S3** | Multi-pack open Hausdorff-lite board | **BOARD_OK** (6 packs; local open_if, no live EFFIS) | `open_perimeter_attempts/deep_research_s3_board.json` · `OPEN_PERIMETER_S3_BOARD.md` |
| **4 S4** | Arrival-time ROS inventory | **BLOCKED_MULTI_PASS_EXPORT** (code ready, no multi-pass export found) | `deep_research_s4_arrival_ros.json` · `ARRIVAL_TIME_ROS_S4_NOTE.md` |

```powershell
$env:PYTHONPATH = "."
python scripts/run_lab_ml_loop_v34_selective_sdc.py
python scripts/run_deep_research_s3_open_perimeter_board.py
python scripts/run_deep_research_s4_arrival_ros_note.py
pytest tests/test_lab_selective_sdc.py -q
```

**Not on the list:** Tobarra LOFO retrain · ECE temperature thrash · Prithvi full fine-tune · field_ops fusion ON.

---

## Gap vs internal mega-research (what is NEW)

| Already in WFD MDs (2026-07/08) | New emphasis from this expansion |
|--------------------------------|-----------------------------------|
| Lampman TIR-ROS method | O’Neill **arrival-time** ROS math; FLAME 3 radiometric; FireCast multi-obj |
| Orion UQ doctrine | SDC, morphological CP, SHRUG-FM burn-scar selective |
| LOFO Head A / Tobarra hard | Dual LOCO/LOFO papers; LOIO; FireScope-Bench OOD Europe |
| EFFIS A1 idea | FireSpread_MedEU 2026; TS-SatFire multi-task; CFSDS 90 m; NOAA NGFS portal 2026 |
| Fuel Med corpus | LFMC-SFX Portugal; Di Giuseppe fuel&gt;architecture; FIRE-RES map |
| Swin/WFTS notes | Prithvi-EO-2.0 + LoRA BA; TerraMind; progression still hard (F1~0.37) |

---

## Explicit non-goals (align CURRENT_STATE)

- Re-open Tobarra KEEP with init-v21 same recipe  
- Claim IoU (mask) = ROS (m/min)  
- Fit thr/ECE on U1 holdout TEST repeatedly  
- Flip `ml_product_go` or `field_ops.allow_ml_live_in_fusion`  
- Present Lampman MAE / Prithvi IoU as SLA mediterráneo  

---

## Product residual (unchanged)

**Primary product work remains H1 third-party demo + acta → GO_Q.**  
This research feeds **lab experiments + demo honesty slides**, not a retrain month.

---

## Links to prior corpus

| Doc | Role |
|-----|------|
| `docs/MEGA_RESEARCH_MEJORAS_SOTA_2024_2026.md` | Implementable matrix A–E (julio) |
| `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` | Lampman / Orion / RGB-TIR doctrine |
| `docs/fire_intel/LITERATURE_CORPUS_ROS_FUEL.md` | Fuel/ROS Med corpus |
| `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md` | Graph IDs R-* |
| `docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026_claims.json` | 75 verified claims machine |

## How this was produced

```text
node .../deep-research/scripts/run.mjs "<expanded WFD question>"
# → 6 sub-queries · 75 findings · adversarial verify · 0 dropped
python scripts/_parse_deep_research_out.py <harness_log>
# + manual product ranking (synthesis agent returned empty)
```
