# Project status — WildfireFrontDynamics

> **Updated:** 2026-08-12  
> **Snapshot 1-page (authority for gates):** `docs/CURRENT_STATE.md`  
> **Goals hub:** `docs/goals/README.md`  
> **SPA / Live Ops:** `docs/APP.md` · `docs/design/LIVE_OPS_DEMO_KERNEL.md`  
> **Grok Bot org:** `docs/EMPRESA_BOTS_TRABAJADORES.md`  
> **HEAD baseline eng:** branch `fix/b2-b3-flags-noise-20260810` (Live Ops + product stack)  
> Archive / residual mes anterior: `docs/PLAN_1_MES_POST_O1_UNLOCK.md`

---

## One-line truth

**GO_MES mínimo true. Cuello de botella: H1 demo a tercero (GO_Q). SPA C2 + Live Ops eng-shipped (`app --demo-day`). ML lab closed W3 MET + Tobarra KILL + FREEZE. Fusion field_ops OFF. `ml_product_go` true solo lab.**

| Gate | Value |
|------|--------|
| **GO_ENG** | **true** — CI, dual product, Decision Card, demos, Live Ops |
| **GO_MES** | **true** — O1∧O4∧P1∧M2∧E1 (plan mínimo); ver `docs/GO_MES_VERDICT.md` |
| **GO_MES+** | **false** — O5 2º grade A / O2 nacional / demo firmada |
| **GO_Q** | **partial** — product stack green; **H1** demo+acta tercero pending |
| **ml_product_go** | **true** (lab; ≠ field fusion) · ML closeout **FREEZE_ML_AND_REQUEST_DATA** |
| **field_ops live fusion** | **OFF** |
| **SPA / Live Ops** | **eng OK** — industrial C2 · `app --demo-day` · residual = H1 human |
| **Confirmed anchors** | **2** (Tobarra + **Hellín** 2024-07-19 Vp=50 m/min) |
| **AEMET Tobarra path** | **live** — station 8175 · 2024-08-02 · envelope scorecard **PASS** |
| **ML mega W3** | **MET** — multi-fire Head A · leak 0 · rails cold |
| **ML Tobarra KEEP** | **KILL** — fresh LOFO IoU **0.4776** · K1 fail vs Head A 0.489 |
| **PR land stack** | fuel PR-α/β ready · SPA audit 10-PR eng residual closed · post–Live Ops: `docs/PLAN_PR_POST_LIVE_OPS.md` |

### Fuel / weather / envelope (Tobarra, 2026-08-03)

| Item | Value |
|------|--------|
| Weather | `source=aemet` · 5.0 m/s · T 27.6 °C · RH 22 % · FMC~6.56 |
| Dir honesty | AEMET `dir=99` (variable) → library 270° fill → `weather_scenario_assumed=true` (partial) |
| Physics head | **6.19 m/min** (raw spatial MED_GRASS; ratio vs obs 1.08 · vs Vp 0.88) |
| Hybrid head | **5.71** obs-locked · primary=head · α≈0.79 |
| Envelope 15' head | **85.65 m** · product `short_horizon_envelope_v3_hybrid` · status `inputs_assumed` |
| Decision Card attach | **weight 0** · fusion stays OFF · incident default still **envelope v2** |
| Scorecard | **PASS** (12 pass / 0 fail) |
| One-shot | `python scripts/run_tobarra_aemet_pipeline.py` (`.env` or cached weather) |
| PR plan | `docs/design/PR_PLAN_FUEL_AEMET_ENVELOPE.md` |
| Key storage | `.env` (gitignored) — never commit |

---

## Product freeze (do not regress without evidence)

| Layer | ID | Honest metric |
|-------|-----|----------------|
| ML lab | `clm_ensemble_v34` | U1 TEST IoU ~**0.86** · sel@80 ~**0.90** · ECE ~**0.15** |
| ML catalog | same | holdout IoU **0.8963** = **provenance only** |
| ML fallback | `clm_v28` | holdout IoU 0.838 |
| ML research | `ndws_v21` | IoU 0.226; G1 **KILL** |
| Ops | `front_dynamics_v1` | Tobarra grade **A**, ROS ~5.71 vs Vp 7 |
| Decision | Decision Card | GO / HOLD / **ABSTAIN** + audit |

Policies: `config/decision_policies.json` — `research_open` fusion experimental ON; **`field_ops` fusion OFF**.

---

## What is done (shippable eng)

- **SPA industrial C2 + Live Ops Kernel (2026-08-11/12)** — `app` / `spa` / `console`; `--serve` + `--demo-day`; primary acts live on `POST /live/v1/*`; docs `docs/APP.md` · design `docs/design/LIVE_OPS_DEMO_KERNEL.md`; tests `make test-spa` + release-flag Live Ops markers
- Decision Card CLI + incident outbox + HTTP `/v1/decide` (+ optional SPA bridge; prefer Live Ops)
- Metrics Hub + reliability gate + commander HUD (**legacy** vs SPA primary)
- Open packs: CEMS + REDIAM AND + RAI EXT + demo multi-CCAA (Tobarra · Níjar · Caminomorisco)
- Piloto honesty card (research_open vs field_ops contrast)
- ML live card demo + U1 honest scorecard rails
- **ML lab product CLI** — `wildfire-front ml list|show|predict|card|doctor|cases|curve|freeze|smoke|lofo|next` (lab · not field_ops fusion · IoU ≠ ROS); entry `docs/ML_PRODUCT_START_HERE.md`
- **ML lab loop closed (2026-08-05)** — freeze **iter1 reject**; W3 **MET**; Tobarra **KILL**; `FREEZE_ML_AND_REQUEST_DATA`
- **Operator UX mode** — plateau eng; residual = **H1 humano** (GO_Q partial)
- Graph integrity cycles c0–c2 + open-pack honesty
- **H1 eng prep** — `scripts/prepare_h1_demo_session.py` · cheatsheet · runbook (no GO_Q invent)
- **Grok Bot company playbook** — `docs/EMPRESA_BOTS_TRABAJADORES.md` (teammates product, not TUI agents)

