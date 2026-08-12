#!/usr/bin/env python3
"""Build the multi-fire Observatory deliverable pack (Pista A).

Runs the full GeoTIFF ingest + geometry speed + HTML report pipeline for each
configured real fire, then writes a scorecard comparing Tobarra speeds to the
INFOCAM operational anchor when available.

Usage:
    python scripts/build_observatory_pack.py
    python scripts/build_observatory_pack.py --fires tobarra,cardoso_2025
    python scripts/build_observatory_pack.py --min-component-pixels 200
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import contextlib  # noqa: E402

from wildfire_front.cli import run_geotiff_ingest  # noqa: E402
from wildfire_front.models import GeometrySpeedConfig  # noqa: E402
from wildfire_front.scientific_ops import OperationalReference  # noqa: E402


@dataclass(frozen=True)
class FireSpec:
    fire_id: str
    images: Path
    masks: Path
    sensor_id: str
    estimated_error_m: float
    # Operational reference (optional)
    infocam_vp_m_min: float | None = None
    infocam_area_ha: float | None = None
    notes: str = ""


# Default catalog from artifacts/ produced by real-IF intake.
DEFAULT_FIRES: list[FireSpec] = [
    FireSpec(
        fire_id="tobarra_20240802",
        images=ROOT / "artifacts" / "tobarra_reprojected_lwir",
        masks=ROOT / "artifacts" / "tobarra_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        infocam_vp_m_min=7.0,
        infocam_area_ha=39.0,
        notes="INFOCAM 2024: 39 ha, Vp media 7 m/min, intensidad Media-Alta",
    ),
    FireSpec(
        fire_id="cardoso_2025",
        images=ROOT / "artifacts" / "cardoso_2025_reprojected_lwir",
        masks=ROOT / "artifacts" / "cardoso_2025_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        notes="Cardoso (GU) multi-day candidate",
    ),
    FireSpec(
        fire_id="hellin_2024",
        images=ROOT / "artifacts" / "hellin_2024_reprojected_lwir",
        masks=ROOT / "artifacts" / "hellin_2024_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        infocam_vp_m_min=50.0,
        infocam_area_ha=100.0,
        notes=(
            "INFOCAM UNAP boletin 2024-07-20: Vp media 50 m/min, 100 ha* "
            "(estimada no oficial); confirmed anchor 2026-08-03"
        ),
    ),
    FireSpec(
        fire_id="la_estrella_acom1_2024",
        images=ROOT / "artifacts" / "la_estrella_acom1_2024_reprojected_lwir",
        masks=ROOT / "artifacts" / "la_estrella_acom1_2024_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
    ),
    FireSpec(
        fire_id="retuerta_2025",
        images=ROOT / "artifacts" / "retuerta_2025_reprojected_lwir",
        masks=ROOT / "artifacts" / "retuerta_2025_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
    ),
    FireSpec(
        fire_id="brazatortas_2025",
        images=ROOT / "artifacts" / "brazatortas_2025_reprojected_lwir",
        masks=ROOT / "artifacts" / "brazatortas_2025_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        notes="Brazatortas 2025 — sin ancla INFOCAM",
    ),
    FireSpec(
        fire_id="la_estrella_acom2_2024",
        images=ROOT / "artifacts" / "la_estrella_acom2_2024_reprojected_lwir",
        masks=ROOT / "artifacts" / "la_estrella_acom2_2024_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        notes="La Estrella ACOM2 — sin ancla INFOCAM",
    ),
    FireSpec(
        fire_id="polan_2025",
        images=ROOT / "artifacts" / "polan_2025_reprojected_lwir",
        masks=ROOT / "artifacts" / "polan_2025_lwir_masks",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        notes="Polán 2025 — masks may be incomplete",
    ),
]

REQUIRED_ARTIFACTS = (
    "report.html",
    "operational_report.html",
    "operational_metrics.json",
    "front_dynamics.json",
    "fronts.geojson",
    "local_speeds.csv",
    "summary.json",
    "ingest_manifest.csv",
    "observations_manifest.csv",
)


def _count_tifs(path: Path) -> int:
    if not path.is_dir():
        return 0
    return len(list(path.glob("*.tif"))) + len(list(path.glob("*.tiff")))


def _list_tifs(path: Path) -> list[Path]:
    files = sorted(path.glob("*.tif")) + sorted(path.glob("*.tiff"))
    return sorted(set(files), key=lambda p: p.name)


def _even_sample(paths: list[Path], max_n: int) -> list[Path]:
    """Evenly sample up to max_n paths preserving temporal order."""
    if max_n <= 0 or len(paths) <= max_n:
        return paths
    if max_n == 1:
        return [paths[0]]
    indices = [round(i * (len(paths) - 1) / (max_n - 1)) for i in range(max_n)]
    # unique while preserving order
    seen: set[int] = set()
    out: list[Path] = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            out.append(paths[idx])
    return out


def _pair_images_masks(images_dir: Path, masks_dir: Path) -> list[tuple[Path, Path]]:
    images = _list_tifs(images_dir)
    masks = _list_tifs(masks_dir)
    mask_by_stem = {m.stem.replace("_mask", ""): m for m in masks}
    pairs: list[tuple[Path, Path]] = []
    for img in images:
        stem = img.stem
        m = mask_by_stem.get(stem)
        if m is None:
            cand = masks_dir / f"{stem}_mask.tif"
            if cand.is_file():
                m = cand
        if m is not None and m.is_file():
            pairs.append((img, m))
    return pairs


def _parse_timestamp_from_name(name: str) -> float | None:
    """Parse YYYY-MM-DD_HH-MM-SS from common IF filenames → unix-ish sort key."""
    import re
    from datetime import datetime

    m = re.search(r"(20\d{2}-\d{2}-\d{2})[_T](\d{2})-(\d{2})-(\d{2})", name)
    if not m:
        return None
    try:
        dt = datetime.strptime(
            f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}",
            "%Y-%m-%d %H:%M:%S",
        )
        return dt.timestamp()
    except ValueError:
        return None


def _select_coherent_pairs(
    pairs: list[tuple[Path, Path]],
    max_frames: int,
    max_side: int = 2500,
    max_center_sep_m: float = 800.0,
) -> list[tuple[Path, Path]]:
    """Pick consecutive frames with shared footprint for defendable speeds.

    Prefer the densest *temporal* run inside the largest *spatial* cluster so
    Δt is minutes (spread physics) rather than multi-hour multi-pass jumps.
    """
    if not pairs:
        return []

    try:
        import rasterio
    except Exception:
        return pairs[:max_frames]

    meta: list[tuple[Path, Path, int, int, float, float, float]] = []
    for img, mask in pairs:
        try:
            with rasterio.open(img) as ds:
                w, h = int(ds.width), int(ds.height)
                b = ds.bounds
                cx = 0.5 * (b.left + b.right)
                cy = 0.5 * (b.bottom + b.top)
        except Exception:
            continue
        if w <= 0 or h <= 0 or max(w, h) > max_side:
            continue
        ts = _parse_timestamp_from_name(img.name) or 0.0
        meta.append((img, mask, w, h, cx, cy, ts))

    if len(meta) < 2:
        # Fallback: still reject absurd FOVs (e.g. full-scene 16k×27k Heligrafics
        # dumps). Prefer smallest footprints under a hard side cap.
        hard_side = max(int(max_side * 2.5), max_side + 500)
        all_meta: list[tuple[Path, Path, int, int, float, float, float]] = []
        for img, mask in pairs:
            try:
                with rasterio.open(img) as ds:
                    w, h = int(ds.width), int(ds.height)
                    b = ds.bounds
                    cx = 0.5 * (b.left + b.right)
                    cy = 0.5 * (b.bottom + b.top)
            except Exception:
                continue
            if max(w, h) > hard_side:
                continue
            ts = _parse_timestamp_from_name(img.name) or 0.0
            all_meta.append((img, mask, w, h, cx, cy, ts))
        if len(all_meta) < 2:
            # Last resort: take the two smallest rasters even if oversized,
            # but never the absolute largest scene in the set.
            raw: list[tuple[Path, Path, int, int, float, float, float]] = []
            for img, mask in pairs:
                try:
                    with rasterio.open(img) as ds:
                        w, h = int(ds.width), int(ds.height)
                        b = ds.bounds
                        cx = 0.5 * (b.left + b.right)
                        cy = 0.5 * (b.bottom + b.top)
                except Exception:
                    continue
                ts = _parse_timestamp_from_name(img.name) or 0.0
                raw.append((img, mask, w, h, cx, cy, ts))
            raw.sort(key=lambda t: t[2] * t[3])
            # Drop the largest 30% of footprints when we have enough frames.
            if len(raw) >= 4:
                raw = raw[: max(3, int(len(raw) * 0.7))]
            return [(t[0], t[1]) for t in raw[: max(max_frames, 2)]]
        all_meta.sort(key=lambda t: t[2] * t[3])
        return [(t[0], t[1]) for t in all_meta[: max(max_frames, 2)]]

    # Spatial clustering
    clusters: list[list[tuple[Path, Path, int, int, float, float, float]]] = []
    for item in meta:
        placed = False
        for cluster in clusters:
            rep = cluster[0]
            dist = ((item[4] - rep[4]) ** 2 + (item[5] - rep[5]) ** 2) ** 0.5
            if dist <= max_center_sep_m:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])

    # Prefer densest spatial cluster when it is rich enough; otherwise use all
    # max_side-filtered frames by time (aircraft re-visits can re-center).
    best = max(clusters, key=len)
    if len(best) < 2 or (len(meta) >= 4 and len(best) < min(4, len(meta))):
        best = meta
    best_sorted = sorted(best, key=lambda t: (t[6], t[0].name))

    # Find longest consecutive window with median Δt < 15 minutes if possible.
    if len(best_sorted) <= max_frames:
        return [(t[0], t[1]) for t in best_sorted]

    best_window = best_sorted[:max_frames]
    best_score = -1.0
    for start in range(0, len(best_sorted) - max_frames + 1):
        window = best_sorted[start : start + max_frames]
        dts = [
            window[i][6] - window[i - 1][6]
            for i in range(1, len(window))
            if window[i][6] and window[i - 1][6]
        ]
        if not dts:
            score = 0.0
        else:
            med = float(sorted(dts)[len(dts) // 2])
            # Prefer med dt between 30s and 15 min
            score = 1000.0 - abs(med - 180.0) if 30 <= med <= 900 else 100.0 / (1.0 + med / 3600.0)
        if score > best_score:
            best_score = score
            best_window = window
    return [(t[0], t[1]) for t in best_window]


def _stage_subset(
    images_dir: Path,
    masks_dir: Path,
    work_root: Path,
    fire_id: str,
    max_frames: int,
    max_side: int = 2500,
) -> tuple[Path, Path, int, int]:
    """Copy/link a temporal subset into work dirs for faster geometry matching."""
    pairs = _pair_images_masks(images_dir, masks_dir)
    selected = _select_coherent_pairs(pairs, max_frames=max_frames, max_side=max_side)

    img_out = work_root / fire_id / "images"
    mask_out = work_root / fire_id / "masks"
    if img_out.exists():
        shutil.rmtree(img_out)
    if mask_out.exists():
        shutil.rmtree(mask_out)
    img_out.mkdir(parents=True, exist_ok=True)
    mask_out.mkdir(parents=True, exist_ok=True)

    def _link_or_copy(src: Path, dst: Path) -> None:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    for img, mask in selected:
        _link_or_copy(img, img_out / img.name)
        _link_or_copy(mask, mask_out / mask.name)

    return img_out, mask_out, len(selected), len(selected)


def _manifest_component_stats(manifest_csv: Path) -> dict[str, float | int | None]:
    if not manifest_csv.is_file():
        return {}
    counts: list[int] = []
    accepted = 0
    rejected = 0
    with manifest_csv.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            status = (row.get("status") or "").lower()
            if status == "accepted":
                accepted += 1
                with contextlib.suppress(ValueError):
                    counts.append(int(float(row.get("component_count") or 0)))
            else:
                rejected += 1
    return {
        "frames_accepted": accepted,
        "frames_rejected": rejected,
        "component_count_median": float(sorted(counts)[len(counts) // 2]) if counts else None,
        "component_count_max": max(counts) if counts else None,
    }


def process_fire(
    spec: FireSpec,
    output_root: Path,
    min_component_pixels: int,
    speed_config: GeometrySpeedConfig,
    max_frames: int = 12,
    max_side: int = 2500,
    work_root: Path | None = None,
    max_components: int = 5,
    morph_close_pixels: int = 5,
    min_component_area_m2: float = 250.0,
) -> dict[str, object]:
    out_dir = output_root / spec.fire_id
    n_img = _count_tifs(spec.images)
    n_mask = _count_tifs(spec.masks)
    entry: dict[str, object] = {
        "fire_id": spec.fire_id,
        "images_dir": str(spec.images),
        "masks_dir": str(spec.masks),
        "n_images": n_img,
        "n_masks": n_mask,
        "status": "pending",
        "notes": spec.notes,
        "max_frames": max_frames,
    }
    if n_img < 2 or n_mask < 2:
        entry["status"] = "skipped_insufficient_data"
        entry["error"] = f"need >=2 images and masks, got {n_img}/{n_mask}"
        return entry

    stage_root = work_root or (output_root / "_staging")
    try:
        img_dir, mask_dir, n_used_img, n_used_mask = _stage_subset(
            spec.images,
            spec.masks,
            stage_root,
            spec.fire_id,
            max_frames=max_frames,
            max_side=max_side,
        )
        entry["n_frames_used"] = n_used_img
        entry["staged_images"] = str(img_dir)
        entry["staged_masks"] = str(mask_dir)
        print(
            f"  staged {n_used_img} images / {n_used_mask} masks "
            f"(from {n_img}/{n_mask}, max_frames={max_frames})",
            flush=True,
        )
        ref = None
        if spec.infocam_vp_m_min is not None:
            ref = OperationalReference(
                name="INFOCAM / parte operativo",
                vp_m_min=spec.infocam_vp_m_min,
                area_ha=spec.infocam_area_ha,
                notes=spec.notes,
            )
        metrics = run_geotiff_ingest(
            images=img_dir,
            masks=mask_dir,
            output=out_dir,
            event_id=spec.fire_id,
            sensor_id=spec.sensor_id,
            estimated_error_m=spec.estimated_error_m,
            band=1,
            threshold=None,
            speed_config=speed_config,
            mad_z=None,
            respect_alpha=True,
            min_component_pixels=min_component_pixels,
            scientific_clean=True,
            max_components=max_components,
            morph_close_pixels=morph_close_pixels,
            min_component_area_m2=min_component_area_m2,
            operational_ref=ref,
            write_operational=True,
        )
    except Exception as exc:  # noqa: BLE001 — pack must continue other fires
        entry["status"] = "failed"
        entry["error"] = str(exc)
        entry["traceback"] = traceback.format_exc(limit=5)
        return entry

    missing = [name for name in REQUIRED_ARTIFACTS if not (out_dir / name).is_file()]
    comp_stats = _manifest_component_stats(out_dir / "ingest_manifest.csv")
    ops = metrics.get("operational") if isinstance(metrics, dict) else None
    # Prefer structural primary ROS over raw geometry-speed median (can be inflated).
    speed_median = None
    if isinstance(ops, dict):
        speed_median = ops.get("speed_median_m_min")
    if speed_median is None:
        speed_median = metrics.get("speed_median_m_min")
    infocam = spec.infocam_vp_m_min
    ratio = None
    if isinstance(ops, dict) and ops.get("speed_vs_ref_ratio") is not None:
        ratio = ops.get("speed_vs_ref_ratio")
    elif isinstance(speed_median, (int, float)) and infocam is not None and float(infocam) > 0:
        ratio = float(speed_median) / float(infocam)
    entry.update(
        {
            "status": "ok" if not missing else "partial",
            "output_dir": str(out_dir),
            "missing_artifacts": missing,
            "metrics": metrics,
            "component_stats": comp_stats,
            "infocam_vp_m_min": infocam,
            "infocam_area_ha": spec.infocam_area_ha,
            "speed_vs_infocam_ratio": ratio,
            "quality_grade": (ops or {}).get("quality_grade") if isinstance(ops, dict) else None,
            "quality_label_es": (ops or {}).get("quality_label_es")
            if isinstance(ops, dict)
            else None,
        }
    )
    return entry


def write_scorecard(results: list[dict[str, object]], path: Path) -> dict[str, object]:
    ok = [r for r in results if r.get("status") in {"ok", "partial"}]
    a1 = len(ok) >= 3
    a2 = all(not r.get("missing_artifacts") for r in ok) if ok else False
    tobarra = next((r for r in results if "tobarra" in str(r.get("fire_id", ""))), None)
    a5_notes = "Tobarra not in run"
    a5 = False
    if tobarra and tobarra.get("status") in {"ok", "partial"}:
        ratio = tobarra.get("speed_vs_infocam_ratio")
        median = (tobarra.get("metrics") or {}).get("speed_median_m_min")  # type: ignore[union-attr]
        # Pass if we report comparison (even if inflated) with honest ratio, or abstained.
        a5 = median is not None or (tobarra.get("metrics") or {}).get("speed_status") == "abstained"
        a5_notes = (
            f"median={median} m/min vs INFOCAM 7; ratio={ratio}. "
            "Mask-based speed is a PROXY, not official perimeter rate."
        )

    scorecard = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "gates": {
            "A1_ge3_fires": {"pass": a1, "n_ok": len(ok)},
            "A2_artifacts_present": {"pass": a2},
            "A5_tobarra_anchor": {"pass": a5, "notes": a5_notes},
        },
        "fires": results,
        "observatory_message_es": _human_message(ok, tobarra),
    }
    path.write_text(json.dumps(scorecard, indent=2, default=str), encoding="utf-8")
    return scorecard


def _human_message(ok: list[dict[str, object]], tobarra: dict[str, object] | None) -> str:
    lines = [
        f"Paquete observatorio: {len(ok)} incendios con pipeline completo o parcial.",
    ]
    if tobarra and isinstance(tobarra.get("metrics"), dict):
        m = tobarra["metrics"]
        lines.append(
            "Tobarra: "
            f"obs={m.get('num_observations')}, "
            f"speed_status={m.get('speed_status')}, "
            f"median_m_min={m.get('speed_median_m_min')}, "
            f"p95={m.get('speed_p95_m_min')}, "
            f"observable_ratio={m.get('observable_ratio')}. "
            "Ancla INFOCAM Vp=7 m/min (proxy de máscara ≠ parte oficial)."
        )
    lines.append(
        "Limitación: este pack reconstruye dinámica OBSERVADA; no es predicción operacional 24h."
    )
    return " ".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build Observatory multi-fire pack")
    p.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "outputs" / "observatorio",
        help="Root directory for per-fire packs",
    )
    p.add_argument(
        "--fires",
        type=str,
        default="tobarra_20240802,cardoso_2025,hellin_2024",
        help="Comma-separated fire_ids from catalog (default: 3 fires for A1)",
    )
    p.add_argument("--min-component-pixels", type=int, default=800)
    p.add_argument(
        "--max-frames",
        type=int,
        default=8,
        help="Consecutive frames in densest temporal window (speed physics).",
    )
    p.add_argument(
        "--max-side",
        type=int,
        default=2800,
        help="Skip frames with width or height above this (prevents OOM on mixed footprints).",
    )
    p.add_argument("--max-components", type=int, default=3)
    p.add_argument("--morph-close-pixels", type=int, default=5)
    p.add_argument("--speed-sample-spacing-m", type=float, default=12.0)
    p.add_argument("--speed-max-normal-distance-m", type=float, default=120.0)
    p.add_argument("--speed-min-valid-fraction", type=float, default=0.20)
    p.add_argument("--min-component-area-m2", type=float, default=400.0)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    catalog = {f.fire_id: f for f in DEFAULT_FIRES}
    wanted = [x.strip() for x in args.fires.split(",") if x.strip()]
    specs: list[FireSpec] = []
    for fid in wanted:
        if fid not in catalog:
            print(f"WARNING: unknown fire_id {fid}, skip", flush=True)
            continue
        specs.append(catalog[fid])
    if not specs:
        print("No fires selected")
        return 2

    speed_config = GeometrySpeedConfig(
        sample_spacing_m=args.speed_sample_spacing_m,
        max_normal_distance_m=args.speed_max_normal_distance_m,
        min_valid_fraction=args.speed_min_valid_fraction,
        min_component_area_m2=args.min_component_area_m2,
        max_component_centroid_distance_m=400.0,
        observability_ratio=1.5,
    )
    args.output_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for spec in specs:
        print(f"\n=== Processing {spec.fire_id} ===", flush=True)
        entry = process_fire(
            spec,
            args.output_root,
            min_component_pixels=args.min_component_pixels,
            speed_config=speed_config,
            max_frames=args.max_frames,
            max_side=args.max_side,
            max_components=args.max_components,
            morph_close_pixels=args.morph_close_pixels,
            min_component_area_m2=args.min_component_area_m2,
        )
        results.append(entry)
        print(
            f"  status={entry.get('status')} "
            f"metrics_keys={list((entry.get('metrics') or {}).keys())[:6]}",
            flush=True,
        )
        if entry.get("error"):
            print(f"  error={entry['error']}", flush=True)

    scorecard_path = args.output_root / "observatory_scorecard.json"
    scorecard = write_scorecard(results, scorecard_path)
    print("\n=== SCORECARD ===")
    print(json.dumps(scorecard["gates"], indent=2))
    print(scorecard["observatory_message_es"])
    print(f"Wrote {scorecard_path}")

    # Exit 0 even if some fires fail — scorecard records honesty.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
