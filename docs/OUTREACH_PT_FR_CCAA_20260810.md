# Outreach — Portugal, Francia y CCAA nuevas (2026-08-10)

> **Objetivo:** pedir **incendios completos** (paquete mínimo para ops + open + anclas).  
> **CSV vivo:** [`CONTACTOS_OUTREACH.csv`](CONTACTOS_OUTREACH.csv)  
> **Directorio histórico:** [`CONTACTOS_EMERGENCIAS_DATOS.md`](CONTACTOS_EMERGENCIAS_DATOS.md)

---

## 0. Gmail — no se pudo re-leer en vivo

| Campo | Valor |
|-------|--------|
| Intento | `~/.gmail-mcp/credentials.json` + Gmail API |
| Resultado | **`invalid_grant` — Token has been expired or revoked** |
| Causa típica | OAuth app en modo **Testing** (`refresh_token_expires_in` ≈ 7 días) |
| Último access útil en disco | **2026-07-29** |
| MCP Gmail en sesión | **no conectado** (handshake/OAuth muerto) |

**Acción humana (5–10 min):** re-autorizar Gmail MCP / OAuth Testing y volver a ejecutar:

```powershell
python scripts\_scan_gmail_last_month.py
```

Hasta entonces, el inventario de correos del “último mes” se reconstruye desde **repo + lecturas Gmail ya documentadas** (corte ~22–30 jul 2026), no desde inbox live 10 ago.

---

## 1. Correos del último mes (reconstrucción honesta)

Ventana útil documentada: **~10 jul – 30 jul 2026** (y silencio admin hasta 10 ago).

### 1.1 Hilos con valor de datos

| Hilo | Fecha útil | Estado | Qué aportó / falta |
|------|------------|--------|--------------------|
| **Pablo GEACAM** | **2026-07-30** | **RESPONDIDO** | KMZ perímetros Tobarra multi-hora + mapas ARGOS; ofrece multi-IF/UNAP; **Cardoso sin extra** |
| **REDIAM Andalucía** | 22 jul | **GO** | Perímetros + ARF públicos / WFS |
| **RAI Extremadura** | 22–23 jul | **GO** | 3 SHP 2025 + form OK |
| **Galicia Defensa do Monte** | 22 jul | Traslado **Extinción** | Sin SHP aún; follow-up ya vencido si no hubo reply |
| **CyL transparencia 4082/2026** | acuse 17 jul | **WAIT silence** | No re-spam antes de **~17 ago**; luego 1 follow-up o cierre |
| **USC Díaz-Varela** | 24 jul | Cerrado datos | Uni sin datos; mandar a Xunta |
| **INIA Madrigal** | ~17 jul | Cerrado gratis | Solo contrato de pago |
| **CTFC Brunet** | ~16–17 jul | Cerrado datos | Redirige stakeholders CLM |
| **ASEMA / DG IIFF AND** | 22 jul | Enviado sin reply útil | 1 follow-up corto máx. |
| **Heligrafics** | 16 jul | Enviado | Metadatos LWIR / más secuencias |

### 1.2 Lo que **no** ha llegado (cuello de datos)

- SHP/GPKG **oficial nacional** (O2)  
- Vp/ha **Cardoso** confirmed  
- Pack Galicia / CyL vectorial  
- Respuesta ASEMA ops  
- Cualquier hilo **Portugal / Francia / Valencia / Navarra / Canarias / Madrid** (aún no contactados o solo WEB)

### 1.3 Conclusión email (sin live inbox)

**Desde ~30 jul no hay evidencia en repo de mails nuevos que desbloqueen datos.**  
El hilo más caliente sigue siendo **Pablo GEACAM** (multi-IF). El resto son waits o GO open ya industrializados (AND/EXT).

---

## 2. Qué es un “incendio completo” (pedir siempre esto)

No pedir “todo el servidor”. Pedir **1–3 IF** con este paquete. Cuanto más llegue, mejor; lo mínimo útil se marca ★.

