# CyL — silence rule / follow-up calendar (D1)

**As of:** 2026-08-04  
**Plan Graph v6.1:** **H5** · gate **D1**  
**Incendio de referencia:** Llamas de Cabrera (Benuza, León) · parte inicio **2025-08-08**  
**No se inventan** perímetros, Vp ni ha oficiales de CyL en este note.

---

## 1. Current status

| Campo | Valor |
|-------|--------|
| **Estado** | **FOLLOW_UP / WAIT** |
| **Trámite** | Derecho de acceso a información pública / medio ambiente JCyL |
| **Documento de solicitud** | [`docs/SOLICITUD_TRANSPARENCIA_CYL.md`](../SOLICITUD_TRANSPARENCIA_CYL.md) |
| **Open data (partes, no vector fino)** | JCyL incendios-forestales + `scripts/fetch_cyl_incendios.py` |
| **Registro / acuse (repo)** | CyL **4082/2026** — acuse ~**2026-07-17** (`docs/DATA_INTAKE_STATUS.md`) |
| **Silence date (plan)** | ~**2026-08-17** |
| **Gate** | D1 — desbloqueo parcial O1/O2 **solo si** llegan vectores/ficha liberables |

**Outreach tracker:** `docs/CONTACTOS_EMERGENCIAS_DATOS.md` (bloque CyL) · `docs/CONTACTOS_OUTREACH.csv` (filas CyL Transparencia / CDF).

---

## 2. Silence rule (no re-spam)

Hasta **2026-08-17** (inclusive como fecha de silencio plan):

1. **No re-spam** a CDF (`centrofuego@jcyl.es`), buzones genéricos, ni nuevo envío masivo del mismo trámite.  
2. **No** contactar 112 CyL / Protección Civil ops como canal de GIS.  
3. **Sí permitido (pasivo):**  
   - consultar open data / INFORCYL / EGIF sin email;  
   - actualizar este note si llega respuesta espontánea;  
   - registrar nº de registro si el humano lo anota.  
4. **No inventar** anclas CyL ni “completar” O2 con press ha.

---

## 3. After silence (~2026-08-17+)

**Una** de estas dos acciones (no ambas en bucle):

| Opción | Cuándo | Qué hacer |
|--------|--------|-----------|
| **A — One follow-up** | Silencio total sin resolución útil al ~17 ago | **Un** follow-up educado (mismo expediente 4082/2026 o trámite transparencia), recordando solicitud de perímetro/ficha Llamas de Cabrera; CC solo si ya existía hilo. Luego volver a wait o cerrar. |
| **B — Close D1 wait** | Respuesta negativa, “no liberable”, o segundo silencio post follow-up | Marcar D1 **CLOSED_NO_DATA** / wait ended en contactos + status; seguir con open proxy (CEMS/REDIAM/RAI) y anclas CLM; **no** inventar CyL. |

**No:** cadenas diarias, multi-buzón spam, ni presión a emails no verificados.

---

## 4. What success looks like (if data arrives)

- Perímetro vectorial SHP/GPKG/GeoJSON y/o ficha consolidada según `docs/SOLICITUD_TRANSPARENCIA_CYL.md` §3.  
- Ingesta vía protocolo real-IF + honestidad proxy (`docs/REAL_IF_INTAKE_PROTOCOL.md`, `docs/DATA_PROXY_HONESTY.md`).  
- Actualizar `docs/DATA_INTAKE_STATUS.md` y scorecards; **nunca** auto-flip `ml_product_go` ni fusion field_ops.

---

## 5. Links

| Recurso | Path / URL |
|---------|------------|
| Solicitud formal | `docs/SOLICITUD_TRANSPARENCIA_CYL.md` |
| Contactos CyL | `docs/CONTACTOS_EMERGENCIAS_DATOS.md` |
| CSV outreach | `docs/CONTACTOS_OUTREACH.csv` |
| Data intake | `docs/DATA_INTAKE_STATUS.md` |
| Trámite JCyL | https://gobiernoabierto.jcyl.es/web/es/transparencia/derecho-informacion-publica.html |
| Open data incendios | https://jcyl.opendatasoft.com/explore/dataset/incendios-forestales/custom/ |
| CDF | `centrofuego@jcyl.es` (entrada institucional; no 112) |

---

## 6. Honesty

- Este note es **documentación de calendario** (H5). **No** se envía email desde esta tarea.  
- D1 **FOLLOW_UP** no bloquea **GO_MES** mínimo ya verificado (`docs/GO_MES_VERDICT.md`).  
- D1 **sí** forma parte de stretch / diversificación de datos, no de claim GO_Q.

*H5 DONE eng — 2026-08-04 · WildfireFrontDynamics project*
