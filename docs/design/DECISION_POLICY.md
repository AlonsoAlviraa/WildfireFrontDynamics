# Design — Decision policy by organism (M2.10)

> Loop-engineering · 2026-07-17  
> **Dream row:** SUENOS §3.1 *Política de decisión configurable por organismo*

---

## Problem

One hard-coded threshold set cannot serve both a **demo/TFG** and a **sala GEACAM**.  
Same sources must be able to yield HOLD under demo and ABSTAIN under a stricter field policy.

## Decision

| Item | Choice |
|------|--------|
| Format | JSON catalog `config/decision_policies.json` |
| Default | `default` ≡ historical thresholds (no behavior change) |
| Profiles | `default`, `field_ops` (strict), `research_open` (lab) |
| Wire | `decide()` + card audit + CLI `--policy` + API + replay |

## Policy fields

```json
{
  "id": "field_ops",
  "label": "Field / emergency ops (strict)",
  "require_ops_for_go": true,
  "abstain_below": 0.25,
  "go_ops_min": 0.65,
  "go_ops_open_min": 0.55,
  "hold_open_min": 0.40,
  "hold_ml_only_min": 0.50,
  "allow_ml_only_hold": false,
  "allow_open_only_hold": true,
  "min_available_sources": 1
}
```

## Non-goals

- Per-user SSO policies  
- Live A/B of policies on production fires without audit  
- Changing source scoring weights in this PR (optional later)

## Forensic

`policy_id` enters audit + replay_sources so rebuild uses the same policy.

## Plan

**M2.10** DONE when tests show default ≡ legacy and field_ops stricter.
