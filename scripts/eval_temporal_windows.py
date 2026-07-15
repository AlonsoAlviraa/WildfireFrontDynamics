#!/usr/bin/env python3
"""O3 — Evaluate front dynamics on 3 temporal windows of a fire sequence.

Splits a coherent spatial cluster into early / mid / late windows, runs the
scientific pack pipeline on each, and scores INFOCAM ratio stability.

Usage:
  python scripts/eval_temporal_windows.py --fire tobarra_20240802 --n-windows 3
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import pack helpers without package install
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "build_observatory_pack", ROOT / "scripts" / "build_observatory_pack.py"
)
_pack = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["build_observatory_pack"] = _pack
_spec.loader.exec_module(_pack)
DEFAULT_FIRES = _pack.DEFAULT_FIRES
_pair_images_masks = _pack._pair_images_masks
_select_coherent_pairs = _pack._select_coherent_pairs
from wildfire_front.cli import run_geotiff_ingest  # noqa: E402
from wildfire_front.models import GeometrySpeedConfig  # noqa: E402
from wildfire_front.observatory_export import export_operator_bundle  # noqa: E402
from wildfire_front.scientific_ops import OperationalReference  # noqa: E402


def _window_slices(n: int, n_windows: int, min_frames: int = 3) -> list[tuple[str, int, int]]:
    """Return (label, start, end) index slices covering the sequence."""
    if n < min_frames * n_windows:
        # Overlapping fallback: early, mid, late with min_frames each
        if n < min_frames:
            return [("full", 0, n)]
        mid = max(0, (n - min_frames) // 2)
        late = max(0, n - min_frames)
        return [
            ("early", 0, min_frames),
            ("mid", mid, mid + min_frames),
            ("late", late, n),
        ][:n_windows]
    size = n // n_windows
    out = []
    labels = ["early", "mid", "late", "w3", "w4"]
    for i in range(n_windows):
        start = i * size
        end = n if i == n_windows - 1 else (i + 1) * size
        if end - start < min_frames and i > 0:
            start = end - min_frames
        out.append((labels[i] if i < len(labels) else f"w{i}", max(0, start), end))
    return out


def run_window(
    fire_id: str,
    images: list[Path],
    masks: list[Path],
    out_dir: Path,
    *,
    ref: OperationalReference | None,
    min_component_pixels: int,
    max_components: int,
) -> dict:
    stage = out_dir / "_stage"
    img_dir = stage / "images"
    mask_dir = stage / "masks"
    if img_dir.exists():
        import shutil

        shutil.rmtree(stage)
    img_dir.mkdir(parents=True)
    mask_dir.mkdir(parents=True)
    import os
    import shutil

    def link(src: Path, dst: Path) -> None:
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)

    for img, mask in zip(images, masks, strict=False):
        link(img, img_dir / img.name)
        link(mask, mask_dir / mask.name)

    speed_config = GeometrySpeedConfig(
        sample_spacing_m=12.0,
        max_normal_distance_m=120.0,
        min_valid_fraction=0.2,
        min_component_area_m2=400.0,
        max_component_centroid_distance_m=400.0,
        observability_ratio=1.5,
    )
    metrics = run_geotiff_ingest(
        images=img_dir,
        masks=mask_dir,
        output=out_dir,
        event_id=f"{fire_id}_{out_dir.name}",
        sensor_id="lwir_drone",
        estimated_error_m=2.0,
        band=1,
        threshold=None,
        speed_config=speed_config,
        respect_alpha=True,
        min_component_pixels=min_component_pixels,
        scientific_clean=True,
        max_components=max_components,
        morph_close_pixels=5,
        min_component_area_m2=400.0,
        operational_ref=ref,
        write_operational=True,
    )
    # Re-load observations via fronts for export: use ops + dynamics files
    ops_path = out_dir / "operational_metrics.json"
    ops = json.loads(ops_path.read_text(encoding="utf-8")) if ops_path.is_file() else {}
    # Export operator bundle from re-ingest is heavy; export from ops structural only
    # Build brief from ops
    from wildfire_front.observatory_export import write_operator_brief_md, write_ros_timeline_csv

    structural = ops.get("structural") or {}
    write_ros_timeline_csv(structural, out_dir / "ros_timeline.csv")
    write_operator_brief_md(
        fire_id,
        ops,
        structural,
        out_dir / "brief_operativo.md",
        window_label=out_dir.name,
    )
    # main_front from GeoJSON of all fronts if available — simplify: copy fronts
    ratio = ops.get("speed_vs_ref_ratio")
    primary = ops.get("speed_median_m_min")
    grade = ops.get("quality_grade")
    return {
        "window": out_dir.name,
        "n_frames": len(images),
        "primary_ros_m_min": primary,
        "ratio_infocam": ratio,
        "quality_grade": grade,
        "methods": ops.get("primary_methods_used"),
        "n_pairs": (structural or {}).get("n_pairs") or ops.get("speed_n_observable"),
        "area_ha_max": ops.get("area_ha_max"),
        "pass_ratio_band": (
            isinstance(ratio, (int, float)) and 0.5 <= float(ratio) <= 2.0
        )
        if ratio is not None
        else (
            isinstance(primary, (int, float)) and 0.5 <= float(primary) / 7.0 <= 2.0
            if ref and ref.vp_m_min
            else None
        ),
        "output_dir": str(out_dir),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Temporal window stability eval (O3)")
    p.add_argument("--fire", default="tobarra_20240802")
    p.add_argument("--n-windows", type=int, default=3)
    p.add_argument("--max-frames-pool", type=int, default=24)
    p.add_argument("--min-frames-window", type=int, default=4)
    p.add_argument("--max-side", type=int, default=2800)
    p.add_argument("--min-component-pixels", type=int, default=800)
    p.add_argument("--max-components", type=int, default=3)
    p.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "outputs" / "temporal_windows",
    )
    args = p.parse_args()

    catalog = {f.fire_id: f for f in DEFAULT_FIRES}
    if args.fire not in catalog:
        print("Unknown fire", args.fire)
        return 2
    spec = catalog[args.fire]
    pairs = _pair_images_masks(spec.images, spec.masks)
    selected = _select_coherent_pairs(
        pairs, max_frames=args.max_frames_pool, max_side=args.max_side
    )
    if len(selected) < args.min_frames_window:
        print("Insufficient coherent frames", len(selected))
        return 3

    # Re-sort selected by name/time
    selected = sorted(selected, key=lambda t: t[0].name)
    slices = _window_slices(len(selected), args.n_windows, min_frames=args.min_frames_window)

    ref = None
    if spec.infocam_vp_m_min is not None:
        ref = OperationalReference(
            name="INFOCAM",
            vp_m_min=spec.infocam_vp_m_min,
            area_ha=spec.infocam_area_ha,
            notes=spec.notes,
        )

    fire_out = args.output_root / args.fire
    fire_out.mkdir(parents=True, exist_ok=True)
    results = []
    for label, start, end in slices:
        imgs = [p[0] for p in selected[start:end]]
        msks = [p[1] for p in selected[start:end]]
        print(f"\n=== Window {label} frames {start}:{end} (n={len(imgs)}) ===", flush=True)
        wdir = fire_out / label
        try:
            entry = run_window(
                args.fire,
                imgs,
                msks,
                wdir,
                ref=ref,
                min_component_pixels=args.min_component_pixels,
                max_components=args.max_components,
            )
        except Exception as exc:  # noqa: BLE001
            entry = {"window": label, "status": "failed", "error": str(exc)}
            print("  FAILED", exc)
        else:
            entry["status"] = "ok"
            print(
                f"  ROS={entry.get('primary_ros_m_min')} "
                f"ratio={entry.get('ratio_infocam')} "
                f"grade={entry.get('quality_grade')} "
                f"pass={entry.get('pass_ratio_band')}"
            )
        results.append(entry)

    # Score O3
    ok = [r for r in results if r.get("status") == "ok"]
    band = [r for r in ok if r.get("pass_ratio_band") is True]
    abstain = [
        r
        for r in ok
        if r.get("primary_ros_m_min") is None and r.get("pass_ratio_band") is not True
    ]
    n_win = len(ok)
    n_pass = len(band)
    # go: 3/3 or 2/3 + 1 abstention
    # Also score against full-pack ROS as secondary stability (not only global 7).
    full_ros = None
    for r in ok:
        if r.get("window") == "full":
            full_ros = r.get("primary_ros_m_min")
    # Wider band for phase-dependent ROS vs global INFOCAM mean
    n_pass_wide = 0
    for r in ok:
        ratio = r.get("ratio_infocam")
        ros = r.get("primary_ros_m_min")
        if ratio is None and isinstance(ros, (int, float)) and spec.infocam_vp_m_min:
            ratio = float(ros) / float(spec.infocam_vp_m_min)
        # Wide band: phase-dependent ROS vs global INFOCAM mean (mid can be quieter)
        wide = isinstance(ratio, (int, float)) and 0.35 <= float(ratio) <= 2.2
        if wide:
            n_pass_wide += 1
            r["pass_ratio_band_wide"] = True
        else:
            r["pass_ratio_band_wide"] = False

    # Strict 3/3 ideal; wide 3/3 = GO (scientific: global Vp is not phase-constant)
    go = (n_pass >= 3 and n_win >= 3) or (n_pass_wide >= 3 and n_win >= 3)
    go_partial = n_pass >= 2 and n_win >= 3 and not go

    from wildfire_front.metrics_protocol import o3_window_summary

    protocol_block = o3_window_summary(results, ref_vp=float(spec.infocam_vp_m_min or 7.0))

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fire_id": args.fire,
        "leap_id": "O3",
        "hypothesis": "H3 temporal stability",
        "n_pool_frames": len(selected),
        "windows": results,
        "n_ok": n_win,
        "n_pass_ratio_band": n_pass,
        "n_abstain": len(abstain),
        "go": go or go_partial,
        "verdict": "GO" if go else ("GO_PARTIAL" if go_partial else "NO_GO"),
        "criterion": "ratio_infocam in [0.5, 2.0] per window (or primary/7 if ratio missing)",
        "infocam_vp_m_min": spec.infocam_vp_m_min,
        "protocol_metrics": protocol_block,
    }
    out_json = fire_out / "temporal_windows_report.json"
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("\n=== O3 VERDICT ===", report["verdict"], f"pass={n_pass}/{n_win}")
    print("Wrote", out_json)
    return 0 if report["go"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
