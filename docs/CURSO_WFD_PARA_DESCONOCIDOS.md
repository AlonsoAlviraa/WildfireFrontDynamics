# Curso WildfireFrontDynamics — para alguien que no conoce el proyecto

**Idioma:** español · **Nivel:** cero conocimiento previo  
**Duración orientativa:** 2–3 horas de lectura + práctica (o 30 min solo módulos 0–2)

Este documento explica **qué es cada cosa**, **para qué sirve**, **cómo usarla** y **qué no debes creer ni decir**. Está pensado como si se lo contaras a un desconocido inteligente.

---

# Módulo 0 — El problema en el mundo real (10 min)

## ¿Qué problema intenta atacar este software?

En un incendio forestal, la gente de sala (y a veces investigadores) necesita respuestas como:

- ¿Hacia dónde avanza el frente?
- ¿A qué velocidad va (orden de magnitud)?
- ¿Qué perímetro “oficial” o de referencia hay?
- **¿Puedo confiar en esta estimación o debo callarme?**

La tentación de la tecnología es **inventar un mapa bonito siempre**.  
Este proyecto hace lo contrario: **prefiere HOLD o ABSTAIN** (esperar / no afirmar) cuando faltan datos o la fiabilidad es baja.

## Una frase de producto (la única que debes memorizar)

> **Apoyo a la decisión multi-CCAA:** térmico donde hay ancla real, perímetro oficial de Junta donde hay datos, y **abstención cuando no se puede mentir**. El ML de máscaras es laboratorio experimental, no despacho táctico.

## Qué NO es

| No es | Por qué |
|-------|---------|
| Un sistema de “apagar incendios con IA” | No manda medios ni sustituye al mando |
| Un GPS táctico de ROS en tiempo real garantizado | Sin termografía o ancla, no inventa Vp |
| “Copernicus pero más guapo” | El valor es la **postura de decisión** + honestidad |
| Un producto que ya da GO en campo con ML fusionado | `field_ops` **no** fusiona ML en vivo por defecto |

---

# Módulo 1 — Mapa mental del repositorio (15 min)

Imagina el repo como una casa con varias habitaciones:

```
WildfireFrontDynamics/
├── wildfire_front/     ← CÓDIGO del producto (biblioteca Python)
├── scripts/            ← Herramientas de línea de comandos (demos, packs, eval)
├── config/             ← Políticas de decisión (JSON)
├── models/             ← Catálogo y pesos ML (a veces locales, no siempre en git)
├── data/               ← Datos de ejemplo / anchors / open_if crudos
├── outputs/            ← Resultados generados (demos, packs, mapas) — a menudo gitignored
├── docs/               ← Documentación, portal HTML, informes, diseños
├── tests/              ← Pruebas automáticas
├── artifacts/          ← Parches NPZ de entrenamiento/eval (locales, pesados)
└── README / START_HERE ← Puertas de entrada
```

## Las dos “personalidades” del producto (dual product)

Hay **dos productos** que no se deben mezclar en la cabeza:

| Producto | ID típico | Qué produce | Analogía |
|----------|-----------|-------------|----------|
| **Ops / dinámica de frente** | `front_dynamics_v1` | Velocidad de frente (ROS), sectores, briefs a partir de **termografía / geometría temporal real** | El reloj de la sala cuando hay dron |
| **ML / máscara de propagación** | `clm_ensemble_v34` | Predicción de **máscara** (quién se quema “mañana” en el sentido del protocolo de patches) + **confianza de parche** | Un modelo de investigación con termómetro de duda |

**Solo se “juntan” en la Decision Card** (la ficha de decisión).  
**Nunca** se entrena el ML con etiquetas inventadas por la política de la Card.

## La Decision Card (el corazón comercial)

Una **tarjeta de decisión** responde con una de tres posturas:

