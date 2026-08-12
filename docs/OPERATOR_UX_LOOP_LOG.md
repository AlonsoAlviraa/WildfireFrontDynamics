# Operator UX Engineering Loop — log

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-05 (implement pass FULL Operator UX plan — relaunch) |
| **Stop criterion** | Operario simulado completa 4 actos sin ayuda **y** sabe qué falta para GO_Q |
| **Rule** | Una sola fricción por iteración · mínimo código · revalidar checklist |
| **Entry** | bare · `ensayo` · `next`/`go_q` · `checklist` · `operador` |
| **Status final** | **LOOP CERRADO v12 / PLATEAU** (iters 1–17; residual estable = H1 humano) |
| **Última revalidación** | #13 holds · **Implement pass 2026-08-05 relaunch** (0 gaps de código; verify-only) |

---

## Método (repetido cada iteración)

1. **Observar** — simular operario sin conocimiento de código  
2. **Medir fricción** — ¿sabe qué hacer en &lt;30 s?  
3. Si NO → **una** fricción concreta  
4. Rediseñar mínimo → implementar → humo + checklist  
5. Si SÍ estable → congelar y siguiente fricción  

### Checklist de operario (criterio de paro)

| # | Item | Cómo se mide |
|---|------|----------------|
| 1 | Único comando de entrada &lt;30 s | `operator` existe y es obvio en START_HERE |
| 2 | Semáforo legible | VERDE / AMARILLO / ROJO en tablero |
| 3 | Acto 1 Ver | `operator do --act 1` exit 0 |
| 4 | Acto 2 Callarse | `operator do --act 2` + ABSTAIN ≠ bug |
| 5 | Acto 3 Decidir | `operator do --act 3` + lenguaje normal |
| 6 | Acto 4 Probar | `operator do --act 4` + replay_ok honesty |
| 7 | Sabe hueco GO_Q | one-liner humano H1/M3.2 (no inventa complete) |

Comando de evaluación: `python -m wildfire_front operator checklist`

---

## Baseline (antes del loop) — observación inicial

### Simulación

Operario abre el repo y ve:

- `docs/START_HERE.md` → `python scripts\show_all.py` (portal pesado, muchas pestañas)
- `wildfire-front --help` → **13** subcomandos (demo, incident, ml, teach, show, …)
- `teach` lista scripts sueltos (`build_demo_multi_ccaa.py`, `run_pilot_honesty_card.py`)
- `decide` vacío → `ABSTAIN` + reasons `missing:ml_clm_ensemble; missing:ops; …` sin español claro
- No hay semáforo ni “qué falta para GO_Q” en una sola pantalla

### Medición

| Pregunta | Respuesta |
|----------|-----------|
| ¿Sabe qué hacer en &lt;30 s? | **NO** |
| Paradas típicas | ¿por dónde empiezo? ¿ABSTAIN es error? ¿qué es un pack? ¿GO_Q? |
| Cuellos de botella (priorizados) | (1) demasiadas puertas (2) ABSTAIN confuso (3) actos = scripts (4) START_HERE no operario |

---

## Iteración 1 — Una sola puerta de entrada + semáforo

| Campo | Valor |
|-------|--------|
| **Fricción** | Demasiadas puertas (scripts + CLI + HTML); no hay modo solo operario |
| **Pregunta &lt;30 s** | NO |
| **Cambio mínimo** | Comando `wildfire-front operator` = tablero único |

### Implementación

| Path | Rol |
|------|-----|
| `wildfire_front/product/operator_ux.py` | Semáforo, GO_Q gap plain, checklist, format board |
| `wildfire_front/cli_teach.py` | `register` + `run_operator` (status / checklist / do / explain-abstain) |
| `wildfire_front/cli.py` | Wire `operator` + epilog “Modo operario” |

### Semántica del semáforo

| Luz | Significado |
|-----|-------------|
| **VERDE** | Listo |
| **AMARILLO** | Falta algo (sistema **no** roto) — p.ej. GO_Q partial |
| **ROJO** | Bloqueado |

### Humo

```text
python -m wildfire_front operator          → exit 0, AMARILLO overall, 4 pasos visibles
python -m wildfire_front operator --json   → schema wfd_operator_status_v1
```

### Checklist post-iter

