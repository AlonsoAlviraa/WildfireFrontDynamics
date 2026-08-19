# Política de investigación WFIGS

Actualizada: 2026-08-19

## Decisión

WFIGS queda habilitado para investigación y entrenamiento interno no comercial. El acceso del [ítem oficial de NIFC](https://www.arcgis.com/sharing/rest/content/items/7fa2437e625d49f7af1017c8617b68c1) es público y su aviso contempla el uso científico y agregado. El ítem no contiene una licencia afirmativa de redistribución; además, [DOI](https://www.doi.gov/copyright) advierte que no todo material alojado por organismos federales tiene necesariamente el mismo titular.

Esta es una política de gestión de riesgo del proyecto, no asesoramiento jurídico.

## Permitido ahora

- Descargar, auditar y conservar WFIGS internamente.
- Construir pares temporales y splits por `event_id`.
- Materializar covariables y entrenar modelos para investigación no comercial.
- Publicar código, configuración, metodología, gráficas y métricas agregadas.

## Bloqueado hasta confirmación expresa

- Redistribuir geometrías o copias de WFIGS.
- Publicar teselas, tensores o datasets derivados.
- Publicar checkpoints entrenados con WFIGS.
- Uso comercial.

La política ejecutable vive en `wildfire_front/open_if/regional/wfigs_rights.py`. Para migrar manifiestos existentes sin recalcular geometrías:

```powershell
python scripts/refresh_wfigs_rights.py --json
python scripts/audit_all_repo_data.py --refresh-existing --json
```
