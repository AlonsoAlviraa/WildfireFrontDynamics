# Design — Forensic acta + radio-bridge + replay (M2.9)

> Loop-engineering · 2026-07-17  
> **Dream row:** SUENOS §3.1 Replay forense · radio-bridge · export legal (acta)

---

## Problem

La Decision Card existe (CLI, outbox, API) pero el valor de **auditoría/pago** pide:

1. Texto corto para mando (tablet/radio)  
2. Acta de 1 página con hashes  
3. Poder **reconstruir** la decisión con los mismos inputs y verificar `output_hash`

## Decision

| Piece | Format | Notes |
|-------|--------|-------|
| Radio-bridge | `fire_decision_radio.txt` | ≤ 280 chars ES, sin markdown |
| Acta | `fire_decision_acta.md` | 1 página: decisión, fuentes, hashes, disclaimers |
| Bundle | `forensic_bundle/` or dir | card JSON + radio + acta + `forensic_manifest.json` |
| Replay | `wildfire-front replay-decide` | re-build from sources snapshot; compare hashes |
| PDF/DOCX | **out of scope** | MD is legal-export MVP (no new deps) |

## Replay contract

Store in bundle:

```json
{
  "schema": "forensic_replay_sources_v1",
  "event_id": "...",
  "require_ops_for_go": true,
  "ml_metrics": {...}|null,
  "ops_metrics": {...}|null,
  "open_metrics": {...}|null,
  "expected_output_hash": "...",
  "expected_decision": "GO|HOLD|ABSTAIN"
}
```

Replay rebuilds card with same metrics → must match `output_hash` and `decision`.

## Non-goals

- Cryptographic signatures / PKI  
- Court-admissible PDF branding  
- Multi-tenant auth  

## Plan mapping

**M2.9** DONE when tests green + outbox writes + CLI export/replay.
