# P2-A — Solicitud formal de datos CONAF (plantilla)

> **Campaña:** [`PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **Estado:** plantilla lista para envío humano. **No** sustituye derechos escritos.  
> **Uso:** lab interno / investigación. **No** despacho táctico. CEMS EMSR647/715 siguen siendo **proxy**, no catastro CONAF.

Copiar a carta membretada. Completar `[corchetes]`. Enviar solo con OK de Alonso.

---

## Destinatario sugerido

- **Organismo:** Corporación Nacional Forestal (CONAF), Chile  
- **Áreas:** Gerencia de Protección contra Incendios Forestales / Unidad de Información Territorial  
- **Web:** https://www.conaf.cl/  
- **Copia:** CIREN / GORE Valparaíso / SENAPRED (si aplica al evento)

---

## Asunto

Solicitud de perímetros oficiales de incendios forestales (SHP/GPKG + fechas) para investigación de laboratorio — no operacional

---

## Cuerpo (ES)

Estimados/as:

Solicitamos, para **uso de laboratorio e investigación** (no despacho táctico, no redistribución comercial sin autorización), el acceso a geometrías oficiales de incendios forestales con sello temporal, en el marco del proyecto WildfireFrontDynamics (soporte a decisión, no mando de extinción).

**Eventos de interés (prioridad):**

1. Temporada Valparaíso / Viña del Mar, febrero 2024 (complemento a Copernicus EMSR715, que **no** sustituye el perímetro CONAF).  
2. Mega-incendios Biobío / Ñuble, febrero 2023 (complemento a EMSR647 AOI Nacimiento).  
3. Si existe un extracto nacional o regional con perímetros **datados** 2020–2025, un subconjunto de 3–6 eventos grandes.

**Formato pedido (mínimo útil para ML):**

| Campo | Detalle |
|-------|---------|
| Geometría | SHP o GPKG o GeoJSON, polígono de área quemada / perímetro |
| Fecha/hora | Al menos fecha del perímetro; si hay multi-pasada, una fila por entrega |
| CRS | EPSG documentado (ideal WGS84 o UTM 18S/19S) |
| Identificador | código CONAF / comuna / nombre del IF |
| Metadato | fuente (terrestre, aéreo, satelital), si es preliminar o final |

**No solicitamos** datos personales de afectados, radios operativos sensibles, ni capas de cuarteles.

**Compromisos:**

- Uso interno de laboratorio; atribución CONAF en toda figura.  
- No publicar el SHP crudo sin autorización escrita.  
- No presentar el perímetro CONAF como O2 España ni como fusión field_ops.  
- Destruir o devolver copias si CONAF lo requiere.

Persona de contacto: `[nombre]` · `[email]` · `[institución]`.

Quedamos atentos a un enlace de descarga, un FTP, o una cesión por oficio.

Atentamente,  
`[nombre, cargo, institución, fecha]`

---

## English short version (optional annex)

We request dated official fire perimeters (SHP/GPKG + CRS + timestamps) for **lab research only**, focused on Valparaíso 2024 and Biobío/Ñuble 2023. Copernicus EMS Rapid Mapping (EMSR715 / EMSR647) is already used as an **open proxy** and does **not** replace CONAF cadastre. No PII, no tactical dispatch, no redistribution without written leave.

---

## Rails (no negociables)

- `lab_ok` CONAF operacional = **no** hasta cesión escrita (ver [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md)).  
- Esta plantilla **no** cierra GO_Q, **no** levanta FREEZE, **no** enciende fusión.  
- Si CONAF no responde: seguir con CEMS proxy + MapBiomas/NAFI weak labels.

## Owners

| Rol | Acción |
|-----|--------|
| Alonso | Firmar / enviar / archivar respuesta |
| Data Steward | Inventariar bytes si llegan; no commitear SHP pesado |
| eng B | No entrenar con CONAF hasta `lab_ok` escrito |
