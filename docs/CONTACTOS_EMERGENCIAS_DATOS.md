# Directorio ampliado: emergencias, universidades y centros de datos

> **Uso:** proyecto propio / validación operativa / datos de dinámica de frente (WFD).  
> **Regla de fidelidad:** solo emails y canales **públicos** verificados en webs oficiales o documentos institucionales (revisión 2026).  
> **No spamear:** 1 correo **personalizado** por organización. Priorizar 8–12 contactos de esta semana.  
> **No existen “miles de emails de emergencias”** listos para scrape: lo legal y útil es un embudo de calidad + formularios + directorios de congresos.

---

## Qué pedir (siempre, adaptando 2 líneas)

1. **Anclas operativas:** Vp media (m/min), superficie (ha), fecha/hora de parte — Cardoso, Hellín, La Estrella, multi-IF CLM.  
2. **Perímetros vectoriales** (GeoJSON / SHP / GPKG) de 1–2 IF con secuencia térmica o BA satelital.  
3. **Uso interno del proyecto** + confidencialidad de crudos (sin publicar sin acuerdo).  
4. (Opcional) Feedback del informe HTML / capa de frente / envelope 15-30-60.

CSV de seguimiento (mismas filas): [`docs/CONTACTOS_OUTREACH.csv`](CONTACTOS_OUTREACH.csv)

---

## Seguimiento CyL — Llamas de Cabrera (2026-07-17)

| Campo | Valor |
|-------|-------|
| Solicitud | `docs/SOLICITUD_TRANSPARENCIA_CYL.md` + `scripts/fetch_cyl_incendios.py` |
| Incendio | Llamas de Cabrera 2025-08-08 |
| Estado | **FOLLOW_UP_DUE** — formulario/transparencia enviado o listo; falta respuesta con perímetro/Vp/ha |
| Acción | Reenviar o registrar nº de registro si ya enviado; no inventar anclas |
| Gate | D1 / O1-O2 desbloqueo parcial si llegan vectores oficiales |

---

## Prioridad 1 — Operativo CLM / hilo actual (ENVIAR YA)