- [x] Entrada única  
- [x] Semáforo  
- [ ] Actos aún requieren conocer scripts (fricción siguiente)  
- [x] GO_Q one-liner presente  

**Congelado.** Siguiente fricción: ABSTAIN parece roto.

---

## Iteración 2 — ABSTAIN en lenguaje normal

| Campo | Valor |
|-------|--------|
| **Fricción** | Cuando el sistema hace ABSTAIN, el operario cree que está roto |
| **Pregunta &lt;30 s** | Aún NO del todo en `decide` corto |
| **Cambio mínimo** | Caja plain-language + nota en `decide` corto |

### Implementación

- `format_abstain_plain(card)` en `operator_ux.py`
- `operator explain-abstain` ejecuta field_ops vacío y explica
- `decide` (sin `--json`): si ABSTAIN → `nota: … No es un bug. … operator explain-abstain`
- `decide --explain`: prefija la caja plain antes del informe técnico

### Humo

```text
python -m wildfire_front decide --policy field_ops
  → decision: ABSTAIN
  → nota: ABSTAIN = el producto se calla a propósito …

python -m wildfire_front operator explain-abstain
  → “EL SISTEMA SE CALLA (ABSTAIN) — esto NO es un fallo”
  → fuentes que faltan en castellano
```

### Checklist post-iter

- [x] Operario no interpreta ABSTAIN como crash  
**Congelado.** Siguiente: actos sin magia negra de scripts.

---

## Iteración 3 — Los 4 actos desde `operator do`

| Campo | Valor |
|-------|--------|
| **Fricción** | Packs/replay y demos multi-CCAA parecen magia negra (scripts sueltos) |
| **Pregunta &lt;30 s** | Casi: tablero dice `do --act N` pero hay que implementarlo |
| **Cambio mínimo** | `operator do --act 1|2|3|4` encapsula scripts/CLI |

### Mapa acto → acción

| Acto | Nombre | Acción encapsulada |
|------|--------|--------------------|
| 1 | Ver | `scripts/build_demo_multi_ccaa.py` (+ `--open`, `--no-build`) |
| 2 | Callarse | `scripts/run_pilot_honesty_card.py` + caja ABSTAIN |
| 3 | Decidir | `decide` field_ops + plain + `--explain` shape |
| 4 | Probar | `demo-third-party` (replay ON) + honesty GO_Q |

### Humo (artefactos ya en repo → `--no-build` donde aplica)

```text
operator do --act 1 --no-build  → exit 0
operator do --act 2 --no-build  → exit 0 + plain ABSTAIN
operator do --act 3             → exit 0 + ABSTAIN feature
operator do --act 4 --no-build  → exit 0 · replay_ok=True
```

### Demos

- multi-CCAA / pilot honesty: presentes (no rebuild largo en esta pasada; `--no-build` OK)
- pack third-party: replay forense re-ejecutado OK

**Congelado.** Siguiente: entrada documental (START_HERE).

---

## Iteración 4 — START_HERE y cheatsheet apuntan al operario

| Campo | Valor |
|-------|--------|
| **Fricción** | Docs de entrada aún empujaban a `show_all.py` / scripts primero |
| **Cambio mínimo** | START_HERE + CHEATSHEET + `teach` human output priorizan `operator` |

### Archivos

- `docs/START_HERE.md` — sección **Operario (un solo comando)** primero; portal pasa a “opcional, pesado”
- `docs/CHEATSHEET_DEMO_12MIN.md` — 4 actos vía `operator do --act N`
- `teach_path.format_teach_human` — línea “Modo operario (recomendado)” + comando por acto

### Humo

```text
python -m wildfire_front teach | findstr operator   → presente
```

**Congelado.**

---

## Iteración 5 — README aún abría otra puerta (revalidación adversaria)

| Campo | Valor |
|-------|--------|
| **Fricción** | `README.md` “Empieza aquí (1 comando)” seguía mandando a `show_all.py` / commander; PROJECT_STATUS y MEMORY no mencionaban operator |
| **Pregunta &lt;30 s** | Si el operario llega por README → **NO** (regresión documental) |
| **Cambio mínimo** | README entrada = `operator`; portal/commander → opcional eng |

### Implementación

