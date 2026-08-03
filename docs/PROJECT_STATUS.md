# Project status — WildfireFrontDynamics

> **Updated:** 2026-08-03  
> **HEAD baseline at write:** regenerate with `python scripts/run_plan_cycle.py --execute-m1`  
> **Authority:** live scorecards + this file; archive docs are historical only.

---

## One-line truth

**Engineering is GO. Month/quarter product gates are blocked on external anchors + one third-party demo — not on code quality.**

| Gate | Value |
|------|--------|
| **GO_ENG** | **true** — CI, dual product, Decision Card, demos |
| **GO_MES** | **false** — O1 second anchor OPEN |
| **GO_Q** | **partial** — product stack green; quarter report + external demo pending |
| **ml_product_go** | **false** (U1 TEST honest true; ECE ~0.15) |
| **field_ops live fusion** | **OFF** |
| **Confirmed anchors** | **1** (Tobarra only) |
| **AEMET Tobarra path** | **live** — station 8175 · 2024-08-02 · envelope scorecard **PASS** |
| **PR land stack** | **PR-α** core physics **ready** · **PR-β** envelope+AEMET **ready** · PR-11 optional |

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

- Decision Card CLI + incident outbox + HTTP `/v1/decide`
- Metrics Hub + reliability gate + commander HUD
- Open packs: CEMS + REDIAM AND + RAI EXT + demo multi-CCAA (Tobarra · Níjar · Caminomorisco)
- Piloto honesty card (research_open vs field_ops contrast)
- ML live card demo + U1 honest scorecard rails
- Graph integrity cycles c0–c2 + open-pack honesty (holdout conf cap 0.75)

---

## What is blocked (external / human)

| ID | Blocker | Owner channel | Unlock |
|----|---------|---------------|--------|
| **O1** | 2ª ancla Vp/ha | INFOCAM / CMA (Pablo) | Cardoso (priority) |
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
| Hellín | 16/36 | pending_external | |
| Brazatortas | 8/16 | pending_external | |
| Retuerta | 8/10 | pending_external | QA flag |
| Polán | 0/1 | — | insufficient |
| La Mierla 2026-07 | open pack only | pending_external | press ha only — not EGIF |

---

## Graph engineering (active) — v3

| Workflow | Role | Cadence |
|----------|------|---------|
| **`wfd-fire-intel-scrape`** | Mega-IF ES/FR: X + news + web + EFFIS hints → inventory | **daily/season** |
| `wfd-external-unblock` | Rank O1/O2/outreach next human action | 2–3×/week while blocked |
| `wfd-status-sync` | Refresh PLAN status + hub | weekly / after product commits |
| `wfd-pilot-regression` | Offline pilot + ML card tests | after product edits |
| `wfd-autonomous-cycle` | Honesty/CI/dual integrity | **weekly** |
| `wfd-open-pack-audit` | Open pack claim hygiene | after open pack builder changes |

**Fire intel live:** `data/fire_intel/mega_fires_2026_es_fr.json` · `docs/fire_intel/MEGA_FIRES_2026_ES_FR.md`  
**Do not** promote press ha to confirmed anchors. **Do not** run honesty cycles as main engine while O1 is OPEN.

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
