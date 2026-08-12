# ELMFIRE / ForeFire spike note (R-SIM1)

**As of:** 2026-08-04  
**Graph ID:** R-SIM1  
**Status:** SPIKE NOTE only — **no install required** · **no product claim**  
**Promote?** lab (compare) — never tactical dispatch  

## Purpose

Document **how** to compare landscape fire-spread simulators (ELMFIRE, ForeFire) against **observed Tobarra ops ROS** later. This note does **not**:

- install or vendor ELMFIRE/ForeFire binaries  
- claim WFD field_ops uses level-set / Rothermel engines for dispatch  
- invent simulated m/min as anchors or Vp  

## Catalog links (OSS)

| Tool | URL | Catalog row |
|------|-----|-------------|
| **ELMFIRE** | https://github.com/lautenberger/elmfire · https://elmfire.io | `docs/fire_intel/OSS_DATASETS_CATALOG_2026.md` |
| **ForeFire** | https://github.com/forefireAPI/forefire | same catalog |
| **FlamMap / FARSITE family** | USFS landscape tools (reference language) | same catalog · **never** WFD product core |

Also: `docs/fire_intel/INDUSTRY_RESEARCH_2024_2026_CONGRESOS_FERIAS_OSS.md` § OSS; `docs/fire_intel/SOTA_STACK_ADOPTION_2026.md`.

## Tobarra observed baseline (already in repo — not invented)

| Quantity | Value | Source |
|----------|------:|--------|
| primary ROS | **5.71 m/min** | Tobarra ops / Metrics Hub / demo pack |
| head / flank / rear | 5.99 / 5.71 / 2.78 m/min | `docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md` |
| grade | A structural | INFOCAM-anchored ops pack |
| Vp ref (anchor) | 7 m/min | `data/infocam_anchors.json` — **not** sim output |
| ratio vs Vp | ~0.82 | observed / anchor |

These numbers are **ops thermal front** products. ELMFIRE/ForeFire would produce a **different** quantity class (fuel+weather+DEM driven spread).

## Compare protocol (when human installs tools)

1. **Domain:** clip fuel/DEM/weather to Tobarra AOI (see `outputs/fuel_stack/tobarra/`).  
2. **Ignition:** use first LWIR mask centroid / ops perimeter start — do not invent ignition time.  
3. **Run window:** align to Tobarra multi-frame window (see observatorio pack timestamps).  
4. **Metrics (lab only):**
   - ROS bulk (m/min) sim vs ops primary  
   - optional area growth ha/h (proxy) vs ops area curve  
   - **do not** map sim ROS → Decision Card GO without new rails  
5. **Report template:** table `sim_ros_m_min | ops_ros_m_min | ratio | notes` + fuel/weather provenance.  
6. **Fail closed:** missing fuel or weather → **ABSTAIN compare**, write GAP, no fake numbers.

### Suggested command sketch (not executed this run)

```text
# ELMFIRE — landscape level-set (see elmfire docs for inputs)
# ForeFire — C++ ROS / coupled fire-atmosphere (FIRE-RES D5.3 context)

# WFD side (already available):
#   outputs/observatorio/tobarra_20240802/operational_metrics.json
#   docs/fire_intel/SECTOR_ROS_TOBARRA_NOTE.md
```

## What “success” looks like for R-SIM1

| Outcome | Meaning |
|---------|---------|
| Note + catalog link | **DONE** (this file) |
| Optional later: one offline sim table vs Tobarra | stretch lab |
| Product claim “WFD uses ELMFIRE in sala” | **FORBIDDEN** |

## Rails

- Spike ≠ tactical  
- No GO_Q from sim  
- No fusion ON  
- No invent Vp from sim head  
- IoU catalog still ≠ ROS  

## Related

- R-B1 sector ROS Tobarra note  
- R-DATA1 / I5 OSS catalog  
- Reliability Report § research (Lampman method; sim not SLA)  
