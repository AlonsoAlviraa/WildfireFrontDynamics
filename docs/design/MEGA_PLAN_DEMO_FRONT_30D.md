# Mega-plan 30 días — Front demo multi-CCAA (referencia)

Portal comercial multi-CCAA (schema **v3** / demo_version **2.1.0**).

- **Portal:** `outputs/demo_multi_ccaa/index.html`
- **Builder:** `python scripts/build_demo_multi_ccaa.py`
- **Handoff venta:** `docs/design/DEMO_FRONT_SALES_HANDOFF.md`
- **Abrir:** `scripts/open_demo_multi_ccaa.ps1`

## Incluido en v2 + v3

- Hero comercial + CTAs + ES/EN
- KPI strip + `data/kpi_board.json`
- Cards con chips de gates + mini-mapas Leaflet
- Scoreboard + compare matrix + chart ha
- Charts extra: gates PASS/SKIP/FAIL + timeline det–ext Camino (`scripts/demo_charts.py`)
- Guion interactivo + what-if HOLD + teclado 1/2/3/G/P/L
- Pitch print + `export/pitch_onepager.html` (`scripts/demo_export_pitch.py`)
- Modes `?mode=pitch|full|guion`
- Decision Card viewer (gold_e2e / docs / forensic — soft SKIP)
- Reliability story (residual silent-GO + audit trail)
- Provenance panel (REDIAM / RAI / INFOCAM / ASEMA)
- Sell kit + Q&A honestidad + silver EXT
- La Mierla opcional (colapsable OPEN HOLD live)
- Version stamp + git short hash en footer
- A11y: focus-visible, skip link, teclado secciones, reduced-motion
- Print CSS one-pager quality
- Tests `tests/test_demo_multi_ccaa.py` (≥ 20)