| Postura | Significado humano |
|---------|-------------------|
| **GO** | Hay suficiente señal confiable (según la política) para una postura proactiva de **monitoreo / apoyo** — **no** es “manda el helicóptero porque lo dice la IA” |
| **HOLD** | Hay información, pero no basta para GO; sigue mirando |
| **ABSTAIN** | Faltan datos o la fiabilidad es mala; **mejor callarse** |

La Card también guarda **razones**, **fuentes** (ops / open / ml) y **disclaimers**.

## Políticas (`config/decision_policies.json`)

| Política | Para qué | ML live en fusión |
|----------|----------|-------------------|
| `field_ops` | Más estricta, “sala” | **OFF** (no fusiona ML en vivo) |
| `research_open` | Lab / demos open | Puede ser experimental ON |
| `default` | Compromiso intermedio | Normalmente OFF |

**Regla de oro:** en campo serio, piensa en `field_ops`. En lab, `research_open`.

---

# Módulo 2 — Tour guiado: abre y mira (30 min)

Haz esto **en orden**. No hace falta entender el código todavía.

## 2.1 Preparar la terminal (Windows PowerShell)

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."
```

(En Linux/mac: `export PYTHONPATH=.`)

## 2.2 Demo multi-CCAA (la “cara comercial”)

```powershell
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html
```

**Qué estás viendo:** tres historias con el **mismo criterio de calidad**:

| Sitio | CCAA | Pista | Qué demuestra |
|-------|------|-------|----------------|
| **Tobarra** | Castilla-La Mancha | **OPS** (termografía + ancla) | Velocidad de frente con datos de dron/ops |
| **Níjar** | Andalucía | **OPEN** (REDIAM) | Perímetro oficial / institucional |
| **Caminomorisco** | Extremadura | **OPEN** (RAI) | Otro perímetro Junta / INFOEX |

**Idea de venta:** no “funciona en toda España”, sino “**mismos gates** en tres contratos de datos distintos”.

## 2.3 Piloto de honestidad (Decision Card multi-fuente)

```powershell
python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot
start outputs\pilot_honesty_card\index.html
```

También se genera / actualiza el informe:

- `docs/PILOT_HONESTY_CARD.md`

**Qué mirar en el portal:**

1. Tres tarjetas de sitio  
2. Pastillas **GO / HOLD / ABSTAIN**  
3. Contraste **research_open** vs **field_ops** (“se calla” cuando field_ops es más estricto)  
4. Barra de disclaimers (texto corto, no un muro)

**Ejemplo de lectura (fixtures offline):**

| Sitio | research_open | field_ops | Cifra típica |
|-------|---------------|-----------|--------------|
| Tobarra | puede ir a **GO** | a menudo **ABSTAIN** | ROS ~ m/min de ops |
| Níjar | **HOLD** | **HOLD** | ha REDIAM |
| Caminomorisco | **HOLD** | **HOLD** | ha RAI |

Eso **no es un bug**: es el mensaje del producto (“en sala no inventamos fiabilidad”).

## 2.4 Demo ML offline (sin pesos de red)

```powershell
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold
python scripts\run_ml_live_card_demo.py --mode offline --scenario abstain
```

Salida típica en `outputs/ml_live_card_demo/`:

- `ml_prediction.json` — predicción / métricas live  
- `decision_card.json` — la Card  
- `README.md` — resumen humano  

## 2.5 Portal general del repo

```powershell
python scripts\show_all.py
# o abrir docs\PORTAL.html
```

Vista de “qué hay en el proyecto” (números, enlaces). Complementa, no sustituye, la demo multi-CCAA.

## 2.6 Commander (sala de mando visual)

```powershell
python scripts\build_commander_app.py
start docs\commander\index.html
```

App más “espectáculo”: packs, teclas 1–4, radio, fullscreen. Útil para impresión visual; el argumento de producto sigue siendo la Card + gates.

---

# Módulo 3 — Glosario (léelo cuando te pierdas)

| Término | Significado sencillo |
|---------|----------------------|
| **ROS** | Rate of spread: velocidad de propagación del frente (p. ej. m/min) |
| **Vp** | A menudo “velocidad de propagación” en lenguaje de parte; **no inventar** sin ancla |
| **LWIR / térmico** | Imagen infrarroja de onda larga (calor); base del track OPS |
| **Perímetro / área quemada** | Geometría del incendio; la “oficial” suele venir de la Junta (REDIAM, RAI…) |
| **FIRMS** | Hotspots satelitales NASA; un **casco de puntos ≠ área quemada oficial** |
| **dNBR** | Índice de severidad quemada por satélite; proxy, no parte oficial |
| **Pack open_if** | Carpeta con mapa, scorecard, brief de un incendio “open” industrializado |
| **Scorecard / gates** | Lista de comprobaciones PASS / SKIP / FAIL (honestidad industrial) |
| **Ancla INFOCAM** | Cifra operativa de referencia (ha, Vp) de parte/fuente operativa |
| **Holdout VAL/TEST** | Particiones del dataset ML: se ajusta en VAL, se reporta en TEST |
| **IoU** | Intersección sobre unión: calidad de solape de máscaras (0–1) |
| **ECE** | Error de calibración: ¿la “confianza 80%” acierta ~80% de las veces? |
| **U1** | Gate de producto sobre incertidumbre (¿la confianza ayuda a seleccionar mejores parches?) |
| **Calibrador** | Modelo chico que convierte señales de duda en probabilidad de “este parche es fiable” |
| **Abstain** | El sistema se niega a afirmar |
| **PSB** | Progressive Synthetic Burn: simulación geométrica bajo techo REDIAM (lab / demo) |
| **CCAA** | Comunidad Autónoma |

---

# Módulo 4 — Los tres “carriles” de datos

## Carril A — OPS (oro térmico)

**Origen:** secuencias térmicas aéreas + metadatos + a veces ancla operativa (ej. Tobarra 2024).

**Salida típica:**

- ROS multi-método  
- Sectores cabeza/flanco/cola  
- Envolventes cortas  
- Grade de calidad A/B/C  

**Entrada en código:** `wildfire_front/front_dynamics.py`, `scientific_ops.py`, incident pipeline.

**Regla:** sin termografía real **no se inventa** un ROS táctico “de sala”.

## Carril B — OPEN industrial (perímetros de Junta / open)

**Origen:**

- Andalucía: **REDIAM**  
- Extremadura: **RAI** (Registro de Áreas Incendiadas)  
- (Otros: CEMS, CyL abiertos, etc. cuando existan packs)

**Salida típica de un pack** (`outputs/open_if/...`):

- `map.html`  
- scorecard industrial  
- métricas O2 (ha oficiales)  
- brief operador  
- a veces FIRMS / dNBR (con SKIP si no aplica)

**Scripts clave:**

- `scripts/build_and_if_pack.py` / `build_ext_if_pack.py`  
- `scripts/verify_*_industrial_e2e.py`  

**Regla:** ha de perímetro oficial ≠ hull FIRMS; `vp_invented` debe ser honesto.

## Carril C — ML lab (máscaras + incertidumbre)

**Origen:** patches NPZ (protocolo tipo NDWS/CLM holdout), pesos ensemble `clm_ensemble_v34`.

**Salida:**

- Máscara predicha  
- Confianza de parche (Head A)  
- Scorecard U1 en `docs/ML_PRODUCT_SCORECARD.json`  

**Números honestos de pitch (lab, no campo):**

| Métrica | Orden de magnitud | Uso |
|---------|-------------------|-----|
| IoU TEST (eval U1) | ~0.86 | Calidad de máscara en holdout **evaluado** |
| Selective IoU @80% | ~0.90 | Si te quedas con el 80% más confiado |
| ECE | ~0.15 | Calibración aún imperfecta |
| Catalog 0.8963 | holdout publicado | **Solo provenance**, no “certeza en vivo” |

**Regla:** no digas “el fuego va a X km/h porque el IoU es 0.89”.

---

# Módulo 5 — Cómo se toma una decisión (Decision Card)

## Flujo conceptual

```
Fuentes
  ├─ ops_metrics   (ROS, grade, n_frames…)
  ├─ open_metrics  (ha, timeline, honesty flags…)
  └─ ml_live       (confianza de parche, abstain…)
        │
        ▼
  Políticas (field_ops / research_open / …)
        │
        ▼
  build_decision_card / decide_service
        │
        ▼
  GO | HOLD | ABSTAIN + reasons + disclaimers
