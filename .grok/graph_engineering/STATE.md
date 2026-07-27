# Graph Engineering — Estado actual

| Campo | Valor |
|-------|--------|
| **Mode** | Fully Autonomous Graph Engineering |
| **Active graph** | `wfd-autonomous-cycle` v1 |
| **Secondary graph** | `wfd-pilot-regression` v1 (validated, queued after post-fix re-run) |
| **Cycle** | c0-bootstrap **SYNTHESIZED** → next: `fix_confirmed_locally` |
| **Workflow handle** | `wfd-autonomous-cycle` |
| **HEAD** | `ba01ee2` |
| **Scheduler** | task `019fa3f50f7c` every **2h** durable continuation |
| **Last CI known** | `907366d` green; later docs/chore commits on main |
| **Human gates** | none |
| **Hard rails** | no invent ROS; field_ops fusion OFF; dual product honesty |

## Topology v1

```
Sense → parallel(ScanHonesty, ScanCI, ScanDualProduct)
      → Verify(max 6 adversarial)
      → Synthesize(report + next_action)
```

## Artifacts

- `.grok/workflows/wfd-autonomous-cycle.rhai`
- `.grok/workflows/wfd-pilot-regression.rhai`
- `docs/graph_evolution/graph_evolution.md`
- `docs/graph_evolution/cycle_c0_local_sense.md`
- `docs/graph_evolution/cycle_c0_bootstrap.md` ← c0 synth report

## Decision policy (autonomous)

| Condition | Action |
|-----------|--------|
| confirmed findings > 0 | fix locally if safe (format/lint/docs honesty); re-run cycle |
| empty confirmed | run pilot-regression graph |
| 2× empty | evolve graph v2 (add open-pack-audit node) |
| CI red | prioritize format/lint fix graph only |

## c0-bootstrap result

| Check | Value |
|-------|--------|
| HEAD | `ba01ee2` |
| confirmed_count | **5** |
| next_action | **fix_confirmed_locally** |
| top bug | `HR-field-ops-cli-or` (clamp field_ops fusion OR) |
| u1_test_honest | true |
| ml_product_go | false |
| allow_ml_live_in_fusion_recommended | true |
| model_iou | ~0.857 |
| ece_patch_conf | ~0.153 |
| field_ops.allow_ml_live_in_fusion | **false** (catalog; runtime gap open) |
| research_open.allow_ml_live_in_fusion | true (experimental, pending_signoff) |
| ruff format | pass |
