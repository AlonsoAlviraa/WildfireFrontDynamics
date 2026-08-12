# EO + LWIR co-located pair inventory (R-B4)

**As of:** 2026-08-04  
**Graph ID:** R-B4  
**Status:** inventory only — **no new network** · honest empty / sparse OK  
**Promote?** lab research only (Fire-YOLO / RoboFireFuseNet class) — **never** mAP-as-ROS  

## Question

Do we have **co-located EO (RGB/visible) + LWIR** frames for the same IF / same pass that could train or evaluate RGB-TIR fusion nets?

## Scan method (eng)

Paths inspected:

| Area | Pattern | Result |
|------|---------|--------|
| `artifacts/*_lwir*` / `*_reprojected_lwir/` | thermal masks & reprojected LWIR | **LWIR-only** sequences (Tobarra, Hellín, Cardoso, La Estrella, …) |
| `data/real_if/` | KMZ/KML/JPG drops | Mixed ops media; **no** systematic EO↔LWIR pair index |
| `data/candidates/` | candidate GeoTIFFs | not dual EO+LWIR pairs |
| `fotosPrueba/` | sample JPG | RGB demo photos — **not** paired LWIR |
| `outputs/*_lwir/` | ingest manifests | LWIR pipeline outputs |
| Contract | `docs/GEOTIFF_INPUT_CONTRACT.md` | platform/sensor fields allow multi-provider; **does not** require EO twin |

## Inventory table

| IF / asset | LWIR path (yes/no) | EO co-located (yes/no) | Pair usable for RGB-TIR? | Notes |
|------------|--------------------|------------------------|--------------------------|-------|
| Tobarra 2024-08-02 | **yes** (`artifacts/tobarra_reprojected_lwir/`, masks) | **no** indexed twin | **no** | Ops ROS grade A from LWIR only |
| Hellín 2024 | **yes** | **no** indexed twin | **no** | Grade B honesty track |
| Cardoso 2025 | **yes** | **no** indexed twin | **no** | |
| La Estrella ACOM1/2 | **yes** | **no** indexed twin | **no** | |
| Brazatortas / Retuerta / Polan | partial LWIR | **no** | **no** | |
| `fotosPrueba/*.jpg` | no | RGB only | **no** | not IF-paired |
| Open CEMS packs | sat delineation (not drone EO+LWIR) | n/a | **no** for RoboFire-class | different modality |
| FIRMS / VIIRS | thermal sat hotspots | no drone EO | **no** | not pair training |

### Summary counts

| Metric | Value |
|--------|------:|
| IF sequences with staged LWIR | ≥6 (see artifacts/) |
| Documented co-located EO+LWIR training pairs | **0** |
| Product path blocked by missing pairs? | **No** — ops product is LWIR ROS + Decision Card |

## Implications

1. **RoboFireFuseNet / Fire-YOLO RGB-TIR** adoption remains **lab backlog** until a partner supplies dual-sensor exports.  
2. Thermal **input contract** (E4) already supports multi-provider LWIR without requiring EO.  
3. Do **not** invent synthetic EO twins from RGB web imagery for metric claims.  
4. If a future drop includes DJI dual (wide+IR) GeoTIFFs, register rows here with paths + CRS + time sync quality.

## Next human/data actions (not eng invent)

- Ask INFOCAM / GEACAM / UAV partners for **same-pass RGB+IR** when available.  
- Prefer sidecar metadata (`platform`, `sensor_id`, time) per `GEOTIFF_INPUT_CONTRACT.md`.  

## Rails

- No network implementation this month  
- No mAP-as-ROS  
- fusion ML-live remains OFF  
