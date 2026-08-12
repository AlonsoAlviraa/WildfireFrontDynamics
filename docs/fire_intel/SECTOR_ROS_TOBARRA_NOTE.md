# Sector ROS Tobarra — R-B1 note

**As of:** 2026-08-04  
**Graph ID:** R-B1  
**Status:** **EXPORTED** (code path exists; numbers from ops pack — not invented)

## Source

| Path | Role |
|------|------|
| `outputs/observatorio/tobarra_20240802/operational_metrics.json` | `sector_ros` + `short_horizon_envelope` |
| `wildfire_front/emergency_products.py` | `compute_sector_ros` (quartile split) |
| `wildfire_front/sector_ros_local.py` | local normal-ray sectors when samples exist |

## Tobarra 2024-08-02 (pack)

| Sector | ROS (m/min) | Notes |
|--------|------------:|-------|
| **head** | **5.9866** | ≈ P75 bulk / expansion bearing ~234° |
| **flank** | **5.7127** | ≈ primary multi-estimator |
| **rear** | **2.7776** | ≈ P25 |
| **primary** | **5.7127** | structural grade **A** · vs Vp 7 → ratio ~0.82 |

Uncertainty band (ops): p25=2.78 · p75=5.99 · half_iqr≈1.60 m/min (n=5 windows).

Method label (from pack): `bulk_ros_quartile_split` —  
*“ROS por sector (orientativo): cabeza≈P75, flanco≈primaria, cola≈P25. No es despacho táctico validado.”*

## Honesty

- Sector values are **guidance from observed ROS structure**, not independent tactical sensors.
- Envelope 15/30/60 min uses head/flank/rear radii from these ROS; still **not** official perimeter forecast.
- Hellín may show flatter head=flank=rear when only isotropic/area methods fire — do not invent anisotropy.
- Lampman-class papers motivate **directional** reporting; they do **not** validate these m/min as SLA.

## Export checklist (eng)

- [x] Code path in emergency products + local sector module  
- [x] Present on Tobarra `operational_metrics.json`  
- [x] Cited in third-party Reliability Report §2  
- [ ] Optional: copy sector block into every gold pack scorecard UI (hygiene)

## GAP (none for numbers)

No GAP note required for Tobarra: export exists.  
Deferred only: interactive map styling of head/flank/rear arcs in portal (non-blocking).