| # | Entregable | Prioridad | Formatos OK | Para qué (WFD) |
|---|------------|-----------|-------------|----------------|
| 1 | **Perímetro vectorial** final y, si existe, **multi-hora / multi-día** | ★★★ | SHP / GPKG / GeoJSON / KMZ | O2, Hausdorff, open packs |
| 2 | **Ancla operativa**: superficie (ha) + **Vp o ROS medio** (m/min o m/h) + **fecha-hora de parte** + fuente | ★★★ | PDF/CSV/tabla | O1 / O5 grade A-B |
| 3 | **Cronología** (detección, ataque, control, extinción) | ★★ | texto / parte | timeline, honesty |
| 4 | **Secuencia térmica / LWIR o RGB-T multi-pasada** con timestamps y CRS | ★★★ (ops) | GeoTIFF / frames + meta | front_dynamics, ROS, grade A |
| 5 | **Metadatos sensor** (plataforma, banda, GSD, FOV, altitud) | ★★ | JSON/PDF | coreg, QA FOV |
| 6 | **Meteorología local** (viento dir/vel, T, HR) en ventana del IF | ★★ | CSV/JSON/estación | envelope / hybrid |
| 7 | **Combustible / modelo de vegetación** del sector (si existe) | ★ | SHP/raster | fuel stack |
| 8 | **Mapas de situación / SITAC** (opcional; no son perímetro oficial) | ★ | PDF/JPG | contexto, no ancla |
| 9 | Condiciones de uso (interno / no redistribuir / embargo) | ★★★ | texto | legal |

**Prohibido en la petición y en el uso:** inventar Vp; tratar press ha como EGIF; usar footprint de dron como perímetro oficial; spamear 112.

---

## 3. Contactos **NUEVOS** prioritarios (PT / FR / CCAA frescas)

Regla: **1 correo personalizado por organización**. No blast.

### 3.1 Portugal (prioridad alta — datos abiertos + ops)

| # | Org | Email / canal | Qué pedir primero | Notas |
|---|-----|---------------|-------------------|-------|
| 1 | **ICNF** | `geral@icnf.pt` | Áreas ardidas vectoriales 2024–2026 + reenvío a cartografía / fogos | Contacto público SGIFR/ICNF |
| 2 | **AGIF** | `agif@agif.pt` | Reenvío técnico SGIFR; IF con ficha + perímetro liberable | Agencia gestión integrada fogos |
| 3 | **geoCATÁLOGO ICNF** | https://geocatalogo.icnf.pt/ | **Descarga open primero** (áreas ardidas) | Sin email |
| 4 | **ANEPC** | `geral@prociv.pt` | Solo si ICNF/AGIF no reenvían | PC nacional; no ideal para GIS |
| 5 | **IPMA** | `info@ipma.pt` | Meteo estación para 1–2 IF grandes | Complemento, no perímetro |

### 3.2 Francia (prioridad media-alta — open + red DFCI)