| Organización | Rol | Contacto público | Qué pedir |
|--------------|-----|------------------|-----------|
| **CMA / GEACAM (Pablo)** | Coordinación aérea, datos Heligrafics | `pablo.arroyobretano@geacam.com` | Vp/ha multi-IF, Cardoso 10d, perímetro, feedback informe |
| **GEACAM** genérico | Empresa pública gestión ambiental CLM | `contacto@geacam.com` · Tel. +34 969 237 427 (Cuenca) · +34 925 333 022 (Toledo) · [web](https://www.geacam.es/contacto) | Escalado institucional |
| **GEACAM DPD** | Protección de datos | `dpd@geacam.com` | Solo si piden base legal |
| **Heligrafics** | Sensor aéreo / termografía (vuestro proveedor de datos) | `info@heligrafics.net` · [contacto](https://www.heligrafics.net/en/contact/) · Tel. +34 965 943 897 | Metadatos LWIR, más secuencias, formato export |
| **INFOCAM portal** | Prevención/extinción CLM | https://infocam.castillalamancha.es/ | Derivación a servicio técnico / partes (no email genérico público estable) |
| **112 CLM** | Emergencias | https://112.castillalamancha.es/ | **No** canal de datos GIS |
| **Protección Civil (Gobierno en CLM)** | Coordinación institucional | `proteccion_civil.castillalamancha@correo.gob.es` · Tel. 925 989 000 | Reenvío a INFOCAM / marco formal |

**CC en correos GEACAM/CMA:** mantener “Cma” si ya está en el hilo.

---

## Prioridad 2 — Satélite / Europa (perímetros BA, O2)

| Organización | Contacto / canal | Qué pedir |
|--------------|------------------|-----------|
| **EFFIS (JRC)** | **`jrc-effis@ec.europa.eu`** · Form: [Data request](https://forest-fire.emergency.copernicus.eu/apps/data.request.form/) · [Data & services](https://forest-fire.emergency.copernicus.eu/applications/data-and-services) | Perímetros burnt area 2024–2025 ES/CLM; BA cerca Tobarra/Cardoso |
| **EFFIS (legacy docs)** | `effis@jrc.ec.europa.eu` (aparece en PDFs antiguos; preferir `jrc-effis@`) | Solo si rebota el principal |
| **JRC data support** | `jrc-data-support@ec.europa.eu` | Datasets en data.jrc.ec.europa.eu |
| **Copernicus EMS Mapping** | https://mapping.emergency.copernicus.eu/ · API Redoc | Delineation shapefiles de EMSR España ya publicados |
| **EU Space Support** | `support@euspace-programme.eu` | Ayuda acceso productos EMS |
| **ERCC / ECHO** | `echo-ercc@ec.europa.eu` | Solo usuarios autorizados PC — **no** canal TFG normal |
| **NASA FIRMS** | MAP_KEY: https://firms.modaps.eosdis.nasa.gov/api/map_key/ | Hotspots (ya: `scripts/fetch_firms_hotspots.py`) |

---

## Prioridad 3 — España nacional (EGIF / MITECO / redes)

| Organización | Contacto / canal | Qué pedir |
|--------------|------------------|-----------|
| **EGIF (MITECO)** | Buscador: https://servicio.mapa.gob.es/incendios/Search/Publico · Stats: https://www.miteco.gob.es/es/biodiversidad/temas/incendios-forestales/estadisticas-datos.html | Ha, fechas, provincias (Cardoso GU, Hellín AB…) XML/Excel |
| **MITECO** | Formularios web miteco.gob.es (no inventar emails de buzón) | Consulta formal EGIF consolidado |
| **CLIF** (Comité Lucha Incendios Forestales) | https://www.miteco.gob.es/es/biodiversidad/temas/incendios-forestales/coordinacion-institucional/grupos_trabajo_clif.html | Documentos técnicos / no datos crudos |
| **SECF** (Sociedad Española de Ciencias Forestales) | `secforestales@secforestales.org` · https://secforestales.org | Difusión / contactos de grupos de trabajo / congresos |
| **ASELF** (Asoc. Española Lucha contra el Fuego) | `administracion@aself.org` · `comunicacion@aself.org` · https://www.aself.org | Red profesional extinción / jornadas |

---

## Prioridad 4 — CCAA operativos (emails institucionales públicos)

| CCAA / plan | Contacto público | Nota |
|-------------|------------------|------|
| **Castilla-La Mancha — INFOCAM / GEACAM** | Ver Prioridad 1 | Principal para vuestros IF |
| **Castilla y León — INFOCAL / CDF / datos** | Ver bloque **CyL** abajo | Datos abiertos + CDF León |
| **Andalucía — INFOCA / datos REDIAM** | **`rediam.atiende.csma@juntadeandalucia.es`** (oficial; `…csmaea@` renombrado) · cartografía: `cor.top.cagpds@juntadeandalucia.es` · ASEMA Gerencia: `gerencia.asema@juntadeandalucia.es` (Alejandro García Hernández) · DG Gestión IIFF: Jorge Luque Illescas (sin email personal público; vía gerencia) · **Agencia de Emergencias de Andalucía** (REDIAM 2026-07: canal ops IIFF) | **GO datos espaciales** 2026-07: perímetros 2008–2025 + ARF 1975–hoy — ver `docs/open_if_intake/REDIAM_ANDALUCIA_PERIMETROS_20260722.md` · WFS `mapwms/REDIAM_perimetros_incendios_forestales` · no es el 112 |
| **Galicia — PLADIGA / Medio Rural** | **`defensadomonte.mediorural@xunta.gal`** (DX Defensa do Monte — **Manuel Francisco Gutiérrez**, jefe incendios) · `forestal.mediorural@xunta.gal` (DX Planificación Forestal) · `secretaria.cmr@xunta.gal` · `sxt.medio-rural@xunta.gal` · **NO usar** `monte.mediorural@` (550 User unknown) | Directorio: https://www.xunta.gal/es/medio-rural/directorio · aviso 085 |
| **Extremadura — INFOEX / DG PEIFF** | `dgpeiiff.prs@juntaex.es` (DIR3; **José Antonio Bayón**, DG) · `dgma.marpat@juntaex.es` · portal: https://www.infoex.info/ · Tel. DG 924 008 745 · X: @PLANINFOEX | Preferir `dgpeiiff`; no es el 112 |
| **Catalunya — Bombers / Interior** | Formulario: https://interior.gencat.cat/ · CTFC más útil para ciencia | Operativo vía web; datos investigación vía CTFC |
| **C. Valenciana — Bombers forestals / GVA** | Portales GVA / SGISE (form web; no listar buzones no verificados) | Investigación causas: GOIIF vía Conselleria Medio Ambiente |
| **Resto CCAA** | Buscar en sede electrónica de cada consejería “incendios forestales” + “contacto” | INFOAR (Aragón), INFOCAEX, etc. — **email solo si aparece en sede** |

---

## Castilla y León (INFOCAL) — contactos y datos

> Plan: **INFOCAL** (Protección Civil ante incendios forestales).  
> Ops en campaña: **INFORCYL** (mapa + partes). Tragsa/personal operativo **no** es canal de datos GIS por email público.

### Datos sin pedir permiso (primero)

| Recurso | Qué da | Link |
|---------|--------|------|
| **INFORCYL** (mapa tiempo real) | Incendios activos, medios, info pública | https://servicios.jcyl.es/incyl/incyl |
| **Open Data JCyL — incendios forestales** | CSV de **partes** en campaña (ha, fechas, etc.) | https://jcyl.opendatasoft.com/explore/dataset/incendios-forestales/custom/ |
| **Portal medio natural CyL** | INFOCAL, planificación, info diaria | https://medioambiente.jcyl.es/web/es/medio-natural/planificacion-sobre-incendios-forestales.html · https://medioambiente.jcyl.es/web/es/medio-natural/informacion-diaria-incendios-forestales.html |
| **EGIF nacional** | ha/fechas también para provincias CyL | https://servicio.mapa.gob.es/incendios/Search/Publico |

### Emails públicos verificados (pedir **datos** o reenvío)

| Organización | Contacto | Qué pedir | Nota |
|--------------|----------|-----------|------|
| **CDF — Centro para la Defensa Contra el Fuego** (Junta CyL, León) | **`centrofuego@jcyl.es`** · Tel. **987 840 603** · C/ Comandante Cortizo s/n, 24008 León | Reenvío al servicio de incendios / cartografía: **perímetros vectoriales** o **partes** liberables de 1–2 IF; o contacto del buzón correcto | Formación + investigación + educación en incendios; **no es el 112** pero es el email institucional más claro de CyL en fuego |
| **ULE — Alfonso Fernández-Manso** (EIAF / teledetección y fuego) | **`aaferm@unileon.es`** · también aparece como `alfonso.manso@unileon.es` (máster) | Solo si tenéis IF en CyL o queréis reenvío; **no** es despacho ops | Profesor MásterFUEGO; remoto sensing / severidad |
| **MásterFUEGO (coord. interuniv.)** | `etseafiv.coordmfuego@udl.cat` | Reenvío a parte ULE | Ya en directorio nacional |
| **Servicios Territoriales Medio Ambiente** | Tel. provinciales (p. ej. León **987 296 000**); emails a menudo **no** públicos en web | Pedir en sede / registro “buzón sección incendios / forestal” | No inventar `info@` provinciales |
| **112 CyL / Agencia Protección Civil** | https://www.jcyl.es · canales 112 | **No** canal de datos GIS | Solo emergencias |
| **TRAGSA** (operativo extinción CyL) | Web empleo/contratos | **No** es buzón de perímetros para terceros | Operador, no open data |

### Plantilla corta CyL (solo datos)

```
Para: centrofuego@jcyl.es
Asunto: Solicitud de datos — perímetros / partes incendios forestales CyL (uso no comercial)

Estimados/as del CDF,

Desarrollo un proyecto propio de dinámica de frente (ROS desde termografía
aérea). Necesito, si es liberable para uso interno sin publicar crudos:

1) Perímetro vectorial (SHP/GPKG/GeoJSON) de 1–2 incendios recientes en CyL
2) O, en su defecto, reenvío al servicio/sección que gestione cartografía
   o partes INFOCAL / datos abiertos adicionales a INFORCYL

Cualquier formato vale. Si el canal correcto es otro buzón de la Junta,
agradecería la dirección.

Gracias,
Alonso Alvira
[teléfono]
alonso.alvbal@gmail.com
```

**Realismo:** CyL publica **partes en CSV** en campaña; los **perímetros finos** suelen ir por DG Patrimonio Natural / ST Medio Ambiente y a menudo exigen registro formal. CDF es el mejor **email de entrada** público.

---

## Prioridad 5 — Universidades y centros de investigación (España)

| Centro / grupo | Contacto público | Enfoque / qué pedir |
|----------------|------------------|---------------------|
| **INIA-CIFOR / ICIFOR (CSIC)** — Lab. incendios | `incendio@inia.es` · Tel. +34 913 476 780 · https://www.inia.es | Combustibles, comportamiento, validación ROS |
| **INIA investigadores (publicados en directorios UVa/doctorado)** | `guijarro@inia.es` (M. Guijarro, dominio inia) | Solo si encaja línea de investigación; preferir buzón `incendio@` |
| **UCLM — Grupo Fuego / FIREC** | `JoseM.Moreno@uclm.es` · `Jorge.Heras@uclm.es` · `juanmanuel.sanchez@uclm.es` · https://blog.uclm.es/grupofuego/ | Régimen incendios CLM, cartografía, colaboración TFG |
| **UdL — MásterFUEGO (coord.)** | `etseafiv.coordmfuego@udl.cat` (Víctor Resco de Dios / coordinación) · https://www.masterfuegoforestal.udl.cat | Red máster incendios UDL–ULE–UPV; reenvío a especialistas |
| **UCO — Ingeniería Forestal / fuego** | `jrmolina@uco.es` (Juan Ramón Molina) · https://www.uco.es/idep/gestion-del-fuego | FirEUrisk, gestión del fuego, modelos |
| **CTFC — Pau Brunet Navarro** | Investigador; coord. adjunto **FIRE-RES** (H2020) | **`pau.brunet@ctfc.cat`** · [ficha CTFC](https://www.ctfc.cat/es/personal24_det.php?id=19) | **Prioridad alta:** feedback WFRM, living labs, reenvío partners, datos/validación si procede |
| **CTFC (Solsona) genérico** | `secretaria@ctfc.cat` · Tel. +34 973 481 752 · form: https://www.ctfc.cat | Canal institucional si no contesta el investigador |
| **FIRE-RES (buzón proyecto)** | `fire-res@ctfc.cat` · https://fire-res.eu/contact-us/ | CC opcional junto a Pau Brunet |
| **Pau Costa Foundation** | `info@paucostafoundation.org` · https://www.paucostafoundation.org | Red profesional, formación, Firelogue legacy |
| **USC** (grupos I+D) | `imaisd@usc.gal` (gestión grupos; pedir IP incendios/restauración) · máster montes: `carlos.amiama@usc.gal` | Galicia — ecología/restauración post-fuego; especialidad incendios |
| **UEx / Mosaico** (prevención territorial) | F. Pulido y red Mosaico (email personal no listado en web pública estable) · portal: https://cortafuegosproductivos.unex.es/ | Extremadura — cortafuegos productivos / prevención; contactar vía web proyecto o DG INFOEX |
| **UPV Máster incendios** | https://www.upv.es/estudios/master/muifcgi/ (contacto vía web máster) | Gestión integral emergencias |
| **UPM / ETSIM / otras ETS forestales** | Directorio escuela en web (no inventar) | Modelos comportamiento |
| **CILIFO** (legado POCTEP ES–PT) | https://cilifo.eu / partners UCO–Junta | Red ibérica; contactar vía UCO `jrmolina@` o webs partner |

---

## Prioridad 6 — Proyectos UE / redes / partners

| Proyecto / red | Contacto | Qué |
|----------------|----------|-----|
| **Firelogue** | `info@firelogue.eu` · `civil-protection@firelogue.eu` · `environ@firelogue.eu` · https://firelogue.eu | Red WFRM; partners list en partners.php |
| **FIRE-RES** | `fire-res@ctfc.cat` | Soluciones fire-resilient territories |
| **FirEUrisk** | Web fireurisk.eu · ES via UCO `jrmolina@uco.es` | Risk strategy Europa |
| **TREEADS** | https://treeads-project.eu/contact/ · partners: `Info@iti.gr` (ITI) · `post@risefr.no` (RISE Fire NO) | Ecosystem prevención–detección–restauración |
| **CMCC** | `info@cmcc.it` | Clima / riesgo / Firelogue partner |
| **Trilateral Research** (Firelogue) | `info@trilateralresearch.com` | Socio tech/policy |
| **IIASA Firelogue** | vía firelogue.eu / iiasa.ac.at | Sistemas WFRM |

---

## Prioridad 7 — Internacional (investigación / open source / journals)

| Entidad | Contacto / canal | Qué |
|---------|------------------|-----|
| **ForeFire** | https://github.com/forefireAPI/forefire (Issues) | ROS física comparable |
| **ELMFIRE** | https://elmfire.io · GitHub lautenberger/elmfire | Modelo operativo US |
| **USFS Missoula Fire Lab** | https://research.fs.usda.gov/firelab · tools: firelab.org · `firelabmissoula@gmail.com` (web tools) | Referencia FARSITE/FlamMap ecosistema |
| **INRAE** (Francia, wildfire units) | `international@inrae.fr` · https://www.inrae.fr | Unidades RECOVER Aix, etc. |
| **CSIRO Bushfire** | https://www.csiro.au/en/research/disasters/bushfires · form contacto | Comportamiento fuego AU |
| **IJWF (CSIRO Publishing)** | `publishing.ijwf@csiro.au` | Solo editorial journal, no datos ops |
| **WA DFES Bushfire CoE** | `BCoEResearch@dfes.wa.gov.au` | Investigación ops AU |
| **NASA Earthdata / FIRMS** | Form MAP_KEY + LANCE support | Hotspots API |
| **Google NDWS / Huot** | Dataset Kaggle + papers | Benchmark ML (ya en repo) |

---

## Cómo llegar a “cientos” de contactos **sin inventar emails**

| Canal | Cómo usarlo | Estimación realista |
|-------|-------------|---------------------|
| **Partners Firelogue / FIRE-RES / TREEADS / FirEUrisk** | Páginas partners + CORDIS | 50–150 orgs (1 email institucional c/u) |
| **Congreso Forestal / jornadas ASELF / masterFUEGO** | Listas de ponentes y actas | Decenas de autores con email en PDF |
| **ResearchGate / ORCID / Google Scholar** | Buscar “wildfire” + “Spain” + “fire behaviour” | Email institucional del paper |
| **Directorios CCAA sedes electrónicas** | “incendios forestales” + “buzón” | 17 CCAA × 1–3 buzones |
| **EGIF / EFFIS national correspondents** | Pedir a EFFIS lista de puntos de contacto nacionales | 20–40 países |
| **LinkedIn (manual)** | GEACAM, INFOCAM, CTFC, Heligrafics | Sin scraping masivo |
| **Papers con datos abiertos** | Zenodo / Figshare coautores | Email de corresponding author |

**Prohibido / contraproducente:** bases de “1000 emails bomberos” compradas, scraping GDPR, BCC masivo, inventar `info@universidad.es`.

---

## Correos tipo (copiar / personalizar)

### A) GEACAM / CMA

```
Para: pablo.arroyobretano@geacam.com
CC: contacto@geacam.com
Asunto: TFG dinámica de frente — anclas Vp/ha y perímetro (CLM)

Hola Pablo / equipo CMA-GEACAM,

Adjunto informe técnico y brief de emergencia sobre las secuencias que
nos facilitasteis (Tobarra grado A vs INFOCAM ~7 m/min).

Para validación multi-incendio necesitamos, si es posible:
1) Vp media y ha de parte (Cardoso, Hellín, La Estrella…)
2) Un perímetro vectorial de 1 IF
3) Cardoso completo si sigue disponible

Uso estrictamente académico/TFG, sin publicar crudos.
Gracias.
Alonso Alvira
```

### B) EFFIS

```
Para: jrc-effis@ec.europa.eu
Asunto: Data request — burned area perimeters Spain CLM 2024–2025 (MSc thesis)

Dear EFFIS team,
I am an MSc student working on fire-front dynamics from aerial thermal
sequences (Castilla-La Mancha). We already process drone/heli IR and
need independent burned-area vectors for geometric validation
(Hausdorff). Could you advise how to obtain BA perimeters for selected
fires in Spain 2024–2025 (or point to downloadable layers)?
Academic use only.
Best regards,
Alonso Alvira — alonso.alvbal@gmail.com
```

### C) INIA-CIFOR

```
Para: incendio@inia.es
Asunto: Colaboración TFG — validación ROS frente térmico aéreo

Estimados/as,
Desarrollo un motor de dinámica de frente (ROS multi-estimador) sobre
secuencias LWIR reales de CLM. Busco orientación o datos de validación
(perímetros, comportamientos de referencia). Puedo compartir informe
técnico y demos.
Saludos,
Alonso Alvira
```

### D) UCLM Grupo Fuego

```
Para: JoseM.Moreno@uclm.es
CC: Jorge.Heras@uclm.es
Asunto: TFG / CLM — dinámica de frente con datos aéreos reales

Estimado Prof. Moreno / equipo Grupo Fuego,
Trabajo en estimación de ROS y envolventes de emergencia a partir de
secuencias térmicas aéreas en CLM (colaboración GEACAM/Heligrafics).
Me gustaría explorar colaboración académica o datos de referencia
(cartografía, régimen, validación).
Saludos,
Alonso Alvira
```

### E) Heligrafics (datos sensor)

```
Para: info@heligrafics.net
Asunto: TFG — secuencias LWIR incendios CLM / metadatos y más IF

Estimados/as,
Trabajamos con secuencias térmicas aéreas de incendios en CLM
(vía CMA/GEACAM) para estimar ROS y productos de emergencia.
¿Podríais indicar si hay metadatos de sensor (FOV, georref., tasa)
o más secuencias liberables con acuerdo de uso académico?
Gracias,
Alonso Alvira
```

### F) CTFC / FIRE-RES

```
Para: fire-res@ctfc.cat
CC: secretaria@ctfc.cat
Asunto: MSc thesis — fire-front ROS from aerial IR / possible living lab data

Dear FIRE-RES / CTFC team,
...
```

### G) Pau Costa / Firelogue

```
Para: info@paucostafoundation.org
CC: info@firelogue.eu
Asunto: TFG — red WFRM y posible feedback operativo a productos de frente
```

### H) MasterFUEGO / UCO

```
Para: etseafiv.coordmfuego@udl.cat
CC: jrmolina@uco.es
Asunto: MásterFUEGO / FirEUrisk — contacto para validación ROS aéreo
```

---

## Orden de envío recomendado (esta semana)

| # | Destinatario | Por qué |
|---|--------------|---------|
| 1 | Pablo + `contacto@geacam.com` | Ya hay hilo; desbloquea O1/O5 |
| 2 | `info@heligrafics.net` | Metadatos + más IF |
| 3 | `jrc-effis@ec.europa.eu` + form EFFIS | Perímetros O2 |
| 4 | EGIF buscador (sin email si sale online) | Anclas ha/fecha |
| 5 | `incendio@inia.es` | Validación científica |
| 6 | UCLM Grupo Fuego | Regional CLM |
| 7 | `fire-res@ctfc.cat` / `secretaria@ctfc.cat` | Red mediterránea |
| 8 | `info@paucostafoundation.org` | Red profesional |
| 9 | `etseafiv.coordmfuego@udl.cat` + `jrmolina@uco.es` | Academia incendios |
| 10 | FIRMS MAP_KEY | Auto-registro |
| 11 | `administracion@aself.org` / `secforestales@secforestales.org` | Ampliar red |
| 12 | Galicia / Andalucía buzones (si necesitáis multi-CCAA) | Solo tras CLM |

---

## Qué NO hacer

- Enviar el mismo mail a 200 direcciones inventadas.  
- Pedir acceso a bases operativas 112 sin marco institucional.  
- Contactar ERCC para **activar** EMS (no sois usuario autorizado).  
- Publicar o reenviar emails personales no listados en web oficial.  
- Comprar listas de correos de “emergencias”.

---

## Enlaces del proyecto

- Demo: `outputs/visual_index.html`  
- Brief: `scripts/emergency_briefing.py`  
- FIRMS: `scripts/fetch_firms_hotspots.py`  
- Catálogo datos: `docs/OPEN_RESOURCES_CATALOG.md`  
- Tracking envíos: `docs/CONTACTOS_OUTREACH.csv`
