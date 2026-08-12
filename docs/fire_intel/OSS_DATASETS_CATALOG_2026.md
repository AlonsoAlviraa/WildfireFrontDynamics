# OSS + datasets catalog 2026 (R-DATA1 / I5)

**As of:** 2026-08-04  
**Graph IDs:** R-DATA1 · I5  
**Rule:** catalog only — **promote?** = never | lab | ops-prior. No silent product promote.

| Name | URL | Role in WFD | Promote? |
|------|-----|-------------|----------|
| **ELMFIRE** | https://github.com/lautenberger/elmfire · https://elmfire.io | Landscape level-set ROS sim; **R-SIM1** compare-only vs Tobarra ROS (spike) | **lab** (compare) — never tactical dispatch |
| **ForeFire** | https://github.com/forefireAPI/forefire | C++ ROS / coupled fire–atm (FIRE-RES D5.3); baseline physics ROS | **lab** (compare) |
| **TS-SatFire** | search: TS-SatFire satellite wildfire dataset (literature 2024–26) | Satellite fire time-series for open/ML transfer studies | **lab** — never field ROS |
| **BCWildfire** | BC Wildfire Open Data / Canadian provincial portals (varies by year) | Extra open perimeter/ha context outside ES | **lab** / open hygiene |
| **Orion UQ** | https://github.com/Orion-AI-Lab/uncertainty-wildfires · arXiv:2509.25017 | Epistemic+aleatory UQ → **GO/HOLD/ABSTAIN** rails (R-UQ1); not EVAC labels | **ops-prior** (rails only) — model weights **lab** |
| **RoboFireFuseNet** | https://github.com/dimfot3/RoboFireFuseNet | RGB+IR attention seg (smoke+flame); upstream mask if EO+LWIR | **lab** — never mAP-as-ROS |
| **NDWS** | Next-Day Wildfire Spread (Kaggle / public) | Historical ML path; G1 killed as primary | **never** (primary product) · archive lab only |
| **WildfireSpreadTS** | WildfireSpreadTS multi-day spread benchmarks (literature) | Multi-day mask / growth research (R-C1 frozen this month) | **lab** · retrain **frozen** mes |
| **EFFIS / CEMS** | https://forest-fire.emergency.copernicus.eu/ · https://mapping.emergency.copernicus.eu/ | Open perimeters, BA, FWI; Pista B packs `outputs/open_if/emsr*` | **ops-prior** (open perimeter layer) — not national cadastre O2 |
| **FIRMS** | https://firms.modaps.eosdis.nasa.gov/ | Hotspots MODIS/VIIRS; direction overlay scripts | **ops-prior** (context) — not LWIR ROS |
| **Pyronear** | https://github.com/pyronear | Open smoke detection / alert stack | **lab** / partner note (R-OSS1) |
| **FEDS** | Fire Event Data Suite (literature / NASA-related open fire events) | Event compilation for open intel | **lab** |
| **FlamMap / FARSITE family** | USFS landscape fire behavior tools | Reference sim language; not WFD runtime | **never** as WFD product core |
| **FLAME / FLAME2/3** | UAV visual+TIR datasets (literature) | Eval masks / detection bench | **lab** |
| **REDIAM Andalucía** | WFS perímetros IIFF (see OPEN_RESOURCES_CATALOG) | Multi-CCAA official-lite perimeters | **ops-prior** (open) — not CLM O2 |
| **NASA FIRMS + CEMS in-repo** | `scripts/fetch_firms_hotspots.py`, open_if builders | Already integrated open path | **ops-prior** (open) |

## Promote legend

| Tag | Meaning |
|-----|---------|
| **never** | Do not promote to field_ops product or GO claims |
| **lab** | Research / spike / compare OK; not sala dispatch |
| **ops-prior** | May inform rails, open layer, or hygiene — still not invent Vp |

## R-OSS1 — Pyronear / FEDS / FlamMap short inventory

Extended inventory for Graph **R-OSS1** (2026-08-04). Catalog only — no install, no promote.

| Name | What it is | Public entry | WFD role | Promote? | Action this month |
|------|------------|--------------|----------|----------|-------------------|
| **Pyronear** | Open-source smoke detection / wildfire alert stack (cameras + models + ops tooling community) | https://github.com/pyronear | Upstream **detection** layer (pre-ROS); partner narrative for early warning | **lab** / partner note | Watch releases; no fork into field_ops ROS |
| **FEDS** (Fire Event Data Suite) | Compilation / suite of fire event datasets (NASA-related open fire events literature & portals; naming varies by release year) | search: “Fire Event Data Suite” / NASA fire events open data | Event-level open intel for pack hygiene & multi-IF context | **lab** | Optional row when a stable DOI/URL is pinned; do not invent coverage for ES IFs |
| **FlamMap** | USFS landscape fire behavior mapping (static weather scenarios, multi-fuel) | USFS fire behavior tools family (FlamMap / related) | Reference **language** for fuel/ROS behavior maps; not a WFD runtime | **never** as WFD core | Cite only when comparing sim vocabulary |
| **FARSITE** (family) | Spatially/temporally explicit fire growth (related USFS lineage) | USFS docs / legacy distributions | Same family as FlamMap — growth sim reference | **never** as WFD core | Lab compare only if someone runs offline |
| **ELMFIRE** | Level-set landscape ROS sim | https://github.com/lautenberger/elmfire | **R-SIM1** compare vs Tobarra ops ROS | **lab** (compare) | See `ELMFIRE_FOREFIRE_SPIKE_NOTE.md` |
| **ForeFire** | C++ fire spread / coupled tools | https://github.com/forefireAPI/forefire | **R-SIM1** physics baseline | **lab** (compare) | Same spike note |

### R-OSS1 honesty

- Pyronear ≠ LWIR front ROS product.  
- FEDS ≠ Spanish national perimeter O2.  
- FlamMap/FARSITE/ELMFIRE/ForeFire ≠ sala Decision Card engine.  
- Spike note: `docs/fire_intel/ELMFIRE_FOREFIRE_SPIKE_NOTE.md`.

## WFD dual-product reminder

```text
Ops TIR medido  +  open CEMS/EFFIS  +  card UQ (Orion rails)
  ≠  ELMFIRE/ForeFire as field product
  ≠  NDWS/WFTS retrain this month
  ≠  IoU catalog as ROS
```

## Related

- `docs/OPEN_RESOURCES_CATALOG.md` — broader open resources  
- `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md` — adoption doctrine  
- `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md` — industry/OSS narrative  
- `docs/fire_intel/ELMFIRE_FOREFIRE_SPIKE_NOTE.md` — R-SIM1  
- `docs/fire_intel/CN_RESEARCH_LAB_ONLY.md` — R-CN1 never-promote  