| # | Org | Email / canal | Qué pedir primero | Notas |
|---|-----|---------------|-------------------|-------|
| 1 | **EFFIS / JRC** | `jrc-effis@ec.europa.eu` + [data request form](https://forest-fire.emergency.copernicus.eu/apps/data.request.form/) | BA perimeters FR (y PT/ES) 2024–2026 | Multi-país en un solo ticket |
| 2 | **OPEN DFCI / Valabre géomatique** | `geomatique@valabre.com` | Cartografía DFCI + reenvío a quien tenga **périmètres feux** liberables | Publicado en opendfci.fr |
| 3 | **Entente Valabre** | `contact@valabre.com` | CC institucional / formación / partner data | Public contact |
| 4 | **BDIFF** | https://bdiff.agriculture.gouv.fr/ | Stats feux por commune (open) | No sustituye perímetro multi-hora |
| 5 | **INRAE RECOVER** | `anne.ganteaume@inrae.fr` (papers) o `international@inrae.fr` | Colab investigación / datasets literarios | **No** es despacho ops |

### 3.3 CCAA España **aún poco o no trabajadas**

| # | CCAA | Email / canal | Qué pedir | Estado outreach |
|---|------|---------------|-----------|-----------------|
| 1 | **C. Valenciana** | **`dgpif@gva.es`** (DG Prevención IIFF; tel. 961 247 003) | 1–2 IF con perímetro SHP + ha + parte; reenvío SIGIF | **NUEVO — enviar** |
| 2 | **Aragón** | `incendios@aragon.es` (+ CC `gestionforestal@aragon.es`) | Perímetros + anclas | Ya en CSV **PENDIENTE — enviar** |
| 3 | **Navarra** | `centralmedioambiente@navarra.es` | Reenvío servicio prevención/extinción; perímetros liberables | **NUEVO — enviar** |
| 4 | **Canarias** | `idecanarias@grafcan.com` (CC `atencionalcliente@grafcan.com`) | Capas perímetro IF en IDECanarias / descarga | **NUEVO — enviar** |
| 5 | **Madrid (INFOMA)** | Web servicio + **sede/transparencia** (sin email GIS público estable) | Mega-IF 2026 Sierra Oeste / Villa del Prado: perímetro + parte | **WEB / sede — no inventar buzón** |
| 6 | **Asturias** | Sede / transparencia Principado | Alta frecuencia IF; perímetros si liberables | **WEB / sede** |
| 7 | **Galicia Extinción** | follow-up a hilo ya abierto vía Defensa do Monte | SHP multi-IF 2025–2026 | **FOLLOW-UP** (no nuevo spam a todos los buzones) |
| 8 | **CyL 4082** | silencio hasta ~**17 ago** | 1 follow-up o cierre | **WAIT** |

### 3.4 No reabrir (o solo con motivo nuevo)

| Contacto | Motivo |
|----------|--------|
| INIA / USC datos gratis | Cerrado |
| `monte.mediorural@xunta.gal` | Bounce 550 |
| ERCC / 112 | No canal datos |
| CyL antes del 17 ago | Silence rule |

---

## 4. Orden de envío recomendado (esta semana)

| Día | Acción | Destinatario |
|-----|--------|--------------|
| 0 | **Re-auth Gmail** | humano |
| 0 | Open data sin email | ICNF geoCATÁLOGO + BDIFF + EFFIS form |
| 1 | PT datos | `geral@icnf.pt` + CC no necesario |
| 1 | PT agencia | `agif@agif.pt` |
| 2 | ES nueva | `dgpif@gva.es` |
| 2 | ES | `incendios@aragon.es` + CC `gestionforestal@aragon.es` |
| 3 | FR | `geomatique@valabre.com` + CC `contact@valabre.com` |
| 3 | FR/EU | EFFIS form + `jrc-effis@ec.europa.eu` |
| 4 | ES | `centralmedioambiente@navarra.es` |
| 4 | ES | `idecanarias@grafcan.com` |
| 5 | CLM caliente | **1** mail a Pablo: pedir **paquete completo multi-IF** (Cardoso Vp/ha + perímetros Hellín/Estrella vectoriales) |
| ≥17 ago | CyL | 1 follow-up 4082 **o** cierre |

**Tope:** 8–10 mails personalizados; no 30 genéricos.

---

## 5. Plantillas

### 5.1 Portugal — ICNF (PT)

```
Para: geral@icnf.pt
Asunto: Pedido de dados — áreas ardidas / perímetros de fogos rurais (uso interno não comercial)

Exmos. Senhores do ICNF,

Desenvolvo um projeto próprio de dinâmica de frente de incêndio (estimativa de
ROS a partir de termografia aérea e perímetros multi-fonte), sem fins de
publicação de dados brutos de terceiros.

Solicito, se for libertável para uso interno:

1) Áreas ardidas / perímetros vetoriais (SHP, GPKG ou GeoJSON) de 1–3 fogos
   recentes (2024–2026), de preferência com data/hora;
2) Ou indicação do catálogo / serviço (geoCATÁLOGO) e contacto da equipa de
   cartografia de fogos;
3) Se existir: ficha com área (ha) e velocidade de propagação / ROS de parte
   operacional (mesmo que aproximada).

Qualquer formato serve. Se o canal correto for outro (AGIF, CCDR, etc.),
agradeço o reencaminhamento.

Com os melhores cumprimentos,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[telefone]
```

### 5.2 Francia — Valabre / OPEN DFCI (FR)

```
To: geomatique@valabre.com
Cc: contact@valabre.com
Subject: Data request — wildfire perimeters / DFCI layers (non-commercial research)

Dear OPEN DFCI / Entente Valabre team,

I develop an independent wildfire front-dynamics tool (ROS from aerial thermal
sequences + multi-source perimeters). I do not redistribute third-party raw data.

If releasable for internal use, I would be grateful for:

1) Vector fire perimeters (SHP/GPKG/GeoJSON/KMZ) for 1–2 recent French fires
   (ideally multi-date), or a pointer to the correct data owner;
2) Any public DFCI layers already shareable via OPEN DFCI;
3) Contact for BDIFF / departmental fire GIS if different from your desk.

Happy to sign a short data-use note. English or French is fine.

Best regards,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
```

### 5.3 C. Valenciana — DGPIF (ES)

```
Para: dgpif@gva.es
Asunto: Solicitud de datos — perímetros y partes de 1–2 incendios forestales (uso interno no comercial)

Estimados/as de la Dirección General de Prevención de Incendios Forestales,

Desarrollo un proyecto propio de dinámica de frente (ROS desde termografía
aérea y perímetros multi-fuente). No redistribuyo crudos de terceros.

Si es liberable para uso interno, solicito para 1–2 incendios recientes:

1) Perímetro vectorial (SHP/GPKG/GeoJSON/KMZ), preferible multi-fecha;
2) Parte o ficha con ha, fechas/horas y, si existe, Vp o velocidad media;
3) Reenvío al servicio de cartografía / SIGIF si el buzón correcto es otro.

Cualquier formato vale. Confidencialidad de crudos garantizada.

Gracias,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

### 5.4 Canarias — GRAFCAN / IDECanarias (ES)

```
Para: idecanarias@grafcan.com
Cc: atencionalcliente@grafcan.com
Asunto: Consulta capas — perímetros de incendios forestales IDECanarias

Estimados/as de IDECanarias / GRAFCAN,

¿Existe capa o servicio (WMS/WFS/descarga) de perímetros de incendios
forestales recientes en Canarias (p. ej. Tenerife u otros) reutilizable para
un proyecto de investigación/ops no comercial de dinámica de frente?

Si la descarga es pública, un enlace al recurso basta.
Si requiere solicitud, indiquen el trámite o el buzón del productor de la capa.

Gracias,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
```

### 5.5 Pablo GEACAM — “paquete completo” (ES, hilo caliente)

```
Para: pablo.arroyobretano@geacam.com
Cc: contacto@geacam.com
Asunto: Seguimiento — paquete multi-IF (perímetros + Vp/ha + térmica si hay)

Hola Pablo,

gracias de nuevo por Tobarra (KMZ multi-hora + mapas). Para cerrar validación
multi-incendio en CLM, ¿sería posible un “paquete mínimo” de 1–2 IF más
(ideal Cardoso y/o Hellín/Estrella) con lo que sea liberable?

1) Perímetro vectorial (KMZ/SHP/GPKG) multi-hora o al menos final
2) Vp o ha de parte / boletín UNAP con fecha-hora
3) Si existe secuencia térmica ya exportable (aunque sea subset)