| Path | Cambio |
|------|--------|
| `README.md` | Bloque operario primero; show_all secundario |
| `docs/PROJECT_STATUS.md` | Bullet **Operator UX mode** + checklist 7/7 · GO_Q partial |
| `MEMORY.md` | What works: operator UX + link al log |

### Humo

```text
README greps "wildfire_front operator" → sí
operator board → Setup PYTHONPATH presente (iter 6)
```

**Congelado.**

---

## Iteración 6 — Checklist demasiado optimista (honestidad)

| Campo | Valor |
|-------|--------|
| **Fricción** | Checklist 7/7 podía leerse como “demo humana hecha”; pass en actos = solo presencia de artefactos |
| **Cambio mínimo** | `basis` por item + notas “artefacto listo” + campo `honesty` en JSON/humano; Setup en tablero |

### Implementación

- `evaluate_operator_checklist`: `basis` ∈ artifact_presence | command_surface | awareness_not_complete | …
- `format_checklist_human`: línea **Honestidad:** …
- `format_operator_human`: bloque Setup (`cd` + `PYTHONPATH`)
- Tests: basis en acts; board tiene PYTHONPATH

### Humo

```text
operator checklist → note artefacto listo + Honestidad: …
operator checklist --json → honesty + basis fields
```

**Congelado.** Criterio de paro eng sigue cumplido; GO_Q no inventado.

---

## Iteración 7 — Curso y runbook H1 reabrían puertas viejas

| Campo | Valor |
|-------|--------|
| **Fricción** | `CURSO_WFD_PARA_DESCONOCIDOS.md` y `H1_GO_Q_RUNBOOK.md` no mencionaban `operator`; §8.3 y Apéndice A seguían scripts/`show_all` |
| **Pregunta &lt;30 s** | Si el operario llega por **curso** o prep H1 → **NO** (bypass de START_HERE/README) |
| **Cambio mínimo** | Curso + runbook H1 priorizan `operator` / `do --act N` |

### Implementación

| Path | Cambio |
|------|--------|
| `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` | Setup operator; §8.3 tabla operario; Apéndice A bloque operator primero |
| `docs/H1_GO_Q_RUNBOOK.md` | Prep paso 2 = operator + checklist; acto 4 en vivo vía `do --act 4`; paths canónicos |
| `tests/test_operator_ux.py` | `test_entry_docs_point_to_operator` (README/START/CURSO/H1/CHEATSHEET) |

### Humo

```text
python -c "assert 'wildfire_front operator' in open('docs/CURSO...').read()"
pytest tests/test_operator_ux.py::test_entry_docs_point_to_operator -q
operator checklist → loop_done true
```

**Congelado.**

---

## Iteración 8 — No había un solo comando para los 4 actos

| Campo | Valor |
|-------|--------|
| **Fricción** | Operario debía lanzar 4 `do --act N`; `do` sin flags → argparse inglés; Makefile sin `operator` |
| **Pregunta &lt;30 s** | Parcial: sabía el tablero, no el ensayo completo en un paso |
| **Cambio mínimo** | `operator do --all` (+ error amable) + `make operator*` |

### Implementación

| Path | Cambio |
|------|--------|
| `wildfire_front/cli_teach.py` | `--all` / `--rebuild`; mensaje ES si falta acto; `_run_operator_do_one` |
| `wildfire_front/product/operator_ux.py` | Ayuda: `do --all` |
| `Makefile` | `operator` · `operator-checklist` · `operator-path` |
| `docs/START_HERE.md` · `CHEATSHEET` | `do --all` / make targets |
| `tests/test_operator_ux.py` | missing-act friendly · do-all smoke · board --all |

### Humo

```text
operator do                 → exit 2 + mensaje ES con --act / --all
operator do --all           → 4/4 OK · GO_Q partial reminder
make operator-path          → mismo
operator checklist          → loop_done true
```

**Congelado.**

---

## Iteración 9 — Ensayo sin rastro + JSON roto

| Campo | Valor |
|-------|--------|
| **Fricción** | `do --all --json` mezclaba banners humanos (JSON inválido); checklist no distinguía “artefacto en disco” vs “ensayo ejecutado” |
| **Pregunta &lt;30 s** | Tras `do --all`, el operario no veía prueba de que el ensayo contó |
| **Cambio mínimo** | Sello `outputs/operator_ux_last_run.json` + quiet en modo `--json` |

