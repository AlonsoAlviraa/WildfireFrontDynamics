# Playbook — de cero (sin empresa) a proyecto financiable UE / ES

**Proyecto:** WildfireFrontDynamics (WFD)  
**Premisa:** aún **no** hay SL / startup constituida.  
**Objetivo:** dar **todos los pasos** en orden para poder entrar en ayudas UE/ES y, cuando toque, crear la empresa.

> Principio: **primero credibilidad + partners + demo**, después forma jurídica.  
> Casi ningún call UCPM/Horizon/SUDOE exige SL el día 1 de networking; **sí** la exigen para firmar y cobrar.

---

## Mapa mental (dónde estás)

```
[HOY] Persona física + repo + demo open (La Mierla) + ML CLM
   │
   ▼ FASE 0  Identidad y cuentas (esta semana)
   ▼ FASE 1  Demo + narrativa + one-pager
   ▼ FASE 2  Partners (end-user + uni + PT/otro)
   ▼ FASE 3  Forma jurídica mínima (cuando haya call o contrato)
   ▼ FASE 4  Primera ayuda ES (NEOTEC/CCAA) o UE (como partner)
   ▼ FASE 5  Producto + datos + EIC / scale
```

---

## FASE 0 — Identidad y cuentas (días 1–7)

### 0.1 Decidir el “sombrero” público

| Opción | Cuándo | Pros | Contras |
|--------|--------|------|---------|
| **Investigador / maker independiente** | Ahora | Rápido, sin coste | Difícil firmar grants grandes solo |
| **Asociado a universidad / centro** | Si hay contacto | Acceso Horizon/UCPM fácil | Menos equity; IP a negociar |
| **Autónomo** | Primeros cobros pequeños | Facturar consultoría | No ideal para equity/EIC |
| **SL / startup** | Antes de NEOTEC/EIC o contrato serio | Elegible CDTI, limpio | Coste notario/gestor + tiempo |

**Recomendación ahora:** operar como **proyecto open-source / research tool** + preparar carpeta para SL en 30–90 días cuando haya partner o call.

### 0.2 Cuentas obligatorias (gratis)