Uso interno del proyecto; sin publicar crudos sin acuerdo.
Cualquier formato y cualquier IF completo vale más que muchos parciales.

Un saludo,
Alonso
```

---

## 6. Checklist post-envío

- [ ] Actualizar `CONTACTOS_OUTREACH.csv` (`estado`, `fecha_envio`, `notas`)  
- [ ] Guardar Message-ID / captura de envío  
- [ ] Si llega SHP/KMZ → drop en `data/real_if/` o `data/open_if/` + nota en `DATA_INTAKE_STATUS.md`  
- [ ] No promover ancla a `confirmed` sin Vp/ha de parte  
- [ ] No re-spam < 14 días salvo que pidan aclaración  

---

## 7. Relación con gates del producto

| Si llega… | Desbloquea |
|-----------|------------|
| 2º IF grade A (Vp+ROS ratio) | **O5 / GO_MES+** pitch |
| Perímetro oficial vector multi-IF | **O2** parcial → fuerte |
| LWIR multi-pasada nuevo no-CLM | Ops multi-IF + ML LOFO futuro |
| Solo BA EFFIS/ICNF open | Open packs multi-país (no ancla ops) |
| Nada nuevo | Sigue valiendo demo con CLM+AND+EXT; cuello = **H1 humano** |

---

*Generado 2026-08-10. Emails solo de fuentes públicas institucionales o directorios oficiales (SGIFR, GVA/administracion.gob.es, GRAFCAN, OPEN DFCI, repo outreach previo).*
