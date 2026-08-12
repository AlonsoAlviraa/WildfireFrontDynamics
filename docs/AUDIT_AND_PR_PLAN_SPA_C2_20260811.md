# Auditoría + plan de 10 PRs — SPA Industrial C2 & producto

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-11 |
| **Scope** | Product SPA (`app` / `spa` / `console`) · dual-mode industria · residual producto |
| **SSOT gates** | `docs/CURRENT_STATE.md` · B1–B6: `docs/BOTTLENECKS_B1_B6_STATUS.md` |
| **SPA SSOT** | `docs/APP.md` · `docs/design/EMERGENCY_UX_INDUSTRY.md` · `docs/design/stitch_wfd_industrial/` |

---

## 1. Auditoría (estado real)

### 1.1 Una línea

**GO_MES true · GO_Q partial (H1 humano) · fusion OFF · SPA industrial C2 shippable en eng · residual = human + datos + depth de producto, no “falta HTML basico”.**

### 1.2 Qué está verde (eng)

| Superficie | Evidencia | Veredicto |
|------------|-----------|-----------|
| Schema SPA | `wfd_product_app_v1` | OK |
| Catálogo fires | 6 IF; cmds `rebuild/map/status/decide/acta` | OK |
| CTAs producto | 35 acciones, 0 sin plain language | OK |
| Intake nuevo IF | 6 pasos | OK |
| Dual-mode Fácil/Pro | `mode-toggle` + hide `.adv` | OK |
| Primary acts | Estado · Decidir · Acta (copy-bound) | OK |
| Shell C2 | `#0B1220`, map-first, IBM Plex, taps 48px | OK |
| CLI | `app` + aliases `spa`/`console` + `--serve` :8766 | OK |
| Rails | fusion OFF · not dispatch · no GO_Q invent | OK |
| Tests SPA | `test_product_app` + `spa_layout` + `plain_language` | 16+ verdes (último goal) |
| Artefacto | `outputs/app/index.html` regenerable | OK |

### 1.3 Gates producto (no mentir)

| Gate | Valor | Control eng |
|------|-------|-------------|
| GO_ENG | true | sí |
| GO_MES | true | sí (mínimo) |
| GO_MES+ | false | parcial (O5 2º A / O2) |
| GO_Q | **partial** | **no** — H1 demo+acta |
| field_ops fusion | **OFF** | no flip sin promote humano |
| Tobarra KEEP | **KILL** | no thrash sin datos nuevos |

### 1.4 Deuda y huecos (auditoría crítica)

| ID | Hallazgo | Severidad | Tipo |
|----|----------|-----------|------|
| **G1** | SPA **estática**: cambiar IF = rebuild/regenerar (no switch en vivo) | media | UX/producto |
| **G2** | Primary acts solo **copian CLI**; no ejecutan ni pegan resultado en UI | media | UX (correcto para air-gap; falta “feedback de acto”) |
| **G3** | `--role` no está en la barra (solo CLI) | baja-media | UX |
| **G4** | Basemap Carto/CDN: **offline real incompleto** (geo local sí, tiles no) | media | ops/demo |
| **G5** | HTML monstruo en `app_spa_html.py` (mantenibilidad) | media | eng |
| **G6** | `api_server` / `serve-decide` **desacoplado** de la SPA (dos mundos) | media | arquitectura |
| **G7** | Sin CI gate explícito “SPA markers” en pipeline principal (si solo se corre subset) | baja | calidad |
| **G8** | Portal (`docs/PORTAL.html`) / commander / app: **tres superficies** de demo | media | producto/sell |
| **G9** | Multi-IF prebuild / selector sin regenerar: no existe | media | producto |
| **G10** | H1 / GO_Q / 2º grade A / O2: **fuera de SPA** pero bloquean “vender cerrado” | crítica | human/data |

### 1.5 Rails no negociables (cualquier PR)

- No despacho táctico  
- field_ops ML fusion **OFF**  
- No inventar GO_Q  
- IoU ≠ ROS · NRT ≠ perímetro oficial  
- ABSTAIN es feature  

---

## 2. Estrategia de los 10 PRs

Orden: **riesgo bajo → valor demo → depth** · cada PR mergeable solo · tests en el mismo PR · no mezclar H1 humano en eng.

