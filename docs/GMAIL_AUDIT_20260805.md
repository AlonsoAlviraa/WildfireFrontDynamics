# Gmail audit — WFD outreach (2026-08-05)

| Campo | Valor |
|-------|--------|
| **As of** | 2026-08-05 |
| **Cuenta esperada** | `alonso.alvbal@gmail.com` (setup doc) |
| **MCP** | server `gmail` · `@gongrzhe/server-gmail-autoauth-mcp` |
| **Resultado** | **BLOCKED** — `invalid_grant` (OAuth token expired / revoked) |

---

## Qué se intentó

| Operación MCP | Resultado |
|---------------|-----------|
| `gmail__search_emails` (inbox WFD/incendio/INFOCAM) | **Error: invalid_grant** |
| `gmail__search_emails` (in:sent outreach) | **Error: invalid_grant** |
| `gmail__list_email_labels` | **Error: invalid_grant** |

No se pudo listar ni leer mensajes. **No** se inventa contenido de correos ni estado de outreach.

---

## Causa probable

Token OAuth de Gmail MCP caducado o revocado (`invalid_grant`). Setup canónico:

- `docs/funding/13_GMAIL_MCP_SETUP.md`
- Keys: `%USERPROFILE%\.gmail-mcp\gcp-oauth.keys.json`
- Re-auth:

```powershell
cd $env:USERPROFILE\.gmail-mcp
npx -y "@gongrzhe/server-gmail-autoauth-mcp" auth
```

Luego reiniciar Grok MCP / sesión.

---

## Fuentes locales (sin Gmail live)

| Artefacto | Uso |
|-----------|-----|
| `docs/CONTACTOS_EMERGENCIAS_DATOS.md` | Contactos / canal datos |
| `docs/CONTACTOS_OUTREACH.csv` | Outreach tracking CSV |
| `docs/PLAN_PROGRAMACION_EMAILS_*.md` | Calendarios de emails (docs) |
| `docs/H1_GO_Q_RUNBOOK.md` | Cierre GO_Q (demo tercero — no email) |

**Acción humana:** re-auth Gmail MCP → re-ejecutar búsqueda WFD. Hasta entonces, outreach por CSV/docs locales.

---

## Qué NO se hizo

- No se enviaron emails
- No se borraron ni archivaron mensajes
- No se inventó “inbox limpio” ni respuestas de terceros

*Audit de acceso MCP, no de contenido de buzón.*
