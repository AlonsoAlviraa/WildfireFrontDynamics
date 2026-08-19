# Relator — constellation desk (no LLM)

**Satellites + tablero + fiscal + `decide()` sellado. Cero tokens de modelo de lenguaje.**

Relator baja chips reales (Sentinel-2 10 m, VIIRS color / SWIR / térmico) y mantiene un expediente. No llama a Gemini, Flash ni Pro. El juez es el `decide()` que ya tienes. El fiscal es regex.

On Google Cloud the same desk swaps GIBS for **Earth Engine + WeatherNext 2** (compute/storage, not LLM tokens).

This folder is a **new** slice. It does **not** flip product gates and is **not** tactical dispatch.

`wildfire_front` is **disclosed prior art** — see [PRIOR_ART.md](PRIOR_ART.md).

## The idea

A sala needs someone who **pulls the sky, cites every pixel source, and shuts up**. Relator keeps a **source board**:

| Cell | How it turns green |
|------|--------------------|
| `open_sat` | VIIRS + Sentinel-2 chips (GIBS / STAC now; Earth Engine / GOES-FDC / WeatherNext on GCP). Present ≠ official ha |
| `ops_thermal` | Operator GeoTIFF. JPG from a phone is refused. |
| `open_official_ha` | Hectares **only** if the document contains both a number and `cite:` |
| `ops_ros` | ROS **only** if a cite is supplied. Nothing invents this cell. |

If a briefing says “ROS 8 m/min” / “4000 ha” / “GO” without a matching cite, the **fiscal** strikes the span and force-ABSTAINS.

Live (project `project-89d8567f-49f2-48bc-a00`):

- Health: https://relator-680645425654.europe-west1.run.app/health
- In-process E2E: https://relator-680645425654.europe-west1.run.app/e2e
- Board UI: https://relator-680645425654.europe-west1.run.app/ui/nijar_e2e
- POST `/events` `{type, incident_id, ...}` — tablero persistido en GCS

## Run locally (no GCP, no LLM keys)

```powershell
$env:PYTHONPATH = ".;hackathon"
python -m relator --pull-sky --aoi nijar
python -m relator --live-europe
python -m relator --html outputs/relator_demo/board.html
python -m pytest tests/test_relator.py -q
```

`--pull-sky` downloads NASA Worldview (VIIRS) + Sentinel-2 previews. `--live-europe` reads today’s FIRMS Europe 24h CSV.

Clock:

0. Empty board → **ABSTAIN**
1. Sky chips + Maps toponym → still **ABSTAIN** (FIRMS ≠ burned area)
2. Dirty drop: GeoTIFF + phone JPG + CEMS text with cited ha → JPG dies, ha is cited
3. Hostile briefing “GO / ROS 8 m/min / 4000 ha” → fiscal **strikes**
4. Second pulse → board updates, still not dispatch

## Google Cloud project

Pinned: **`project-89d8567f-49f2-48bc-a00`** · region `europe-west1` · bucket `relator-sky-project-89d8567f-49f2-48bc-a00`

```powershell
$env:PYTHONPATH = ".;hackathon"
python -m relator --gcp
# after: winget install Google.CloudSDK
#        gcloud auth login
#        gcloud auth application-default login
.\hackathon\relator\deploy.ps1
```

APIs we enable: Cloud Run, Storage, Pub/Sub, Earth Engine, Cloud Build, Artifact Registry, Firestore.  
**We do not enable** Vertex AI / Generative Language.

## Infra (Cloud, still no LLM)

- Cloud Run + Pub/Sub + Firestore + GCS (`server.py`)
- Earth Engine: FIRMS, GOES-19 FDC, Sentinel-2
- WeatherNext 2 as a **cited** weather cell (not ROS)

Credits, if you redeem them later: Earth Engine + storage + Cloud Run. **Not** Vertex / Gemini tokens.

## Rails

- Not tactical dispatch
- FIRMS hull ≠ official burned area
- GO_Q partial · fusion ON ≠ despacho
- IoU ≠ ROS
- ABSTAIN is a feature
- No language model
