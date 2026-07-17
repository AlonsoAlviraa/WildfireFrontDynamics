# Field kit — incident_runtime_v1 (1 página)

**Qué es:** observar frames LWIR que caen en un inbox → actualizar frente, ROS, sectores y envelope.  
**Qué no es:** despacho táctico validado ni perímetro oficial.

## Windows (rápido)

```bat
scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF_DEMO
```

Una sola pasada (sin watch infinito):

```bat
scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF_DEMO --once
```

Con máscaras preferidas (mejor que MAD):

```bat
scripts\run_incident.cmd D:\drops\inbox outputs\incidents\IF_DEMO --masks D:\masks
```

## Pre-vuelo (doctor)

```bash
python -m wildfire_front incident doctor --inbox path/inbox --masks path/masks
```

Revisa: archivos legibles, CRS, timestamps, huecos temporales, coherencia masks/frames.

## Ciclo de trabajo

1. `doctor` → corregir errores listados  
2. `update` o `watch` → genera `work_dir/outbox/`  
3. Abrir `emergency_briefing.md` + `main_front.geojson`  
4. `status` para estado sin reprocesar  

```bash
python -m wildfire_front incident update --inbox IN --work-dir WORK --event-id IF_X --force
python -m wildfire_front incident status --work-dir WORK
python -m wildfire_front incident watch --inbox IN --work-dir WORK --interval-s 2
```

## Ancla INFOCAM (opcional)

```bash
python -m wildfire_front incident update ... --ref-name "INFOCAM Tobarra" --ref-vp-m-min 7 --ref-area-ha 39
```

Solo valores con fuente real (`data/infocam_anchors.json`).

## Checklist 5 minutos (operador)

- [ ] Doctor sin errores bloqueantes  
- [ ] Outbox tiene `incident_state.json` + briefing  
- [ ] ROS y grado leídos; disclaimer entendido  
- [ ] **No** interpretar IoU ML como ROS de dron  
- [ ] Envelope 15/30/60 = proyección, no orden táctica  

## Artefactos típicos en outbox

| Archivo | Uso |
|---------|-----|
| `incident_state.json` | Estado máquina |
| `emergency_briefing.md` | Brief humano |
| `main_front.geojson` | Frente principal GIS |
| `*_envelope*.geojson` | Envelope si activo |

Smoke local: `python scripts/smoke_incident_runtime.py` (+ `--tobarra` si hay datos).
