# Emergency UX industry patterns → WFD OPS

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-11 |
| **Source** | deep-research workflow (nuclear + hospital EMNS) |
| **Runtime** | `wildfire_front/product/app_spa_html.py` |

## What critical environments use

| Domain | Platforms (examples) | Pattern |
|--------|----------------------|---------|
| Nuclear | Everbridge, Alertus, CommanderOne/OmniWarn | Multi-channel notify, NRC-class incident comms, multi-endpoint |
| Hospital | Everbridge, InformaCast, Alertus Healthcare | Panic button, codes to many devices, discrete alerts, role/location targeting |

## Features to preserve (or map)

| Industry capability | WFD mapping |
|---------------------|-------------|
| Multi-channel alert | Out of scope (not mass-notify); honesty chips + Decision Card instead |
| Bidirectional confirm | Toast + copy feedback; status/decide/export as “ack” path |
| Role / location targeting | CLI `--role` · fire picker · work-dir |
| Map + geo awareness | Leaflet map-first ~68% · FIRMS + local front |
| Audit / compliance | Decision Card + `export-acta` · reasons/sources |
| Checklists / action plans | Operator checklist · next_action · intake steps |
| Integrations | `serve-decide` API · CLI surface (Pro mode) |

## Stress UX (copy)

1. **Dual mode** — Fácil default; Pro one click (no feature cut).
2. **Priority first** — 3 primary acts always visible (Estado · Decidir · Acta).
3. **One task** — progressive disclosure (accordion actions, tabs).
4. **Touch ≥48px** · short labels · color-coded GO/HOLD/ABSTAIN.
5. **Defaults** — richest fire auto-selected · rebuild bound to work-dir.
6. **Offline-critical** — static SPA + local GeoJSON layers (tiles need network).

## Honesty rails (never hide)

- Not tactical dispatch  
- field_ops ML fusion OFF  
- NRT hotspot ≠ official perimeter  
- ABSTAIN is product behaviour  

## Open SPA

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front app --fire _sla_measure --open
```
