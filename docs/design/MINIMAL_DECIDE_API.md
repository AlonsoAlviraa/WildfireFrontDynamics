# Design — Minimal Decision Card API + latency budget

> Loop-engineering · 2026-07-17  
> **Dream row pulled into plan:** API Decision Card JSON (SUENOS §2.4) + latency measurable (scaled from §2.1 “&lt;15 s p95 field”).

---

## Problem

`decide` exists only as CLI. GO_Q+ and the dream list want a **JSON HTTP surface** for sala de crisis / integration demos. Field dream is **&lt;15 s** inbox→card; pure fusion decide should be **milliseconds**.

## Decision

| Choice | Rationale |
|--------|-----------|
| stdlib `http.server` only | No new deps in `pyproject.toml` |
| Shared `decide_service` | CLI + API same code path |
| Latency in every response | `latency_ms` + script p50/p95 |
| Local bind default | `127.0.0.1` — not a production crisis-room deployment |

## API (v1)

| Method | Path | Body / query | Response |
|--------|------|--------------|----------|
| GET | `/health` | — | `{ok, product, version}` |
| GET | `/v1/openapi.json` | — | Minimal OpenAPI 3 skeleton |
| POST | `/v1/decide` | JSON sources or paths | Fire Decision Card + `latency_ms` |

### POST /v1/decide body

```json
{
  "event_id": "demo",
  "use_ml_v34": true,
  "work_dir": "outputs/incidents/IF_x",
  "open_pack": "outputs/open_if/emsr578",
  "require_ops_for_go": true,
  "ml_metrics": null,
  "ops_metrics": null,
  "open_metrics": null
}
```

Path fields resolve relative to process CWD / repo root. Explicit `*_metrics` override path loading.

## Latency budget (plan, not dream ceiling)

| Path | Target | Notes |
|------|-------:|-------|
| POST /v1/decide (metrics-only / manifest paths) | **p95 &lt; 500 ms** | No GeoTIFF ingest |
| Synthetic incident update → FDC | **&lt; 10 min** (already M2.5) | Existing SLA |
| Live field multi-frame (dream) | **p95 &lt; 15 s** | Not claimed until measured on real drops |

## Non-goals (this PR)

- Auth / TLS / multi-tenant  
- Signed JWT cards  
- 99.9% uptime hosting  
- Live GeoTIFF upload over HTTP  

## Tests

- Empty body → ABSTAIN  
- ML + open paths → card with audit  
- Latency report script writes JSON with `sla_pass`  

## Plan mapping

- **M2.8** (new, Mes 2): API mínima + p95 decide medido → DONE when green  
- **M3.1** becomes: stabilize version tag / OpenAPI freeze (not first HTTP)

## PR plan

1. `decide_service.py` — load sources + build + latency  
2. `api_server.py` + CLI `serve-decide`  
3. Tests + `measure_decide_api_latency.py`  
4. Docs plan / portal / SUENOS ladder note  
