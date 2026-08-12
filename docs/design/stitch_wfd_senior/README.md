# Stitch · WFD Consola Accesible (señor mayor)

| Campo | Valor |
|-------|--------|
| **Stitch project** | `projects/2753452354185331249` — *WFD Consola Incendios - Accesible Senior* |
| **Design system** | `assets/10889567912844061620` — *WFD Accesible Mayor* |
| **As of** | 2026-08-10 |
| **Runtime** | `wildfire_front/product/app_spa_html.py` ← generado a partir de estas pantallas |

## Pantallas generadas

| Pantalla | Archivo local | Idea |
|----------|---------------|------|
| Estado del incendio | `estado_incendio.html` | Mapa + decisión grande + pestañas |
| Qué puedo hacer | `que_puedo_hacer.html` | CTAs con «Copiar instrucción» |
| Diccionario | `diccionario.html` | GO/HOLD/ABSTAIN en español llano |

## Tokens

- Fondo crema `#F7F4ED`, papel `#FFFDF5`
- Verde bosque `#1B4D3E` (primario)
- GO `#0B7A4B` · HOLD `#C47A00` · ABSTAIN `#B3261E`
- Mapa cian `#0E7C8A` · FIRMS naranja `#D9480F`
- Tipografía legible (Atkinson Hyperlegible en runtime)
- Botones ≥ 56px, cuerpo ≥ 18px, modo **Texto grande**

## Principios

1. Un mando o un técnico senior entiende la pantalla en 10 s.
2. GO / HOLD / ABSTAIN siempre con frase en español debajo.
3. **Todos** los botones dan feedback (toast «Copiado» / «Hecho»).
4. Modo fácil = sin CLI; Avanzado = comandos `python -m wildfire_front …`.
5. No es despacho táctico; fusión ML de campo OFF.

## Regenerar runtime

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front app --fire _sla_measure --open
```
