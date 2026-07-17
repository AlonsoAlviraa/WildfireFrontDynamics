# Design — dNBR / STAC post-fire for open IF packs (M2.3)

> Loop-engineering · 2026-07-17  
> Plan: *dNBR/STAC opcional post-fuego 1 pack — layer o BLOCKED doc*

---

## Goal

Add an optional **post-fire severity proxy** (dNBR from Sentinel-2 L2A via STAC) to one open CEMS pack, with honest provenance. Not a national official perimeter.

## Approach

1. Bbox from pack `timeline_perimeters.geojson` (or largest product).  
2. STAC search (Element84 Earth Search) for `sentinel-2-l2a` pre/post windows.  
3. Windowed COG read of NIR (B08) + SWIR (B12) — no full-scene download.  
4. Compute NBR, dNBR, severity class fractions (USGS-style bins).  
5. Write pack artifacts; on network/STAC failure → `dnbr_status.json` **BLOCKED** (still DONE for plan).

## Formulas

```
NBR  = (NIR - SWIR) / (NIR + SWIR)
dNBR = NBR_pre - NBR_post
```

Severity bins (dNBR): unburned &lt;0.1 · low 0.1–0.27 · mod-low 0.27–0.44 · mod-high 0.44–0.66 · high ≥0.66.

## Non-goals

- Full BA mask product at 10 m national scale  
- Official cadastre replacement  
- Requires paid APIs  

## Artifacts (per pack)

| File | Content |
|------|---------|
| `dnbr_summary.json` | stats + severity fractions + STAC item ids |
| `dnbr_stac_items.json` | pre/post item metadata + asset hrefs |
| `dnbr_preview.tif` | optional small float32 dNBR window |
| `dnbr_status.json` | GO / PARTIAL / BLOCKED + reasons |
| `dnbr_layer.md` | human brief + disclaimers |

## Tests

- Pure numpy NBR/dNBR + bins (no network)  
- Bbox extraction from synthetic FC  
- Optional live STAC smoke (skip if offline)