```text
PR01 ──► PR02 ──► PR03          (calidad / maintain)
  │
  ├──► PR04 ──► PR05            (SPA depth: role + act feedback)
  │
  ├──► PR06 ──► PR07            (serve + optional live card bridge)
  │
  ├──► PR08                     (multi-fire / no full rebuild)
  │
  ├──► PR09                     (demo surface unify)
  │
  └──► PR10                     (CI + release gate SPA)
```

**Fuera del stack de 10 (tracked, no eng-solo):** H1 agenda, O2 FOI, 2º grade A datos, ML Tobarra reopen.

---

## 3. Plan de 10 PRs

### PR01 — `docs(audit): SSOT auditoría SPA C2 + residual gates`

| | |
|--|--|
| **Problema** | CURRENT_STATE as-of 08-10; APP vs senior/cream residual en cabeza; falta SSOT “siguiente” |
| **Cambio** | Mergear este doc en SSOT; bump `CURRENT_STATE` as-of; puntero SPA C2; tabla G1–G10 |
| **Tests** | n/a o link check |
| **Done when** | `docs/CURRENT_STATE.md` cita SPA industrial + GO_Q partial + este plan |
| **Risk** | bajo |

### PR02 — `test(spa): CI pack SPA industrial (markers + catalog cmds)`

| | |
|--|--|
| **Problema** | G7 — riesgo de regresión silenciosa si CI no corre el trio SPA |
| **Cambio** | Makefile/`pytest` marker `spa` o job CI que corra `test_product_app` + `spa_layout` + `plain_language`; assert `acta_cmd` en todos los fires |
| **Tests** | los del pack + 1 test parametrizado cmds |
| **Done when** | `make test-spa` o CI step verde en PR |
| **Risk** | bajo |

### PR03 — `refactor(spa): split HTML renderer modules`

| | |
|--|--|
| **Problema** | G5 — `app_spa_html.py` monolítico, hard to review |
| **Cambio** | Extraer CSS/JS/HTML partials o builders (`_css()`, `_shell()`, `_js()`) sin cambiar UX |
| **Tests** | golden markers (`#0B1220`, `primary-acts`, leaflet) + snapshot size band |
| **Done when** | diff funcional 0 en HTML generado (o hash estable de markers) |
| **Risk** | medio (solo si se rompe escape/JSON) |

### PR04 — `feat(spa): role switcher in top bar`

| | |
|--|--|
| **Problema** | G3 — `--role` invisible en UI |
| **Cambio** | Segment `operator|field|lab|decision` en top; en Pro muestra rebuild con `--role`; en Fácil solo label; payload `role` + brief playbook hints cortos |
| **Tests** | parse/render por role; no inventar gates |
| **Done when** | cambiar rol actualiza chips/next sin mentir GO_Q |
| **Risk** | bajo-medio |

### PR05 — `feat(spa): primary-act result panel (copy + last-run stub)`

| | |
|--|--|
| **Problema** | G2 — actos copian y el usuario no ve “qué pasó” |
| **Cambio** | Panel “Último acto” con cmd copiado + timestamp + hint; opcional leer `outbox/*` ya existente (card/ops) al rebuild; **no** shell-exec desde browser |
| **Tests** | DOM markers + payload fields |
| **Done when** | Estado/Decidir/Acta dejan rastro visible en UI tras copiar |
| **Risk** | bajo |

### PR06 — `feat(app): harden --serve (bind, index, SPA headers)`

| | |
|--|--|
| **Problema** | `--serve` existe; falta hardening demo (loopback-only assert, CORS no, path traversal) |
| **Cambio** | Bind 127.0.0.1 only · serve solo `output_dir` · Content-Type · test path escape reject |
| **Tests** | HTTP smoke + security path |
| **Done when** | no serve 0.0.0.0 por defecto; doc APP.md actualizado |
| **Risk** | bajo |

### PR07 — `feat(spa): optional live Decision Card bridge (serve-decide)`

| | |
|--|--|
| **Problema** | G6 — SPA y `serve-decide` no se hablan |
| **Cambio** | Flag `--bridge-decide URL` o Pro-mode “Refrescar card” que haga GET/POST local a `serve-decide` **solo si** bridge flag; fallback silencioso a card embebida; honesty: no fusion |
| **Tests** | mock HTTP · offline fallback |
| **Done when** | demo puede levantar `serve-decide` + SPA y ver card sin re-build full si bridge on |
| **Risk** | medio |

