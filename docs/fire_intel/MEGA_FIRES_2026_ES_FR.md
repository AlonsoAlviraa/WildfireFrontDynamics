# WFD mega-fire inventory — normalized 2026-07-29

**As-of:** 2026-07-29 · **Iteration:** 3 · **Tobarra only T4** · **No invented Vp** · **Press ha ≠ official**

**Machine inventory:** [`data/fire_intel/mega_fires_2026_es_fr.json`](../../data/fire_intel/mega_fires_2026_es_fr.json)  
**Schema (gaps vs Tobarra):** [`data/fire_intel/schema_v1.json`](../../data/fire_intel/schema_v1.json)  
**Anchors:** [`data/infocam_anchors.json`](../../data/infocam_anchors.json) · cycle note [`docs/graph_evolution/fire_intel_cycle.md`](../graph_evolution/fire_intel_cycle.md)

## Rules applied this pass

| Rule | Application |
|------|-------------|
| Press ha NEVER → `area_ha_official` | All `area_ha_official: null` |
| `vp_m_min_official` only from explicit parte | All `null` (no m/min parte found) |
| INFOCAM “superficie estimada” | `area_ha_ops_estimate_infocam` only (La Mierla 32k) |
| Merge duplicates | Saumos/Cap Ferret → Gironde; Ávila–Madrid kept **split** + complex band 66–77k |
| CEMS present | max open tier **T2_agency_open** (perimeter **proxy**, not official) |
| Cotignac | T0 → **T1_press** (~2.5–2.7k) |
| Ejulve | press band **~1.4–3k** (late press ~3k) |
| Selas | **~2.8k extinguished** 27 Jul |
| `confirmed` / grade A | requires **T3+** ops parte — not set for any 2026 mega |

## Gold reference (not a 2026 mega)

| Field | Tobarra |
|-------|--------|
| `vp_m_min_official` | **7.0** (ops parte) |
| `area_ha_official` | **39.0** |
| LWIR / masks | 35 / 35 |
| Tier | **T4_gold_stack** |
| `perimeter_official_vector` | false even on Tobarra |

**GO_MES = false** · second O1 confirmed anchor still **OPEN** (Cardoso + La Mierla parte path).

## National context (provisional only)

| Country | Metric | Value | Tier |
|---------|--------|-------|------|
| ES | MITECO avance 1 Jan–19 Jul | ~65.8k forest ha · 21 GIF | T2 PDF |
| ES | Press late Jul (EcoAvant) | **~152.7k ha** · 32 GIF | T1 |
| ES | EFFIS RDA season proxy | **~207k ha** vs LTA ~95k | T2 (not EGIF) |
| FR | Ministry press YTD | **~115k ha** | T1 |
| FR | EFFIS RDA season proxy | **~90.5k ha** vs LTA ~14.8k | T2 |
| FR | Gironde+Landes evac | ~197–250k cumulative | T1 |

National totals are **not** per-fire EGIF / official BA anchors.

## Inventory (14 fires)

| Pri | fire_id | Tier | Press ha | Official Vp/ha | CEMS | Anchor |
|-----|---------|------|----------|----------------|------|--------|
| 1 | `es_gu_la_mierla_20260716` | T2 | ~32k (+INFOCAM est.) | null/null | EMSR898 | `pending_external` |
| 1 | `es_av_burgohondo_202607` | T2 | ~50k (cx 66–77k) | null/null | EMSR900 | `pending_external` |
| 1 | `es_md_sierra_oeste_202607` | T2 | ~19k (16–34k) | null/null | EMSR900 | `pending_external` |
| 1 | `fr_gironde_bordeaux_202607` | T2 | ~42k (CEMS~26k) | null/null | EMSR899 | — |
| 2 | `es_cs_vall_duixo_espadan_202607` | T2 | ~4.3–10k | null/null | EMSR905 | `pending_external` |
| 2 | `fr_landes_biscarrosse_202607` | T2 | ~3.5–3.6k | null/null | EMSR902 | — |
| 2 | `es_to_almorox_202607` | T2 | ~1k | null/null | EMSR900 | — |
| 3 | `es_z_ores_202607` | T2 | ~15.4k | null/null | EMSR896 | — |
| 3 | `es_sg_brieva_202607` | T2 | null (CEMS~2.9k) | null/null | EMSR900 | — |
| 3 | `fr_fontainebleau_20260713` | T2 | ~2k | null/null | EMSR894 | — |
| 4 | `es_gu_selas_202607` | T2 | ~2.8k ext. | null/null | EMSR898 | — |
| 4 | `fr_aude_herault_20260702` | T1 | null | null/null | — | — |
| 5 | `es_te_ejulve_202607` | T1 | ~3k | null/null | — | — |
| 5 | `fr_cotignac_var_202607` | T1 | ~2.5–2.7k | null/null | — | — |

## Top priority IDs

