# P2-B — Paper / public datasets (pretrain only, ablated)

> **As of:** 2026-08-13  
> **Campaign:** [`PLAN_ML_DATA_LATAM_AU_2026-08-13.md`](../PLAN_ML_DATA_LATAM_AU_2026-08-13.md)  
> **Hub local:** `data/external/EXTERNAL_DATASETS_HUB.json`  
> **Producto:** `clm_ensemble_v34` lab · **no** field_ops GO · **no** multi-IF ops

Estos conjuntos **no** sustituyen packs multi-escena LATAM/AU ni anclas CLM. Sirven solo como **pretrain / ablación** si un humano levanta FREEZE (F5). Hoy: **no retrain**.

## Tabla (bytes en repo vs papel)

| Dataset | En disco | Qué es | Uso permitido | No es |
|---------|----------|--------|---------------|-------|
| FireBench Caldor 2021 | `data/external/firebench/caldor_2021/` | Benchmark US fire (H5 + KML) | Pretrain / ROS research **ablated** | Perímetro CONAF/INFOCAM; no O2 ES |
| GOFER | `data/external/gofer/` | Perímetros investigación US | Ablation de geometría | Cadastro nacional ES/CL/AU |
| PT-FireSprd | `data/external/pt_firesprd/` | Fires Portugal (SHP) | Pretrain Europa | Dominio LATAM/AU |
| UAV smoke / FLAME-like | `data/external/uav_smoke_flame/` | Detección humo/llama en foto | Pretrain visión (no NDWS 17-ch) | Máscara quemada multi-fecha |
| WildfireSpreadTS / NDWS proxy | `data/external/wildfirespreadts/` | Series next-day US | Contrato NDWS (CLM ya usa este esquema) | Evento LATAM/AU |
| FLAME / Corsican (papel) | **no** staged aquí | UAV / mediterráneo clásico | Citar; bajar solo con rights | Multi-IF ops |

Hub stamp (`EXTERNAL_DATASETS_HUB.json`): FireBench `caldor_2021_staged`; UAV `kaggle_subsets_staged`; WildfireSpreadTS `partial_stage_docs_plus_ndws_proxy`. Rails del hub: `field_ops_allow_ml_live_in_fusion=false` en ese JSON histórico — el SSOT de producto es `docs/ML_PRODUCT_GO_STATUS.json` (fusion ON humana 2026-08-13). **No mezclar.**

## Protocolo de ablación (si F5)

1. Un dataset de la tabla = **un** run ablated, seed fijo, split sin leakage.  
2. Reportar IoU **solo** en el split de ese dataset; **no** mezclar con U1 TEST CLM ni con CEMS mask IoU.  
3. `compatible_with_clm_ensemble_v34` solo si el tensor es NDWS 17-ch. FLAME/UAV **no** lo son.  
4. No promover pesos a producto sin Δ vs copy en test CLM (`ML_TRANSFER_PROTOCOL`).

## Non-claims

- No “tenemos dataset mundial listo para field GO”.  
- No IoU FLAME = ROS táctico.  
- No MapBiomas/NAFI = paper FLAME.  
- No inventar transfer IoU LATAM/AU desde estos sets.

## Next (humano)

- Si se quiere FLAME original: anotar DOI + licencia en [`LATAM_AU_RIGHTS.md`](LATAM_AU_RIGHTS.md) **antes** de bajar.  
- No abrir retrain desde este documento.
