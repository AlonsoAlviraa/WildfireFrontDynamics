# Solicitud de información ambiental — Junta de Castilla y León

**Fecha:** 2026-07-17  
**Contexto:** Respuesta institucional que deriva al trámite de derecho de acceso a información pública / medio ambiente.  
**Trámite:** https://gobiernoabierto.jcyl.es/web/es/transparencia/derecho-informacion-publica.html  
**Catálogo open data (elegir IF):** https://analisis.datosabiertos.jcyl.es/explore/dataset/incendios-forestales/table/

> **Seguimiento (as of 2026-08-04):** estado **FOLLOW_UP / WAIT** · acuse ~**4082/2026** · **silence rule** — no re-spam antes de ~**2026-08-17**; tras silencio un follow-up o cierre D1.  
> Calendario y reglas: [`docs/fire_intel/CYL_SILENCE_RULE_NOTE.md`](fire_intel/CYL_SILENCE_RULE_NOTE.md) · contactos: [`docs/CONTACTOS_EMERGENCIAS_DATOS.md`](CONTACTOS_EMERGENCIAS_DATOS.md).

---

## 1. Qué significa el correo

La Junta **no entrega cartografía fina por email informal**. Hay que:

1. Identificar **un incendio concreto** (mejor 1, opcional 2º de respaldo).  
2. Presentar el **trámite formal** de acceso a información.  
3. Pedir solo lo que **no se obtiene** en open data / EGIF / EFFIS.

El dataset `incendios-forestales` da **partes diarios** (municipio, fechas, nivel, a veces ha en texto), **no** perímetros vectoriales ni ROS/Vp oficiales.

---

## 2. Incendio recomendado (principal)

| Campo | Valor |
|-------|--------|
| **Nombre / término** | **Llamas de Cabrera (Benuza), León** |
| **Fecha de inicio (parte)** | **2025-08-08** |
| **Provincia** | León |
| **Nivel máximo en parte** | **2** |
| **Superficie en parte (orden de magnitud)** | ~**22.284 ha** mixtas (árbol ~3.740; matorral ~16.366; pasto ~2.153; agrícola ~26) |
| **Por qué** | Uno de los grandes del oeste de León / “triángulo del fuego” 2025; gravedad alta; ha muy relevantes; fácil de localizar en open data y prensa |

**Fuente open data:** filtrar en el portal por `termino_municipal` ≈ *LLAMAS DE CABRERA* y `fecha_de_inicio` 2025-08-08.

### Incendio de respaldo (si piden 2º o el 1º no es liberable)

| Campo | Valor |
|-------|--------|
| **Nombre** | **Yeres (Puente de Domingo Flórez), León** |
| **Inicio** | **2025-08-09** |
| **Nivel max** | 2 |
| **Nota** | Complejo / contiguo al gran incendio de agosto 2025 en el oeste de León |

**Alternativa Zamora:** Molezuelas de la Carballeda, inicio **2025-08-10**, nivel 2 (complejo multi-provincia con León).

---

## 3. Qué pedir (solo lo no auto-obtenible)

### Prioridad A — desbloquea validación del proyecto (O1/O2)

1. **Perímetro final o de estabilización** del incendio en formato vectorial:
   - SHP / GPKG / GeoJSON (ETRS89 o WGS84).  
   - Si hay **varias capas temporales** (perímetro por día o por parte), pedir la serie o al menos **inicial + final**.  
2. **Parte consolidado / ficha del incendio** con:
   - Superficie final (ha arbolada / matorral / total).  
   - Fecha/hora detección, control, extinción.  
   - **Índice de gravedad** (nivel INFOCAL antiguo o **IGR** según Decreto 6/2025).  
3. Si existe: **velocidad de propagación estimada** o valores de **frente / ROS** usados en parte operativo (Vp media m/min o m/h), o indicar si **no se registra**.

### Prioridad B — útil pero opcional

4. Coordenadas o croquis del **punto de origen**.  
5. Condiciones meteorológicas de campaña en el parte (viento, etc.), si no son solo “internas”.  
6. Referencia a si hay **cartografía Copernicus EMS / EFFIS** ya publicada para ese IF.

### No pedir (ya se puede obtener fuera o no aplica)

- CSV de partes diarios del open data (ya público).  
- Imágenes de satélite genéricas (EFFIS, Sentinel).  
- Datos de personas, medios nominales, comunicaciones tácticas, ni “todo el servidor GIS”.

---

## 4. Texto para el formulario (copiar/adaptar)

**Asunto / objeto de la solicitud:**

> Solicitud de información ambiental — perímetro y datos técnicos del incendio forestal de Llamas de Cabrera (Benuza, León), inicio 2025-08-08

**Cuerpo:**

