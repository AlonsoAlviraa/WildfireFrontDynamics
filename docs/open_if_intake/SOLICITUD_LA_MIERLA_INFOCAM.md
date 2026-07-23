# Solicitud formal de datos — IF La Mierla (Guadalajara) 2026-07

> **Estado:** BORRADOR — no enviado.  
> **Destinatario previsto:** INFOCAM / CMA (Castilla-La Mancha) · Observatorio / coordinación técnica.  
> **event_id WFD:** `guadalajara_la_mierla_20260717`  
> **Pack open:** `outputs/open_if/la_mierla_20260717/`  
> **Ancla actual:** `pending_external` en `data/infocam_anchors.json` (no confirmed).

---

## 1. Contexto (1 párrafo)

El incendio de **La Mierla / Sierra Norte de Guadalajara** (detección ~16 jul 2026) es el de mayor superficie estimada de la temporada en CLM según partes INFOCAM (~26–29k ha estimadas, Nivel 2). WildfireFrontDynamics mantiene un **pack de monitorización open** (NASA FIRMS multi-sensor + metadatos de prensa/X oficiales) en modo **HOLD** táctico: **sin perímetro oficial, sin ROS de incident, sin ancla O1 confirmed**. Para desbloquear productos operativos y de validación científica (ROS multi-estimador, grade A, ancla EGIF) necesitamos material que solo INFOCAM/CMA puede facilitar.

---

## 2. Datos solicitados (prioridad)

| # | Dato | Formato aceptable | Uso WFD | Prioridad |
|---|------|------------------|---------|-----------|
| 1 | **LWIR / térmico de medios** (heli / dron / cámaras) del IF | GeoTIFF, frames georref., o secuencia + CRS | ROS incident, front dynamics, parches real_if | **P0** |
| 2 | **KMZ / shapefile / GeoPackage de perímetro** (uno o varios instantes) | KMZ, SHP, GPKG, GeoJSON (ETRS89/UTM preferible) | O2 error geométrico, fusión open | **P0** |
| 3 | **Vp media (m/min)** o rango de propagación del parte | tabla / correo / CSV | Ancla O1 `confirmed` | **P0** |
| 4 | **Superficie (ha) EGIF u oficial de parte** (no solo estimación de prensa) | ha + fecha/hora del parte + fuente | Ancla O1; no usar 29k press como EGIF | **P0** |
| 5 | Croquis / franjas horarias de avance (si existen) | PDF georref. o vector | timeline ROS | P1 |
| 6 | Confirmación de si hay activación **CEMS EMSR** propia (no EMSR896 Orés) | código EMSR o “no activado” | O2 open pack | P1 |

**No pedimos** datos personales de afectados ni material clasificado de investigación policial del origen.

---

## 3. Qué **no** usaremos como ancla confirmed

- Estimaciones de ha en X/prensa (~26k–29k) sin parte EGIF.  
- Hull convexo de hotspots FIRMS (~40–50k ha proxy térmico).  
- EMSR896 (Orés, Aragón) como perímetro de La Mierla.  
- Cualquier ROS inventado a partir de solo open data.

La promoción a `status: confirmed` en nuestro repositorio **requiere** `vp_m_min` + `area_ha` + `source` operativo (guard automatizado en código).

---

## 4. Qué devolvemos a cambio

1. Informe operativo / pack GIS de dinámica de frente si hay LWIR alineado.  
2. Scorecard multi-fuente (open + ops) con trazabilidad de ancla.  
3. Comparativa honesta FIRMS / dNBR / perímetro oficial (labels `not_official` donde aplique).  
4. Sin reentrenamiento ML publicitario sobre este IF hasta tener parches legítimos.

---

## 5. Texto corto para correo (copiar/adaptar)

```text
Asunto: Solicitud datos IF La Mierla (GU) — LWIR/KMZ + Vp/ha EGIF — validación WFD

Buenos días,

En el marco de la validación del motor de dinámica de frente (WildfireFrontDynamics)
para incendios de Castilla-La Mancha, solicitamos, si es posible, para el IF
La Mierla / Sierra Norte de Guadalajara (detección ~16 jul 2026):

1) Secuencia o frames térmicos LWIR georreferenciados (heli/dron/cámaras) y/o
   exportación KMZ/shapefile de perímetro en uno o varios instantes.
2) Vp media (m/min) o rango de propagación del parte operativo.
3) Superficie (ha) de parte EGIF / oficial (distinta de la estimación pública
   provisional de ~29.000 ha).
4) Confirmación de si existe activación CEMS EMSR específica (no confundir con
   EMSR896 Orés, Aragón).

Compromiso de uso: investigación y producto de apoyo a decisión, con etiquetas
honestas (no despacho táctico sin ancla). No publicaremos ha/Vp como “oficiales”
sin vuestra fuente.

Quedamos a disposición para el canal y formato que os resulte más simple
(correo, enlace interno, reunión breve).

Gracias y un saludo,
[Nombre / afiliación / contacto]
```

---

## 6. Seguimiento interno WFD

| Paso | Owner | Estado |
|------|-------|--------|
| Redactar este borrador | repo | **DONE** (este doc) |
| Enviar correo / registro formal | **humano** | PENDIENTE |
| Registrar fecha de envío en `docs/CONTACTOS_OUTREACH.csv` | humano | PENDIENTE |
| Si llega material → protocolo `real_if` + re-evaluar ancla | pipeline | bloqueado externo |
| Si no hay respuesta → dejar `pending_external` documentado | repo | default |

**No automatizar el envío.** Este archivo es plantilla.
