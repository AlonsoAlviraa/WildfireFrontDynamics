# Send checklist — Hellín / Cardoso / R4 (humano)

> Ingeniería deja **plantillas**. Solo un humano completa destinatario, envía y registra.  
> **No** marcar `sent=true` desde CI/scripts. **No** generar `.eml` fingiendo envío.

## Antes de enviar

- [ ] Revisar `EMAIL_HELLIN_PDF_KMZ.md`, `EMAIL_CARDOSO_VP_HA.md`, `EMAIL_R4_CESSION.md`
- [ ] Completar todos los `[corchetes]` (nombre, email, institución, fecha)
- [ ] Confirmar TO institucional real (no inventar)
- [ ] Verificar: laboratorio / no despacho táctico
- [ ] Verificar: no PII, no FOI fills
- [ ] Verificar: no se inventan Vp/ha/ROS
- [ ] OK Alonso para envío

## Envío (humano)

- [ ] Enviar desde cliente humano (no script de este repo)
- [ ] Guardar copia fuera de git
- [ ] Anotar fecha/hora UTC

## Después

Editar `send_status.json` **a mano**:

```json
{
  "sent": true,
  "sent_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "sent_by": "Alonso"
}
```

- [ ] Si llega cite: `python scripts/copy_cite_to_real_if.py --cite PATH --fire-id <id>`
- [ ] Copy ≠ promote. Promote solo con H1–H7 + Alonso en el mismo PR.
- [ ] No flip GO_Q / FREEZE / Hellín confirmed por este envío
