# Reliability Gate Report — third-party demo pack

> **Not a field unlock key.** Does **not** close GO_Q.
> Eng rehearsal pointer for the H1 12-min demo. Human acta still required.

## Pointers

- Pack: `outputs/demo_third_party`
- Pack reliability JSON: `outputs/demo_third_party/reliability_gate_report.json`
- Suite sample (neutralized, not a field key): `docs/RELIABILITY_GATE_REPORT.json`
- Rehearsal summary: `outputs/demo_third_party/REHEARSAL_SUMMARY.json`

## Pack presence

- pack_ok: `true`
- missing: (none)

## Honesty rails

- `replay_ok` = forensic consistency, **not** third-party authenticity
- A this-run `field_unlock` flag in the pack JSON ≠ GO_Q complete ≠ despacho táctico
- `docs/RELIABILITY_GATE_REPORT.json` is suite-only (`field_unlock=false`)
- GO_Q stays **partial** until a real external demo + signed acta
- Do **not** invent a tercero or pass `ACTA_DEMO_PENDING_HUMAN.md` to record

## Close GO_Q (human only)

```powershell
python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md
```

Exit 0 updates stamp + CURRENT_STATE. Exit 2 = placeholder / PENDING (no mutation).
