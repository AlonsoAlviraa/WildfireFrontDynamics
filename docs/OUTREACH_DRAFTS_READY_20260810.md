# Borradores listos para enviar — 2026-08-10

> **Uso:** copiar/pegar tal cual (ajusta teléfono).  
> **Regla:** 1 mail por organización · no CC masivo · no 112.  
> **Qué pedimos:** paquete IF completo (ver checklist abajo).  
> **CSV:** actualizar `CONTACTOS_OUTREACH.csv` tras cada envío.

---

## Checklist “IF completo” (pegar o resumir en cada mail)

1. Perímetro vectorial (ideal multi-hora) — SHP / GPKG / GeoJSON / KMZ  
2. Ancla: **ha + Vp o ROS + fecha-hora de parte**  
3. Cronología (detección → control → extinción)  
4. Si hay: secuencia térmica multi-pasada + timestamps/CRS + meta sensor  
5. Si hay: meteo local (viento, T, HR)  
6. Condiciones de uso (interno, sin redistribuir)

---

## Orden de envío sugerido

| # | Destinatario | Asunto (corto) | Prioridad |
|---|--------------|----------------|-----------|
| 1 | `geral@icnf.pt` | Dados fogos / áreas ardidas | P0 PT |
| 2 | `agif@agif.pt` | Dados fogos rurais SGIFR | P0 PT |
| 3 | `dgpif@gva.es` | Perímetros y partes IF CV | P0 ES |
| 4 | `incendios@aragon.es` | Perímetros y anclas Aragón | P0 ES |
| 5 | `geomatique@valabre.com` | Wildfire perimeters / DFCI | P0 FR |
| 6 | `jrc-effis@ec.europa.eu` | BA perimeters ES/PT/FR | P0 EU |
| 7 | `idecanarias@grafcan.com` | Capas perímetros IF Canarias | P1 ES |
| 8 | `centralmedioambiente@navarra.es` | Perímetros IF Navarra | P1 ES |
| 9 | `pablo.arroyobretano@geacam.com` | Paquete multi-IF completo | P0 CLM hilo |

**Open data (sin mail, hazlo el mismo día):**  
- https://geocatalogo.icnf.pt/  
- https://bdiff.agriculture.gouv.fr/  
- https://forest-fire.emergency.copernicus.eu/apps/data.request.form/

---

## DRAFT 1 — Portugal ICNF

**Para:** `geral@icnf.pt`  
**CC:** (vacío)  
**Asunto:** Pedido de dados — áreas ardidas e perímetros de fogos rurais (uso interno não comercial)

```
Exmos. Senhores do ICNF,

Chamo-me Alonso Alvira Ballano. Desenvolvo um projeto próprio de dinâmica de
frente de incêndio (estimativa de ROS a partir de termografia aérea e
perímetros multi-fonte), sem redistribuição de dados brutos de terceiros.

Solicito, se for libertável para uso interno de investigação/validação:

1) Áreas ardidas / perímetros vetoriais (SHP, GPKG ou GeoJSON) de 1 a 3 fogos
   rurais recentes (2024–2026), de preferência com data/hora;
2) Ficha ou parte com área (ha) e, se existir, velocidade de propagação (m/min
   ou m/h) e data/hora do registo;
3) Indicação do catálogo correto (geoCATÁLOGO) ou reencaminhamento para a
   equipa de cartografia de fogos / AGIF, se este não for o canal adequado.

Qualquer formato serve. Confidencialidade dos dados brutos garantida.

Com os melhores cumprimentos,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[telefone]
```

---

## DRAFT 2 — Portugal AGIF

**Para:** `agif@agif.pt`  
**CC:** (vacío)  
**Asunto:** Pedido de dados / contacto técnico — fogos rurais com perímetro e ficha (uso interno)