### Implementación

| Path | Cambio |
|------|--------|
| `operator_ux.py` | `write_operator_session` / `load_operator_session`; checklist `basis=session_ran` |
| `cli_teach.py` | `quiet_acts` si `--json`; escribe sello tras do |
| Tests | pure JSON do-all; checklist upgrades basis |

### Humo

```text
operator do --all --json  → schema wfd_operator_do_all_v1, 4× ok, go_q partial
operator checklist        → "Último ensayo: …" · basis session_ran · NO H1
outputs/operator_ux_last_run.json  (gitignored under outputs/)
```

**Congelado.**

---

## Iteración 10 — Guion 30 min y guía de comandos reabrían arqueología

| Campo | Valor |
|-------|--------|
| **Fricción** | `GUION_DEMO_30MIN_POST_O1.md` y `GUIA_COMANDOS_RECREAR_TODO.md` no mencionaban `operator` (presentador / eng caen en scripts) |
| **Pregunta &lt;30 s** | Si el camino es guion demo o guía de comandos → **NO** sin este fix |
| **Cambio mínimo** | Bloque operator primero en ambos docs + test entry-docs |

### Implementación

| Path | Cambio |
|------|--------|
| `docs/GUIA_COMANDOS_RECREAR_TODO.md` | Sección “Antes de todo: modo operario” |
| `docs/GUION_DEMO_30MIN_POST_O1.md` | P0 operator + arranque `do --all` / checklist |
| `tests/test_operator_ux.py` | entry-docs incluye GUIA + GUION |

### Humo

```text
pytest … test_entry_docs_point_to_operator → pass
operator checklist → loop_done + session_ran (sello previo)
```

**Congelado.**

---

## Iteración 11 — Un `do --act` borraba el sello de 4 actos

| Campo | Valor |
|-------|--------|
| **Fricción** | Tras `do --all`, un `do --act 4` reescribía el sello con solo acto 4 → checklist perdía `session_ran` en 1–3 |
| **Cambio mínimo** | `write_operator_session`: merge en single-act; replace en `--all` |

### Humo

```text
do --all -q → all_four_ok true
do --act 4 --no-build -q → all_four_ok sigue true · ok_acts ⊇ {1,2,3,4}
```

**Congelado.**

---

## Iteración 12 — Alias ES + regenerar portal no debe romper el loop

| Campo | Valor |
|-------|--------|
| **Fricción** | (1) `operador` / `ops` → argparse inglés; (2) `build_portal.py` reescribía START_HERE/PORTAL con `show_all` como única puerta |
| **Cambio mínimo** | Alias argv en `cli.main`; plantilla portal/START operator-first |

### Implementación

| Path | Cambio |
|------|--------|
| `wildfire_front/cli.py` | `_COMMAND_ALIASES`: `operador`/`ops` → `operator` |
| `scripts/build_portal.py` | Hero = operator; 4 actos; START_HERE operator-first |
| `docs/PORTAL.html` · `START_HERE.md` | Regenerados |
| Tests | aliases + plantilla build_portal |

### Humo

```text
python -m wildfire_front operador          → tablero
python -m wildfire_front ops checklist --json → loop_done
docs/PORTAL.html contiene wildfire_front operator
build_portal.py no es solo show_all
pytest … → 39 passed
```

**Congelado.**

---

## Iteración 13 — CLI vacío fallaba; show_all se vendía como la puerta

| Campo | Valor |
|-------|--------|
| **Fricción** | `python -m wildfire_front` sin COMMAND → error argparse; `show_all.py` / commander README sin camino operario |
| **Cambio mínimo** | argv vacío → `["operator"]`; show_all nota eng + checklist; commander README operator-first |

### Humo

```text
python -m wildfire_front                 → tablero operario (exit 0)
python -m wildfire_front operador        → igual
scripts/show_all.py docstring            → operator-first
pytest … test_bare_cli_defaults_to_operator → pass
```

**Congelado.**

---

## Iteración 14 — Ensayo ruidoso + one-pager comercial reabría show_all

