# AND Industrial E2E Verification — REDIAM Andalucía

**Verdict:** `GO_AND_INDUSTRIAL_E2E`  
**Started:** 2026-07-22T08:44:29.447959+00:00  
**Finished:** 2026-07-22T08:44:29.449964+00:00  
**Attribution:** Fuente: REDIAM — Junta de Andalucía

## Layer contract

| Layer | Pass |
|-------|------|
| `rediam_perimeter_present` | PASS |
| `inventory_catalog` | PASS |
| `gold_selection` | PASS |
| `pack_manifest` | PASS |
| `metrics_o2` | PASS |
| `scorecard_go_or_partial` | PASS |
| `map_html` | PASS |
| `provenance_attribution` | PASS |
| `pytest_and_smoke` | PASS |
| `honest_gates` | PASS |

Layers pass: **10/10**

## Selection

- Catalog n: 189
- Gold: ['2024040053']
- Silver n: 2

## Packs

- `and_2024040053_20240606` · verdict=GO_OPEN_AND_O2 · ha=2169.34 · firms=85 · dnbr=GO · score=8/8
- `and_2024140035_20240712` · verdict=PARTIAL · ha=2095.86 · firms=0 · dnbr=SKIP · score=8/8
- `and_iiff2025040059_20250828` · verdict=PARTIAL · ha=909.99 · firms=0 · dnbr=SKIP · score=8/8

## WFS cache years
- ['2022', '2023', '2024', '2025']

## Live WFS
- attempted: False
- ok: None

## Steps

- **inventory_catalog**: PASS
- **wfs_cache**: PASS
- **live_wfs_smoke**: SKIP
- **and_packs**: PASS
- **honest_gates**: PASS
- **pytest_and_smoke**: SKIP

## Honest constraints

- No invented Vp / tactical ROS
- FIRMS hull ≠ official burned area
- REDIAM / Junta de Andalucía attributed
- Field decision HOLD without ASEMA anchor

## Relation to gold dual stack

| Track | Champion |
|-------|----------|
| OPS | Tobarra 2024-08-02 (LWIR + Vp) |
| OPEN CEMS | EMSR578 |
| OPEN O2 CCAA | AND REDIAM gold (this acta) |

_Schema: `and_industrial_e2e_verification_v1`_