- [ ] Email profesional del proyecto (ej. `hola@…` o Gmail serio del proyecto)
- [ ] [Funding & Tenders EU Login](https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home) — **persona física** primero
- [ ] Perfil en [UCP Knowledge Network](https://civil-protection-knowledge-network.europa.eu/) (newsletter / events)
- [ ] Alertas F&T: `wildfire`, `forest fire`, `UCPM`, `disaster prevention`, `civil protection`
- [ ] GitHub del repo limpio y README claro (si aún no es público, preparar versión pública sin datos sensibles)
- [ ] LinkedIn / X del proyecto (opcional pero útil para partners)

### 0.3 Qué **no** hacer aún

- No montar SL “por si acaso” sin dinero ni partner (gastos + obligaciones).
- No prometer GO táctico en mails a INFOCAM.
- No enviar 50 mails genéricos a la Comisión.

**Checklist operativa:** [01_CHECKLIST_SEMANA_1.md](01_CHECKLIST_SEMANA_1.md)

---

## FASE 1 — Demo y narrativa (días 1–14)

### 1.1 Paquete de evidencia (ya casi lo tenéis)

| Pieza | Ruta / comando |
|-------|----------------|
| Portal | `docs/PORTAL.html` · `python scripts/show_all.py` |
| La Mierla open pack | `outputs/open_if/la_mierla_20260717/` |
| Cadence diaria | `python scripts/run_la_mierla_open_day.py` |
| One-pager comercial | `docs/ONEPAGER_COMERCIAL_ES.md` |
| One-pager UE (EN) | [02_ONEPAGER_EU_EN.md](02_ONEPAGER_EU_EN.md) |
| One-pager ES corto | [03_ONEPAGER_ES.md](03_ONEPAGER_ES.md) |
| Solicitud datos INFOCAM | `docs/open_if_intake/SOLICITUD_LA_MIERLA_INFOCAM.md` |

### 1.2 Mensaje en 30 segundos (memorizar)

> “Herramienta de **apoyo a la decisión** en incendios: fusiona satélite abierto y, cuando hay, térmico de campo; emite **GO / HOLD / ABSTAIN** con auditoría. **No inventa ROS** sin LWIR. Piloto open en La Mierla (CLM) y base ML en IF reales. Buscamos **end-user de protección civil** y partners UE.”

### 1.3 Demo de 10 minutos (guion)

1. Abrir mapa La Mierla + brief (open only).  
2. Mostrar Decision Card **HOLD** y por qué (sin ops).  
3. Mostrar reliability / no silent GO.  
4. Mostrar Tobarra / pack real_if si hay material.  
5. Cerrar: “para GO de campo necesitamos LWIR/partner; para UCPM aportamos software + open intelligence.”

**Guion detallado:** [04_GUION_DEMO_10MIN.md](04_GUION_DEMO_10MIN.md)

---

## FASE 2 — Partners (semanas 2–8) — **lo más importante sin empresa**

Sin end-user **no hay** UCPM/Horizon serio. Sin uni a veces no hay Horizon. La empresa puede venir **después**.

### 2.1 Tres tipos de partner

| Tipo | Rol | Ejemplo ES |
|------|-----|------------|
| **End-user** | Validar, carta de apoyo, piloto | INFOCAM, CMA CLM, 112, UME, BRIF, CCAA |
| **Research** | Coordinar Horizon / papers | Univ. CLM, UPM, CTFC, INIA-CSIC, centros FIRE-RES |
| **SME / tech** | Consorcio multi-país | Startup PT/IT/GR sensores o GIS |

### 2.2 Orden de contactos

1. **Carta / correo datos + piloto** → CMA / INFOCAM (plantilla lista).  
2. **1 universidad** con track incendios o teledetección.  
3. **1 contacto PT o FR** (SUDOE).  
4. Solo entonces: mirar call concreta y “encajar” el consorcio.

**Plantillas:**
- [05_CARTA_END_USER_ES.md](05_CARTA_END_USER_ES.md)  
- [06_EMAIL_UNIVERSIDAD_ES.md](06_EMAIL_UNIVERSIDAD_ES.md)  
- [07_EMAIL_PARTNER_UE_EN.md](07_EMAIL_PARTNER_UE_EN.md)  
- [08_MAPA_PARTNERS.md](08_MAPA_PARTNERS.md)

### 2.3 Qué pedís (y qué no)

| Pedir | No pedir al inicio |
|-------|-------------------|
| Reunión 30 min + feedback del repo | Presupuesto millonario |
| Carta de interés / letter of support | Datos clasificados día 1 |
| Acceso piloto a 1 IF (LWIR anónimo o retrasado) | Compromiso de compra |
| Co-autoría en propuesta UE | Exclusividad eterna de IP sin contrato |

---

## FASE 3 — Forma jurídica (cuando toque)

### 3.1 Señales de que **ya** hace falta empresa

- [ ] Call NEOTEC / EIC con deadline y elegís presentar  
- [ ] Partner pide NIF de entidad para MoU  
- [ ] Alguien quiere **pagaros** (factura) de forma recurrente  
- [ ] Queréis equity / inversores  

### 3.2 Camino España típico (simplificado)

1. **Nombre + objeto social** (software, datos, consultoría de emergencia, I+D).  
2. **Gestoría / notario** → **SL** (capital mínimo 1 € en la práctica actual de SL; confirmad con gestor).  
3. **CIF, cuenta bancaria empresa**, alta IAE/CNAE software/I+D.  
4. **Registro en Funding & Tenders** como organización (PIC).  
5. Si NEOTEC: empresa **joven**, base tecnológica, plan de negocio.

### 3.3 Alternativas temporales

| Forma | Uso |
|-------|-----|
| **Autónomo** | Facturar un taller o consultoría pequeña |
| **Convenio con uni** | La uni es beneficiary; vosotros personal o subcontract |
| **Asociación sin ánimo de lucro** | Raro para deeptech product; no prioritario |

**Checklist legal (no sustituye abogado):** [09_CHECKLIST_CREAR_SL.md](09_CHECKLIST_CREAR_SL.md)

---

## FASE 4 — Primera financiación (elige 1 pista principal)

### Pista A — España primero (recomendada sin empresa aún → con SL)

| Paso | Acción |
|------|--------|
| A1 | Cerrar demo + 1 carta de apoyo |
| A2 | Constituir SL si hace falta para NEOTEC |
| A3 | Dossier NEOTEC (I+D + plan negocio + equipo) |
| A4 | En paralelo: ayudas CCAA innovación / digitalización |

### Pista B — UE como **partner** (se puede empezar **sin** SL)

| Paso | Acción |
|------|--------|
| B1 | One-pager EN + GitHub |
| B2 | Buscar consorcios abiertos (FIRE-RES network, UCPM projects, uni) |
| B3 | Entrar como **affiliated / third party / SME partner** vía uni o SL recién creada |
| B4 | Call UCPM Prevention o Interreg SUDOE cuando abra |

### Pista C — Solo grants de investigación personal

| Paso | Acción |
|------|--------|
| C1 | Si elegible: Marie Curie / postdoc / Juan de la Cierva (si perfil academic) |
| C2 | No es el camino principal si el objetivo es **producto** |

**Matriz de programas:** [10_MATRIZ_AYUDAS.md](10_MATRIZ_AYUDAS.md)

---

## FASE 5 — Operativa de propuesta (cuando haya call)

1. Leer elegibilidad (¿SME? ¿consorcio mínimo 3 países?).  
2. Asignar rol: **tech software / decision support**.  
3. Work package realista: open pack cadence, decide API, pilot 1 CCAA, training.  
4. Budget: personal + cloud + travel + open data no se inventa como coste absurdo.  
5. Ethics: no tactical dispatch claims; GDPR; no datos personales de evacuados.  
6. Letter of support del end-user adjunta.  

**Esqueleto de propuesta corta:** [11_ESQUELETO_PROPUESTA_UCPM.md](11_ESQUELETO_PROPUESTA_UCPM.md)

---

## Calendario 90 días (sin empresa al día 0)

| Semana | Entregable |
|--------|------------|
| 1 | Cuentas UE + one-pagers + demo guionada + GitHub public-ready |
| 2 | 5 emails end-user / uni enviados (plantillas) |
| 3–4 | 2 reuniones; 1 carta de interés en borrador |
| 5–6 | Decidir SL sí/no; si sí, gestoría |
| 7–8 | PIC organización o partnership uni firmado (MoU simple) |
| 9–10 | Elegir 1 call objetivo (NEOTEC o SUDOE o UCPM) |
| 11–12 | Primer draft de work package + budget rough |

---

## Métricas de progreso (honestas)

| Señal | Significa |
|-------|-----------|
| 0 mails enviados | Aún en fantasía |
| 1 reunión end-user | En el juego |
| 1 letter of support | Elegible para consorcio serio |
| PIC + partner | Podéis firmar |
| 1 call presentada | Habéis cruzado la línea |

---

## Archivos de esta carpeta

| Archivo | Uso |
|---------|-----|
| [00_PLAYBOOK_SIN_EMPRESA.md](00_PLAYBOOK_SIN_EMPRESA.md) | Este documento |
| [01_CHECKLIST_SEMANA_1.md](01_CHECKLIST_SEMANA_1.md) | Acciones inmediatas |
| [02_ONEPAGER_EU_EN.md](02_ONEPAGER_EU_EN.md) | Partners UE |
| [03_ONEPAGER_ES.md](03_ONEPAGER_ES.md) | End-users ES |
| [04_GUION_DEMO_10MIN.md](04_GUION_DEMO_10MIN.md) | Demo |
| [05_CARTA_END_USER_ES.md](05_CARTA_END_USER_ES.md) | Apoyo INFOCAM/CMA |
| [06_EMAIL_UNIVERSIDAD_ES.md](06_EMAIL_UNIVERSIDAD_ES.md) | Uni |
| [07_EMAIL_PARTNER_UE_EN.md](07_EMAIL_PARTNER_UE_EN.md) | SME/uni EU |
| [08_MAPA_PARTNERS.md](08_MAPA_PARTNERS.md) | Lista de a quién escribir |
| [09_CHECKLIST_CREAR_SL.md](09_CHECKLIST_CREAR_SL.md) | Cuando toque empresa |
| [10_MATRIZ_AYUDAS.md](10_MATRIZ_AYUDAS.md) | Programas y prioridad |
| [11_ESQUELETO_PROPUESTA_UCPM.md](11_ESQUELETO_PROPUESTA_UCPM.md) | Draft call |
| [12_REGISTRO_CONTACTOS.md](12_REGISTRO_CONTACTOS.md) | CRM minimal en markdown |

---

## Siguiente acción (ahora mismo)

1. Abrir [01_CHECKLIST_SEMANA_1.md](01_CHECKLIST_SEMANA_1.md) y tachar.  
2. Personalizar [03_ONEPAGER_ES.md](03_ONEPAGER_ES.md) con tu nombre y email.  
3. Enviar **un** correo con [05_CARTA_END_USER_ES.md](05_CARTA_END_USER_ES.md) (no veinte).  
4. Crear EU Login y anotar usuario en [12_REGISTRO_CONTACTOS.md](12_REGISTRO_CONTACTOS.md).