```

## CLI mínimo

```powershell
python -m wildfire_front decide
# sin datos → casi seguro ABSTAIN (bien)

python -m wildfire_front decide --list-policies

python -m wildfire_front decide --use-ml-v34 --policy field_ops
```

API local (avanzado):

```powershell
python -m wildfire_front serve-decide --port 8765
```

**Seguridad:** la API HTTP **no** debe aceptar “ops inventados” en JSON sin sandbox de ficheros (remediación de auditoría).

## Lectura de una Card

Cuando veas un JSON de Card, busca:

1. `decision` o postura  
2. `confidence`  
3. `sources` / flags `available`, `abstained`, `actionable`, `weight`  
4. `reasons`  
5. `disclaimers`  

Si `field_ops` da **ABSTAIN** y `research_open` da **GO**, no es incoherencia: son **políticas distintas**.

---

# Módulo 6 — Carpetas importantes una a una

## `wildfire_front/` (código de producto)

| Subcarpeta / módulo | Qué es |
|---------------------|--------|
| `product/` | Decision Card, API decide, políticas, confidence |
| `ml/` | Dataset, U-Net/ensemble, uncertainty, U1, scorecard |
| `open_if/` | Lógica de packs open (timeline, dNBR queue, anchors guard) |
| `progressive_burn/` | Simulación de quemado progresivo (PSB) |
| `incident/` | Pipeline de incidente / reliability de corrida |
| `front_dynamics.py` | Corazón del ROS ops |
| `cli.py` | Comandos `python -m wildfire_front ...` |

## `scripts/`

| Script | Para qué lo usas |
|--------|------------------|
| `build_demo_multi_ccaa.py` | Regenerar portal de venta multi-CCAA |
| `run_pilot_honesty_card.py` | Piloto 3 sitios + HTML + informe honesty |
| `run_ml_live_card_demo.py` | Demo ML → Card (offline/live) |
| `predict_spread.py` | Inferencia de máscaras ML |
| `promote_ml_live_fusion.py` | Checklist de promote (no flipa field_ops) |
| `build_*_if_pack.py` | Construir packs open AND/EXT |
| `verify_*_industrial_e2e.py` | Comprobar gates de packs |
| `show_all.py` | Abrir portal general |
| `build_commander_app.py` | App commander |

## `docs/`

| Doc / carpeta | Para qué |
|---------------|----------|
| `START_HERE.md` | Arranque 2 minutos |
| `CURSO_WFD_PARA_DESCONOCIDOS.md` | **Este curso** |
| `PILOT_HONESTY_CARD.md` | Informe piloto ≤2 págs |
| `PORTAL.html` | Portal HTML del repo |
| `ML_PRODUCT_SCORECARD.json` | Claim lab ML |
| `ML_U1_PROMOTE_RECORD.json` | Registro de promote U1 |
| `ML_LIVE_ABSTAIN_ECE_NOTE.md` | Nota abstain / ECE |
| `design/` | Diseños técnicos (ML focus, piloto, auditoría…) |
| `commander/` | HTML de sala de mando |
| `funding/` | Playbook de ayudas / partners |

## `data/` y `outputs/`

- **`data/`**: inputs semi-estables (anchors, open_if crudos, etc.)  
- **`outputs/`**: resultados regenerables (a menudo **no** están en git; se construyen con scripts)

## `models/`

Catálogo de productos ML y, si existen localmente, pesos y calibrador de incertidumbre.  
Los tests CI suelen marcar `requires_weights` cuando no hay pesos.

## `tests/`

La red de seguridad. Comandos típicos:

```powershell
python -m pytest tests/ -q -m "not slow and not requires_weights"
python -m pytest tests/test_pilot_honesty_card.py -q
```

---

# Módulo 7 — Casos de uso: “quiero hacer X”

## Soy nuevo y solo quiero ver la demo

1. `build_demo_multi_ccaa.py` → abrir `index.html`  
2. `run_pilot_honesty_card.py --fixture-root tests/fixtures/pilot` → abrir portal piloto  
3. Leer `docs/PILOT_HONESTY_CARD.md`

## Voy a hacer una call de 12 minutos

1. Ensayar el guion del portal multi-CCAA  
2. Abrir piloto honesty en segunda pestaña (“se calla”)  
3. Frase de claim del Módulo 0  
4. No mencionar 0.8963 como “precisión del fuego en vivo”

## Soy desarrollador y quiero un Decision Card

```powershell
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold
# o
python -m wildfire_front decide --help
```

## Quiero un pack open de un incendio AND/EXT

1. Datos en `data/open_if/...`  
2. Script `build_and_if_pack` / `build_ext_if_pack`  
3. Verificar con `verify_*_industrial_e2e`  
4. Integrar en demo solo si gates honestos

## Quiero “activar el ML en fusión de campo”

**No lo hagas** sin checklist de promote y decisión humana.  
`field_ops.allow_ml_live_in_fusion` está **OFF** a propósito.  
`research_open` es lab.

## Quiero entrenar / reentrenar el ensemble

Eso es un proyecto aparte (Kaggle/GPU, pesos, holdout).  
No es necesario para enseñar el piloto.  
Entrada conceptual: `docs/design/ML_FOCUS_PRODUCT_V1.md`, `models/catalog.json`.

---

# Módulo 8 — Honestidad: las 10 mandamientos del proyecto

1. **No inventes ROS/Vp táctico** sin termografía o ancla operativa creíble.  
2. **FIRMS hull ≠ quemado oficial.**  
3. **Ops ≠ ML** en la cabeza y en el pitch.  
4. **ABSTAIN es una feature**, no un fallo.  
5. **0.8963 es provenance de catálogo**, no certeza en vivo.  
6. **U1 ~0.86 es lab holdout**, no “el incendio de Níjar”.  
7. **field_ops no fusiona ML live** por defecto.  
8. **Faltan flags de honesty en un pack** → no asumas “todo limpio”.  
9. **HTTP decide no acepta ops inventados** en el cuerpo.  
10. **Un email de CCAA no obliga a más código** si ya puedes demoar con AND/EXT/CLM.

---

# Módulo 9 — Arquitectura en una servilleta

```
                    ┌─────────────────────┐
   Dron LWIR  ───►  │  front_dynamics_v1  │──► ROS, grade, ops JSON
                    └──────────┬──────────┘
                               │
   Junta SHP  ───►  open_if packs ──────────► ha, scorecard, map.html
                               │
   NPZ + pesos ─►  clm_ensemble_v34 ───────► máscara + conf parche
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Decision Card     │
                    │  GO / HOLD / ABSTAIN│
                    └─────────────────────┘
                               │
              portal demo · piloto HTML · API decide
