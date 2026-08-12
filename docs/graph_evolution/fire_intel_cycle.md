# Fire intel cycle — 2026-07-29 (iter 3)

**Stack:** lanes `spain_news_web` · `france_news_web` · `x_twitter` · `satellite_open` → inventory normalize → write agent  
**Artifacts:** `data/fire_intel/mega_fires_2026_es_fr.json` · `docs/fire_intel/MEGA_FIRES_2026_ES_FR.md` · `data/infocam_anchors.json` (stubs only)

## Result

| Item | Value |
|------|-------|
| Fires inventoried | **14** ES/FR (max 20) |
| Max open tier | **T2_agency_open** |
| Tobarra | only **T4** / grade A gold |
| `vp_m_min_official` mega | all **null** (no invent) |
| `area_ha_official` mega | all **null** |
| GO_MES | **false** — second O1 OPEN |
| CEMS packs ready | EMSR **898 / 900 / 899** (pri 1) |

## Anchor honesty

Pri-1 ES stubs already present as **`pending_external`** (La Mierla, Burgohondo, Sierra Oeste).  
Refreshed provisional press notes only — **no `confirmed`**, **no invented Vp**.

## Next

```bash
python scripts/build_open_if_pack.py --activation EMSR898
python scripts/build_open_if_pack.py --activation EMSR900
python scripts/build_open_if_pack.py --activation EMSR899
```

Human O1: Cardoso + La Mierla Vp/ha (INFOCAM/CMA parte). Update `la_mierla` `cems_watch` → EMSR898.