---

## What is blocked (external / human)

| ID | Blocker | Owner channel | Unlock |
|----|---------|---------------|--------|
| **O1** | ~~2ª ancla~~ **Hellín confirmed** (boletin UNAP 20/07/2024) | INFOCAM / CMA (Pablo) | Optional 3rd (Cardoso Vp) + recompute GO_MES |
| **O2 official** | perímetro nacional | Observatorio / CCAA | SHP/GPKG 1 IF |
| **O5** | 2º grado A | same as O1 | confirmed anchor + criteria |
| **M3.2** | demo con tercero | human calendar | 30 min + 1-page acta |
| **M3.4** | informe trimestre | human write | 8–12 pp |
| **CyL 4082** | wait | transparencia | ~2026-08-17 silence rule |
| **GAL Extinción** | wait / follow-up | Xunta | ~2026-08-01 if silence |
| **Gmail MCP** | OAuth Testing token expired | re-auth `~/.gmail-mcp` | live email sense |

---

## Data inventory (ops)

| Fire | Masks / reproy | Anchor | Notes |
|------|----------------|--------|-------|
| Tobarra | 35/35 | **confirmed** | Gold ops |
| Cardoso 2025 | 79/85 | pending_external | Best 2nd-anchor candidate |
| LA ACOM1 | 181/199 | pending_external | LOFO / holdout val |
| LA ACOM2 | 17/67 | pending_external | partial masks |
| Hellín | 16/36 | **confirmed anchor** (Vp 50; grade **B** ops) | Inventory masks incomplete; O1 PASS · O5 grade A still open |
| Brazatortas | 8/16 | pending_external | |
| Retuerta | 8/10 | pending_external | QA flag |
| Polán | 0/1 | — | insufficient |
| La Mierla 2026-07 | open pack only | pending_external | press ha only — not EGIF |

---

## Graph engineering (active) — **v6.1** (evidence + research-backed)

| Workflow / track | Role | Cadence |
|------------------|------|---------|
| **H1 demo M3.2** (product primary) | Third-party demo + acta → GO_Q | human |
| **E1–E3 evidence stack** | demo pack + Reliability Report + replay one-cmd | eng P0 (72 h) |
| **R-*** research-backed | Lampman/Orion in report; OSS catalog; sector/EFFIS stretch | P0–P2; **0 h ML retrain** |
| `wfd-external-unblock` | Rank **demo** / pack / O2 — not Cardoso-as-O1 | 2–3×/week |
| **`wfd-fire-intel-scrape`** | Mega-IF ES/FR inventory | season |
| `wfd-literature-ingest` | Corpus → update RESEARCH_TO_GRAPH map | on research |
| `wfd-status-sync` | PLAN + hub (2 anchors; GO_MES true) | weekly / after product |
| `wfd-pilot-regression` | Offline pilot + ML card tests | after product edits |
| `wfd-autonomous-cycle` | Honesty/CI/dual integrity | **weekly** (not main engine) |
| `wfd-open-pack-audit` | Open pack + freshness claims | after open builders |
| `wfd-ml-w3-mega-goal` | **CLOSED MET** — re-audit only | archive / smoke |
| `wfd-ml-tobarra-keep-or-kill` | **CLOSED KILL** — re-audit only | archive / smoke |
| Hellín grade A | eng BLOCKED for **O5 only** — not primary | optional |

**Plan implement mes:** `docs/PLAN_1_MES_GRAPH_V6_IMPLEMENT.md`  
**Research → IDs:** `docs/fire_intel/RESEARCH_TO_GRAPH_V6_MAP.md`  
**Sub-ventana:** `docs/PLAN_1_MES_POST_O1_UNLOCK.md`  
**Cycle c5:** `docs/graph_evolution/cycle_c5_graph_v6_implement.md`  
**STATE:** `.grok/graph_engineering/STATE.md` **v6.1**  
**ML goals:** `docs/goals/README.md` · snapshot `docs/CURRENT_STATE.md`

**Do not** promote press/SITAC/Δha to confirmed anchors.  
**GO_MES** plan mínimo is **true** (`docs/GO_MES_VERDICT.md`); **O5 grade A** still open.  
**Do not** single-k calibrate Tobarra 7 ↔ Hellín 50.  
**Do not** retrain ensemble / re-open Tobarra KEEP without new signal.  
**Do not** thrash ECE on same U1 TEST.

Details: `.grok/graph_engineering/STATE.md`, `docs/graph_evolution/`.

---

## Commands (status hygiene)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python scripts/run_plan_cycle.py --execute-m1
python -m pytest tests/test_pilot_honesty_card.py tests/test_ml_live_card_demo.py tests/test_confidence_product.py -q
```

---

## Explicit non-goals (while blocked)

- Retrain ensemble without new non-Cardoso fire patches
- Flip `field_ops.allow_ml_live_in_fusion` without human promote
- Invent Vp/ha or KMZ-as-official-perimeter
- More catalog-pitch doc churn for its own sake
- Re-open Tobarra KEEP with same LOFO recipe after **KILL**
- Treat beats-copy or v29 re-score alone as KEEP
