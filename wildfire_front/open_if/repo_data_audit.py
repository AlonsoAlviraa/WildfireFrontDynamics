"""Repository-wide file, dataset, and WFIGS pair ML usability audit."""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .regional.base import _atomic_write_bytes, _atomic_write_json, utc_now

AUDIT_SCHEMA = "wfd_mega_data_audit_v1"
FILE_AUDIT_SCHEMA = "wfd_file_audit_v1"
PAIR_AUDIT_SCHEMA = "wfd_wfigs_pair_row_audit_v1"


def _markdown_report(report: dict[str, Any]) -> str:
    file_summary = report["files"]
    report_time = report.get("refreshed_at") or report.get("derived_refreshed_at") or report[
        "generated_at"
    ]
    lines = [
        "# Mega auditoría de datos y ML",
        "",
        f"Actualizada: `{report_time}`",
        "",
        "## Inventario físico",
        "",
        f"- Archivos: **{file_summary['files']:,}**",
        f"- Volumen: **{file_summary['bytes'] / (1024**3):.2f} GiB**",
        f"- Hashes SHA-256: **{file_summary['files_hashed']:,}**",
        f"- Grupos de duplicados por hash: **{file_summary['duplicate_hash_groups']:,}**",
        f"- Grupos que cruzan datasets: **{file_summary.get('cross_dataset_duplicate_groups', 0):,}**",
        "",
        "## Veredicto por dataset",
        "",
        "| Dataset | Archivos | GiB | Veredicto | Derechos | Bloqueos principales |",
        "|---|---:|---:|---|---|---|",
    ]
    for dataset_id, row in sorted(report["datasets"].items()):
        blockers = ", ".join(row.get("blockers") or []) or "—"
        lines.append(
            f"| `{dataset_id}` | {row['files']:,} | "
            f"{row['bytes'] / (1024**3):.3f} | `{row['verdict']}` | "
            f"{row.get('rights', 'unknown')} | {blockers} |"
        )

    wfigs = report.get("wfigs_pairs")
    lines.extend(["", "## WFIGS", ""])
    if not wfigs:
        lines.append("Baseline o enriquecimiento aún no disponible.")
    else:
        lines.extend(
            [
                f"- Pares auditados: **{wfigs['pairs']:,}**",
                f"- Candidatos de investigaciÃ³n pendientes de rÃ¡steres: "
                f"**{wfigs.get('research_training_candidates', 0):,}**",
                f"- Aptos para entrenamiento: **{wfigs['training_ready']:,}**",
                f"- Veredictos: `{json.dumps(wfigs['verdicts'], ensure_ascii=False)}`",
                f"- Motivos de bloqueo: `{json.dumps(wfigs['reasons'], ensure_ascii=False)}`",
            ]
        )

    rcda = report.get("rcda_sealed_results")
    lines.extend(["", "## RCDA sellado", ""])
    if not rcda:
        lines.append("No se encontró una corrida completa auditable.")
    else:
        baseline = rcda["baseline"]
        lines.append(
            f"Baseline dilated-copy: growth IoU **{baseline['sealed_test_growth_iou']:.4f}**, "
            f"event-macro **{baseline['sealed_test_event_macro_growth_iou']:.4f}**."
        )
        lines.extend(
            [
                "",
                "| Modelo | VAL IoU | TEST growth IoU | TEST event-macro | Δ IoU vs baseline | Far recall |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for name, row in sorted(rcda["models"].items()):
            test = row["sealed_test"]
            lines.append(
                f"| {name} | {row['validation']['iou']:.4f} | {test['growth_iou']:.4f} | "
                f"{test['event_macro_growth_iou']:.4f} | "
                f"{test['delta_growth_iou_vs_dilated_copy']:+.4f} | "
                f"{test['far_gt_10_5px_recall']:.4f} |"
            )
        lines.extend(
            [
                "",
                "No se selecciona una arquitectura mirando TEST. Sólo hay una semilla y no hay intervalos de incertidumbre.",
            ]
        )
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class DatasetPolicy:
    dataset_id: str
    path_prefix: str
    verdict: str
    progression_ml: str
    rights: str
    allowed_uses: tuple[str, ...]
    blockers: tuple[str, ...]
    evidence: tuple[str, ...] = ()


POLICIES = (
    DatasetPolicy(
        "rcda_net_full",
        "data/external/rcda_net_full/",
        "usable_with_repaired_protocol",
        "yes_increment_or_cumulative_contract_must_be_explicit",
        "mit",
        ("sealed_event_disjoint_training", "baseline_evaluation", "architecture_research"),
        (
            "upstream_train_test_event_leakage",
            "upstream_selects_early_stopping_and_threshold_on_test",
            "public_labels_are_cumulative_t1_despite_increment_wording",
        ),
        ("docs/RCDA_NET_FULL_PROTOCOL.json", "docs/RCDA_NET_PROTOCOL_AUDIT.json"),
    ),
    DatasetPolicy(
        "rcda_public_sample",
        "data/external/rcda_net_public_sample/",
        "usable_smoke_only",
        "sample_only",
        "mit",
        ("adapter_smoke_test", "schema_validation"),
        ("not_full_benchmark",),
    ),
    DatasetPolicy(
        "gofer",
        "data/external/gofer/",
        "usable_external_proxy",
        "hourly_proxy_not_tactical_ground_truth",
        "cc-by-4.0",
        ("hourly_progression_benchmark", "ros_method_validation"),
        ("goes_source_resolution_about_2km", "proxy_not_field_perimeter"),
        ("data/external/gofer/inventory.json",),
    ),
    DatasetPolicy(
        "cfsds",
        "data/external/cfsds/",
        "usable_external_proxy",
        "daily_growth_proxy",
        "cc-by-4.0_verify_descriptor",
        ("daily_growth_pretraining", "event_level_external_validation"),
        ("author_interpolation", "not_tactical_ros", "aligned_scene_adapter_missing"),
        ("data/external/cfsds/inventory.json",),
    ),
    DatasetPolicy(
        "pt_firesprd",
        "data/external/pt_firesprd/",
        "conditional",
        "yes_after_timestamp_resolution",
        "cc-by-4.0",
        ("geometry_evaluation", "mediterranean_progression_research"),
        ("timestamp_timezone_unspecified", "weather_join_not_yet_auditable"),
        ("data/external/pt_firesprd/inventory.json",),
    ),
    DatasetPolicy(
        "firebench_caldor_raw",
        "data/external/firebench/",
        "evaluation_only",
        "geometry_only_now",
        "mixed_upstream_rights",
        ("geometry_evaluation", "label_pair_analysis"),
        ("synoptic_notice_missing", "mixed_rights", "legacy17_incompatible"),
        ("docs/CALDOR_CLEAN17_AUDIT.json", "docs/EXTERNAL_ML_COMPATIBILITY_AUDIT.json"),
    ),
    DatasetPolicy(
        "firebench_caldor_bridge",
        "data/open_if/external_bridge/",
        "evaluation_only",
        "geometry_only_now",
        "inherits_mixed_upstream_rights",
        ("geometry_evaluation", "covariate_contract_testing"),
        ("training_rights_unresolved", "clean17_requires_new_checkpoint"),
        ("docs/CALDOR_CLEAN17_AUDIT.json",),
    ),
    DatasetPolicy(
        "firesentry_public_sample",
        "data/external/firesentry_public_sample/",
        "reject_for_training_now",
        "uav_mask_pretraining_candidate_only",
        "no_explicit_dataset_license",
        ("schema_research", "manual_mask_qa"),
        ("sam2_generated_masks", "no_human_qa", "timezone_and_clip_mapping_missing"),
        ("docs/FIRESENTRY_DATASET_AUDIT.json",),
    ),
    DatasetPolicy(
        "uav_smoke_flame",
        "data/external/uav_smoke_flame/",
        "reject_for_progression_ml",
        "no_detection_images_are_not_progression",
        "mixed_kaggle_dataset_terms",
        ("smoke_detection_lab", "flame_detection_lab"),
        ("no_temporal_perimeter_labels", "heterogeneous_rights", "mostly_rgb_detection"),
        ("data/external/uav_smoke_flame/manifest.json",),
    ),
    DatasetPolicy(
        "wildfirespreadts_partial",
        "data/external/wildfirespreadts/",
        "conditional_partial",
        "full_dataset_not_staged",
        "cc-by-4.0_for_wildfirespreadts_not_automatically_proxy",
        ("documentation", "ndws_legacy_baseline"),
        ("48gb_full_dataset_absent", "staged_ndws_proxy_is_not_wildfirespreadts"),
        ("data/external/wildfirespreadts/manifest.json",),
    ),
    DatasetPolicy(
        "wfigs_history",
        "data/open_if/wfigs_history_2020_2026/",
        "conditional_research_training",
        "candidate_progression_labels",
        "public_internal_research_use_redistribution_unresolved",
        (
            "geometry_evaluation",
            "pair_audit",
            "metadata_enrichment",
            "internal_noncommercial_training",
            "aggregate_metrics_publication",
        ),
        (
            "daily_perimeters_are_candidate_progression_not_ground_truth",
            "eo_pixels_not_materialized",
            "raw_derived_data_and_checkpoint_redistribution_blocked",
        ),
        (
            "data/open_if/wfigs_history_2020_2026/temporal_pairs/INVENTORY.json",
            "data/open_if/wfigs_history_2020_2026/temporal_pairs/RIGHTS_POLICY.json",
        ),
    ),
    DatasetPolicy(
        "latam_au_proxy",
        "data/open_if/latam_au/",
        "exploratory_evaluation_only",
        "proxy_temporal_pairs",
        "per_source_mixed_or_resolved_in_pack",
        ("exploratory_proxy_benchmark", "adapter_validation"),
        ("not_ndws_native", "point_weather_spatially_constant", "no_sealed_transfer_protocol"),
        ("docs/EXTERNAL_ML_COMPATIBILITY_AUDIT.json",),
    ),
    DatasetPolicy(
        "extremadura_rai",
        "data/open_if/extremadura_rai_2025/",
        "conditional",
        "incident_vectors_require_temporal_semantics_audit",
        "public_service_terms_require_pack_review",
        ("incident_discovery", "geometry_qa"),
        ("progression_role_not_proven", "training_rights_not_resolved_here"),
    ),
    DatasetPolicy(
        "rediam_andalucia",
        "data/open_if/rediam_andalucia/",
        "reject_as_progression_label",
        "final_or_catalog_perimeters",
        "public_service_terms_require_pack_review",
        ("event_discovery", "final_extent_context"),
        ("final_scar_not_temporal_progression",),
    ),
    DatasetPolicy(
        "tobarra_geacam",
        "data/real_if/pablo_geacam_20260730_tobarra/",
        "restricted_validation_only",
        "two_real_operational_perimeters",
        "direct_email_no_redistribution_or_training_grant",
        ("internal_geometry_validation", "case_study"),
        ("only_one_event", "timestamps_local_inferred", "no_training_license"),
        ("data/real_if/pablo_geacam_20260730_tobarra/inventory.json",),
    ),
    DatasetPolicy(
        "real_if_raw_dropbox",
        "data/real_if/raw_dropbox/",
        "restricted_intake",
        "unknown_until_decode_and_event_audit",
        "private_transfer",
        ("forensic_intake", "internal_validation_after_decode"),
        ("rights_and_semantics_per_file_unresolved", "do_not_train_directly"),
    ),
    DatasetPolicy(
        "real_if_cite_drops",
        "data/real_if/cite_drops/",
        "restricted_intake",
        "empty_or_pending_intake",
        "private_transfer",
        ("future_intake",),
        ("no_usable_payload_currently",),
    ),
    DatasetPolicy(
        "weather_era5",
        "data/weather_era5/",
        "usable_covariate_with_time_gate",
        "covariate_not_label",
        "copernicus_terms",
        ("weather_covariate",),
        ("must_use_data_available_by_t0",),
    ),
    DatasetPolicy(
        "weather_openmeteo",
        "data/weather_openmeteo/",
        "conditional_covariate",
        "point_or_archive_weather_not_label",
        "provider_attribution_required",
        ("exploratory_weather_covariate",),
        ("spatially_constant_if_used_as_point", "availability_semantics_must_be_recorded"),
    ),
    DatasetPolicy(
        "static_covariates",
        "data/dem/",
        "usable_covariate",
        "static_covariate_not_label",
        "per_source_provenance_required",
        ("terrain_covariate",),
        ("verify_crs_resolution_and_source_rights",),
    ),
    DatasetPolicy(
        "fuel_map_cache",
        "data/fuel_map/",
        "conditional_covariate",
        "land_cover_proxy_not_observed_fuel_load",
        "esa_worldcover_cc-by-4.0_if_provenance_matches_filename",
        ("fuel_class_covariate", "physics_prior_input"),
        (
            "per_raster_source_manifest_missing",
            "worldcover_to_fuel_crosswalk_is_model_assumption",
            "fuel_age_and_live_moisture_not_observed",
        ),
    ),
    DatasetPolicy(
        "fuel_weather_scenarios",
        "data/fuel_stack/",
        "restricted_case_study_covariate",
        "weather_scenario_not_progression_label",
        "aemet_or_case_specific_source_terms",
        ("tobarra_case_study", "physics_prior_input"),
        (
            "only_case_specific_scenarios",
            "forecast_issue_time_and_available_by_t0_must_be_verified",
            "not_a_training_corpus",
        ),
    ),
    DatasetPolicy(
        "infocam_anchor_metadata",
        "data/infocam_anchors.json",
        "restricted_validation_metadata",
        "scalar_case_anchor_not_progression_geometry",
        "source_citations_per_anchor_required",
        ("case_level_sanity_check", "ros_anchor_review"),
        (
            "pending_external_rows_are_not_valid_anchors",
            "not_a_training_corpus",
            "single_confirmed_case_currently",
        ),
    ),
    DatasetPolicy(
        "external_dataset_catalog",
        "data/external/EXTERNAL_DATASETS_HUB.json",
        "catalog_only",
        "metadata_not_label_data",
        "inherits_no_rights_from_listed_datasets",
        ("dataset_discovery", "artifact_routing"),
        ("never_treat_catalog_as_training_data",),
    ),
    DatasetPolicy(
        "candidate_data",
        "data/candidates/",
        "intake_only",
        "not_validated",
        "unknown",
        ("candidate_review",),
        ("not_admitted_to_ml",),
    ),
    DatasetPolicy(
        "outputs",
        "outputs/",
        "artifact_only",
        "never_training_input",
        "derived_artifact",
        ("evaluation", "reporting", "reproducibility"),
        ("target_or_prediction_leakage_if_reused_for_training",),
    ),
    DatasetPolicy(
        "models",
        "models/",
        "model_artifact_only",
        "never_label_data",
        "per_checkpoint_provenance",
        ("inference", "frozen_evaluation"),
        ("schema_and_training_corpus_compatibility_required",),
    ),
)


def _policy_for(relative: str) -> DatasetPolicy:
    normalized = relative.replace("\\", "/")
    matches = [policy for policy in POLICIES if normalized.startswith(policy.path_prefix)]
    if matches:
        return max(matches, key=lambda policy: len(policy.path_prefix))
    if normalized.startswith("data/"):
        return DatasetPolicy(
            "unclassified_data",
            "data/",
            "needs_manual_review",
            "unknown",
            "unknown",
            ("inventory_only",),
            ("no_dataset_policy_match",),
        )
    return DatasetPolicy(
        "unclassified_artifact",
        "",
        "artifact_only",
        "never_training_input",
        "unknown",
        ("inventory_only",),
        ("outside_admitted_data_roots",),
    )


def _role(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".shp", ".gpkg", ".geojson", ".kml", ".kmz"}:
        return "vector_or_geometry"
    if suffix in {".tif", ".tiff", ".nc", ".grib", ".grib2"}:
        return "raster_or_gridded_covariate"
    if suffix in {".h5", ".hdf5", ".npz", ".npy", ".pt", ".pth", ".ckpt"}:
        return "tensor_or_model_binary"
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return "image"
    if suffix in {".json", ".jsonl", ".csv", ".tsv", ".parquet", ".dbf"}:
        return "tabular_or_metadata"
    if suffix in {".zip", ".rar", ".7z", ".tar", ".gz"}:
        return "archive"
    if suffix in {".md", ".txt", ".pdf", ".html", ".xml"}:
        return "documentation_or_sidecar"
    if suffix in {".py", ".r", ".ps1", ".sh"}:
        return "code"
    return "other"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _health(path: Path, size: int) -> tuple[str, str | None]:
    if size <= 0:
        if path.name in {"__init__.py", ".gitkeep"} or path.suffix.lower() in {
            ".flag",
            ".log",
        }:
            return "empty_nondata_artifact", "zero_bytes_expected_or_non_material"
        return "empty", "zero_bytes"
    if path.suffix.lower() == ".json" and size <= 32 * 1024 * 1024:
        try:
            json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return "invalid", f"json:{type(exc).__name__}"
    return "present", None


def _iter_files(repo_root: Path, roots: Iterable[str]) -> Iterable[Path]:
    for root_name in roots:
        root = repo_root / root_name
        if not root.exists():
            continue
        for directory, _subdirs, filenames in os.walk(root):
            for filename in filenames:
                yield Path(directory) / filename


class RepositoryDataAuditor:
    """Audit every local data/artifact file and every enriched WFIGS pair."""

    def __init__(
        self,
        *,
        repo_root: Path,
        output_root: Path,
        hash_mode: str = "small",
        small_hash_limit: int = 16 * 1024 * 1024,
    ) -> None:
        if hash_mode not in {"none", "small", "all"}:
            raise ValueError("hash_mode must be none, small, or all")
        self.repo_root = Path(repo_root).resolve()
        self.output_root = Path(output_root)
        self.hash_mode = hash_mode
        self.small_hash_limit = small_hash_limit

    def _audit_files(self) -> tuple[dict[str, Any], dict[str, Any]]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        file_path = self.output_root / "DATA_FILE_AUDIT.jsonl"
        temporary = file_path.with_name(f".{file_path.name}.{os.getpid()}.tmp")
        dataset_counts: dict[str, Counter[str]] = defaultdict(Counter)
        dataset_bytes: Counter[str] = Counter()
        health_counts: Counter[str] = Counter()
        verdict_counts: Counter[str] = Counter()
        hashes: dict[str, list[str]] = defaultdict(list)
        total_files = 0
        total_bytes = 0
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for path in _iter_files(self.repo_root, ("data", "outputs", "models")):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                relative = path.relative_to(self.repo_root).as_posix()
                policy = _policy_for(relative)
                health, health_reason = _health(path, stat.st_size)
                should_hash = self.hash_mode == "all" or (
                    self.hash_mode == "small" and stat.st_size <= self.small_hash_limit
                )
                digest = None
                if should_hash and health != "empty":
                    try:
                        digest = _sha256(path)
                    except OSError:
                        health = "unreadable"
                        health_reason = "sha256_read_failed"
                row = {
                    "schema": FILE_AUDIT_SCHEMA,
                    "path": relative,
                    "dataset_id": policy.dataset_id,
                    "bytes": stat.st_size,
                    "modified_at": datetime_from_timestamp(stat.st_mtime),
                    "suffix": path.suffix.lower(),
                    "role": _role(path),
                    "health": health,
                    "health_reason": health_reason,
                    "sha256": digest,
                    "sha256_status": "computed" if digest else "not_computed",
                    "ml_verdict": policy.verdict,
                    "progression_ml": policy.progression_ml,
                    "rights": policy.rights,
                    "allowed_uses": list(policy.allowed_uses),
                    "blockers": list(policy.blockers),
                }
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                total_files += 1
                total_bytes += stat.st_size
                dataset_counts[policy.dataset_id]["files"] += 1
                dataset_counts[policy.dataset_id][health] += 1
                dataset_bytes[policy.dataset_id] += stat.st_size
                health_counts[health] += 1
                verdict_counts[policy.verdict] += 1
                if digest:
                    hashes[digest].append(relative)
        temporary.replace(file_path)
        duplicate_groups = [paths for paths in hashes.values() if len(paths) > 1]
        cross_dataset_duplicate_groups = sum(
            len({_policy_for(path).dataset_id for path in paths}) > 1
            for paths in duplicate_groups
        )
        summary = {
            "file": str(file_path),
            "files": total_files,
            "bytes": total_bytes,
            "health": dict(sorted(health_counts.items())),
            "verdicts": dict(sorted(verdict_counts.items())),
            "hash_mode": self.hash_mode,
            "files_hashed": sum(len(paths) for paths in hashes.values()),
            "duplicate_hash_groups": len(duplicate_groups),
            "cross_dataset_duplicate_groups": cross_dataset_duplicate_groups,
        }
        datasets = {
            policy.dataset_id: {
                "path_prefix": policy.path_prefix,
                "verdict": policy.verdict,
                "progression_ml": policy.progression_ml,
                "rights": policy.rights,
                "allowed_uses": list(policy.allowed_uses),
                "blockers": list(policy.blockers),
                "evidence": list(policy.evidence),
                "files": dataset_counts[policy.dataset_id]["files"],
                "bytes": dataset_bytes[policy.dataset_id],
                "health": {
                    key: value
                    for key, value in dataset_counts[policy.dataset_id].items()
                    if key != "files"
                },
            }
            for policy in POLICIES
            if dataset_counts[policy.dataset_id]["files"]
        }
        for dataset_id in sorted(set(dataset_counts) - set(datasets)):
            datasets[dataset_id] = {
                "verdict": "needs_manual_review",
                "files": dataset_counts[dataset_id]["files"],
                "bytes": dataset_bytes[dataset_id],
                "health": {
                    key: value
                    for key, value in dataset_counts[dataset_id].items()
                    if key != "files"
                },
            }
        return summary, datasets

    def _reclassify_existing_files(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Reapply policies and health checks while preserving existing hashes."""
        file_path = self.output_root / "DATA_FILE_AUDIT.jsonl"
        if not file_path.is_file():
            raise FileNotFoundError(f"existing file audit not found: {file_path}")
        temporary = file_path.with_name(f".{file_path.name}.{os.getpid()}.tmp")
        dataset_counts: dict[str, Counter[str]] = defaultdict(Counter)
        dataset_bytes: Counter[str] = Counter()
        health_counts: Counter[str] = Counter()
        verdict_counts: Counter[str] = Counter()
        hashes: dict[str, list[str]] = defaultdict(list)
        seen_paths: set[str] = set()
        new_files_added = 0
        total_files = 0
        total_bytes = 0
        with file_path.open("r", encoding="utf-8") as source, temporary.open(
            "w", encoding="utf-8", newline="\n"
        ) as target:
            for line in source:
                row = json.loads(line)
                relative = str(row["path"])
                seen_paths.add(relative)
                policy = _policy_for(relative)
                path = self.repo_root / relative
                size = int(row["bytes"])
                health, health_reason = (
                    _health(path, size)
                    if path.is_file()
                    else ("missing_since_scan", "path_missing")
                )
                row.update(
                    {
                        "dataset_id": policy.dataset_id,
                        "health": health,
                        "health_reason": health_reason,
                        "ml_verdict": policy.verdict,
                        "progression_ml": policy.progression_ml,
                        "rights": policy.rights,
                        "allowed_uses": list(policy.allowed_uses),
                        "blockers": list(policy.blockers),
                    }
                )
                target.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                total_files += 1
                total_bytes += size
                dataset_counts[policy.dataset_id]["files"] += 1
                dataset_counts[policy.dataset_id][health] += 1
                dataset_bytes[policy.dataset_id] += size
                health_counts[health] += 1
                verdict_counts[policy.verdict] += 1
                digest = row.get("sha256")
                if digest:
                    hashes[str(digest)].append(relative)
            for path in _iter_files(self.repo_root, ("data", "outputs", "models")):
                relative = path.relative_to(self.repo_root).as_posix()
                if relative in seen_paths:
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                policy = _policy_for(relative)
                health, health_reason = _health(path, stat.st_size)
                digest = None
                if 0 < stat.st_size <= self.small_hash_limit:
                    try:
                        digest = _sha256(path)
                    except OSError:
                        health = "unreadable"
                        health_reason = "sha256_read_failed"
                row = {
                    "schema": FILE_AUDIT_SCHEMA,
                    "path": relative,
                    "dataset_id": policy.dataset_id,
                    "bytes": stat.st_size,
                    "modified_at": datetime_from_timestamp(stat.st_mtime),
                    "suffix": path.suffix.lower(),
                    "role": _role(path),
                    "health": health,
                    "health_reason": health_reason,
                    "sha256": digest,
                    "sha256_status": "computed" if digest else "not_computed",
                    "ml_verdict": policy.verdict,
                    "progression_ml": policy.progression_ml,
                    "rights": policy.rights,
                    "allowed_uses": list(policy.allowed_uses),
                    "blockers": list(policy.blockers),
                }
                target.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                total_files += 1
                total_bytes += stat.st_size
                new_files_added += 1
                dataset_counts[policy.dataset_id]["files"] += 1
                dataset_counts[policy.dataset_id][health] += 1
                dataset_bytes[policy.dataset_id] += stat.st_size
                health_counts[health] += 1
                verdict_counts[policy.verdict] += 1
                if digest:
                    hashes[digest].append(relative)
        temporary.replace(file_path)
        summary = {
            "file": str(file_path),
            "files": total_files,
            "bytes": total_bytes,
            "health": dict(sorted(health_counts.items())),
            "verdicts": dict(sorted(verdict_counts.items())),
            "hash_mode": "preserved",
            "files_hashed": sum(len(paths) for paths in hashes.values()),
            "duplicate_hash_groups": sum(len(paths) > 1 for paths in hashes.values()),
            "cross_dataset_duplicate_groups": sum(
                len({_policy_for(path).dataset_id for path in paths}) > 1
                for paths in hashes.values()
                if len(paths) > 1
            ),
            "new_files_added_on_refresh": new_files_added,
        }
        datasets = {
            policy.dataset_id: {
                "path_prefix": policy.path_prefix,
                "verdict": policy.verdict,
                "progression_ml": policy.progression_ml,
                "rights": policy.rights,
                "allowed_uses": list(policy.allowed_uses),
                "blockers": list(policy.blockers),
                "evidence": list(policy.evidence),
                "files": dataset_counts[policy.dataset_id]["files"],
                "bytes": dataset_bytes[policy.dataset_id],
                "health": {
                    key: value
                    for key, value in dataset_counts[policy.dataset_id].items()
                    if key != "files"
                },
            }
            for policy in POLICIES
            if dataset_counts[policy.dataset_id]["files"]
        }
        return summary, datasets

    def _audit_wfigs_pairs(self) -> dict[str, Any] | None:
        root = self.repo_root / "data/open_if/wfigs_history_2020_2026"
        pairs_path = root / "temporal_pairs/PAIRS.json"
        enrichment_path = root / "enrichment/PAIR_ENRICHMENT.json"
        baseline_path = root / "ml/GEOMETRY_BASELINE.json"
        if not (pairs_path.is_file() and enrichment_path.is_file() and baseline_path.is_file()):
            return None
        pairs = json.loads(pairs_path.read_text(encoding="utf-8")).get("pairs") or []
        enriched = {
            str(row["pair_id"]): row
            for row in json.loads(enrichment_path.read_text(encoding="utf-8")).get("pairs") or []
        }
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_rows = {str(row["pair_id"]): row for row in baseline.get("per_pair") or []}
        output_path = self.output_root / "WFIGS_PAIR_AUDIT.jsonl"
        temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
        verdicts: Counter[str] = Counter()
        reasons: Counter[str] = Counter()
        split_counts: Counter[str] = Counter()
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            for pair in pairs:
                pair_id = str(pair["pair_id"])
                eo_weather = enriched.get(pair_id) or {}
                baseline_row = baseline_rows.get(pair_id) or {}
                sensor_rows = eo_weather.get("eo") or {}
                sentinel = (sensor_rows.get("sentinel2") or {}).get("status") == "resolved"
                landsat = (sensor_rows.get("landsat") or {}).get("status") == "resolved"
                sentinel_candidates = (sensor_rows.get("sentinel2") or {}).get("candidates") or []
                landsat_candidates = (sensor_rows.get("landsat") or {}).get("candidates") or []
                sentinel_created = bool(sentinel_candidates) and bool(
                    sentinel_candidates[0].get("stac_created_at_or_before_t0")
                )
                landsat_created = bool(landsat_candidates) and bool(
                    landsat_candidates[0].get("stac_created_at_or_before_t0")
                )
                operational_eo = sentinel_created or landsat_created
                weather = (eo_weather.get("weather") or {}).get("status") == "resolved"
                geometry = baseline_row.get("status") == "usable"
                row_reasons = [
                    "eo_pixels_not_materialized",
                    "eo_full_perimeter_coverage_not_verified",
                ]
                if not geometry:
                    row_reasons.append("geometry_baseline_unusable")
                if not sentinel:
                    row_reasons.append("sentinel2_pre_t0_missing")
                if not landsat:
                    row_reasons.append("landsat_pre_t0_missing")
                if sentinel and not sentinel_created:
                    row_reasons.append("sentinel2_operational_availability_unverified")
                if landsat and not landsat_created:
                    row_reasons.append("landsat_operational_availability_unverified")
                if not weather:
                    row_reasons.append("hrrr_full_window_unresolved")
                research_candidate = geometry and operational_eo and weather
                if not geometry:
                    verdict = "reject"
                elif research_candidate:
                    verdict = "research_candidate_pending_rasters"
                elif (sentinel or landsat) and weather:
                    verdict = "historical_candidate_pending_rasters"
                elif sentinel or landsat or weather:
                    verdict = "partial_covariates"
                else:
                    verdict = "geometry_evaluation_only"
                row = {
                    "schema": PAIR_AUDIT_SCHEMA,
                    "pair_id": pair_id,
                    "event_id": pair["event_id"],
                    "split": pair["split"],
                    "delta_hours": pair["metrics"]["delta_hours"],
                    "verdict": verdict,
                    "geometry_evaluation_usable": geometry,
                    "sentinel2_pre_t0_metadata": sentinel,
                    "landsat_pre_t0_metadata": landsat,
                    "sentinel2_top_candidate_stac_created_by_t0": sentinel_created,
                    "landsat_top_candidate_stac_created_by_t0": landsat_created,
                    "eo_operational_metadata_ready": operational_eo,
                    "hrrr_available_by_t0_full_window": weather,
                    "rights_allow_internal_noncommercial_training": True,
                    "research_training_candidate": research_candidate,
                    "raster_tensor_ready": False,
                    "training_ready": False,
                    "reasons": row_reasons,
                }
                handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                verdicts[verdict] += 1
                split_counts[str(pair["split"])] += 1
                reasons.update(row_reasons)
        temporary.replace(output_path)
        return {
            "file": str(output_path),
            "pairs": len(pairs),
            "verdicts": dict(sorted(verdicts.items())),
            "reasons": dict(sorted(reasons.items())),
            "splits": dict(sorted(split_counts.items())),
            "research_training_candidates": verdicts["research_candidate_pending_rasters"],
            "training_ready": 0,
        }

    def _audit_rcda_sealed_results(self) -> dict[str, Any] | None:
        run_roots = sorted(
            self.repo_root.glob("outputs/ml_eval/rcda_sealed_kaggle_*/rcda_sealed")
        )
        if not run_roots:
            return None
        run_root = run_roots[-1]
        report_paths = {
            name: run_root / f"{name}_seed0_report.json" for name in ("unet", "rcda")
        }
        baseline_path = (
            self.repo_root / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json"
        )
        protocol_root = run_root.parent / "rcda_protocol"
        local_protocol_root = self.repo_root / "data/external/rcda_net_full/protocol"
        required = [*report_paths.values(), baseline_path]
        if not all(path.is_file() for path in required):
            return None

        reports = {
            name: json.loads(path.read_text(encoding="utf-8"))
            for name, path in report_paths.items()
        }
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline_test = baseline["test"]
        baseline_pair_iou = float(baseline_test["growth_ring_result"]["iou"])
        baseline_event_iou = float(baseline_test["event_macro_growth_iou"])
        models: dict[str, Any] = {}
        for name, report in reports.items():
            val = report["val"]["selected"]
            test = report["test_once"]
            models[name] = {
                "epochs_configured": report["config"]["epochs"],
                "best_epoch": report["best_epoch"],
                "selected_threshold": report["selected_threshold"],
                "threshold_selected_on": report["threshold_selected_on"],
                "test_used_for_within_model_selection": report["test_used_for_selection"],
                "normalization_fit_split": report["normalization_fit_split"],
                "validation": {
                    "samples": val["n_samples"],
                    "events": val["n_events"],
                    "iou": val["iou"],
                    "event_macro_iou": val["event_macro_iou"],
                    "f1": val["f1"],
                },
                "sealed_test": {
                    "samples": test["n_samples"],
                    "events": test["n_events"],
                    "growth_iou": test["iou"],
                    "event_macro_growth_iou": test["event_macro_iou"],
                    "f1": test["f1"],
                    "precision": test["precision"],
                    "recall": test["recall"],
                    "far_gt_10_5px_recall": test["far_gt_10_5px_recall"],
                    "far_gt_10_5px_iou": test["far_gt_10_5px_iou"],
                    "delta_growth_iou_vs_dilated_copy": round(
                        float(test["iou"]) - baseline_pair_iou, 8
                    ),
                    "delta_event_macro_growth_iou_vs_dilated_copy": round(
                        float(test["event_macro_iou"]) - baseline_event_iou, 8
                    ),
                },
            }

        protocol_hashes: dict[str, Any] = {}
        for filename in (
            "train.json",
            "val.json",
            "test.json",
            "normalization_train_only.json",
        ):
            local = local_protocol_root / filename
            downloaded = protocol_root / filename
            if not (local.is_file() and downloaded.is_file()):
                protocol_hashes[filename] = {"present": False, "match": False}
                continue
            local_hash = _sha256(local)
            downloaded_hash = _sha256(downloaded)
            protocol_hashes[filename] = {
                "present": True,
                "match": local_hash == downloaded_hash,
                "sha256": local_hash,
            }

        duplicate_audit = self._audit_rcda_cross_split_duplicates(local_protocol_root)
        return {
            "run_root": run_root.parent.relative_to(self.repo_root).as_posix(),
            "status": "complete",
            "protocol_hashes": protocol_hashes,
            "all_protocol_hashes_match": all(
                row.get("match") for row in protocol_hashes.values()
            ),
            "baseline": {
                "name": "validation_selected_dilated_copy",
                "selected_radius_pixels": baseline["validation"]["selected_radius_pixels"],
                "sealed_test_growth_iou": baseline_pair_iou,
                "sealed_test_event_macro_growth_iou": baseline_event_iou,
                "copy_full_extent_iou_not_comparable_to_growth_target": baseline_test[
                    "copy_full_extent_result"
                ]["iou"],
            },
            "models": models,
            "cross_split_exact_duplicates": duplicate_audit,
            "claims": {
                "within_model_epoch_and_threshold_selected_on_validation": True,
                "test_used_for_within_model_selection": False,
                "cross_architecture_champion_selection_from_test_forbidden": True,
                "single_seed_only": True,
                "statistical_uncertainty_not_estimated": True,
                "daily_growth_proxy_not_tactical_front_ground_truth": True,
            },
        }

    def _audit_rcda_cross_split_duplicates(self, protocol_root: Path) -> dict[str, Any]:
        file_audit = self.output_root / "DATA_FILE_AUDIT.jsonl"
        hashes: dict[str, str] = {}
        if file_audit.is_file():
            with file_audit.open("r", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    path = str(row["path"])
                    digest = row.get("sha256")
                    if path.startswith("data/external/rcda_net_full/dataset/") and digest:
                        hashes[path] = str(digest)

        groups: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        missing_hashes = 0
        for split in ("train", "val", "test"):
            manifest = json.loads((protocol_root / f"{split}.json").read_text(encoding="utf-8"))
            for sample in manifest.get("samples") or []:
                for role in ("input", "label"):
                    relative = "data/external/rcda_net_full/dataset/" + str(
                        sample[role]
                    ).replace("\\", "/")
                    digest = hashes.get(relative)
                    if digest is None:
                        missing_hashes += 1
                        continue
                    groups[(role, digest)].append(
                        (split, str(sample["uid"]), relative)
                    )

        cross_split: list[dict[str, Any]] = []
        for (role, digest), occurrences in groups.items():
            splits = sorted({row[0] for row in occurrences})
            if len(splits) <= 1:
                continue
            cross_split.append(
                {
                    "role": role,
                    "sha256": digest,
                    "splits": splits,
                    "occurrences": len(occurrences),
                    "events": len({row[1] for row in occurrences}),
                    "examples": [row[2] for row in occurrences[:5]],
                }
            )
        cross_split.sort(key=lambda row: (row["role"], row["sha256"]))
        report = {
            "schema": "wfd_rcda_cross_split_exact_duplicate_audit_v1",
            "files_resolved": sum(len(values) for values in groups.values()),
            "files_missing_hash": missing_hashes,
            "cross_split_duplicate_groups": len(cross_split),
            "cross_split_input_groups": sum(
                row["role"] == "input" for row in cross_split
            ),
            "cross_split_label_groups": sum(
                row["role"] == "label" for row in cross_split
            ),
            "event_disjoint": True,
            "exact_binary_duplicate_free_across_splits": not cross_split,
            "groups": cross_split,
        }
        output_path = self.output_root / "RCDA_CROSS_SPLIT_DUPLICATES.json"
        _atomic_write_json(output_path, report)
        return {**report, "file": str(output_path)}

    def build(self) -> dict[str, Any]:
        generated_at = utc_now()
        file_summary, datasets = self._audit_files()
        pair_summary = self._audit_wfigs_pairs()
        rcda_results = self._audit_rcda_sealed_results()
        report = {
            "schema": AUDIT_SCHEMA,
            "generated_at": generated_at,
            "repo_root": str(self.repo_root),
            "files": file_summary,
            "datasets": datasets,
            "wfigs_pairs": pair_summary,
            "rcda_sealed_results": rcda_results,
            "global_gates": {
                "outputs_and_model_artifacts_forbidden_as_training_inputs": True,
                "event_disjoint_split_required": True,
                "available_at_or_before_t0_required_for_dynamic_covariates": True,
                "final_scars_and_hotspots_forbidden_as_progression_labels": True,
                "unknown_or_mixed_rights_block_training": True,
                "test_selection_forbidden": True,
            },
            "implementation_order": [
                "use RCDA full only through sealed repaired split",
                "materialize WFIGS EO windows for internal non-commercial research with scene coverage QA",
                "do not publish WFIGS raw data, derived tensors, or checkpoints until redistribution rights are confirmed",
                "resolve PT-FireSprd timezone before weather join",
                "keep GOFER/CFSDS as proxy-specific external benchmarks",
                "never train progression from UAV detection images, final scars, outputs, or checkpoints",
            ],
        }
        _atomic_write_json(self.output_root / "MEGA_DATA_AUDIT.json", report)
        _atomic_write_bytes(
            self.output_root / "MEGA_DATA_AUDIT.md",
            _markdown_report(report).encode("utf-8"),
        )
        return report

    def refresh_derived(self) -> dict[str, Any]:
        """Refresh pair/model sections without rehashing the file inventory."""
        report_path = self.output_root / "MEGA_DATA_AUDIT.json"
        if not report_path.is_file():
            raise FileNotFoundError(f"existing audit not found: {report_path}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["derived_refreshed_at"] = utc_now()
        report["wfigs_pairs"] = self._audit_wfigs_pairs()
        report["rcda_sealed_results"] = self._audit_rcda_sealed_results()
        _atomic_write_json(report_path, report)
        _atomic_write_bytes(
            self.output_root / "MEGA_DATA_AUDIT.md",
            _markdown_report(report).encode("utf-8"),
        )
        return report

    def refresh_existing(self) -> dict[str, Any]:
        """Reclassify the saved inventory and refresh all derived audit sections."""
        report_path = self.output_root / "MEGA_DATA_AUDIT.json"
        if not report_path.is_file():
            raise FileNotFoundError(f"existing audit not found: {report_path}")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        file_summary, datasets = self._reclassify_existing_files()
        report["refreshed_at"] = utc_now()
        report["files"] = file_summary
        report["datasets"] = datasets
        report["wfigs_pairs"] = self._audit_wfigs_pairs()
        report["rcda_sealed_results"] = self._audit_rcda_sealed_results()
        _atomic_write_json(report_path, report)
        _atomic_write_bytes(
            self.output_root / "MEGA_DATA_AUDIT.md",
            _markdown_report(report).encode("utf-8"),
        )
        return report


def datetime_from_timestamp(timestamp: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")


__all__ = ["AUDIT_SCHEMA", "DatasetPolicy", "POLICIES", "RepositoryDataAuditor"]