### PR08 — `feat(spa): multi-fire catalog pack (prebuild N fires)`

| | |
|--|--|
| **Problema** | G1/G9 — switch de IF requiere regenerar |
| **Cambio** | `app --all-fires` o `--pack-fires` genera payload multi-IF (cap N=8) con capas slim; selector cambia hero/map layers **en cliente** sin CLI |
| **Tests** | payload size cap · selector JS · no OOM |
| **Done when** | demo de 2–3 IF sin re-ejecutar Python entre clicks |
| **Risk** | medio-alto (payload size) |

### PR09 — `feat(demo): unify entry — app is the only third-party surface`

| | |
|--|--|
| **Problema** | G8 — PORTAL / commander / app compiten en la cabeza del demo |
| **Cambio** | PORTAL link primario → `outputs/app`; commander marcado legacy; START_HERE one path; cheatsheet 12 min actualizado a C2 primary acts |
| **Tests** | doc grep / portal build script |
| **Done when** | un solo “open this for third party” en START_HERE |
| **Risk** | bajo (docs+links) |

### PR10 — `chore(release): SPA industrial gate in check_release_flags / scorecard`

| | |
|--|--|
| **Problema** | Release flags no mencionan SPA C2 como superficie sellable |
| **Cambio** | `check_release_flags` o scorecard: SPA markers present · fusion OFF · GO_Q not true without H1 · optional `outputs/app` freshness |
| **Tests** | `test_check_release_flags` update |
| **Done when** | release script falla si SPA regresa a shell roto o inventa GO_Q |
| **Risk** | bajo-medio |

---

## 4. Mapa PR → gap

| PR | Cierra |
|----|--------|
| 01 | SSOT / drift docs |
| 02 | G7 |
| 03 | G5 |
| 04 | G3 |
| 05 | G2 |
| 06 | serve hardening |
| 07 | G6 |
| 08 | G1, G9 |
| 09 | G8 |
| 10 | release honesty |

**No cerrados por estos 10:** G10 (H1, O2, 2º A, ML data).

---

## 5. Orden de merge recomendado (1–2 días eng)

| Día | PRs | Por qué |
|-----|-----|---------|
| D1 AM | 01, 02, 03 | base limpia + CI |
| D1 PM | 04, 05, 06 | UX actos + serve seguro |
| D2 AM | 07, 08 | depth + multi-fire (el valor demo) |
| D2 PM | 09, 10 | sell path + release gate |

Si solo hay **medio día**: **02 + 05 + 08 + 09** (máximo impacto demo).

---

## 6. Criterios de “no empezar” un PR

- Requiere fusion ON  
- Requiere declarar GO_Q true sin H1  
- Requiere reabrir Tobarra KEEP sin datos nuevos  
- Scope > 1 PR sin DAG  

---

## 7. Comandos de verificación (post-stack)

```powershell
$env:PYTHONPATH = "."
python -m pytest tests/test_product_app.py tests/test_spa_layout.py tests/test_plain_language_app.py -q
python -m wildfire_front app --fire _sla_measure --open
python -m wildfire_front app --fire _sla_measure --serve
python scripts/check_release_flags.py
```

---

## 8. Residual humano / datos (fuera de los 10 PRs)

| Item | Owner | Next action |
|------|-------|-------------|
| H1 demo+acta → GO_Q | humano | `docs/H1_*` + calendar |
| 2º grade A (B4) | datos + eng | Hellín re-score / 2º IF |
| O2 nacional (B5) | externo | FOI / partner |
| Chain multi-day IF | data+lab | REQUEST_DATA only |

---

*Fin auditoría (2026-08-11).*

### Addendum — post stack (Live Ops)

Los PR01–PR10 de SPA C2 quedaron **eng-done** en gran medida. La siguiente mejora grande fue el **Live Ops Demo Kernel** (`app --serve` / `--demo-day`, `POST /live/v1/*`). Plan de aterrizaje + residual: sesión plan *Post–Live Ops PR stack* (A1–A4 land · B1–B5 residual: decide honesty, panel, replay, release flags, START_HERE).

**No cierra G10** (H1 humano / O2 / 2º grade A).
