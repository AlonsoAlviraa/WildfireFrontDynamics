"""Attach progressive synthetic burn artifacts into an open_if pack directory."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import mapping

from .geometry import geojson_to_geom, reproject
from .metrics import evaluate_invariants
from .pipeline import ProgressiveBurnConfig, StageSequence, build_stage_sequence
from .schemas import (
    ARTIFACT_BRIEF,
    ARTIFACT_FRONT_DYNAMICS,
    ARTIFACT_METRICS,
    ARTIFACT_SCORECARD,
    ARTIFACT_TIMELINE,
    ATTRIBUTION_REDIAM,
    MAP_BANNER_ES,
    PRODUCT_SCHEMA,
)
from .to_observations import run_psb_front_dynamics


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _load_final_from_pack(pack_dir: Path) -> tuple[Any, str, dict[str, Any]]:
    """Return (geom, source_crs, meta) from pack perimeter_rediam."""
    candidates = [
        pack_dir / "vectors" / "perimeter_rediam.geojson",
        pack_dir / "perimeter_rediam.geojson",
        pack_dir / "timeline_perimeters.geojson",
    ]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise FileNotFoundError(f"no perimeter geojson in pack {pack_dir}")

    data = json.loads(path.read_text(encoding="utf-8"))
    geom = geojson_to_geom(data)
    # Pack vectors are WGS84
    source_crs = "EPSG:4326"
    meta: dict[str, Any] = {"perimeter_path": str(path.relative_to(pack_dir))}
    man = pack_dir / "manifest.json"
    if man.is_file():
        meta["manifest"] = json.loads(man.read_text(encoding="utf-8"))
    return geom, source_crs, meta


def sequence_to_geojson_fc(
    seq: StageSequence,
    *,
    publish_crs: str = "EPSG:4326",
    terminal_pack_geom=None,
) -> dict[str, Any]:
    """Publish stages in pack CRS. Terminal uses exact pack geometry when provided (KD1)."""
    features = []
    n = len(seq.stages)
    for s in seq.stages:
        if s.stage_index == n - 1 and terminal_pack_geom is not None:
            g = terminal_pack_geom
        else:
            g = s.geom_metric
            if seq.config.metric_crs != publish_crs:
                g = reproject(g, seq.config.metric_crs, publish_crs)
        features.append(
            {
                "type": "Feature",
                "properties": s.feature_props(),
                "geometry": mapping(g),
            }
        )
    return {
        "type": "FeatureCollection",
        "name": "progressive_synthetic_burn",
        "crs_note": publish_crs,
        "schema": PRODUCT_SCHEMA,
        "banner": MAP_BANNER_ES,
        "features": features,
    }


def attach_progressive_burn(
    pack_dir: str | Path,
    config: ProgressiveBurnConfig | None = None,
    *,
    run_fd: bool = True,
) -> dict[str, Any]:
    """Write progressive/* into pack and register artifacts in manifest (KD16)."""
    pack = Path(pack_dir)
    if not pack.is_dir():
        raise NotADirectoryError(str(pack))

    geom, source_crs, meta = _load_final_from_pack(pack)
    man = meta.get("manifest") or {}
    codigo = None
    if isinstance(man, dict):
        codigo = man.get("codigo") or man.get("pack_id")
    cfg = config or ProgressiveBurnConfig()
    # freeze codigo/source
    cfg = ProgressiveBurnConfig(
        n_stages=cfg.n_stages,
        engine=cfg.engine,
        schedule=cfg.schedule,
        total_duration_s=cfg.total_duration_s,
        metric_crs=cfg.metric_crs,
        source_crs=source_crs,
        seed=cfg.seed,
        min_area_ha=cfg.min_area_ha,
        min_component_area_ha=cfg.min_component_area_ha,
        custom_fractions=cfg.custom_fractions,
        source_final=cfg.source_final,
        codigo=str(codigo) if codigo else cfg.codigo,
        attribution=cfg.attribution or ATTRIBUTION_REDIAM,
    )

    seq = build_stage_sequence(geom, cfg, source_crs=source_crs)
    metrics = evaluate_invariants(seq)
    metrics["pack_id"] = pack.name
    metrics["codigo"] = cfg.codigo
    metrics["area_final_source"] = "rediam_official"

    prog = pack / "progressive"
    prog.mkdir(parents=True, exist_ok=True)

    # KD1: publish terminal as exact pack-CRS official geometry (no 6933 round-trip)
    fc = sequence_to_geojson_fc(seq, terminal_pack_geom=geom)
    _write_json(pack / ARTIFACT_TIMELINE, fc)
    _write_json(pack / ARTIFACT_METRICS, metrics)

    scorecard = {
        "schema": PRODUCT_SCHEMA,
        "verdict": metrics["verdict"],
        "gates": metrics["gates"],
        "partial_reasons": metrics.get("partial_reasons") or [],
        "vp_tactical": None,
        "vp_invented": False,
        "synthetic_stages_present": True,
        "map_banner": MAP_BANNER_ES,
        "attribution": ATTRIBUTION_REDIAM,
        "honest_notes": metrics.get("honest_notes"),
        "industrial_scorecard_independent": True,
        "note": "PSB does not alter GO_OPEN_AND_O2 / industrial gates",
    }
    _write_json(pack / ARTIFACT_SCORECARD, scorecard)

    fd_payload = None
    if run_fd:
        fd_payload = run_psb_front_dynamics(seq, event_id=pack.name)
        _write_json(pack / ARTIFACT_FRONT_DYNAMICS, fd_payload)

    brief = (
        f"# Progressive Synthetic Burn (addendum)\n\n"
        f"**Banner:** {MAP_BANNER_ES}\n\n"
        f"- Schema: `{PRODUCT_SCHEMA}`\n"
        f"- Verdict: **{metrics['verdict']}**\n"
        f"- Stages: {seq.n_stages} · engine: `{seq.engine_name}` · schedule: `{cfg.schedule}`\n"
        f"- Final area: {seq.final_area_ha:.2f} ha (official ceiling)\n"
        f"- Geom: {seq.final_geom_type} · parts: {seq.final_n_parts}\n"
        f"- vp_tactical: **null** (not invented)\n"
        f"- ROS: geometric proxy only (`proxy_synthetic`); not dispatch\n\n"
        f"**Attribution:** {ATTRIBUTION_REDIAM}\n\n"
        f"Stages under `progressive/` are **synthetic reverse-growth** ending on the "
        f"official REDIAM perimeter. They are **not** multi-day official O2 and **not** LWIR.\n"
    )
    (pack / ARTIFACT_BRIEF).write_text(brief, encoding="utf-8")

    # Manifest registration (KD16) — do not touch vp_tactical / industrial verdict
    man_path = pack / "manifest.json"
    if man_path.is_file():
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
    else:
        manifest = {"pack_id": pack.name}

    arts = manifest.setdefault("artifacts", {})
    if not isinstance(arts, dict):
        arts = {}
        manifest["artifacts"] = arts
    arts["progressive_timeline"] = ARTIFACT_TIMELINE
    arts["progressive_metrics"] = ARTIFACT_METRICS
    arts["progressive_scorecard"] = ARTIFACT_SCORECARD
    arts["progressive_brief"] = ARTIFACT_BRIEF
    if fd_payload is not None:
        arts["progressive_front_dynamics"] = ARTIFACT_FRONT_DYNAMICS

    # Do not overwrite industrial fields
    manifest["progressive_synthetic_burn"] = {
        "schema": PRODUCT_SCHEMA,
        "verdict": metrics["verdict"],
        "n_stages": seq.n_stages,
        "engine": seq.engine_name,
        "schedule": cfg.schedule,
        "seed": cfg.seed,
        "final_geom_type": seq.final_geom_type,
        "final_n_parts": seq.final_n_parts,
    }
    # Explicit: leave vp_tactical / scorecard_verdict untouched if present
    _write_json(man_path, manifest)

    # provenance touch
    prov_path = pack / "provenance.json"
    if prov_path.is_file():
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
            if isinstance(prov, dict):
                prov["progressive_synthetic_burn"] = {
                    "schema": PRODUCT_SCHEMA,
                    "attached": True,
                    "verdict": metrics["verdict"],
                }
                _write_json(prov_path, prov)
        except json.JSONDecodeError:
            pass

    return {
        "pack": str(pack),
        "verdict": metrics["verdict"],
        "n_stages": seq.n_stages,
        "final_area_ha": seq.final_area_ha,
        "artifacts": {
            "timeline": ARTIFACT_TIMELINE,
            "metrics": ARTIFACT_METRICS,
            "scorecard": ARTIFACT_SCORECARD,
        },
    }
