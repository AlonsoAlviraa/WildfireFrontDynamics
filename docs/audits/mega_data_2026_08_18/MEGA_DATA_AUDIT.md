# Mega auditoría de datos y ML

Actualizada: `2026-08-18T22:41:21.195880Z`

## Inventario físico

- Archivos: **46,755**
- Volumen: **80.13 GiB**
- Hashes SHA-256: **46,443**
- Grupos de duplicados por hash: **676**
- Grupos que cruzan datasets: **82**

## Veredicto por dataset

| Dataset | Archivos | GiB | Veredicto | Derechos | Bloqueos principales |
|---|---:|---:|---|---|---|
| `candidate_data` | 13 | 0.000 | `intake_only` | unknown | not_admitted_to_ml |
| `cfsds` | 28 | 0.058 | `usable_external_proxy` | cc-by-4.0_verify_descriptor | author_interpolation, not_tactical_ros, aligned_scene_adapter_missing |
| `external_dataset_catalog` | 1 | 0.000 | `catalog_only` | inherits_no_rights_from_listed_datasets | never_treat_catalog_as_training_data |
| `extremadura_rai` | 23 | 0.000 | `conditional` | public_service_terms_require_pack_review | progression_role_not_proven, training_rights_not_resolved_here |
| `firebench_caldor_bridge` | 1,084 | 8.921 | `evaluation_only` | inherits_mixed_upstream_rights | training_rights_unresolved, clean17_requires_new_checkpoint |
| `firebench_caldor_raw` | 79 | 1.306 | `evaluation_only` | mixed_upstream_rights | synoptic_notice_missing, mixed_rights, legacy17_incompatible |
| `firesentry_public_sample` | 5 | 0.001 | `reject_for_training_now` | no_explicit_dataset_license | sam2_generated_masks, no_human_qa, timezone_and_clip_mapping_missing |
| `fuel_map_cache` | 7 | 0.000 | `conditional_covariate` | esa_worldcover_cc-by-4.0_if_provenance_matches_filename | per_raster_source_manifest_missing, worldcover_to_fuel_crosswalk_is_model_assumption, fuel_age_and_live_moisture_not_observed |
| `fuel_weather_scenarios` | 2 | 0.000 | `restricted_case_study_covariate` | aemet_or_case_specific_source_terms | only_case_specific_scenarios, forecast_issue_time_and_available_by_t0_must_be_verified, not_a_training_corpus |
| `gofer` | 120 | 0.808 | `usable_external_proxy` | cc-by-4.0 | goes_source_resolution_about_2km, proxy_not_field_perimeter |
| `infocam_anchor_metadata` | 1 | 0.000 | `restricted_validation_metadata` | source_citations_per_anchor_required | pending_external_rows_are_not_valid_anchors, not_a_training_corpus, single_confirmed_case_currently |
| `latam_au_proxy` | 282 | 0.590 | `exploratory_evaluation_only` | per_source_mixed_or_resolved_in_pack | not_ndws_native, point_weather_spatially_constant, no_sealed_transfer_protocol |
| `models` | 21 | 0.032 | `model_artifact_only` | per_checkpoint_provenance | schema_and_training_corpus_compatibility_required |
| `outputs` | 8,201 | 7.268 | `artifact_only` | derived_artifact | target_or_prediction_leakage_if_reused_for_training |
| `pt_firesprd` | 400 | 0.079 | `conditional` | cc-by-4.0 | timestamp_timezone_unspecified, weather_join_not_yet_auditable |
| `rcda_net_full` | 18,016 | 30.740 | `usable_with_repaired_protocol` | mit | upstream_train_test_event_leakage, upstream_selects_early_stopping_and_threshold_on_test, public_labels_are_cumulative_t1_despite_increment_wording |
| `rcda_public_sample` | 5 | 0.006 | `usable_smoke_only` | mit | not_full_benchmark |
| `real_if_cite_drops` | 2 | 0.000 | `restricted_intake` | private_transfer | no_usable_payload_currently |
| `real_if_raw_dropbox` | 4,913 | 4.225 | `restricted_intake` | private_transfer | rights_and_semantics_per_file_unresolved, do_not_train_directly |
| `rediam_andalucia` | 13 | 0.084 | `reject_as_progression_label` | public_service_terms_require_pack_review | final_scar_not_temporal_progression |
| `static_covariates` | 7 | 0.002 | `usable_covariate` | per_source_provenance_required | verify_crs_resolution_and_source_rights |
| `tobarra_geacam` | 12 | 0.000 | `restricted_validation_only` | direct_email_no_redistribution_or_training_grant | only_one_event, timestamps_local_inferred, no_training_license |
| `uav_smoke_flame` | 12,181 | 10.567 | `reject_for_progression_ml` | mixed_kaggle_dataset_terms | no_temporal_perimeter_labels, heterogeneous_rights, mostly_rgb_detection |
| `weather_era5` | 70 | 0.005 | `usable_covariate_with_time_gate` | copernicus_terms | must_use_data_available_by_t0 |
| `weather_openmeteo` | 56 | 0.004 | `conditional_covariate` | provider_attribution_required | spatially_constant_if_used_as_point, availability_semantics_must_be_recorded |
| `wfigs_history` | 1,207 | 12.772 | `conditional_research_training` | public_internal_research_use_redistribution_unresolved | daily_perimeters_are_candidate_progression_not_ground_truth, eo_pixels_not_materialized, raw_derived_data_and_checkpoint_redistribution_blocked |
| `wildfirespreadts_partial` | 6 | 2.660 | `conditional_partial` | cc-by-4.0_for_wildfirespreadts_not_automatically_proxy | 48gb_full_dataset_absent, staged_ndws_proxy_is_not_wildfirespreadts |

## WFIGS

- Pares auditados: **3,439**
- Candidatos de investigaciÃ³n pendientes de rÃ¡steres: **2,767**
- Aptos para entrenamiento: **0**
- Veredictos: `{"historical_candidate_pending_rasters": 291, "partial_covariates": 381, "research_candidate_pending_rasters": 2767}`
- Motivos de bloqueo: `{"eo_full_perimeter_coverage_not_verified": 3439, "eo_pixels_not_materialized": 3439, "hrrr_full_window_unresolved": 381, "landsat_operational_availability_unverified": 2062, "sentinel2_operational_availability_unverified": 562}`

## RCDA sellado

Baseline dilated-copy: growth IoU **0.1108**, event-macro **0.1219**.

| Modelo | VAL IoU | TEST growth IoU | TEST event-macro | Δ IoU vs baseline | Far recall |
|---|---:|---:|---:|---:|---:|
| rcda | 0.1480 | 0.1543 | 0.1564 | +0.0435 | 0.0253 |
| unet | 0.1421 | 0.1553 | 0.1633 | +0.0445 | 0.0185 |

No se selecciona una arquitectura mirando TEST. Sólo hay una semilla y no hay intervalos de incertidumbre.
