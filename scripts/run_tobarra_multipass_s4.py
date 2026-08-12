#!/usr/bin/env python3
"""Tobarra multi-pass ops chain → arrival-time field + geometry ROS (S4 unlock).

Discovers real geo-referenced LWIR/mask pairs on disk (≥2), runs the ops
geometry path (ingest → reconstruct_arrival_from_components → front_dynamics /
geometry_speed / O'Neill arrival-gradient ROS), and exports a machine board +
human MD under ``outputs/tobarra_multipass_s4/``.

Does **not** invent frames, Vp, or ML IoU-as-ROS. Lampman MAE is not SLA.

Usage
-----
::

    $env:PYTHONPATH = "."
    python scripts/run_tobarra_multipass_s4.py
    python scripts/run_tobarra_multipass_s4.py --mode reuse
    python scripts/run_tobarra_multipass_s4.py --mode ingest --max-frames 8
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.arrival_ros import (  # noqa: E402
    TOBARRA_AREA_HA,
    TOBARRA_FIRE_ID,
    TOBARRA_VP_M_MIN,
    arrival_gradient_ros_m_min,
    build_s4_board,
    compare_ros_to_anchor,
    discover_multipass_chain,
    strip_frame_objects,
)
from wildfire_front.front_dynamics import build_structural_operational_bundle  # noqa: E402
from wildfire_front.geometry_speed import (  # noqa: E402
    estimate_geometry_speeds,
    summarize_geometry_speeds,
)
from wildfire_front.models import GeometrySpeedConfig  # noqa: E402
from wildfire_front.reconstruction import reconstruct_arrival_from_components  # noqa: E402
from wildfire_front.scientific_ops import OperationalReference  # noqa: E402

DEFAULT_IMAGES = ROOT / "artifacts" / "tobarra_reprojected_lwir"
DEFAULT_MASKS = ROOT / "artifacts" / "tobarra_lwir_masks"
DEFAULT_STAGING_IMG = ROOT / "outputs" / "observatorio" / "_staging" / "tobarra_20240802" / "images"
DEFAULT_STAGING_MASK = ROOT / "outputs" / "observatorio" / "_staging" / "tobarra_20240802" / "masks"
DEFAULT_OPS_PACK = ROOT / "outputs" / "observatorio" / "tobarra_20240802"
DEFAULT_OUT = ROOT / "outputs" / "tobarra_multipass_s4"
HYBRID_SCORECARD = ROOT / "outputs" / "fuel_stack" / "tobarra" / "envelope_scorecard_tobarra.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _stage_frames(
    frames: list[Any],
    stage_root: Path,
    max_frames: int,
) -> tuple[Path, Path, int]:
    """Copy up to max_frames image/mask pairs into stage_root/{images,masks}."""
    img_dir = stage_root / "images"
    mask_dir = stage_root / "masks"
    if img_dir.exists():
        shutil.rmtree(img_dir)
    if mask_dir.exists():
        shutil.rmtree(mask_dir)
    img_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)

    # max_frames <= 0 → keep full chain; == 1 → first only (caller may still block S4)
    if max_frames <= 0 or len(frames) <= max_frames:
        selected = list(frames)
    elif max_frames == 1:
        selected = frames[:1]
    else:
        # Even temporal sample when truncating a longer chain (safe denom for max_frames >= 2)
        denom = max(max_frames - 1, 1)
        idxs = [round(i * (len(frames) - 1) / denom) for i in range(max_frames)]
        seen: set[int] = set()
        selected = []
        for i in idxs:
            if i not in seen:
                seen.add(i)
                selected.append(frames[i])

    n = 0
    for f in selected:
        shutil.copy2(f.image_path, img_dir / f.image_path.name)
        if f.mask_path is not None and f.mask_path.is_file():
            shutil.copy2(f.mask_path, mask_dir / f.mask_path.name)
            n += 1
    return img_dir, mask_dir, n


def _run_ops_geometry(
    images: Path,
    masks: Path,
    *,
    arrival_resolution_m: float,
    estimated_error_m: float,
    min_component_pixels: int,
    min_component_area_m2: float,
    max_components: int,
) -> dict[str, Any]:
    """Ingest multi-pass sequence and compute arrival + ROS (in-memory heavy path)."""
    from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence

    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=TOBARRA_FIRE_ID,
        sensor_id="lwir_drone",
        estimated_error_m=estimated_error_m,
        band=1,
        threshold=None,
        mad_z=None,
        respect_alpha=True,
        min_component_pixels=min_component_pixels,
        scientific_clean=True,
        max_components=max_components,
        morph_close_pixels=3,
        min_component_area_m2=min_component_area_m2,
    )
    observations = list(result.observations)
    if len(observations) < 2:
        return {
            "ok": False,
            "error": "need_at_least_2_accepted_observations",
            "n_observations": len(observations),
            "ingest_records": len(result.records),
        }

    res = float(arrival_resolution_m)
    # Adaptive downscale if domain is huge
    xx, yy, arrival = reconstruct_arrival_from_components(observations, res)
    max_cells = 2_000_000
    while arrival.size > max_cells and res < 64.0:
        res *= 2.0
        xx, yy, arrival = reconstruct_arrival_from_components(observations, res)

    oneill = arrival_gradient_ros_m_min(arrival, res)

    speed_config = GeometrySpeedConfig(
        sample_spacing_m=10.0,
        max_normal_distance_m=100.0,
        min_component_area_m2=max(200.0, min_component_area_m2),
        min_valid_fraction=0.2,
        max_component_centroid_distance_m=350.0,
    )
    speed_result = estimate_geometry_speeds(observations, speed_config)
    geom_summary = summarize_geometry_speeds(speed_result)
    ref = OperationalReference(
        name="INFOCAM / parte operativo",
        vp_m_min=TOBARRA_VP_M_MIN,
        area_ha=TOBARRA_AREA_HA,
        notes="INFOCAM 2024: 39 ha, Vp media 7 m/min, intensidad Media-Alta",
    )
    ops = build_structural_operational_bundle(
        observations,
        {**geom_summary, "arrival_cells_observed": int(np.isfinite(arrival).sum())},
        speed_config=speed_config,
        ref=ref,
    )
    fd_summary = ops.get("structural") if isinstance(ops.get("structural"), dict) else {}
    primary = ops.get("speed_median_m_min")
    if primary is None:
        primary = fd_summary.get("primary_ros_m_min")

    fd_keys = (
        "engine",
        "n_pairs",
        "primary_ros_m_min",
        "primary_ros_p25_m_min",
        "primary_ros_p75_m_min",
        "primary_ros_n",
        "primary_methods_used",
        "mean_coreg_shift_m",
        "structural_grade",
        "structural_label_es",
        "calibration",
    )
    return {
        "ok": True,
        "n_observations": len(observations),
        "n_components": sum(len(o.components) for o in observations),
        "arrival_resolution_m": res,
        "arrival_cells_observed": int(np.isfinite(arrival).sum()),
        "arrival": arrival,
        "xx": xx,
        "yy": yy,
        "oneill": oneill,
        "geometry_speed": geom_summary,
        "front_dynamics": {k: fd_summary.get(k) for k in fd_keys},
        "operational": {
            "speed_median_m_min": ops.get("speed_median_m_min"),
            "speed_defendable": ops.get("speed_defendable"),
            "quality_grade": ops.get("quality_grade"),
            "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
            "speed_vs_ref_grade": ops.get("speed_vs_ref_grade"),
            "reference_vp_m_min": ops.get("reference_vp_m_min"),
            "primary_ros_m_min": primary,
        },
        "primary_ros_m_min": primary,
        "ingest_accepted": sum(1 for r in result.records if r.status == "accepted"),
        "ingest_total": len(result.records),
        "observations_meta": [
            {
                "observation_id": o.observation_id,
                "observed_at": o.observed_at,
                "time_s": o.time_s,
                "n_components": len(o.components),
                "source_uri": o.source_uri,
            }
            for o in observations
        ],
    }


def _reuse_ops_pack(ops_dir: Path) -> dict[str, Any]:
    """Build S4 metrics from existing observatory pack (no re-ingest)."""
    ops = _load_json(ops_dir / "operational_metrics.json") or {}
    fd = _load_json(ops_dir / "front_dynamics.json") or {}
    summary = _load_json(ops_dir / "summary.json") or {}
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}

    primary = None
    if isinstance(fd, dict):
        primary = fd.get("primary_ros_m_min")
    if primary is None:
        primary = ops.get("speed_median_m_min")

    n_obs = ops.get("num_observations") or metrics.get("num_observations") or 0
    if int(n_obs) < 2:
        return {
            "ok": False,
            "error": "reuse_pack_has_fewer_than_2_observations",
            "n_observations": n_obs,
        }

    # Optional coarse arrival recompute from staged images if present
    oneill: dict[str, Any] = {
        "status": "skipped",
        "reason": "reuse_mode_no_in_memory_arrival_grid",
        "n_ros_cells": 0,
        "ros_median_m_min": None,
        "method": "oneill_arrival_gradient_v1",
    }
    return {
        "ok": True,
        "n_observations": int(n_obs),
        "n_components": ops.get("num_components") or metrics.get("num_components"),
        "arrival_resolution_m": ops.get("arrival_resolution_m")
        or metrics.get("arrival_resolution_m"),
        "arrival_cells_observed": ops.get("arrival_cells_observed")
        or metrics.get("arrival_cells_observed"),
        "oneill": oneill,
        "geometry_speed": (fd.get("geometry_speed") if isinstance(fd, dict) else None)
        or {
            "speed_median_m_min": metrics.get("speed_median_m_min"),
            "num_observable": metrics.get("num_observable"),
            "speed_status": metrics.get("speed_status"),
        },
        "front_dynamics": {
            "engine": fd.get("engine"),
            "n_pairs": fd.get("n_pairs"),
            "primary_ros_m_min": fd.get("primary_ros_m_min"),
            "primary_ros_p25_m_min": fd.get("primary_ros_p25_m_min"),
            "primary_ros_p75_m_min": fd.get("primary_ros_p75_m_min"),
            "primary_ros_n": fd.get("primary_ros_n"),
            "primary_methods_used": fd.get("primary_methods_used"),
            "mean_coreg_shift_m": fd.get("mean_coreg_shift_m"),
            "structural_grade": fd.get("structural_grade"),
            "structural_label_es": fd.get("structural_label_es"),
        },
        "operational": {
            "speed_median_m_min": ops.get("speed_median_m_min"),
            "speed_defendable": ops.get("speed_defendable"),
            "quality_grade": ops.get("quality_grade"),
            "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
            "speed_vs_ref_grade": ops.get("speed_vs_ref_grade"),
            "reference_vp_m_min": ops.get("reference_vp_m_min"),
            "primary_ros_m_min": primary,
        },
        "primary_ros_m_min": primary,
        "source_pack": str(ops_dir),
    }


def _write_arrival_stats_npz(
    path: Path,
    arrival: np.ndarray,
    resolution_m: float,
    oneill: dict[str, Any],
) -> None:
    """Compact arrival field stats (not full CSV — honesty: progressive field exists)."""
    finite = arrival[np.isfinite(arrival)]
    payload = {
        "schema": "wfd_arrival_field_stats_v1",
        "resolution_m": resolution_m,
        "shape": list(arrival.shape),
        "n_cells_total": int(arrival.size),
        "n_cells_observed": int(finite.size),
        "time_s_min": float(finite.min()) if finite.size else None,
        "time_s_max": float(finite.max()) if finite.size else None,
        "oneill_ros": oneill,
        "provenance": "reconstruct_arrival_from_components",
        "honesty": "first-arrival from observed multi-pass geometries; not official perimeter",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _maybe_sync_canonical(out: Path, board: dict[str, Any], status: str | None = None) -> None:
    """Write fire_intel / PLAN only when exporting the canonical multipass outbox."""
    try:
        if out.resolve() != DEFAULT_OUT.resolve():
            return
    except OSError:
        return
    _sync_docs(board)
    if status is not None:
        _patch_plan_status(status)
    elif board.get("status") is not None:
        _patch_plan_status(str(board["status"]))


def _enrich_multihorizon_export(
    board: dict[str, Any],
    out: Path,
    *,
    inv: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stamp Vp vs geometry delta and write multipass envelope scorecard (PR6/PR8)."""
    geom = board.get("geometry_ros") or {}
    anc = board.get("anchor_compare") or {}
    mh = board.get("multihorizon_fieldops")
    geom_ros = geom.get("primary_ros_m_min")
    vp = anc.get("reference_vp_m_min")
    if vp is None:
        vp = TOBARRA_VP_M_MIN
    delta_block: dict[str, Any] = {
        "vp_m_min": float(vp),
        "vp_1h_advance_m": float(vp) * 60.0,
        "geometry_primary_ros_m_min": geom_ros,
        "geometry_1h_advance_m": (float(geom_ros) * 60.0 if geom_ros is not None else None),
        "note": (
            "Vp is INFOCAM cite; multihorizon primary prefers measured geometry ROS. "
            "No silent rescale. Not ML IoU."
        ),
    }
    if geom_ros is not None:
        try:
            delta_block["delta_vp_minus_geometry_m_min"] = float(vp) - float(geom_ros)
            delta_block["delta_1h_advance_m"] = (float(vp) - float(geom_ros)) * 60.0
        except (TypeError, ValueError):
            pass
    board["multihorizon_vp_vs_geometry"] = delta_block

    if isinstance(mh, dict) and mh.get("schema") == "wfd_multihorizon_fieldops_v1":
        try:
            from wildfire_front.multihorizon_fieldops import multipass_envelope_scorecard

            span_s = None
            if inv is not None:
                span_s = inv.get("span_s")
            elif isinstance(board.get("multipass_inventory"), dict):
                span_s = board["multipass_inventory"].get("span_s")
            sc = multipass_envelope_scorecard(
                mh,
                lead_time_h=1.0,
                multipass_span_s=float(span_s) if span_s is not None else None,
                fire_id=str(board.get("fire_id") or TOBARRA_FIRE_ID),
                extra={"source": "run_tobarra_multipass_s4"},
            )
            sc_path = out / "multihorizon_multipass_scorecard.json"
            sc_path.write_text(json.dumps(sc, indent=2, default=str), encoding="utf-8")
            board.setdefault("artifacts", {})["multihorizon_scorecard"] = str(sc_path)
            board["multihorizon_multipass_scorecard"] = sc
        except Exception as exc:  # pragma: no cover — defensive
            board["multihorizon_multipass_scorecard"] = {
                "status": "error",
                "reason": str(exc),
            }
    return board


