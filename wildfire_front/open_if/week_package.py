"""Week package manifest for open IF packs (export list + honesty flags)."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

WEEK_PACKAGE_SCHEMA = "open_if_week_package_manifest_v1"

# Relative paths under the pack dir that form the week export (if present).
DEFAULT_KEY_ARTIFACTS = (
    "manifest.json",
    "scorecard_pista_b.json",
    "scrape_latest.json",
    "scrape_history.json",
    "timeline_daily.json",
    "cems_watch.json",
    "dnbr_queue.json",
    "dnbr_status.json",
    "dnbr_summary.json",
    "dnbr_layer.md",
    "firms_hotspots.geojson",
    "firms_hotspots_7d.geojson",
    "firms_footprint_proxy.geojson",
    "timeline_perimeters.geojson",
    "firms_metrics.json",
    "open_metrics_for_decide.json",
    "operator_brief_open_if.md",
    "map.html",
    "map_satellite.html",
    "fire_decision_card_field_ops.json",
    "fire_decision_card_research.json",
    "satellite_enrichment/enrichment_report.json",
    "satellite_enrichment/sentinel2_stac_search.json",
    "satellite_enrichment/SATELLITE_BRIEF.md",
    "satellite_enrichment/firms_multi_sensor_union.geojson",
    "hull_vs_dnbr_comparison.json",
    "forensic_week1_brief.md",
    "day_run_report.json",
)


DEFAULT_HONESTY_FLAGS = {
    "not_official_perimeter": True,
    "not_tactical_dispatch": True,
    "no_field_ops_go_from_open_only": True,
    "no_confirmed_anchor_from_press_ha": True,
    "hull_is_not_burned_area": True,
    "emsr896_is_not_la_mierla": True,
    "google_tiles_not_scraped": True,
}


def build_week_package_manifest(
    *,
    event_id: str,
    pack_dir: Path | str,
    artifacts: list[dict[str, Any]] | None = None,
    honesty_flags: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build week package manifest document (does not write files)."""
    pack = Path(pack_dir)
    flags = dict(DEFAULT_HONESTY_FLAGS)
    if honesty_flags:
        flags.update(honesty_flags)
    doc: dict[str, Any] = {
        "schema": WEEK_PACKAGE_SCHEMA,
        "event_id": event_id,
        "pack_dir": str(pack).replace("\\", "/"),
        "built_at_utc": datetime.now(UTC).isoformat(),
        "artifacts": artifacts or [],
        "honesty_flags": flags,
        "track": "open_firms_only",
        "decision_policy_hard_rule": "field_ops GO forbidden on open-only path",
    }
    if extra:
        doc["extra"] = extra
    return doc


def inventory_pack_artifacts(
    pack_dir: Path | str,
    *,
    key_paths: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """List key artifacts under pack_dir with exists flag and size."""
    pack = Path(pack_dir)
    paths = tuple(key_paths) if key_paths is not None else DEFAULT_KEY_ARTIFACTS
    out: list[dict[str, Any]] = []
    for rel in paths:
        p = pack / rel
        exists = p.is_file()
        item: dict[str, Any] = {
            "path": rel.replace("\\", "/"),
            "exists": exists,
        }
        if exists:
            try:
                item["size_bytes"] = p.stat().st_size
            except OSError:
                item["size_bytes"] = None
        out.append(item)
    return out


def export_week_package(
    pack_dir: Path | str,
    *,
    event_id: str,
    dest_name: str = "week_package",
    copy_existing: bool = True,
) -> dict[str, Any]:
    """Write ``week_package/manifest.json`` and optionally copy present artifacts.

    Returns the manifest dict.
    """
    pack = Path(pack_dir)
    dest = pack / dest_name
    dest.mkdir(parents=True, exist_ok=True)
    artifacts = inventory_pack_artifacts(pack)
    manifest = build_week_package_manifest(
        event_id=event_id,
        pack_dir=pack,
        artifacts=artifacts,
    )
    if copy_existing:
        copied: list[str] = []
        for item in artifacts:
            if not item.get("exists"):
                continue
            rel = str(item["path"])
            if Path(rel).parts and Path(rel).parts[0] == dest_name:
                continue
            src = pack / rel
            target = dest / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, target)
                copied.append(rel)
            except OSError:
                pass
        manifest["copied"] = copied
    man_path = dest / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(man_path).replace("\\", "/")
    return manifest


def validate_week_package_manifest(doc: dict[str, Any]) -> list[str]:
    """Return list of schema errors (empty if OK)."""
    errors: list[str] = []
    if doc.get("schema") != WEEK_PACKAGE_SCHEMA:
        errors.append(f"schema_expected_{WEEK_PACKAGE_SCHEMA}")
    if not doc.get("event_id"):
        errors.append("missing_event_id")
    if "artifacts" not in doc or not isinstance(doc["artifacts"], list):
        errors.append("missing_artifacts_list")
    flags = doc.get("honesty_flags")
    if not isinstance(flags, dict):
        errors.append("missing_honesty_flags")
    else:
        for k in (
            "not_official_perimeter",
            "no_field_ops_go_from_open_only",
            "emsr896_is_not_la_mierla",
        ):
            if k not in flags:
                errors.append(f"missing_honesty_flag:{k}")
    return errors