```

**PSB (progressive burn):** lab geométrico bajo techo de perímetro (p. ej. REDIAM); útil para demos de etapas; **no** es un incendio real medido minuto a minuto.

---

# Módulo 10 — Hoja de ruta de aprendizaje (si tienes una semana)

| Día | Objetivo | Acción |
|-----|----------|--------|
| 1 | Ver el producto | Módulos 0–2 (demos) |
| 2 | Hablar el idioma | Módulo 3 + releer piloto |
| 3 | Entender datos | Módulo 4 (OPS vs OPEN vs ML) |
| 4 | Decision Card | Módulo 5 + CLI `decide` |
| 5 | Orientarse en código | Módulo 6 (solo carpetas) |
| 6 | Caso práctico | Enseñar a otra persona con el guion 12 min |
| 7 | Límites | Módulo 8 de memoria |

---

# Módulo 11 — FAQ del desconocido

**P: ¿Por qué a veces “falla” y no da GO?**  
R: Porque está diseñado para **no mentir**. HOLD/ABSTAIN es el valor.

**P: ¿Sirve sin dron?**  
R: Sí, en modo open (perímetros Junta + satélite con SKIP honestos). No tendrás ROS táctico de frente térmico.

**P: ¿El ML predice dónde irá el fuego mañana en España entera?**  
R: No. Predice máscaras bajo un **protocolo de patches** de laboratorio y da fiabilidad de parche. No es un modelo meteorológico operativo nacional.

**P: ¿Qué abro en una reunión de 5 minutos?**  
R: `outputs/demo_multi_ccaa/index.html` + una frase del Módulo 0.

**P: ¿Y en 15 minutos con profundidad?**  
R: Multi-CCAA + `outputs/pilot_honesty_card/index.html` (contraste de políticas).

**P: ¿Dónde está “la verdad” del ML?**  
R: `docs/ML_PRODUCT_SCORECARD.json` + `docs/ML_U1_PROMOTE_RECORD.json`.

**P: ¿Puedo copiar números al PowerPoint?**  
R: Sí, si etiquetas: **lab / holdout** vs **ops / ancla** vs **perímetro Junta**. Nunca mezcles.

---

# Módulo 12 — Checklist “ya entiendo el proyecto”

Marca cuando puedas explicar en voz alta:

- [ ] Producto dual ops vs ML  
- [ ] GO / HOLD / ABSTAIN  
- [ ] Por qué field_ops se calla a veces  
- [ ] Qué es Tobarra / Níjar / Caminomorisco  
- [ ] FIRMS ≠ área oficial  
- [ ] Diferencia 0.86 U1 vs 0.8963 catálogo  
- [ ] Dónde está el portal multi-CCAA y el piloto honesty  
- [ ] Un comando de `decide` y uno de piloto  

Si marcas 6/8, ya no eres un desconocido.

---

# Apéndice A — Comandos cheatsheet

```powershell
cd C:\Users\Mariano\Documents\ALONSOO\WildfireFrontDynamics
$env:PYTHONPATH = "."

