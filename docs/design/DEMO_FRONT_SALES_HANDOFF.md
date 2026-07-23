# Handoff — demo front multi-CCAA (ventas / TFG / partner)

**Portal version:** schema `demo_multi_ccaa_v3` · demo_version `2.1.0`  
**Única pestaña de demo:** `outputs/demo_multi_ccaa/index.html`

## Abrir en 10 segundos

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
.\scripts\open_demo_multi_ccaa.ps1
# o:
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html
```

Deep-links:

- `index.html?mode=pitch` — one-pager visual  
- `index.html?mode=guion` — guion 12 min  
- `index.html?panel=tobarra|nijar|camino`  
- `export/pitch_onepager.html` — print/PDF dedicado  

## Qué enseñar (orden 12 min)

1. **Hero** — promesa + HOLD como valor (ES/EN con botón L / lang)  
2. **KPI strip** — CCAA, ha O2, catálogo AND, anclas, gates PASS  
3. **3 cards** — Tobarra OPS → Níjar REDIAM → Caminomorisco RAI (+ mini-mapas)  
4. **Charts** — ha por IF · gates PASS/SKIP/FAIL · timeline det→ext Camino  
5. **Scoreboard + comparar** — mismos gates multi-CCAA  
6. **Decision Card viewer** — GO/HOLD/ABSTAIN desde gold/decide (SKIP soft si no hay JSON)  
7. **Guion** — Iniciar / Siguiente (teclas 1–3 resaltan sitios)  
8. **Reliability story** — residual silent-GO, audit trail, actas  
9. **Provenance** — contactos RAI / REDIAM / INFOCAM  
10. **CTA** — feedback / ancla / carta UE  

**Opcional (colapsado):** silver EXT · La Mierla OPEN HOLD live (no diluye el pitch).

## Claim seguro

> “Decision support multi-CCAA: térmico validado donde hay datos, perímetro oficial donde hay Junta, abstención cuando no se puede mentir.”

## No decir

- Apagamos incendios con IA  
- 99% de precisión del fuego  
- Sustituimos INFOCA/INFOEX  
- Hull FIRMS = ha quemadas  
- Inventamos Vp/ha  

## Artefactos generados

| Path | Contenido |
|------|-----------|
| `outputs/demo_multi_ccaa/index.html` | SPA demo |
| `data/kpi_board.json` | KPIs strip |
| `data/scoreboard.json` | Gates por sitio |
| `data/compare_matrix.json` | OPS vs OPEN |
| `data/decision_cards.json` | Cards GO/HOLD |
| `export/pitch_onepager.md` | Markdown pitch |
| `export/pitch_onepager.html` | Print one-pager |
| `export/guion_12min.md` | Guion base |
| `demo_manifest.json` | Schema v3 + skips + provenance |

## Scripts

| Script | Rol |
|--------|-----|
| `scripts/build_demo_multi_ccaa.py` | Orquestador (un comando) |
| `scripts/demo_kpi_board.py` | KPIs + scoreboard + ha bars |
| `scripts/demo_charts.py` | Gates stacked + timeline Camino |
| `scripts/demo_portal_html.py` | HTML portal |
| `scripts/demo_export_pitch.py` | Pitch HTML/MD |
| `scripts/open_demo_multi_ccaa.ps1` | Rebuild + open |

## Contacto CTA

`alonso.alvbal@gmail.com`

### Provenance buzones (para demos honestas)

| Fuente | Contacto |
|--------|----------|
| REDIAM AND | `rediam.atiende.csma@juntadeandalucia.es` |
| ASEMA ancla | `gerencia.asema@juntadeandalucia.es` |
| RAI/INFOEX | `rai@juntaex.es` |
| INFOCAM anclas | `data/infocam_anchors.json` (solo `confirmed`) |

## Teclado (a11y)

- `1` / `2` / `3` — resaltar Tobarra / Níjar / Camino  
- `G` — modo guion  
- `P` — modo pitch  
- `L` — ES/EN hero  
- `Tab` + `Enter`/`Espacio` — abrir secciones  

## Regenerar + tests

```powershell
python scripts\build_demo_multi_ccaa.py
$env:PYTHONPATH = "."
pytest tests\test_demo_multi_ccaa.py -q
```

`make demo-multi-ccaa` si el Makefile del repo lo expone.

## Links producto (relativos desde el portal)

- Commander: `../../docs/commander/index.html`  
- Portal hub: `../../docs/PORTAL.html`  

## Checklist pre-call

- [ ] Builder exit 0 (o 2 solo si integrity fail `vp_invented`)  
- [ ] Tres cards con números reales o SKIP honesto  
- [ ] HOLD visible y explicado  
- [ ] One-pager abre / imprime  
- [ ] No claims tácticos inventados  
