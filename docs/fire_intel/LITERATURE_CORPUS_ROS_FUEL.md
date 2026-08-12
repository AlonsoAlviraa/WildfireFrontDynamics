# Corpus literatura ROS / combustible / híbrido (WFD)

**Fecha:** 2026-07-31  
**Protocolo:** `data/fire_intel/literature/corpus_v1.json`  
**n estudios indexados:** ~93 (objetivo 100; margen por solapes ES↔Med)

## Qué se hizo

Tres subagentes de research en paralelo:

| Batch | n | Contenido |
|-------|---|-----------|
| España | 32 | Vega 2024, UCO40, Aragoneses/FirEUrisk, Anderson/Fernandes shrub, LFMC Chuvieco/Yebra, Alcasena exposure |
| Med FR/IT/GR/PT | 33 | Dimitrakopoulos, Salis/Arca FARSITE, Elia Apulia, Fernandes PT, Ganteaume FR, Prometheus |
| Physics–ML hybrid | 28 | Andrews Rothermel docs, pyrothermel, Cell2Fire adj., PINN Vogiatzoglou, Globe-LFMC, Benali LFMC ops |

## Aprendizajes que **ya entran en código**

1. **Custom Med fuels > Scott–Burgan genérico** (Salis 2016, Arca 2007, Vega 2024).  
   → Catálogo `wildfire_front/fuel/models.py` con `MED_*` + SB subset + CLC crosswalk.

2. **ROS matorral ibérico típico 5–25 m/min** en condiciones moderadas–fuertes (Cruz 2025, Fernandes 2001).  
   → Rothermel-lite calibrado en orden de magnitud; Tobarra Vp=7 es ancla **ops**, no paper.

3. **Híbrido = ajuste de factores / α, no U-Net de sala** (Kim Cell2Fire 2025, Cardil 2023).  
   → `hybrid_ros_prior` con α por edad de obs; `no_tactical_dispatch=True`.

4. **ABSTAIN sin viento o fuel unknown** (mega-plan §7 + Cardil honesty).  
   → `rothermel_lite` abstains.

5. **Stack fuel+DEM primero** (F1).  
   → `build_fuel_terrain_stack.py` (sintético Tobarra hasta PNOA real).

## Módulos nuevos

```
wildfire_front/fuel/
  models.py          # catálogo fuel
  terrain.py         # slope/aspect
  rothermel_lite.py  # ROS potential + sectores
  hybrid.py          # α obs + physics
  stack.py           # artefacto F1
scripts/build_fuel_terrain_stack.py
scripts/run_rothermel_prior.py
tests/test_fuel_rothermel_lite.py
```

## Cómo correr

```bash
python scripts/build_fuel_terrain_stack.py --fire tobarra --with-physics
python scripts/run_rothermel_prior.py --fuel MED_MAQUIS_LOW --obs-ros 5.71 --vp 7
pytest tests/test_fuel_rothermel_lite.py -q
```

## Graph engineering

Workflow: `.grok/workflows/wfd-literature-ingest.rhai`  
Estado: `.grok/graph_engineering/STATE.md` (v4 literature + fuel stack)

## No-claims

- Este corpus **no** descarga PDFs paywalled en bloque; metadata + findings de abstracts/fuentes abiertas.  
- Ratios physics/obs/Vp son **diagnóstico de ingeniería**, no GO de campo.  
- Stack sintético **no** es cartografía oficial.
