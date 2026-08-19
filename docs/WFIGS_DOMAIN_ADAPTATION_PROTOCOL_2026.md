# Protocolo pre-registrado de adaptación RCDA → WFIGS

Fecha: 2026-08-19. Registrado antes de materializar o evaluar WFIGS TEST.

## Objetivo

Medir dos escenarios distintos sobre incendios WFIGS no vistos:

1. transferencia cero-shot de los tres checkpoints RCDA congelados;
2. adaptación de dominio usando únicamente WFIGS TRAIN y VALIDATION.

## Cohortes

- Hasta 8 incendios TRAIN por región CONUS, un par por incendio.
- Hasta 3 incendios VALIDATION por región, sin eventos compartidos con TRAIN.
- Hasta 3 incendios TEST por región, materializados solo después de congelar los
  modelos y umbrales correspondientes.
- Recorte fijo 256×256 a 60 m, posicionado solo mediante `t0`.
- Sentinel-2 creado antes de `t0`, DEM GLO-30 y corrida HRRR disponible antes de
  `t0` y válida espacialmente.
- Para mantener compatibilidad con los 16 canales RCDA, los píxeles ópticos no
  válidos se imputan con la mediana de píxeles válidos de la misma escena; la
  máscara se conserva en el tensor fuente y la imputación nunca usa `t1`.

## Cero-shot

- Arquitectura, pesos y umbral: los ya congelados por RCDA VALIDATION.
- WFIGS VALIDATION y TEST no intervienen en ninguna selección del modelo.
- Se reportan las tres semillas por separado y su media macro por incendio.

## Adaptación de dominio

- Inicialización: cada uno de los tres checkpoints finales RCDA.
- Optimizador: AdamW, `lr=1e-4`, `weight_decay=1e-4`.
- Máximo 30 épocas, batch 4 y paciencia 7.
- Objetivo y arquitectura: los de la receta RCDA congelada; no se abre un sweep
  adicional.
- Época: máximo IoU macro por incendio en WFIGS VALIDATION sobre umbrales
  `0.1..0.9`.
- Umbral final: rejilla `0.05..0.95` sobre WFIGS VALIDATION.
- WFIGS TEST se evalúa una sola vez por semilla después de guardar los tres
  checkpoints adaptados.

## Comparadores y claims

- Baseline geométrico: dilatación cuyo radio se eligió exclusivamente en WFIGS
  VALIDATION.
- La evaluación se aborta si el baseline no contiene exactamente un registro
  utilizable para cada `pair_id` de TEST; no se permite convertir cobertura
  ausente en IoU cero.
- Se reportará cero-shot y adaptación por separado; adaptar no se presentará
  como generalización cero-shot.
- No se afirmará validez operativa por superar el baseline en este piloto.
- Tensores y checkpoints WFIGS son internos, no comerciales y no redistribuibles
  bajo la política conservadora de derechos vigente.

## Auditoría previa a entrenamiento

El ensamblado TRAIN/VALIDATION produjo 80 tensores (61/19), uno por incendio,
todos con forma `13×256×256`. `scripts/audit_wfigs_tensor_dataset.py` releyó los
80 archivos, recomputó los extremos de normalización sólo desde TRAIN y verificó
finitud, máscaras binarias, definición del target de crecimiento, IDs únicos y
disjunción por evento. Resultado: `pass`, 0 incidencias. TEST permaneció ausente.