def _write_md(path: Path, board: dict[str, Any]) -> None:
    status = board.get("status")
    inv = board.get("multipass_inventory") or {}
    geom = board.get("geometry_ros") or {}
    oneill = board.get("arrival_oneill_ros") or {}
    anc = board.get("anchor_compare") or {}
    fd = board.get("front_dynamics_summary") or {}
    lines = [
        "# Arrival-time ROS — Tobarra multi-pass S4",
        "",
        f"**UTC:** {board.get('created_utc')}",
        f"**Status:** **{status}**",
        f"**Fire:** `{board.get('fire_id')}`",
        f"**Mode:** `{board.get('mode')}`",
        "",
        "## Multi-pass chain (on-disk, not invented)",
        "",
        f"- Frames (paired image+mask): **{inv.get('n_frames')}**",
        f"- With parseable timestamp: **{inv.get('n_with_timestamp')}**",
        f"- First: `{inv.get('first_timestamp_utc')}`",
        f"- Last: `{inv.get('last_timestamp_utc')}`",
        f"- Span: {inv.get('span_s')} s · median Δt: {inv.get('median_dt_s')} s",
        f"- Images: `{inv.get('images_dir')}`",
        f"- Masks: `{inv.get('masks_dir')}`",
        "",
    ]
    if board.get("blocked_reason"):
        lines += [
            "## Blocked",
            "",
            f"- Reason: `{board.get('blocked_reason')}`",
            "",
        ]
    lines += [
        "## Geometry ROS (ops)",
        "",
        f"- Primary / structural ROS: **{geom.get('primary_ros_m_min')} m/min**",
        f"- Quality grade: `{geom.get('quality_grade')}`",
        f"- Front-dynamics primary: `{fd.get('primary_ros_m_min')}` "
        f"(n_pairs={fd.get('n_pairs')}, methods={fd.get('primary_methods_used')})",
        f"- Coreg mean shift m: `{fd.get('mean_coreg_shift_m')}`",
        "",
        "## O'Neill arrival-gradient ROS",
        "",
        f"- Status: `{oneill.get('status')}`",
        f"- Median ROS: **{oneill.get('ros_median_m_min')} m/min** "
        f"(n_cells={oneill.get('n_ros_cells')})",
        f"- Formula: `{oneill.get('formula')}`",
        f"- Skip reason: `{oneill.get('reason')}`",
        "",
        "## vs INFOCAM Vp (cite, not SLA invent)",
        "",
        f"- Vp anchor: **{anc.get('reference_vp_m_min')} m/min**",
        f"- Ratio: `{anc.get('ratio')}` · grade: `{anc.get('grade')}`",
        f"- {anc.get('interpretation_es')}",
        "",
        "## Multi-horizon field_ops (from measured geometry ROS)",
        "",
    ]
    mh = board.get("multihorizon_fieldops") or {}
    geom_ros = geom.get("primary_ros_m_min")
    vp = anc.get("reference_vp_m_min") or TOBARRA_VP_M_MIN
    if isinstance(mh, dict) and mh.get("status") != "skipped" and mh.get("ros_m_min") is not None:
        h1 = None
        for h in mh.get("horizons") or []:
            if float(h.get("lead_time_h") or 0) == 1.0:
                h1 = h
                break
        if h1 is None and mh.get("horizons"):
            h1 = mh["horizons"][0]
        adv_1h = (h1 or {}).get("advance_m")
        lines += [
            f"- Schema: `{mh.get('schema')}` · method: `{mh.get('method')}`",
            f"- ROS source: `{mh.get('ros_source')}` → **{mh.get('ros_m_min')} m/min**",
            f"- 1h isotropic advance: **{adv_1h} m** (= ROS × 60; not ML IoU)",
            f"- Rails: fusion="
            f"`{(mh.get('rails') or {}).get('field_ops_ml_live_fusion')}` · "
            f"iou_is_not_ros=`{(mh.get('rails') or {}).get('iou_is_not_ros')}`",
            "",
            "### Vp cite vs geometry primary (demo delta)",
            "",
            f"- INFOCAM Vp cite: **{vp} m/min** → 1h advance **{float(vp) * 60.0:.1f} m**",
        ]
        if geom_ros is not None:
            lines.append(
                f"- Geometry primary: **{geom_ros} m/min** → 1h advance "
                f"**{float(geom_ros) * 60.0:.1f} m**"
            )
            try:
                delta = float(vp) - float(geom_ros)
                lines.append(
                    f"- Delta (Vp − geometry): **{delta:.3f} m/min** "
                    f"(~{delta * 60.0:.1f} m at 1h) — cite vs measured; no silent rescale"
                )
            except (TypeError, ValueError):
                pass
        lines += [
            "- O'Neill median is **not** silently averaged into multihorizon primary.",
            "",
        ]
    else:
        lines += [
            "- Multihorizon: **not attached** "
            f"(status=`{(mh or {}).get('status')}`, reason=`{(mh or {}).get('reason')}`)",
            "",
        ]
    lines += [
        "## Method",
        "",
        "- O'Neill et al. (IJWF 2024): arrival-time raster → ROS from gradient.",
        "- Lampman et al. (IJWF 2026): multi-pass TIR **method cite only** — not Tobarra SLA.",
        "- WFD: `geometry_speed` normal-ray + `front_dynamics_v1` + `reconstruct_arrival_from_components`.",
        "- Multihorizon: `wildfire_front.multihorizon_fieldops` from geometry primary ROS.",
        "",
        "## Rails",
        "",
        "- ml_product_go true (lab) · field_ops ML fusion **OFF**",
        "- IoU ≠ ROS · never invent Vp · thermal mask ≠ official perimeter",
        "- Multihorizon is field_ops product surface — not lab model_iou",
        "",
        "Machine board: see sibling `s4_board.json` / export path in artifacts.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--mode",
        choices=("auto", "ingest", "reuse"),
        default="auto",
        help="auto: ingest if staging/artifacts usable else reuse; ingest: always run geometry; reuse: pack only",
    )
    p.add_argument("--images", type=Path, default=None, help="LWIR images dir")
    p.add_argument("--masks", type=Path, default=None, help="Masks dir")
    p.add_argument(
        "--ops-pack",
        type=Path,
        default=DEFAULT_OPS_PACK,
        help="Existing observatory pack for reuse mode",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--max-frames", type=int, default=10)
    p.add_argument("--arrival-resolution-m", type=float, default=5.0)
    p.add_argument("--estimated-error-m", type=float, default=2.0)
    p.add_argument("--min-component-pixels", type=int, default=200)
    p.add_argument("--min-component-area-m2", type=float, default=100.0)
    p.add_argument("--max-components", type=int, default=5)
    p.add_argument(
        "--prefer-staging",
        action="store_true",
        default=True,
        help="Prefer observatorio staging subset when present (default)",
    )
    p.add_argument("--no-prefer-staging", action="store_true")
    args = p.parse_args(argv)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)
    created = datetime.now(UTC).isoformat()

    prefer_staging = args.prefer_staging and not args.no_prefer_staging
    explicit_images = args.images is not None
    if explicit_images:
        images_dir = args.images
        masks_dir = args.masks if args.masks is not None else (args.images.parent / "masks")
    elif prefer_staging and DEFAULT_STAGING_IMG.is_dir() and DEFAULT_STAGING_MASK.is_dir():
        images_dir = DEFAULT_STAGING_IMG
        masks_dir = DEFAULT_STAGING_MASK
    else:
        images_dir = DEFAULT_IMAGES
        masks_dir = DEFAULT_MASKS

    # Full-disk inventory (artifacts) for honesty of chain existence
    full_inv = discover_multipass_chain(DEFAULT_IMAGES, DEFAULT_MASKS, require_mask=True)
    work_inv = discover_multipass_chain(images_dir, masks_dir, require_mask=True)

    hybrid_refs: list[str] = []
    if HYBRID_SCORECARD.is_file():
        hybrid_refs.append(str(HYBRID_SCORECARD.relative_to(ROOT)).replace("\\", "/"))

    # When user passed --images explicitly, do not fall back to full-disk chain
    # (empty temp dirs must BLOCKED rather than silently re-using Tobarra artifacts).
    chain_gate = (
        work_inv if explicit_images else (work_inv if work_inv["n_frames"] >= 2 else full_inv)
    )
    if chain_gate["n_frames"] < 2:
        board = build_s4_board(
            status="BLOCKED_MULTI_PASS_EXPORT",
            inventory=chain_gate if explicit_images else full_inv,
            blocked_reason=(
                chain_gate.get("blocked_reason")
                or full_inv.get("blocked_reason")
                or "no_multipass_frames"
            ),
            mode=args.mode,
            hybrid_refs=hybrid_refs,
            created_utc=created,
            artifacts={"out_dir": str(out)},
        )
        gap = {
            "schema": "wfd_tobarra_multipass_s4_gap_v1",
            "missing": [
                "≥2 geo-referenced LWIR frames with timestamps under artifacts/tobarra_reprojected_lwir",
                "paired masks under artifacts/tobarra_lwir_masks",
            ],
            "pipeline_ready": True,
            "note": "Pipeline implemented; blocked only on data absence. Do not invent Tobarra gold ROS.",
        }
        (out / "s4_board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
        (out / "GAP.json").write_text(json.dumps(gap, indent=2), encoding="utf-8")
        _write_md(out / "S4_NOTE.md", board)
        _maybe_sync_canonical(out, board)
        print(json.dumps({"ok": False, "status": board["status"], "out": str(out)}, indent=2))
        return 2

    # Choose inventory for work (prefer work dir if enough frames)
    inv = work_inv if explicit_images else work_inv if work_inv["n_frames"] >= 2 else full_inv
    frames = inv.get("frame_objects") or []

    mode = args.mode
    if mode == "auto":
        # Prefer live ingest when ≥2 frames available (proves ops path).
        mode = "ingest" if inv["n_frames"] >= 2 else "reuse"

    result: dict[str, Any]
    if mode == "reuse":
        result = _reuse_ops_pack(args.ops_pack)
        if not result.get("ok"):
            # Fall back to ingest if reuse fails
            mode = "ingest"

    if mode == "ingest":
        stage = out / "_staging"
        # If already pointing at staging dirs with enough frames, use them directly
        use_direct = (
            images_dir == DEFAULT_STAGING_IMG
            and masks_dir == DEFAULT_STAGING_MASK
            and inv["n_frames"] >= 2
            and inv["n_frames"] <= args.max_frames
        )
        if use_direct:
            img_dir, mask_dir = images_dir, masks_dir
            n_staged = inv["n_frames"]
        else:
            src_frames = frames
            if not src_frames and not explicit_images and full_inv["n_frames"] >= 2:
                src_frames = full_inv.get("frame_objects") or []
            img_dir, mask_dir, n_staged = _stage_frames(src_frames, stage, args.max_frames)
            inv = discover_multipass_chain(img_dir, mask_dir, require_mask=True)

        if inv["n_frames"] < 2:
            board = build_s4_board(
                status="BLOCKED_MULTI_PASS_EXPORT",
                inventory=inv,
                blocked_reason="staging_yielded_fewer_than_2_frames",
                mode=mode,
                hybrid_refs=hybrid_refs,
                created_utc=created,
            )
            (out / "s4_board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
            _write_md(out / "S4_NOTE.md", board)
            _maybe_sync_canonical(out, board)
            print(json.dumps({"ok": False, "status": board["status"]}, indent=2))
            return 2

        print(
            f"[S4] ingest multipass n_frames={inv['n_frames']} "
            f"images={img_dir} arrival_res={args.arrival_resolution_m}m",
            flush=True,
        )
        result = _run_ops_geometry(
            img_dir,
            mask_dir,
            arrival_resolution_m=args.arrival_resolution_m,
            estimated_error_m=args.estimated_error_m,
            min_component_pixels=args.min_component_pixels,
            min_component_area_m2=args.min_component_area_m2,
            max_components=args.max_components,
        )

    if not result.get("ok"):
        board = build_s4_board(
            status="BLOCKED_MULTI_PASS_EXPORT",
            inventory=strip_frame_objects(inv),
            blocked_reason=str(result.get("error") or "ops_geometry_failed"),
            mode=mode,
            hybrid_refs=hybrid_refs,
            created_utc=created,
            artifacts={"out_dir": str(out)},
        )
        (out / "s4_board.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
        _write_md(out / "S4_NOTE.md", board)
        _maybe_sync_canonical(out, board)
        print(
            json.dumps(
                {"ok": False, "status": board["status"], "error": result.get("error")}, indent=2
            )
        )
        return 2

    primary = result.get("primary_ros_m_min")
    oneill = result.get("oneill") or {}
    # Prefer structural primary for headline; fall back to O'Neill median
    headline = primary if primary is not None else oneill.get("ros_median_m_min")
    anchor = compare_ros_to_anchor(headline if isinstance(headline, (int, float)) else None)

    # Coreg kill gate from front_dynamics
    fd_sum = result.get("front_dynamics") or {}
    mean_shift = fd_sum.get("mean_coreg_shift_m")
    status = "OK"
    blocked_reason = None
    if mean_shift is not None and float(mean_shift) > 50.0:
        status = "BLOCKED_MULTI_PASS_EXPORT"
        blocked_reason = f"coreg_shift_m={mean_shift} exceeds 50 m kill gate"
    if headline is None and oneill.get("status") != "ok":
        status = "BLOCKED_MULTI_PASS_EXPORT"
        blocked_reason = blocked_reason or "no_defendable_ros_from_geometry_or_arrival"

    geometry_ros = {
        "primary_ros_m_min": primary,
        "quality_grade": (result.get("operational") or {}).get("quality_grade"),
        "speed_defendable": (result.get("operational") or {}).get("speed_defendable"),
        "geometry_speed_median_m_min": (result.get("geometry_speed") or {}).get(
            "speed_median_m_min"
        ),
        "n_observations": result.get("n_observations"),
        "arrival_cells_observed": result.get("arrival_cells_observed"),
        "arrival_resolution_m": result.get("arrival_resolution_m"),
        "note": "Primary prefers front_dynamics structural ROS over raw normal-ray median",
    }

    arts = {
        "out_dir": str(out),
        "s4_board": str(out / "s4_board.json"),
        "s4_note_md": str(out / "S4_NOTE.md"),
        "full_disk_inventory_n": str(full_inv.get("n_frames")),
        "work_inventory_n": str(inv.get("n_frames")),
    }
    if result.get("source_pack"):
        arts["reused_ops_pack"] = str(result["source_pack"])

    if "arrival" in result and isinstance(result["arrival"], np.ndarray):
        _write_arrival_stats_npz(
            out / "arrival_field_stats.json",
            result["arrival"],
            float(result.get("arrival_resolution_m") or args.arrival_resolution_m),
            oneill,
        )
        arts["arrival_field_stats"] = str(out / "arrival_field_stats.json")
        # Optional compact npz for progressive field (not full CSV)
        np.savez_compressed(
            out / "arrival_field.npz",
            arrival=result["arrival"].astype(np.float32),
            resolution_m=np.array([float(result.get("arrival_resolution_m") or 0.0)]),
        )
        arts["arrival_field_npz"] = str(out / "arrival_field.npz")

    (out / "front_dynamics_s4.json").write_text(
        json.dumps(fd_sum, indent=2, default=str), encoding="utf-8"
    )
    (out / "operational_s4.json").write_text(
        json.dumps(result.get("operational") or {}, indent=2, default=str),
        encoding="utf-8",
    )
    if result.get("observations_meta"):
        (out / "observations_meta.json").write_text(
            json.dumps(result["observations_meta"], indent=2), encoding="utf-8"
        )

    board = build_s4_board(
        status=status,
        inventory=strip_frame_objects(inv),
        geometry_ros=geometry_ros,
        arrival_oneill=oneill,
        front_dynamics=fd_sum,
        anchor_compare=anchor,
        hybrid_refs=hybrid_refs,
        artifacts=arts,
        blocked_reason=blocked_reason,
        mode=mode,
        created_utc=created,
    )
    # Attach full-disk discovery for honesty
    board["full_disk_chain"] = strip_frame_objects(full_inv)
    board["full_disk_n_frames"] = full_inv.get("n_frames")

    # PR6: stamp Vp vs geometry multihorizon delta + optional scorecard (ops, not ML IoU)
    board = _enrich_multihorizon_export(board, out, inv=inv)

    (out / "s4_board.json").write_text(json.dumps(board, indent=2, default=str), encoding="utf-8")
    _write_md(out / "S4_NOTE.md", board)
    _maybe_sync_canonical(out, board, status=status)

    print(
        json.dumps(
            {
                "ok": status == "OK",
                "status": status,
                "primary_ros_m_min": primary,
                "oneill_median_m_min": oneill.get("ros_median_m_min"),
                "vp_m_min": TOBARRA_VP_M_MIN,
                "ratio": anchor.get("ratio"),
                "n_frames": inv.get("n_frames"),
                "out": str(out),
            },
            indent=2,
        )
    )
    return 0 if status == "OK" else 2


def _sync_docs(board: dict[str, Any]) -> None:
    """Write fire_intel S4 note + lab_loop JSON mirror for re-check script."""
    md_path = ROOT / "docs" / "fire_intel" / "ARRIVAL_TIME_ROS_S4_NOTE.md"
    lab = ROOT / "outputs" / "ml_eval" / "lab_loop" / "deep_research_s4_arrival_ros.json"
    lab.parent.mkdir(parents=True, exist_ok=True)

    # Human note (full multipass narrative)
    status = board.get("status")
    inv = board.get("multipass_inventory") or {}
    geom = board.get("geometry_ros") or {}
    oneill = board.get("arrival_oneill_ros") or {}
    anc = board.get("anchor_compare") or {}
    lines = [
        "# Arrival-time ROS (deep research S4)",
        "",
        f"**UTC:** {board.get('created_utc')}",
        f"**Status:** **{status}**",
        "",
        "## Method (literature + WFD)",
        "",
        "- O'Neill et al. (IJWF 2024): arrival-time raster → "
        "**ROS = 60 / |∇T| m/min** (geometry, not IoU).",
        "- Lampman et al. (IJWF 2026): multi-pass TIR method anchor — **not** Tobarra SLA.",
        "- WFD: `wildfire_front/geometry_speed.py` + `reconstruct_arrival_from_components` "
        "+ `front_dynamics_v1` + `wildfire_front/arrival_ros.py`.",
        "",
        "## Multi-pass Tobarra chain",
        "",
        f"- Work frames: **{inv.get('n_frames')}** (paired LWIR + mask, geo-referenced)",
        f"- Full-disk frames: **{board.get('full_disk_n_frames')}**",
        f"- Window: `{inv.get('first_timestamp_utc')}` → `{inv.get('last_timestamp_utc')}`",
        "- Export: `outputs/tobarra_multipass_s4/`",
        "",
        "## ROS results",
        "",
        f"- Structural / primary ROS: **{geom.get('primary_ros_m_min')} m/min** "
        f"(grade `{geom.get('quality_grade')}`)",
        f"- O'Neill arrival-gradient median: **{oneill.get('ros_median_m_min')} m/min** "
        f"(status `{oneill.get('status')}`)",
        f"- vs Vp {anc.get('reference_vp_m_min')} m/min: ratio `{anc.get('ratio')}` "
        f"· `{anc.get('grade')}`",
        "",
        "## Kill / success",
        "",
        "| | |",
        "|--|--|",
        "| Success | Multi-frame export → arrival + ROS vs Vp table |",
        "| Kill / blocked | Single frame or coreg fail → document BLOCKED |",
        "",
        "## Rails",
        "",
        "- ml_product_go false · fusion OFF · IoU ≠ ROS · Lampman MAE ≠ Tobarra SLA",
        "",
        "Machine: `outputs/tobarra_multipass_s4/s4_board.json`",
        "Lab mirror: `outputs/ml_eval/lab_loop/deep_research_s4_arrival_ros.json`",
        "Runner: `python scripts/run_tobarra_multipass_s4.py`",
        "",
    ]
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")

    lab_board = {
        "schema": "deep_research_s4_arrival_ros_v1",
        "created_utc": board.get("created_utc"),
        "strategy": "S4_arrival_time_ros_geometry",
        "deep_research": "docs/fire_intel/DEEP_RESEARCH_STRATEGIES_2024_2026.md",
        "status": status,
        "verdict": status,
        "multipass_export": "outputs/tobarra_multipass_s4/s4_board.json",
        "primary_ros_m_min": (board.get("geometry_ros") or {}).get("primary_ros_m_min"),
        "oneill_ros_median_m_min": (board.get("arrival_oneill_ros") or {}).get("ros_median_m_min"),
        "anchor_compare": board.get("anchor_compare"),
        "n_frames": inv.get("n_frames"),
        "rails": board.get("rails"),
        "honesty": board.get("honesty"),
        "source_board_schema": board.get("schema"),
    }
    lab.write_text(json.dumps(lab_board, indent=2), encoding="utf-8")


def _patch_plan_status(status: str) -> None:
    path = ROOT / "docs" / "PLAN_ML_PRODUCT_STATUS.json"
    data = _load_json(path)
    if not data:
        return
    block = data.get("deep_research_s1_s3_s4")
    if not isinstance(block, dict):
        return
    block["S4_arrival_ros"] = status
    block["S4_board"] = "outputs/tobarra_multipass_s4/s4_board.json"
    data["deep_research_s1_s3_s4"] = block
    data["updated_utc"] = datetime.now(UTC).isoformat()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(run())