```
Exmos. Senhores da AGIF,

Sou Alonso Alvira Ballano e desenvolvo um projeto próprio de dinâmica de
frente de incêndio (ROS a partir de termografia aérea + perímetros). Não
publico dados brutos de terceiros.

Se for possível, peço:

1) Contacto da equipa que gere dados espaciais / SGIFR para pedidos de
   investigação;
2) Para 1–2 fogos recentes com boa documentação: perímetro vetorial
   (SHP/GPKG/GeoJSON/KMZ) e ficha com ha, datas e, se existir, velocidade
   de propagação;
3) Ou reencaminhamento para ICNF cartografia / outro organismo competente.

Uso estritamente interno. Qualquer formato é bem-vindo.

Com os melhores cumprimentos,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[telefone]
```

---

## DRAFT 3 — C. Valenciana DGPIF

**Para:** `dgpif@gva.es`  
**CC:** (vacío)  
**Asunto:** Solicitud de datos — perímetros y partes de 1–2 incendios forestales (uso interno no comercial)

```
Estimados/as de la Dirección General de Prevención de Incendios Forestales,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
(ROS desde termografía aérea y perímetros multi-fuente). No redistribuyo
crudos de terceros.

Si es liberable para uso interno, solicito para 1–2 incendios recientes en la
Comunitat Valenciana:

1) Perímetro vectorial (SHP, GPKG, GeoJSON o KMZ), preferible multi-fecha;
2) Parte o ficha con superficie (ha), fechas/horas y, si existe, Vp o
   velocidad media de propagación;
3) Reenvío al servicio de cartografía / SIGIF si el buzón correcto es otro.

Cualquier formato vale. Confidencialidad de crudos garantizada.

Gracias y un saludo,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

---

## DRAFT 4 — Aragón INFOAR

**Para:** `incendios@aragon.es`  
**CC:** `gestionforestal@aragon.es`  
**Asunto:** Solicitud de datos — perímetros y anclas operativas de 1–2 IF (uso interno no comercial)

```
Estimados/as del servicio de incendios forestales / gestión forestal de Aragón,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
de incendio (ROS desde termografía aérea + perímetros). No redistribuyo datos
brutos de terceros.

Si es liberable para uso interno, ruego para 1–2 incendios recientes:

1) Perímetro vectorial (SHP/GPKG/GeoJSON/KMZ), idealmente multi-hora o
   multi-día;
2) Ficha o parte con ha, fecha/hora y, si existe, Vp o ROS medio;
3) Indicación del canal de cartografía correcto si no es este buzón.

Cualquier formato es útil. Compromiso de uso interno y no publicación de crudos.

Un saludo,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

---

## DRAFT 5 — Francia OPEN DFCI / Valabre

**Para:** `geomatique@valabre.com`  
**CC:** `contact@valabre.com`  
**Asunto:** Data request — wildfire perimeters / DFCI layers (non-commercial, internal use)

```
Dear OPEN DFCI / Entente Valabre team,

My name is Alonso Alvira Ballano. I develop an independent wildfire
front-dynamics tool (ROS from aerial thermal sequences + multi-source
perimeters). I do not redistribute third-party raw data.

If releasable for internal research/validation use, I would be grateful for:

1) Vector fire perimeters (SHP/GPKG/GeoJSON/KMZ) for 1–2 recent French fires
   (ideally multi-date), or a pointer to the correct data owner;
2) Any public DFCI layers already shareable via OPEN DFCI;
3) Contact for departmental fire GIS / BDIFF contributors if different from
   your desk.

I can sign a short data-use note. English or French is fine.

Best regards,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[phone]
```

---

## DRAFT 6 — EFFIS / JRC

**Para:** `jrc-effis@ec.europa.eu`  
**CC:** (vacío)  
**Asunto:** Data request — burnt area perimeters Spain / Portugal / France 2024–2026 (research, non-commercial)