| Campo | Valor |
|-------|--------|
| **Fricción** | `do --all` volcaba ABSTAIN+explain × actos (operario se pierde); `ONEPAGER_COMERCIAL` demo = show_all |
| **Cambio mínimo** | `--all` compacto por defecto (`-v` detalle); alias `ensayo`; one-pager operator-first |

### Humo

```text
python -m wildfire_front ensayo -q     → 4/4 + sello
python -m wildfire_front operator do --all  → líneas cortas Acto N: OK · sin Teach footnote
ONEPAGER demo → wildfire_front / ensayo
pytest → 43+ passed
```

**Congelado.**

---

## Iteración 15 — Error argparse opaco + “¿y ahora qué?”

| Campo | Valor |
|-------|--------|
| **Fricción** | COMMAND inválido = muro inglés sin pista; no hay `operator next`; tablero no listaba `ensayo` |
| **Cambio mínimo** | Hint ES en SystemExit; subcomando `next`; ayuda del tablero |

### Humo

```text
python -m wildfire_front foo           → hint operario/ensayo
python -m wildfire_front operator next → GO_Q gap + eng vs humano
tablero                                → línea ensayo + next
pytest → 45+ passed
```

**Congelado.**

---

## Iteración 16 — `next` / `go_q` top-level solo daban hint

| Campo | Valor |
|-------|--------|
| **Fricción** | Escribir `next` o `go_q` como COMMAND no abría el hueco GO_Q (solo hint de error) |
| **Cambio mínimo** | Expansiones top-level `next`/`go_q`/`checklist`; Make `ensayo` + `operator-next` |

### Humo

```text
python -m wildfire_front next      → Operario · NEXT + GO_Q humano
python -m wildfire_front go_q      → igual
python -m wildfire_front checklist --json → wfd_operator_checklist_v1
make ensayo / make operator-next
pytest → 47+ passed · loop_done 7/7
```

**Congelado.** Residual estable = H1 humano.

---

## Iteración 17 — Ensayo compacto duplicaba el scoreboard

| Campo | Valor |
|-------|--------|
| **Fricción** | `ensayo` listaba Acto 1–4 dos veces (loop + footer) |
| **Cambio mínimo** | Footer sin re-listar si `compact_all`; “Siguiente: next” |

### Humo

```text
python -m wildfire_front ensayo
  Acto 1–4: OK  (una sola vez)
  Fin ensayo: 4/4
  Siguiente: next
```

**Congelado.**

---

## 2026-08-10 — CLI discoverability / footguns (side pass)

No reabre el loop de 4 actos. Corrige fricción de **descubrimiento** y mensajes de error:

| Footgun | Fix |
|---------|-----|
| `help` / `doctor` / `status` inválidos | `help`→mapa · `doctor` hub · `status` smart |
| Hint operario en flags faltantes | Solo COMMAND desconocido; hints contextuales |
| `export-acta` / `replay-decide` opacos | exit 2 + ejemplos |
| `decide` sin policy | nota `default` vs `field_ops` |
| bare `ml` / bare `incident` | hubs exit 0 (`wfd_ml_hub_v1` / `wfd_incident_hub_v1`) |
| `version` como COMMAND | alias `version` / `ver` / `about` |
| typos (`predic`, `decied`) | `¿Quisiste decir?` + listado |

Detalle: **`docs/OPERATOR_CLI_CHANGES.md`**. Rails ML/GO_Q sin tocar.

---

## Plateau eng (no más fricción de código estable)

Tras **17 iters** el stop criterion eng se cumple de forma estable:

| Check | Resultado revalidación #12 |
|-------|----------------------------|
| bare CLI | tablero operario |
| `ensayo` | 4/4 + sello |
| `next` / `go_q` | hueco H1, `go_q_complete=false` |
| `checklist` | 7/7 · `loop_done` · `session_all_four_ok` |
| pytest operator+teach | **47+** passed |
| Rails | GO_Q partial · fusion OFF |

**Reabrir el loop eng solo si:**

1. Un operario real se atasca con evidencia (comando + pantalla), o  
2. Se rompe un test de contrato / regresión de entry docs, o  
3. H1 se completa y hay que reflejar GO_Q en el tablero (sin inventar).

**No reabrir por:** más aliases, más docs secundarios, o polish cosmético sin atasco &lt;30 s.

---

