# Emergency product status (lives first)

**Updated:** 2026-07-16  
**Unified launch:**  
```bash
python scripts/emergency_briefing.py --fires tobarra_20240802,cardoso_2025
python scripts/smoke_emergency_products.py
```

## G1 / NDWS closed

| Run | Verdict |
|-----|---------|
| v27b T=3 IoU 0.2249 Δ+0.0751 | **NO_PROMOTE → KILL** (`docs/archive/G1_KILL_FEATURES_TEMPORAL.json`) |
| Emergency ML primary | **`clm_v28`** |
| NDWS | research baseline only |

## Shippable artifacts (per pack)

| File | Role |
|------|------|
| `emergency_briefing.md` | Human brief: grade, ROS, sectors, 15/30/60, blocked items |
| `emergency_envelope.json` | Sector-aware numeric envelope |
| `emergency_envelope_guidance.geojson` | **GIS rings/wedges** (extrapolated guidance, NOT official perimeter) |
| `operational_metrics.json` | Full ops metrics + sector_ros |
| `main_front.geojson` | Observed front |

## Multi-IF briefing

Default fires: Tobarra + Cardoso. Also works with hellin/brazatortas packs when present.

GIS features properties always include:
- `not_official_perimeter: true`
- `not_tactical_dispatch: true`
- sector: `flank_isotropic` | `head` | `rear`

## Explicitly blocked

- Multi-IF anchors without external Vp/ha  
- Official Hausdorff without official GeoJSON  
- Validated tactical dispatch  
- NDWS as emergency “best model”
