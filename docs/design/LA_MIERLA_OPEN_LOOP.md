# Design — La Mierla open intake loop (2026-07)

## Goal

Produce **everything possible** for IF `guadalajara_la_mierla_20260717` from **open sources only** (FIRMS + press/X metadata). No LWIR claimed as ROS.

## Non-goals

- Official perimeter O2 GO
- Confirmed INFOCAM Vp/ha
- Drone thermal incident ROS
- ML retrain on this IF

## Deliverables

| Artifact | Path |
|----------|------|
| Open pack | `outputs/open_if/la_mierla_20260717/` |
| FIRMS layer | pack + `outputs/firms/...` |
| Scorecard open | `scorecard_pista_b.json` (open-only fields) |
| Operator brief | `operator_brief_open_if.md` |
| Map HTML | `map.html` |
| Anchor stub | `data/infocam_anchors.json` pending_external |
| Scrape log | `docs/open_if_intake/GUADALAJARA_LA_MIERLA_20260717.md` |

## Pipeline steps

1. Scrape latest press + X official
2. Download FIRMS Europe 24h, filter bbox Sierra Norte GU
3. Convex hull of hotspots → **indicative** footprint (not official perimeter)
4. Manifest + scorecard + brief + map
5. Optional: decide CLI with open_metrics only (ABSTAIN expected)

## Honesty labels

All vectors: `not_official_perimeter: true`, `source: firms_nrt_proxy`.

## Evidence (loop closed 2026-07-21)

| Step | Result |
|------|--------|
| Design | this doc |
| Scrape X primary | INFOCAM 29k ha est., 34+14 mun., Nivel 2, 72/394 medios |
| FIRMS NRT | **595** hotspots; hull ~**39 980 ha** (proxy) |
| Open pack | `outputs/open_if/la_mierla_20260717/` |
| Decide field_ops / research_open | **HOLD** (missing ml+ops; open_only_monitoring) |
| Anchor | `pending_external` in `data/infocam_anchors.json` |
| Blocked | LWIR, official perimeter EGIF, confirmed Vp/ha |

### Regenerate

```bash
python scripts/build_la_mierla_open_pack.py
PYTHONPATH=. python -m wildfire_front.cli decide \
  --event-id guadalajara_la_mierla_20260717 \
  --open-pack outputs/open_if/la_mierla_20260717 \
  --policy field_ops \
  --output outputs/open_if/la_mierla_20260717/fire_decision_card_field_ops.json
```