# Demo venta
python scripts\build_demo_multi_ccaa.py
start outputs\demo_multi_ccaa\index.html

# Piloto honesty (offline)
python scripts\run_pilot_honesty_card.py --fixture-root tests\fixtures\pilot
start outputs\pilot_honesty_card\index.html

# ML → Card offline
python scripts\run_ml_live_card_demo.py --mode offline --scenario hold

# Decision CLI
python -m wildfire_front decide --list-policies

# Tests offline
python -m pytest tests\ -q -m "not slow and not requires_weights"

# Portal general
python scripts\show_all.py
```

# Apéndice B — Lecturas siguientes (cuando quieras profundidad)

| Si te interesa… | Lee… |
|-----------------|------|
| Arquitectura dual | `ARCHITECTURE.md`, `docs/PRODUCTO_DUAL.md` |
| Diseño ML + Card | `docs/design/ML_FOCUS_PRODUCT_V1.md` |
| Diseño piloto packs | `docs/design/PILOT_PACK_REAL_HONESTY_CARD.md` |
| Demo multi-CCAA | `docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md` |
| Auditoría honesty | `docs/design/REPO_AUDIT_REMEDIATION_2026_07.md` |
| Plan post-datos email | `docs/PLAN_PROGRAMACION_EMAILS_20260724_POST_S1.md` |
| Venta corta | `docs/ONEPAGER_COMERCIAL_ES.md` (si existe) |

---

# Cierre

Si solo recuerdas tres cosas:

1. **Callarse es una función del producto.**  
2. **Hay dos motores (ops y ML) y un solo tablero (la Card).**  
3. **Empieza siempre por la demo multi-CCAA y el piloto honesty; el resto es profundidad.**

Bienvenido al proyecto.
