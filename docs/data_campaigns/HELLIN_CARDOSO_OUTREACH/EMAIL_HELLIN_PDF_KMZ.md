# Solicitud — Hellín 2024 parte PDF + perímetro KMZ

> **Plantilla.** No enviar desde CI/scripts. Owner = humano (Alonso).  
> **No** rellenar PII / FOI. **No** inventar Vp/ha/ROS.  
> Producto: soporte a decisión, **no** despacho táctico.

## Destinatario

- **Organismo:** `[completar — INFOCAM / Observatorio / GEACAM]`
- **TO:** `[email institucional — no rellenar desde eng]`
- **CC:** `[opcional]`

## Asunto

Solicitud de parte/boletín oficial (PDF) y perímetro KMZ/KML con hora — IF Hellín 2024 — laboratorio, no operacional

## Cuerpo

Estimados/as:

Solicitamos, para **uso de laboratorio e investigación** (soporte a decisión; **no** despacho táctico, **no** redistribución comercial sin autorización), el material oficial del incendio forestal **Hellín 2024** (`fire_id` estable: `hellin_2024`) que permita completar el checklist H1–H7:

1. **Parte / boletín operativo en PDF** (o equivalente oficial) con fecha, nombre del IF y, si existen, Vp media y/o hectáreas.
2. **Perímetro KMZ o KML con sello temporal** (hora de la entrega).

**No solicitamos** datos personales de afectados, radios operativos sensibles, ni PII.

**No inventamos números.** Si el parte no trae Vp/ha, el ancla sigue `pending_external`.

Compromisos: uso interno de laboratorio; atribución a la fuente; no publicar el KMZ crudo sin autorización; no presentar este material como GO_Q complete ni como fusión de despacho.

Persona de contacto: `[nombre]` · `[email]` · `[institución]`.

Atentamente,  
`[nombre, cargo, institución, fecha]`

## Rails

- Hellín SSOT hoy: `pending_external` en `data/infocam_anchors.json`.
- Promote solo con cite literal + H1–H7 + OK Alonso en el **mismo** PR.
- FREEZE_ML intacto. GO_Q partial. fusion ON ≠ despacho.
