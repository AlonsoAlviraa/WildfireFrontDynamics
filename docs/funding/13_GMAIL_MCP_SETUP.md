# Gmail MCP — setup para Alonso Alvira Ballano

**Cuenta:** `alonso.alvbal@gmail.com`  
**Objetivo:** que Grok pueda **leer / enviar / buscar** correo (outreach INFOCAM, unis, partners) vía MCP.

---

## 1. Qué se ha configurado en Grok

- Launcher: `~/.grok/scripts/run-gmail-mcp.ps1`
- Server name: `gmail` en `~/.grok/config.toml`
- Paquete npm: `@gongrzhe/server-gmail-autoauth-mcp`
- Credenciales esperadas en: `%USERPROFILE%\.gmail-mcp\gcp-oauth.keys.json`

---

## 2. Pasos que debes hacer tú (Google Cloud OAuth) — ~10 min

### 2.1 Proyecto Google Cloud

1. Entra en [Google Cloud Console](https://console.cloud.google.com/) con **alonso.alvbal@gmail.com**.
2. Crea un proyecto (ej. `wfd-gmail-mcp`).
3. **APIs y servicios → Biblioteca** → habilita **Gmail API**.

### 2.2 Pantalla de consentimiento OAuth

1. **APIs y servicios → Pantalla de consentimiento OAuth**.
2. Tipo: **Externo** (cuenta personal Gmail).
3. App name: `WFD Gmail MCP` (o similar).
4. User support email: `alonso.alvbal@gmail.com`.
5. Scopes: añade scopes de Gmail (el servidor suele pedir `gmail.modify` / `gmail.readonly` / `gmail.send` en el primer login).
6. **Usuarios de prueba:** añade `alonso.alvbal@gmail.com` (obligatorio mientras la app esté en Testing).

### 2.3 Credenciales OAuth (cliente de escritorio)

1. **Credenciales → Crear credenciales → ID de cliente de OAuth**.
2. Tipo: **Aplicación de escritorio**.
3. Nombre: `grok-gmail-mcp`.
4. **Descargar JSON**.
5. Guárdalo exactamente aquí:

```
C:\Users\Mariano\.gmail-mcp\gcp-oauth.keys.json
```

(Crea la carpeta si no existe.)

Opcional: variable de usuario Windows  
`GMAIL_OAUTH_KEYS` = ruta absoluta al JSON.

### 2.4 Primera autenticación

En PowerShell:

```powershell
cd $env:USERPROFILE\.gmail-mcp
npx -y "@gongrzhe/server-gmail-autoauth-mcp" auth
```

(Si el paquete no tiene subcomando `auth`, arranca el server una vez; debería abrir el navegador.)

- Inicia sesión con **alonso.alvbal@gmail.com**.
- Acepta permisos.
- Se guardará un token en `~/.gmail-mcp/` (no lo subas a git).

### 2.5 Activar en Grok TUI

1. Reinicia Grok o abre `/mcps`.
2. Pulsa **`r`** para refrescar.
3. Servidor **gmail** → debe salir enabled.
4. Si pide OAuth de nuevo, usa **`i`** (authenticate) en el modal.

Comprobar:

```powershell
grok mcp list
grok mcp doctor gmail
```

---

## 3. Uso típico con WFD

Cuando el MCP esté online, puedes pedir en el chat:

- “Borra en borrador el correo a INFOCAM con el one-pager”
- “Envía el mail de la plantilla 05 a …”
- “Lista correos sin leer de esta semana sobre incendios”

**Antes de enviar** a instituciones: revisa el borrador (tono, datos, no prometer GO).

---

## 4. Seguridad

| Hacer | No hacer |
|-------|----------|
| Token solo en `~/.gmail-mcp/` | Subir `gcp-oauth.keys.json` al repo |
| App en Testing + solo tu user | Publicar app OAuth sin revisar |
| Revocar en [Google Account → Seguridad](https://myaccount.google.com/permissions) si pierdes el PC | Compartir client secret |

Añade a `.gitignore` global si hace falta: `.gmail-mcp/`, `gcp-oauth.keys.json`.

---

## 5. Si `doctor gmail` falla

| Error | Qué mirar |
|-------|-----------|
| keys not found | Ruta `~\.gmail-mcp\gcp-oauth.keys.json` |
| npx timeout | `startup_timeout_sec` ya es 120; reintentar con red |
| access_denied | Usuario de prueba no añadido en OAuth consent |
| Gmail API disabled | Habilitar API en el proyecto GCP |

---

## 6. Contacto del proyecto (ya rellenado en one-pagers)

- **Nombre:** Alonso Alvira Ballano  
- **Email:** alonso.alvbal@gmail.com  
