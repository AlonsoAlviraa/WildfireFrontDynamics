# CURRENT_STATE snapshot — 2026-08-12 (Europe/Madrid)

> **Historical snapshot** (pre human fusion promote). Living SSOT: `docs/CURRENT_STATE.md` — field_ops ML fusion **ON** as of 2026-08-13 (cap 0.20 / abstain 0.45) ≠ GO_Q complete ≠ despacho.

Companion to `docs/CURRENT_STATE.md` on main. Honest ops snapshot after P0 eng close + SPA land attempt.

## One-line truth

**GO_MES true · GO_Q partial (H1 third-party acta) · ml_product_go true (lab only) · field_ops ML fusion OFF · FREEZE_ML_AND_REQUEST_DATA · SPA land via clean PR #19 (supersedes #10).**

## Done today (merged to main)

| PR | Topic | Note |
|----|--------|------|
| #11 | CLI opaque errors → exit 2 | shipped |
| #13 | `docs/CURRENT_STATE.md` SSOT | shipped |
| #14 | PII scrub + anti-reentry `.gitignore` | shipped |
| #15 | ONEPAGER quarantine; VENTA_GO ≠ GO_Q | shipped |
| #16 | PILOT/ACTA/pitch honesty | shipped |
| #17 | Hellín SSOT pending + DATA_INTAKE honesty | shipped |
| #18 | Operator hub (replaces dirty #12) | shipped |
| #12 | closed | superseded by #18 |

## In flight / hold

| Item | State |
|------|--------|
| **#19** SPA Live Ops on clean main | open — supersedes #10; wait CI green then merge |
| **#10** SPA on secret-bearing base | **DO NOT MERGE** — comment supersede → #19 |
| Cloud agents (Cursor) | blocked until Alonso reconnects GitHub in Cursor |

## Gates (unchanged rails)

| Gate | Value |
|------|--------|
| GO_MES | true |
| ml_product_go | true (lab ≠ field) |
| field_ops ML fusion | **OFF** |
| GO_Q | **partial** until third-party demo + signed acta |
| GO_MES+ | false |
| FREEZE_ML_AND_REQUEST_DATA | active |

## Human-only open

1. Agenda H1 third-party + signed acta (`go_q_met` stays false until then).
2. Rotate historical activation tokens **outside git**.
3. Hellín: keep `pending_external` until cite + Alonso promote.
4. Marketing outbound embargado until Claims Guardian clear.
5. Reconnect GitHub in Cursor (cloud agents).
6. Delete empty sidebar “New Bot” if still present.

## Explicit non-claims

- Not tactical dispatch.
- Not fusion ON / not GO_Q complete / not invent metrics.
- Not merge of `fix/b2-b3-flags-noise*` into main.