1. `es_gu_la_mierla_20260716` — INFOCAM est. 32k + EMSR898 · second O1 candidate  
2. `es_av_burgohondo_202607` — ~50k press; complex 66–77k · interés nacional  
3. `es_md_sierra_oeste_202607` — merged IF; ~19–34k press · interés nacional  
4. `fr_gironde_bordeaux_202607` — ~42k press; EMSR899 ~26k · ~220k évac  

## Merges

- **Gironde:** Saumos / Cap Ferret sectors → `fr_gironde_bordeaux_202607`
- **Ávila–Madrid–Toledo:** keep split IDs (`burgohondo`, `sierra_oeste`, `almorox`); complex press band **66–77k**; **no double-count**
- **EMSR900 AOIs:** Brieva (SG) ≠ 50k Ávila; La Atalaya = main complex; Villa del Prado = Almorox/Madrid interface

## Press vs CEMS (proxy only)

| Fire | Press ha | CEMS proxy | Comment |
|------|----------|------------|---------|
| La Mierla | ~30–35k | ~25.6–31.8k | Same order; INFOCAM estimada 32k |
| Burgohondo + Sierra Oeste | ~50k + ~19k; cx ~66–77k | EMSR900 max ~54.6k | Split AOIs; date-stamp ha |
| Orés | ~15.4k | GRA ~12.1k | Closed pack, good timeline |
| Gironde / Saumos | ~20–42k | ~26k (26-jul) | Press ahead of CEMS |
| Biscarrosse | ~3.5–3.6k | GRA ~2.7k | Consistent scale |
| Selas | ~2.8k | GRA ~2.5k | Extinguished 27 Jul |

## Gaps vs Tobarra (everywhere except gold)

`vp_m_min_official`, `area_ha_official`, `intensity_behavior` (parte), `lwir_geotiff_seq`, `masks`, `perimeter_official_vector`

## Promotion / GO

- Max open tier: **T2_agency_open** (CEMS/EFFIS)
- **confirmed / grade A** requires T3+ ops parte
- INFOCAM *estimada* ≠ `area_ha_official`
- **GO_MES = false** (second O1 anchor OPEN)
- Never fill `vp_m_min_official` without explicit ops parte quote (m/min)

## CEMS open packs (proxy only)

| EMSR | Fires | Priority |
|------|-------|----------|
| **898** | La Mierla + Selas | 1 |
| **900** | Burgohondo / Sierra Oeste / Almorox / Brieva | 1 |
| **899** | Gironde (Saumos sector) | 1 |
| **902** | Biscarrosse | 2 |
| **905** | Vall d’Uixó / Espadán | 2 |
| **896** | Orés (closed) | 3 |
| **894** | Fontainebleau | 3 |

```bash
python scripts/build_open_if_pack.py --activation EMSR898
python scripts/build_open_if_pack.py --activation EMSR900
python scripts/build_open_if_pack.py --activation EMSR899
```

If HTML scrape is empty, use API:

`https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/?code=EMSR###`

Also: set `outputs/open_if/la_mierla_20260717/cems_watch.json` → **EMSR898** (stale “no EMSR” claim from 2026-07-21).

## Anchor stubs (ES priority 1) — status check

| fire_id | anchor key | status | `area_ha` | `vp_m_min` | press provisional |
|---------|------------|--------|-----------|------------|-------------------|
| `es_gu_la_mierla_20260716` | `guadalajara_la_mierla_20260717` | **pending_external** | null | null | 32k (INFOCAM est.) |
| `es_av_burgohondo_202607` | `avila_burgohondo_202607` | **pending_external** | null | null | ~50k |
| `es_md_sierra_oeste_202607` | `madrid_sierra_oeste_202607` | **pending_external** | null | null | ~19k |

No new Pri-1 ES stubs needed this cycle. **Do not set `confirmed`.**

## Priority scrape queue (human / parte)

1. **La Mierla** — INFOCAM / EGIF closed ha + Vp m/min  
2. **Cardoso** — existing external-unblock (O1 second anchor path)  
3. **Burgohondo** — Junta CyL / INFOCAL parte ha  
4. **Sierra Oeste** — CM ASEM final perimeter ha (reconcile 19k vs 34k)  
5. **Orés** — Gobierno de Aragón final ha  
6. **Gironde** — préfecture 33 / SDIS final ha  

## Summary

Normalized **14** ES/FR mega-fires. Tobarra remains only T4 gold (Vp **7.0**, ha **39**). All mega entries keep `area_ha_official` and `vp_m_min_official` **null**; press ha provisional only. Merged Saumos into Gironde; kept Ávila–Madrid split with complex **66–77k** band. Cotignac T0→T1 (~2.7k); Ejulve press ~3k; Selas ~2.8k extinguished. CEMS 898/900/899/902/896/894/905 enable **T2 open perimeter proxy only**. **GO_MES false** — second confirmed O1 anchor still open.

## Next action

Build CEMS open_if packs (898/900/899) + human/parte path for La Mierla & Cardoso Vp/ha. Never promote press ROS → `vp_m_min_official`.
