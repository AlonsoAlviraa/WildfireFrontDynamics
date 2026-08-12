# Data proxy honesty — confirmed vs proxy

Short policy for O1 anchors, ops drops, and fuel guidance.  
Canonical anchor file: `data/infocam_anchors.json`.  
Protocol: only `status=confirmed` values with an explicit source count for O1/O5 GO.  
`pending_external` is **not** GO material.

---

## Confirmed (may set `status=confirmed` on ancla)

| Source class | What it is | Example in-repo |
|--------------|------------|-----------------|
| **Parte INFOCAM / ops official table** | Explicit Vp media and/or ha with institutional provenance | Tobarra Vp=7 m/min, ha=39 |
| **Boletín UNAP** | Table SEGUIMIENTO (or equivalent) quoting Vp media + superficie with literal cite | Hellín 2024-07-19: Vp **50** m/min, 100 ha\* (\*estimada no oficial) |

Rules:

- Quote the source string on the anchor (`source` field).
- Footnotes travel with the number (e.g. ha\* estimated non-official).
- Never invent Vp/ha to “close” O1.

---

## Proxy only (never alone → `confirmed`)

| Source class | What it is | In-repo handle | Allowed use |
|--------------|------------|----------------|-------------|
| **Cardoso Δha timeline** | Multi-day ops KMZ polygon area growth (ha/h) | `data/real_if/pablo_geacam_20260803_drop/cardoso/timeline_delta_ha.json` · rebuild: `python scripts/build_cardoso_timeline.py` | Engineering growth proxy. **Not** head ROS m/min. **Not** EGIF. **Not** Vp. |
| **La Estrella SITAC** | Map/photo readings of scenario Vp / ha (visual or OCR) | `…/la_estrella/photo_readings.json` | Scenario context only. `not_confirmed_anchor: true`. Keep ancla **`pending_external`**. |
| **KMZ ha attrs** | `sup_ha` / Sup.Activa on ops or thermal KMZ | Tobarra, Hellín, Estrella, Cardoso drops | Ops perimeter geometry / O2-lite. **Not** EGIF national cadastre. |
| **EGIF** | National catalog ha/dates when available | external MITECO | Official ha candidate when bound to fire_id; still does **not** invent Vp. |
| **Boletín UNAP (context without Vp row)** | Weather/risk narrative, other fires | Hellín PDF in drop | Context; only the explicit SEGUIMIENTO Vp/ha row promotes the named fire. |
| **Press / CEMS / EFFIS ha** | Media or satellite provisional extents | La Mierla, Burgohondo, etc. | `area_ha_press_*` / open packs only. Never promote to `area_ha` or `confirmed`. |
| **Hybrid envelope 15/30/60** | Fuel stack extrapolation | Decision Card attach **weight = 0** | Audit/guidance only. Not tactical dispatch. |

---

## Fire-by-fire cheat sheet (post 0308 drop)

| fire_id | Anchor status | Confirmed fields | Proxies (do not promote) |
|---------|---------------|------------------|--------------------------|
| `tobarra_20240802` | **confirmed** | Vp 7 · ha 39 (parte) | KMZ multi-hora ~21–37 ha |
| `hellin_2024` | **confirmed** | Vp 50 · ha 100\* (boletín UNAP) | KMZ 20:45 ~93.7 ha |
| `cardoso_2025` | **pending_external** | — | Timeline Δha / ha/h polygon proxy |
| `la_estrella_acom1_2024` | **pending_external** | — | SITAC map Vp ~20–25; KMZ ~2524 ha |

---

## Kill list

- Treating Cardoso ha/h or Estrella SITAC Vp as INFOCAM confirmed anchors  
- Setting `area_ha` / `vp_m_min` from press, CEMS, or EFFIS alone  
- Calling KMZ `sup_ha` “EGIF” or “official final area”  
- Using envelope / physics ROS as tactical dispatch or fusion-driving confidence (weight stays **0**)  
- Averaging Tobarra Vp 7 with Hellín Vp 50 into one global k without fire-class split  

---

## Fuel / AEMET offline paths (no live network)

| Fire day | Offline WeatherScenario path | Build (when raw AEMET list exists) |
|----------|------------------------------|--------------------------------------|
| Tobarra 2024-08-02 | `data/fuel_stack/tobarra/weather_aemet_20240802.json` | `python scripts/build_aemet_weather_scenario.py --from-json <aemet_raw.json> --date 2024-08-02 --station 8175 --fire-id tobarra_20240802 --out data/fuel_stack/tobarra/weather_aemet_20240802.json` |
| Hellín 2024-07-19 (optional) | **Convention:** `data/fuel_stack/hellin/weather_aemet_20240719.json` | Same CLI with `--date 2024-07-19 --fire-id hellin_2024 --station <nearest>` and `--from-json` — **fixture not shipped** until a raw day file is checked in offline. No API key required with `--from-json`. |

End-to-end Tobarra (uses cached JSON if present):

```bash
python scripts/run_tobarra_aemet_pipeline.py
```

Envelope remains Decision Card **weight 0** (`attach_envelope_to_decision_card` → `fusion_weight: 0.0`).

---

## Rebuild / maintain

```bash
# Cardoso proxy timeline (C1)
python scripts/build_cardoso_timeline.py

# Fuel maintain smoke (D1 / D3)
pytest tests/test_fuel_envelope.py tests/test_aemet_weather.py tests/test_ops_perimeter.py -q
```
