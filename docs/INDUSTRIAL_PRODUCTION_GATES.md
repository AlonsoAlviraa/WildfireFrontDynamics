# Industrial production gates (honest definition)

Industrial ≠ “IoU magic”. For this project it means **reproducible products with
measured quality, abstention when uncertain, and dual-track separation**.

## Production products (freeze candidates)

| Product | ID | Gate to ship |
|---------|-----|--------------|
| NDWS global | `ndws_v21` | G0 locked; G1 optional; no silent replace |
| CLM Spain specialist | `clm_v28` | G2 holdout test Δ>0 **and** per-source Δ>0 on ≥2 sources |
| Ops front dynamics | `front_dynamics_v1` | Tobarra A + ratio ∈[0.5,2] + multi-IF packs + no FOV junk |

## Industrial checklist

### A. Reliability
- [ ] `predict_spread.py --list-products` both ready
- [ ] Smoke CLM + NDWS on fixed seed subset
- [ ] Observatorio pack builds for ≥5 IF without crash
- [ ] Retuerta (and similar) cannot report multi-kha garbage without QA flag

### B. Validation honesty
- [ ] O1: multi-anchor or documented BLOCKED with request
- [ ] O2: official Hausdorff or BLOCKED (never KMZ-as-perimeter)
- [ ] G1: GO or NO_GO closed in writing
- [ ] G2: holdout test only; LOFO/per-source table exists

### C. Ops usability
- [ ] CMA technical report (DOCX) + GeoJSON main_front
- [ ] Brief operativo 1 page
- [ ] Kill list enforced in tracker

### D. Engineering hygiene
- [ ] CI tests: product_catalog, hausdorff, core unit
- [ ] Experiment queue with single_change
- [ ] Manifests versioned; weights install script

## Current verdict (update as we go)

See `docs/INDUSTRIAL_READINESS_STATUS.json` (refreshed 2026-08-17 to match the
stamp: GO_MES true, GO_Q partial, fusion ON, RCDA/Caldor not product) and
`docs/PLAN_INDUSTRIAL_GARANTIAS_2026-08-17.md`.

`docs/LOOP_1M_SCORECARD_SNAPSHOT.json` remains a historical month-1 snapshot.
