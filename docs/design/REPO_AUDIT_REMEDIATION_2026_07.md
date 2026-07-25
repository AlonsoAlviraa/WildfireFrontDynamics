# Repo audit remediation — 2026-07-24

| Campo | Valor |
|-------|--------|
| **Scope** | Full Python health + honesty/security correctness |
| **Automated** | ruff ✅ · pytest (not slow/weights) ✅ · mypy local 2 errs (geometry Transformer) |
| **Manual** | explore audits on `wildfire_front/` + `scripts/`/`tests/` |

## Priority batches

### Batch A — P0 honesty / security (this implement)

| ID | Area | Fix |
|----|------|-----|
| A1 | `progressive_burn/geometry.py` | Type-safe optional `Transformer` for mypy |
| A2 | HTTP decide | Reject inline `ops_metrics`/`open_metrics` on `http_api` (file packs only) |
| A3 | `score_ops_source` | Require finite positive ROS for `available=True` |
| A4 | incident reliability | `ros_ok` requires `ros > 0` (not `>= 0`) |
| A5 | `_normalize_ml_live_payload` | Never invent `schema: ml_live_metrics_v1` |
| A6 | `load_infocam_anchor` | Fail closed on path not allowed (no arbitrary FS) |
| A7 | promote | Refuse primary IoU ≈ catalog 0.8963 |
| A8 | verify AND | Require explicit `vp_invented is False` |
| A9 | verify EXT | Report `honest.*` from pack results, not hardcode True |
| A10 | ensemble temps | Raise on length mismatch (no silent drop) |
| A11 | U1 fallback | `u1_test_honest` / fusion recommended default **False** |
| A12 | industrial open honesty | Missing `vp_invented` → treat as incomplete / not false-claim |

### Batch B — P1 product honesty (implement 2026-07-25) ✅

| ID | Status | Fix |
|----|--------|-----|
| B1 | ✅ | `enrich_ops_dict(cn_hybrid=False)`; no invent 270° wind; hybrid only with explicit `wind_from_deg` |
| B2 | ✅ | PSB `to_observations` sanitized summary (`vp_tactical=null`, proxy flags, no raw FD primary_ros) |
| B3 | ✅ | open_if pack: ha/day + `ros_is_proxy`; drop unflagged m/min; promote catalog IoU 0.8963 refuse solid |
| B4 | ✅ | DEM `np.gradient` scaled by resolution_m/transform; unaligned multi-frame refuse (opt-in crop) |
| B5 | ✅ | demo multi-CCAA load U1 via `load_u1_honesty_snapshot`; portal i18n nav/CTA/sections; run_mvp → pytest |
| extra | ✅ | `predict_spread` exit 2 if uncertainty API missing; `geojson_to_geom` union/last not first-only |

### Batch C — DX / polish (partially covered with B5)

- demo multi-CCAA load scorecard live ✅  
- portal i18n complete ✅  
- run_mvp.cmd → pytest ✅  

## Non-goals this batch

- Full rewrite of ML training alignment  
- field_ops fusion ON  
- Retrain  

## PR Plan

1. **PR-A:** Batch A fixes + tests  
2. **PR-B:** Batch B (separate)  
3. **PR-C:** DX polish  