## Revalidación #13 (2026-08-04) — plateau holds

Observación adversaria del camino completo. **¿Sabe qué hacer en &lt;30 s?** **SÍ** (estable).

| Paso | Comando | Resultado |
|------|---------|-----------|
| Tablero | `python -m wildfire_front` | MODO OPERARIO · AMARILLO (GO_Q) |
| Ensayo | `python -m wildfire_front ensayo` | 4/4 OK · sello · sin scoreboard duplicado |
| Next | `python -m wildfire_front next --json` | `go_q_complete=false` · loop/sess true · eng_ready |
| Checklist | `python -m wildfire_front checklist --json` | **7/7** · `loop_done` · `session_all_four_ok` |
| Tests | `pytest tests/test_operator_ux.py tests/test_cli_teach_product.py` | **47 passed** |
| Entry docs | README/START/ONEPAGER/H1/CURSO/CHEATSHEET/portal/show_all | **OK** (operator/ensayo) |
| Rails | GO_Q / fusion / ml_product_go | partial / OFF / false — sin inventar |
| Hint inválido | `no_such_cmd` | pistas a tablero / ensayo / next |

**Nueva fricción de código que bloquee &lt;30 s:** ninguna.  
**Acción:** no iteración de implementación; solo actualización de resultados.  
**Residual:** H1 humano — `docs/H1_GO_Q_RUNBOOK.md`.

---

## Implement pass (2026-08-05) — FULL Operator UX plan

Auditoría end-to-end del plan completo (criterios 1–12 + teach V7 sin regresión).  
**Código nuevo:** ninguno (plateau ya cubría el target state).  
**Acción:** revalidar humo + pytest; documentar pass/fail por criterio; no inventar GO_Q.

| Criterio | Resultado |
|----------|-----------|
| 1 Single entry (`python -m wildfire_front` / operator / aliases) | **PASS** |
| 2 Traffic light VERDE/AMARILLO/ROJO | **PASS** (overall AMARILLO por GO_Q) |
| 3 ABSTAIN plain (`explain-abstain` + `decide` nota) | **PASS** |
| 4 Solo 4 actos (`do --act N` / `ensayo` / `do --all`) | **PASS** compact 4/4 |
| 5 GO_Q gap (`next` / `go_q` / board) · `go_q_complete=false` | **PASS** |
| 6 Checklist 7 items · `loop_done` sin flip GO_Q | **PASS** 7/7 |
| 7 Session stamp merge (single `do --act` no wipe) | **PASS** |
| 8 Compact ensayo sin scoreboard duplicado | **PASS** |
| 9 Entry docs → operator (README/START/ONEPAGER/CURSO/H1/CHEATSHEET/portal/show_all) | **PASS** |
| 10 Make `operator` · `ensayo`/`operator-path` · `operator-checklist` · `operator-next` | **PASS** |
| 11 Invalid COMMAND → hint ES operario | **PASS** |
| 12 Rails (fusion OFF · ml_product_go false · GO_Q partial) | **PASS** |

### Humo revalidado (PowerShell)

```text
$env:PYTHONPATH = "."
python -m wildfire_front                 → MODO OPERARIO · AMARILLO
python -m wildfire_front ensayo -q       → exit 0 · sello 4/4
python -m wildfire_front next --json     → go_q_complete=false · session_all_four_ok
python -m wildfire_front checklist --json → 7/7 · loop_done · honesty ≠ H1
pytest tests/test_operator_ux.py tests/test_cli_teach_product.py -q → 47 passed
```

**Residual humano (no eng):** H1 demo+acta → `docs/H1_GO_Q_RUNBOOK.md`.  
**No se reabre loop eng** sin atasco real &lt;30 s o regresión de contrato.

---

## Implement pass (2026-08-05) — relaunch FULL Operator UX plan

Re-auditoría tras stall de run previo. **Código nuevo:** ninguno (plateau iters 1–17 + pass anterior ya cubren target).  
**Acción:** re-ejecutar humo + pytest; confirmar criterios 1–12; no inventar GO_Q / H1 / fusion.