```
Dear EFFIS team,

I am Alonso Alvira Ballano, developing an independent wildfire front-dynamics
project (operational thermal ROS + open multi-source perimeters). I will not
redistribute raw third-party datasets.

I request, if available for research/internal use:

1) Burnt area / fire perimeter vectors for selected large fires in Spain,
   Portugal and France (2024–2026), preferably with acquisition / mapping
   dates;
2) Or guidance to the preferred channel (data request form / national
   correspondents) for multi-country BA layers.

I have also submitted / will submit the online data request form on the EFFIS
portal. Any format (SHP/GPKG/GeoJSON) is welcome.

Thank you,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[phone]
```

*(También rellena el formulario: https://forest-fire.emergency.copernicus.eu/apps/data.request.form/)*

---

## DRAFT 7 — Canarias GRAFCAN / IDECanarias

**Para:** `idecanarias@grafcan.com`  
**CC:** `atencionalcliente@grafcan.com`  
**Asunto:** Consulta capas — perímetros de incendios forestales en IDECanarias

```
Estimados/as de IDECanarias / GRAFCAN,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
de incendio (uso interno, no comercial; sin redistribuir crudos).

¿Existe capa o servicio (WMS/WFS/descarga) de perímetros de incendios
forestales recientes en Canarias reutilizable para validación?

- Si es público: basta el enlace al recurso o al visor/capa.
- Si requiere solicitud: indiquen trámite o buzón del productor de la capa
  (Cabildo / Gobierno de Canarias / otro).

Gracias,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

---

## DRAFT 8 — Navarra Medio Ambiente

**Para:** `centralmedioambiente@navarra.es`  
**CC:** (vacío)  
**Asunto:** Solicitud / reenvío — perímetros y partes de incendios forestales (uso interno)

```
Estimados/as del servicio de Medio Ambiente del Gobierno de Navarra,

Soy Alonso Alvira Ballano. Desarrollo un proyecto propio de dinámica de frente
de incendio (ROS desde termografía y perímetros multi-fuente). No redistribuyo
crudos de terceros.

Si es liberable, solicito para 1–2 incendios recientes en Navarra:

1) Perímetro vectorial (SHP/GPKG/GeoJSON/KMZ);
2) Parte o ficha con ha, fechas/horas y, si existe, Vp o velocidad media;
3) O reenvío al servicio de prevención/extinción / cartografía competente.

Cualquier formato vale. Uso estrictamente interno.

Gracias,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

---

## DRAFT 9 — Pablo GEACAM (hilo caliente CLM)

**Para:** `pablo.arroyobretano@geacam.com`  
**CC:** `contacto@geacam.com`  
**Asunto:** Seguimiento — paquete multi-IF (perímetros + Vp/ha + térmica si hay)

```
Hola Pablo,

gracias de nuevo por el material de Tobarra (KMZ multi-hora y mapas). Nos
sirvió mucho para validar el pipeline.

Para cerrar una validación multi-incendio en CLM, ¿sería posible un “paquete
mínimo” de 1–2 IF más (ideal Cardoso y/o Hellín o La Estrella) con lo que sea
liberable?

1) Perímetro vectorial (KMZ/SHP/GPKG) multi-hora o al menos final
2) Vp o ha de parte / boletín UNAP con fecha-hora
3) Si existe alguna secuencia térmica ya exportable (aunque sea un subset)

Uso interno del proyecto; sin publicar crudos sin acuerdo.
Cualquier formato y cualquier IF “completo” vale más que muchos parciales.

Un saludo y gracias otra vez,
Alonso Alvira Ballano
alonso.alvbal@gmail.com
[teléfono]
```

---

## Tras enviar (checklist)

- [ ] Marcar en `CONTACTOS_OUTREACH.csv`: `estado=ENVIADO`, `fecha_envio=YYYY-MM-DD`
- [ ] Guardar Message-ID o captura
- [ ] No re-spam &lt; 14 días
- [ ] Si llega dato → drop en `data/real_if/` o `data/open_if/` + nota en `DATA_INTAKE_STATUS.md`
- [ ] No promover ancla `confirmed` sin Vp/ha de parte

---

*Borradores generados 2026-08-10. No enviados automáticamente.*
