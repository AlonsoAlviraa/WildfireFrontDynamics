# WFD COMMAND — App de sala de mando (**LEGACY**)

> **No es la superficie demo terceros.** Primary path = product SPA industrial C2:  
> `python -m wildfire_front app --open` → `outputs/app/index.html` · doc `docs/APP.md`.

## Primero: SPA industrial C2 (demo) o modo operario (CLI)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
python -m wildfire_front app --fire _sla_measure --open
python -m wildfire_front operator
python -m wildfire_front operator do --all
```

Semáforo + 4 actos + GO_Q. Esta app HTML es **legacy / complemento** visual, no la puerta de entrada.

## Abrir la app

```powershell
python scripts\build_commander_app.py
start docs\commander\index.html
```

Rebuild eng pesado (portal + hub + esta app): `python scripts/show_all.py`

UI táctica: Decision Card GO/HOLD/ABSTAIN, mapa Leaflet packs CEMS, radio-bridge, fuentes, métricas ops/ML.
No es orden táctica de despacho.