| Criterio (acceptance relaunch) | Resultado |
|--------------------------------|-----------|
| 1 Bare CLI → tablero semáforo | **PASS** AMARILLO (GO_Q) |
| 2 Aliases operador/ops/estado/semaforo | **PASS** |
| 3 Expansions ensayo/next/go_q/checklist | **PASS** |
| 4 4 actos `do --act` + `ensayo` compact | **PASS** 4/4 |
| 5 ABSTAIN plain (`explain-abstain` + decide nota) | **PASS** |
| 6 Session stamp merge (single act no wipe) | **PASS** all_four_ok |
| 7 Checklist 7/7 eng · GO_Q awareness ≠ complete | **PASS** loop_done |
| 8 `next` hueco H1 · `go_q_complete=false` | **PASS** |
| 9 Invalid COMMAND → hint ES | **PASS** |
| 10 Entry docs → operator | **PASS** |
| 11 Make operator/ensayo/checklist/next | **PASS** |
| 12 Rails fusion OFF · ml_product_go false · GO_Q partial | **PASS** |

### Humo relaunch (PowerShell)

```text
$env:PYTHONPATH = "."
python -m wildfire_front                 → MODO OPERARIO · AMARILLO
python -m wildfire_front ensayo -q       → exit 0 · sello 4/4
python -m wildfire_front next --json     → go_q_complete=false · eng_ready
python -m wildfire_front checklist --json → 7/7 · loop_done · session_all_four_ok
pytest tests/test_operator_ux.py tests/test_cli_teach_product.py -q → 47 passed
```

**Files changed:** none (verify-only).  
**Residual humano:** H1 only — `docs/H1_GO_Q_RUNBOOK.md`. Loop eng **no reabierto**.

---

## Validación final (criterio de paro)

### Operario simulado (script mental)

1. Lee START_HERE → único comando `operator` (&lt;30 s)  
2. Ve semáforo **AMARILLO** + plain “camino listo; GO_Q falta humano”  
3. Ejecuta actos 1→4 con `operator do --act N` sin abrir scripts  
4. En acto 2/3 entiende ABSTAIN como feature  
5. En acto 4 ve `replay_ok` y el aviso de que **no** cierra GO_Q  
6. Lee bloque “Qué falta para GO_Q”: tercero + acta + `record_h1_demo_complete.py`

### Checklist automático (revalidado 2026-08-04 loop-engineering)

```text
$ python -m wildfire_front operator checklist
=== Checklist operario ===
Semáforo: VERDE  ·  7/7
  [OK] … entrada …
  [OK] … semáforo …
  [OK] Acto 1 … note: artefacto listo (ejecuta do --act …)
  [OK] Acto 2 … note: artefacto listo …
  [OK] Acto 3 … note: decide siempre ejecutable …
  [OK] Acto 4 … note: artefacto listo …
  [OK] GO_Q … note: sabe el hueco (GO_Q aún partial)

Operario eng-path LISTO: 4 actos ejecutables + sabe GO_Q.
Loop UX eng CERRADO (H1 humano sigue pendiente).
Honestidad: pass en actos 1/2/4 = artefacto en disco … GO_Q complete solo con H1.
loop_done=true · n_pass=7/7
```

### Humo actos (revalidación)

```text
operator do --act 1 --no-build  → 0
operator do --act 2 --no-build  → 0 + ABSTAIN plain
operator do --act 3             → 0 + ABSTAIN feature
operator do --act 4 --no-build  → 0 · replay_ok=True
operator do --all               → 4/4 OK (iter 8) + sello (iter 9)
operator do --all --json        → JSON puro wfd_operator_do_all_v1 (iter 9)
operator do                     → exit 2, mensaje amable ES
operator checklist              → session_ran si hay sello
```

### Tests

```text
pytest tests/test_operator_ux.py tests/test_cli_teach_product.py -q
→ 47 passed (revalidación #12–#13 · plateau iters 1–17)
```

### Honestidad (rails no tocados)

| Rail | Valor |
|------|--------|
| GO_MES | true |
| GO_Q | **partial** (humano H1/M3.2) |
| field_ops ML live fusion | OFF |
| ml_product_go | false |
| Inventar GO_Q=true | **prohibido** (tests) |
| Checklist ≠ demo H1 | **explícito** (`honesty` + `basis`) |

### Status docs sincronizados