```
Solicito el acceso a la siguiente información ambiental que obre en poder de la
Junta de Castilla y León (Dirección General de Medio Natural / servicios
competentes en incendios forestales / INFOCAL), al amparo de la normativa de
transparencia y del derecho de acceso a la información en materia de medio ambiente.

IDENTIFICACIÓN DEL INCENDIO
- Denominación / término: Llamas de Cabrera (Benuza), provincia de León
- Fecha de inicio según parte diario de incendios forestales (datos abiertos JCyL):
  2025-08-08
- Nivel máximo alcanzado en parte: 2
- Referencia open data: dataset "incendios-forestales" (partes diarios campaña)

INFORMACIÓN QUE SOLICITO (uso de investigación / validación científica, no
comercial; no se solicitará la publicación de crudos operativos sensibles)

1) Cartografía del perímetro del incendio en formato vectorial (SHP, GPKG o
   GeoJSON), preferentemente perímetro final o de estabilización/extinción.
   Si existen perímetros intermedios por fecha, solicito la serie disponible
   o, en su defecto, el perímetro inicial y el final.

2) Datos técnicos consolidados del incendio:
   - Superficie afectada final (ha por tipo de vegetación y total)
   - Fechas y horas de detección, control y extinción (si constan)
   - Índice de gravedad (nivel INFOCAL o IGR según normativa vigente)

3) Si obra en el expediente y es liberable: cualquier estimación de velocidad
   de propagación o avance de frente (p. ej. Vp media) recogida en parte
   operativo o informe técnico. Si no se registra, basta con indicarlo.

FINALIDAD
Proyecto de investigación y desarrollo propio sobre reconstrucción de la
dinámica observada del frente de incendio a partir de secuencias térmicas
georreferenciadas y validación geométrica frente a perímetros oficiales
(uso interno de validación; no se solicita reutilización comercial de datos
restringidos).

FORMATO PREFERIDO
Archivos vectoriales y/o PDF/CSV de ficha técnica. Acepto cualquier formato
disponible.

Si la información debe solicitarse a otra unidad o servicio de la Junta,
agradezco la reorientación del trámite o el reenvío interno.

Datos de contacto del solicitante:
[NOMBRE COMPLETO]
[NIF si lo piden]
[EMAIL]
[TELÉFONO]
[DOMICILIO a efectos de notificaciones, si el formulario lo exige]
```

**Incendio alternativo** (sustituir el bloque IDENTIFICACIÓN):

```
- Denominación: Yeres (Puente de Domingo Flórez), León
- Fecha de inicio (parte): 2025-08-09
- Nivel máximo en parte: 2
```

---

## 5. Checklist antes de enviar

- [ ] Abrir el portal open data y **guardar captura o export CSV** del parte de Llamas de Cabrera 2025-08-08 (prueba de identificación).  
- [ ] Completar el **trámite online** del enlace de gobierno abierto (identificación digital si la piden: Cl@ve / certificado).  
- [ ] Adjuntar, si el formulario lo permite, el extracto del dataset o un PDF con la identificación del IF.  
- [ ] Guardar **número de registro / acuse** de la solicitud.  
- [ ] Anotar en `docs/CONTACTOS_OUTREACH.csv` el estado: `ENVIADO_TRANSPARENCIA_CYL` + fecha.

---

## 6. Cómo se usa en WildfireFrontDynamics si contestan

| Dato que llegue | Gate / uso en el repo |
|-----------------|----------------------|
| Perímetro vectorial | **O2** Hausdorff oficial (`eval_perimeter_hausdorff`) |
| ha + fechas | Ancla de área; inventario IF CyL |
| Vp / ROS en parte | **O1/O5** ancla operativa (si es numérica y con fuente) |
| Solo PDF sin vector | Digitalizar con cuidado o pedir de nuevo el vector |

**No mezclar** con Tobarra/CLM Heligrafics sin re-etiquetar dominio: esto es validación **CyL / INFOCAL**, no el specialist `clm_v28` de Castilla-La Mancha.

---

## 7. Mientras esperan (paralelo, sin burocracia)

```bash
# Extraer partes del open data (recomendado Llamas de Cabrera)
python scripts/fetch_cyl_incendios.py --recommend --out docs/cyl_llamas_cabrera.json --csv docs/cyl_llamas_cabrera.csv

# Otros candidatos nivel ≥ 2
python scripts/fetch_cyl_incendios.py --min-nivel 2 --limit 100 --out docs/cyl_nivel2.json
```

1. Guardar JSON/CSV como prueba de identificación del IF.  
2. Cruzar con **EFFIS / Copernicus EMS** para el bbox de Llamas de Cabrera / Bierzo agosto 2025.  
3. EGIF MITECO: https://servicio.mapa.gob.es/incendios/Search/Publico  
4. Seguir validación CLM (Tobarra ancla + ensemble v30) sin bloquear el TFG.  
5. **No re-spam** del trámite/email mientras rija el silence calendar (~**2026-08-17**): ver [`docs/fire_intel/CYL_SILENCE_RULE_NOTE.md`](fire_intel/CYL_SILENCE_RULE_NOTE.md).

---

## 8. Respuesta corta de cortesía (opcional, al remitente del correo)

```
Buenos días,

Muchas gracias por la orientación y el enlace al trámite de acceso a la
información. Voy a formalizar la solicitud centrándome en un incendio
concreto de alta gravedad (Llamas de Cabrera / Benuza, León, inicio
2025-08-08 según el dataset de partes diarios), pidiendo fundamentalmente
perímetro vectorial y datos técnicos consolidados que no figuran en el
open data.

Un saludo,
[Nombre]
```
