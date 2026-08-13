# Acta — demo con tercero (plantilla 1 página)

> **Uso:** rellenar **después** de una demo real de ~30 min con persona externa al proyecto.  
> **Gate:** M3.2 / GO_Q (humano).  
> **No es** acta forense de incidente (`export-acta`); es **prueba de demo externa**.  
> **Guion de apoyo:** `docs/GUION_DEMO_30MIN_POST_O1.md`

---

## 1. Metadatos

| Campo | Valor |
|-------|--------|
| **Fecha** | YYYY-MM-DD |
| **Hora (inicio–fin)** | HH:MM – HH:MM (zona: Europe/Madrid) |
| **Formato** | [ ] presencial · [ ] videollamada · [ ] híbrido |
| **Lugar / enlace** | |
| **Producto mostrado** | WildfireFrontDynamics (ops + ML lab + Decision Card) |
| **Versión / commit / tag** | (ej. main @ `________` o tag `________`) |
| **Duración real** | ___ min |
| **Idioma** | ES / EN |

---

## 2. Asistentes

| Rol | Nombre | Organización | Contacto (opcional) |
|-----|--------|--------------|---------------------|
| **Presentador** | | | |
| **Tercero (externo)** | | | |
| **Observador** (si hay) | | | |

**Tipo de tercero (marcar uno):**  
[ ] end-user / servicio de emergencias · [ ] universidad / TFG · [ ] partner datos · [ ] partner UE / consorcio · [ ] otro: ________

---

## 3. Guion ejecutado (checklist 10 bloques · ~30 min)

Marcar lo **realmente** enseñado (no lo ideal):

| # | Bloque | Hecho |
|---|--------|:-----:|
| 1 | Gancho: decisión auditada + abstención como valor | [ ] |
| 2 | Producto dual: **ops** ≠ **ML lab** (no mezclar ROS y IoU) | [ ] |
| 3 | **Tobarra** OPS (LWIR + ancla Vp 7 / ha 39, grade A) | [ ] |
| 4 | **Hellín** 2ª ancla (Vp 50; ROS ops vs ancla; grade B honesto) — solo si SSOT confirmed | [ ] |
| 5 | Open multi-CCAA (Níjar / Caminomorisco o portal) | [ ] |
| 6 | Decision Card GO/HOLD/ABSTAIN + contraste `field_ops` vs `research_open` | [ ] |
| 7 | Fuel / AEMET / envelope **solo contexto** (peso 0 táctico en Card) | [ ] |
| 8 | Kill list verbal (sin inventar ROS; fusion ON ≠ GO_Q complete ≠ despacho) | [ ] |
| 9 | Límites abiertos (O2 nacional, GO_MES+ false, `ml_product_go=true` **lab only**, field fusion **ON** cap 0.20 / abstain 0.45, GO_Q **partial**) | [ ] |
| 10 | Ask / next step con el tercero | [ ] |

**Artefactos abiertos en la sesión (paths o capturas):**

-  
-  
-  

---

## 4. Claims permitidos vs prohibidos (acta de honestidad)

### Permitido decir / se dijo

- [ ] Decision support con **audit trail** y abstención (HOLD/ABSTAIN)
- [ ] Tobarra: ROS ops validable vs ancla INFOCAM **confirmed**
- [ ] Hellín: 2ª ancla solo si **confirmed** en SSOT; ratio in-band posible **sin** grade A
- [ ] ML CLM v34: métricas de **laboratorio**; no orden de mando
- [ ] Open multi-CCAA: perímetros institucionales donde existen (REDIAM/RAI/CEMS) — proxy ≠ cadastro nacional
- [ ] `field_ops`: fusión ML live **ON** (peso máx 0.20, abstain_below 0.45) · **≠** despacho táctico · GO_Q partial
- [ ] Envelope / fuel: **no** claim táctico de despacho
- [ ] `ml_product_go=true` **lab only** (honesto) — **nunca** como field GO

### Prohibido (y no se afirmó)

- [ ] No se inventó **ROS / Vp / ha** sin fuente
- [ ] No se vendió **fusion ON como GO_Q complete / despacho táctico**
- [ ] No se vendió **`ml_product_go` lab como field GO** (el token lab honest sí es permitido)
- [ ] No se recalibró **k único** Tobarra(7) + Hellín(50) en silencio
- [ ] No se presentó hull FIRMS como **área quemada oficial**
- [ ] No se dijo “apagamos incendios con IA” / “99 % de precisión del fuego” / silent-GO ≤1e-6
- [ ] No se afirmó **GO_Q complete** / `go_q_met=true` sin demo+acta
- [ ] No se afirmó **GO_MES** solo por O1 PASS
- [ ] No se usó Cardoso ha/h ni Estrella SITAC Vp como ancla **confirmed**
- [ ] No se equivalió **VENTA_GO** (packaging) a **GO_Q**

**Incidencias de claim (si alguna se deslizó):**  
_Ninguna / descripción y corrección verbal:_

---

## 5. Feedback del tercero (resumen 5 líneas)

1.  
2.  
3.  
4.  
5.  

**¿Solicita follow-up?** [ ] sí · [ ] no · **Fecha tent.: ________**  
**¿Carta de interés / datos / segundo IF?** [ ] sí · [ ] no · **Notas: ________**

---

## 6. Resultado para gates del plan

| Gate | Resultado |
|------|-----------|
| **M3.2 demo tercero** | [ ] CUMPLIDO (esta acta firmada) · [ ] NO (reprogramar) |
| **Calidad demo** | [ ] útil · [ ] neutra · [ ] no repetir mismo pitch |
| **Riesgo de claim** | [ ] bajo · [ ] medio (anotar) · [ ] alto → no citar en GO_Q |

**Evidencia a archivar (opcional):** captura portal / Decision Card / scorecard Hellín · path: `________`

---

## 7. Firmas / sign-off

| | Presentador | Tercero (o “asistió sin firma formal”) |
|--|-------------|----------------------------------------|
| **Nombre** | | |
| **Fecha** | | |
| **Firma / OK escrito** | | |

> Con la firma del presentador se certifica que la demo ocurrió en la fecha indicada, con tercero externo, y que la kill list de §4 se respetó en lo sustancial.

---

## 8. Enlaces canónicos (no rellenar en la call)

| Doc | Path |
|-----|------|
| Guion 30 min | `docs/GUION_DEMO_30MIN_POST_O1.md` |
| Pitch 60s demo-day | `docs/PITCH_DEMO_DAY_60S.md` |
| Overlay plan Track B | `docs/PLAN_1_MES_POST_O1_UNLOCK.md` |
| Scorecard mes | `docs/SCORECARD_MES_1.md` |
| Honesty card | `docs/PILOT_HONESTY_CARD.md` |
| Hellín Track A | `docs/HELLIN_TRACK_A_SCORECARD.md` |
| P1 Hellín eng BLOCKED (por qué no GO_MES) | `docs/P1_HELLIN_ENG_STATUS.md` |
| Proxy vs confirmed (Estrella/Cardoso) | `docs/DATA_PROXY_HONESTY.md` |
| Producto dual | `docs/PRODUCTO_DUAL.md` |
| Anclas | `data/infocam_anchors.json` |
| Demo portal | `outputs/demo_multi_ccaa/index.html` |
| CURRENT_STATE (gates) | `docs/CURRENT_STATE.md` |

**Copia rellenada sugerida:** `docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md` (crear carpeta al primer uso).