| Doc | Evidencia |
|-----|-----------|
| `docs/PROJECT_STATUS.md` | Operator UX en “What is done” |
| `MEMORY.md` | Operator UX en “What works” |
| `README.md` | Entrada = operator |
| `docs/START_HERE.md` | Entrada = operator (iter 4) |
| `CHANGELOG.md` | Operator UX mode |

---

## Estado objetivo vs logrado

| Objetivo | Estado |
|----------|--------|
| Un solo comando modo operario | **Sí** `wildfire-front operator` |
| Semáforo verde/amarillo/rojo | **Sí** |
| Por qué se calla en lenguaje normal | **Sí** `explain-abstain` + decide nota |
| Solo 4 pasos | **Sí** Ver → Callarse → Decidir → Probar |
| Saber qué falta para GO_Q | **Sí** bloque dedicado + runbook/acta |
| Entrada en README/START_HERE | **Sí** (iter 4–5) |
| Checklist no miente “demo hecha” | **Sí** (iter 6 basis/honesty) |
| Curso + H1 runbook → operator | **Sí** (iter 7) |
| Ensayo 4 actos en un comando | **Sí** `do --all` / `make operator-path` (iter 8) |
| Sello de ensayo + JSON limpio | **Sí** session stamp + `do --all --json` (iter 9) |
| Guion 30 min + guía comandos → operator | **Sí** (iter 10) |
| Sello merge (do --act no borra --all) | **Sí** (iter 11) |
| Alias `operador`/`ops` + portal no regresa | **Sí** (iter 12) |
| CLI vacío → operator; show_all eng-only | **Sí** (iter 13) |
| Ensayo compacto + one-pager operator + alias ensayo | **Sí** (iter 14) |
| operator next + hint en COMMAND inválido | **Sí** (iter 15) |
| Top-level next/go_q/checklist + Make ensayo | **Sí** (iter 16) |
| Ensayo sin scoreboard duplicado | **Sí** (iter 17) |
| Plateau eng (residual = H1) | **Sí** (revalidación #12–#13 holds) |

---

## Archivos tocados (resumen)

| Archivo | Cambio |
|---------|--------|
| `wildfire_front/product/operator_ux.py` | Board, lights, checklist, ABSTAIN plain, setup, basis/honesty |
| `wildfire_front/cli_teach.py` | Comando `operator` + `do` / checklist / explain-abstain |
| `wildfire_front/cli.py` | Dispatch + nota ABSTAIN en decide + epilog |
| `wildfire_front/product/teach_path.py` | Teach apunta a operator |
| `docs/START_HERE.md` | Entrada operario primero |
| `docs/CHEATSHEET_DEMO_12MIN.md` | Actos vía operator |
| `docs/CURSO_WFD_PARA_DESCONOCIDOS.md` | §8.3 + Apéndice A operator (iter 7) |
| `docs/H1_GO_Q_RUNBOOK.md` | Prep operator (iter 7) |
| `README.md` | Entrada operario (iter 5) |
| `docs/PROJECT_STATUS.md` / `MEMORY.md` | Sync resultados |
| `tests/test_operator_ux.py` | Contrato CLI/UX + honesty + entry-docs + do --all |
| `Makefile` | `operator` · `operator-path` · `operator-checklist` (iter 8) |
| `docs/OPERATOR_UX_LOOP_LOG.md` | Este log |

---

## Qué queda **fuera** del loop eng (no es fricción UX de código)

1. **H1 real** — demo con tercero externo + acta firmada → cierra GO_Q  
2. Rebuild pesado multi-CCAA en CI en cada commit (artefactos locales bastan con `--no-build`)  
3. Unificar *todos* los scripts del repo bajo operator (solo los 4 actos de demo)  
4. Portal HTML / Commander — siguen siendo lab/eng, no puerta de operario  

---

## Cómo reabrir el loop

Si un operario real se atasca:

1. Añadir entrada en este log: **Iteración N**  
2. Una fricción  
3. Cambio mínimo  
4. `operator checklist` + pytest  
5. No tocar rails de honesty  

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front operator
python -m wildfire_front operator checklist
python -m pytest tests/test_operator_ux.py -q
```

## Implement pass 2026-08-05 (/implement full plan)
- Verified criteria 1–12: PASS
- pytest: 47 passed
- Residual human: H1 only
