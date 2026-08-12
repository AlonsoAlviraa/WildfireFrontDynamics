# Stitch · WFD Industrial C2 Console

| Campo | Valor |
|-------|--------|
| **Stitch project** | `projects/6685398829230236101` — *WFD Industrial C2 Console* |
| **Design system** | `assets/9115718078965767463` — *WFD Industrial C2* |
| **Screen** | `ops_console.html` (mock) · runtime `wildfire_front/product/app_spa_html.py` |
| **As of** | 2026-08-11 |

## Industry references (copied)

- **EOC / WebEOC-class** situational awareness: dense status chips, short labels
- **GIS ops (Esri dashboard density)**: map-first (~68%), legend bottom-left, FAB
- **SOC / C2**: dark panels `#111827`, borders `#1F2937`, no marketing fluff
- **ATC-like**: decision color-only (GO/HOLD/ABSTAIN), max one line under word

## Tokens

| Token | Value |
|-------|--------|
| bg | `#0B1220` |
| panel | `#111827` |
| border | `#1F2937` |
| accent | `#0EA5E9` |
| GO / HOLD / ABSTAIN | `#22C55E` / `#F59E0B` / `#EF4444` |
| local / FIRMS | `#38BDF8` / `#FB7185` |
| font | IBM Plex Sans |
| radius | 4px |
| top bar | 48px |
| rail | ≤380px |

## Layout

```
┌─ top 48px: W WFD OPS | incident | chips | Fácil|Pro | ? ─┐
│ map 68%                              │ rail 380px        │
│  HUD + legend + FAB                  │ GO / HOLD         │
│                                      │ KPI 2×2           │
│                                      │ next one-liner    │
│                                      │ Estado|Decidir|Acta│
│                                      │ Abrir | Mapa      │
│                                      │ tabs + content    │
└──────────────────────────────────────┴───────────────────┘
```

Shell never scrolls. Only rail content scrolls. Primary acts always visible (`acta_cmd` etc. from fire catalog).

## Runtime

```powershell
$env:PYTHONPATH = "."
python -m wildfire_front app --fire _sla_measure --open
```
