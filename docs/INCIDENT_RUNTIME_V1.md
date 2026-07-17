# incident_runtime_v1 — Live front decision support

**Product:** observe LWIR frames as they land → update front / ROS / envelope → operator outbox.  
**Not:** validated tactical dispatch or official perimeter.

## Quick start

```bash
# Pre-flight (timestamps, CRS, masks)
python -m wildfire_front incident doctor --inbox path/to/inbox --masks path/to/masks

# One-shot process of everything currently in inbox
python -m wildfire_front incident update \
  --inbox path/to/inbox \
  --work-dir outputs/incidents/IF_demo \
  --event-id IF_demo \
  --force

# Poll forever (Ctrl+C to stop)
python -m wildfire_front incident watch \
  --inbox path/to/inbox \
  --work-dir outputs/incidents/IF_demo \
  --interval-s 2

# Read last state without processing
python -m wildfire_front incident status --work-dir outputs/incidents/IF_demo

# Machine JSON
python -m wildfire_front incident status --work-dir outputs/incidents/IF_demo --json

# Windows field kit
scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF_demo
```

Human-readable reports by default (grade, ROS, sectors, envelope, artifacts, disclaimers).  
Use `--json` for full machine payload · `-v` for frame list / hybrid detail · `-q` quiet watch.

Optional masks (preferred over MAD):

```bash
--masks path/to/masks
```

Optional INFOCAM-style anchor:

```bash
--ref-name "INFOCAM Tobarra" --ref-vp-m-min 7 --ref-area-ha 39
```

## Layout

```
work_dir/
  stage/images/     # cumulative accepted GeoTIFFs (sha-deduped)
  stage/masks/      # paired masks when --masks given
  outbox/
    fire_decision_card.json   # GO / HOLD / ABSTAIN + audit (paid-value unit)
    fire_decision_card.md     # human decision one-pager
    fire_decision_radio.txt   # radio-bridge short line for mando
    fire_decision_acta.md     # 1-page forensic acta (hashes)
    replay_sources.json       # rebuild card + verify output_hash
    forensic_manifest.json    # bundle index + self_replay_ok
    incident_state.json
    watch_heartbeat.json      # last status (+ decision) for field monitors
    incident_log.jsonl        # append-only update history
    emergency_briefing.md     # includes Decision Card section
    emergency_envelope.json
    emergency_envelope_guidance.geojson
    main_front.geojson
    operational_metrics.json
    operational_report.html
    ...
```

### Decision Card on every update

Each successful `incident update` publishes a **Fire Decision Card**:

- Sources fused: ops thermal (required for GO by default) + optional ML v34 metrics + optional `--open-pack`
- Heartbeat and `incident_log.jsonl` include `decision` / `confidence_pred`
- Flags: `--open-pack DIR`, `--no-ml-metrics`, `--allow-go-without-ops`

```bash
python -m wildfire_front incident update \
  --inbox path/to/inbox --work-dir outputs/incidents/IF_demo --force \
  --open-pack outputs/open_if/emsr578
```

Unified smoke (ops + ML):

```bash
python scripts/smoke_ops_ml.py
```

## Smoke

```bash
python scripts/smoke_incident_runtime.py
python scripts/smoke_incident_runtime.py --tobarra
```

## CLI flags (watch)

| Flag | Default | Meaning |
|------|---------|---------|
| `--interval-s` | 2 | Poll period |
| `--max-frames` | — | Stop when staged ≥ N |
| `--max-iterations` | — | Stop after N polls |
| `--once` | false | Single update |
| `--min-file-age-s` | 0.5 | Ignore files still being written |
| `--mad-z` | 6 | Adaptive mask if no `--masks` |

## Input contract (field)

- GeoTIFF with **projected metric CRS** (e.g. EPSG:32630)
- Filename must embed a parseable timestamp, e.g. `2024-08-02_16-09-52-717_LWIR.tif` or `burn_20260610_120000.tif`
- Prefer stable files (runtime waits for age + size stability across polls)
- Optional masks: `{stem}.tif` or `{stem}_mask.tif` in `--masks`

## Honest limits

- Thermal mask ≠ official fire perimeter  
- 15/30/60 envelope is **extrapolated guidance**, not dispatch  
- Needs ≥2 accepted frames for ROS  
- Full recompute each update (v1); cost grows with staged frame count  
- Envelope WGS84 currently assumes UTM 30N (CLM)
