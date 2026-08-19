#!/usr/bin/env python3
"""Warp LATAM/AU S2 NBR (often EPSG:4326) onto CEMS label CRS/grid.

Uses rasterio.warp when available. Writes:
  - pack/eo_aligned/*.tif
  - updates pack meta.json warp provenance
  - measured nbr_vs_cems proxy IoU JSON (only after successful warp)

  python scripts/warp_latam_au_s2_to_cems.py --event-id AU_EMSR500_PERTH
  python scripts/warp_latam_au_s2_to_cems.py --event-id CL_EMSR647_NACIMIENTO

Exit codes:
  0 — warp + measured proxy metrics written
  1 — pack missing / warp fail / no rasterio (GAP; no fake IoU)
  2 — usage
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    NBR_THRESHOLD_SWEEP,
    binary_iou,
    gc_nested_to_cems,
    is_nested_to_cems_name,
    label_records_from_meta,
    pack_dir_for,
    pick_post_s2_path,
    remap_pack_s2_roles,
    s2_source_paths,
    source_pack_ready,
)

WARP_SCHEMA = "wfd_latam_au_s2_warp_v1"
DEFAULT_REPORT_ROOT = ROOT / "outputs" / "ml_eval" / "latam_au_warp"


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_rasterio() -> Any:
    try:
        import rasterio
        from rasterio.warp import Resampling, reproject
    except ImportError as exc:
        raise RuntimeError(
            "rasterio_unavailable: install rasterio/gdal to warp S2→CEMS. "
            "Refusing invented IoU."
        ) from exc
    return rasterio, reproject, Resampling


def _label_refs(pack_dir: Path, meta: dict[str, Any]) -> list[Path]:
    out: list[Path] = []
    for rec in meta.get("geotiffs") or []:
        if not str(rec.get("role") or "").startswith("label_"):
            continue
        rel = rec.get("rel")
        if rel and (pack_dir / rel).is_file():
            out.append(pack_dir / rel)
    if not out:
        labels = pack_dir / "labels"
        if labels.is_dir():
            out = sorted(labels.glob("*.tif"))
    return out


def _s2_refs(pack_dir: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """S2 sources ONLY from pack/eo/*.tif. Never eo_aligned or *_to_cems stems."""
    by_stem = {
        Path(str(rec.get("rel") or "")).stem: rec
        for rec in (meta.get("geotiffs") or [])
        if rec.get("rel")
    }
    rows: list[dict[str, Any]] = []
    for path in s2_source_paths(pack_dir, meta):
        rec = by_stem.get(path.stem) or {}
        role = str(rec.get("role") or "eo_s2_nbr")
        rows.append({"rel": f"eo/{path.name}", "role": role, "path": path, "meta": rec})
    return rows


def dest_matches_ref(dest: Path, ref: Path) -> bool:
    try:
        import rasterio
    except ImportError:
        return dest.is_file()
    if not dest.is_file():
        return False
    try:
        with rasterio.open(dest) as dds, rasterio.open(ref) as rds:
            return (
                str(dds.crs) == str(rds.crs)
                and int(dds.height) == int(rds.height)
                and int(dds.width) == int(rds.width)
            )
    except Exception:  # noqa: BLE001
        return False


def _proxy_low_reason(
    *,
    iou: float | None,
    pair_rule: str,
    nan_frac: float | None,
    pred_pos_frac: float | None,
    sweep_best: float | None,
) -> str | None:
    if iou is not None and iou >= 0.15:
        return None
    if pair_rule in {"fallback_latest_s2", "nearest_after_first_label"}:
        return "s2_not_post"
    if nan_frac is not None and nan_frac >= 0.45:
        return "cloud"
    if pred_pos_frac is not None and pred_pos_frac < 0.01:
        return "cloud"
    if sweep_best is not None and sweep_best < 0.15:
        return "threshold_unusable"
    return "threshold_unusable"


def warp_to_reference(
    src_path: Path,
    ref_path: Path,
    dest_path: Path,
) -> dict[str, Any]:
    rasterio, reproject, Resampling = _require_rasterio()
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(ref_path) as ref:
        dst_crs = ref.crs
        dst_transform = ref.transform
        dst_height = ref.height
        dst_width = ref.width
        ref_profile = ref.profile.copy()
    with rasterio.open(src_path) as src:
        src_crs = src.crs
        src_arr = src.read(1).astype(np.float32)
        nodata = src.nodata
        dest = np.full((dst_height, dst_width), np.nan, dtype=np.float32)
        reproject(
            source=src_arr,
            destination=dest,
            src_transform=src.transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
            src_nodata=nodata,
            dst_nodata=np.nan,
        )
        profile = ref_profile.copy()
        profile.update(
            {
                "dtype": "float32",
                "count": 1,
                "nodata": np.nan,
                "compress": "deflate",
            }
        )
        # Drop photometric etc. that may not apply
        for k in ("photometric", "colormap"):
            profile.pop(k, None)
        with rasterio.open(dest_path, "w", **profile) as dst:
            dst.write(dest, 1)
            dst.update_tags(
                warp_source=str(src_path.name),
                warp_ref=str(ref_path.name),
                warp_src_crs=str(src_crs),
                warp_dst_crs=str(dst_crs),
                warp_tool="rasterio.warp.reproject",
                warp_resampling="bilinear",
            )
    finite = int(np.isfinite(dest).sum())
    return {
        "dest": str(dest_path).replace("\\", "/"),
        "src_crs": str(src_crs),
        "dst_crs": str(dst_crs),
        "width": int(dst_width),
        "height": int(dst_height),
        "finite_pixels": finite,
        "nan_frac": float(1.0 - finite / max(1, dst_height * dst_width)),
    }


def threshold_nbr_mask(nbr: np.ndarray, thr: float = -0.1) -> np.ndarray:
    """Binary burned-ish mask from NBR (low NBR → burned). Audited default thr."""
    valid = np.isfinite(nbr)
    # NBR post-fire often lower; threshold is documented proxy, not CONAF.
    return (valid & (nbr < thr)).astype(np.uint8)


def measure_proxy_iou(
    warped_nbr_path: Path,
    label_path: Path,
    *,
    thr: float,
) -> dict[str, Any]:
    rasterio, _, _ = _require_rasterio()
    with rasterio.open(warped_nbr_path) as ds:
        nbr = ds.read(1).astype(np.float32)
    with rasterio.open(label_path) as ds:
        lab = (ds.read(1) > 0).astype(np.uint8)
    if nbr.shape != lab.shape:
        return {
            "status": "failed_shape_mismatch",
            "nbr_vs_cems_iou": None,
            "nbr_shape": list(nbr.shape),
            "label_shape": list(lab.shape),
        }
    pred = threshold_nbr_mask(nbr, thr=thr)
    iou = binary_iou(pred, lab)
    return {
        "status": "measured" if iou is not None else "measured_empty_union",
        "metric": "nbr_vs_cems_iou",
        "nbr_vs_cems_iou": iou,
        "threshold": thr,
        "threshold_rule": "nbr < thr (default thr=-0.1) on warped grid",
        "pred_pos_frac": float(pred.mean()),
        "label_pos_frac": float(lab.mean()),
        "honesty": [
            "Proxy NBR threshold IoU after audited warp — not model IoU",
            "not transfer IoU",
            "not O2 / CONAF official",
            "threshold is lab default, not agency-calibrated",
        ],
    }


def warp_pack(
    event_id: str,
    pack_dir: Path,
    *,
    nbr_threshold: float | None = None,
    report_root: Path | None = None,
    gc: bool = True,
) -> dict[str, Any]:
    ready, reason = source_pack_ready(pack_dir)
    if not ready:
        return {"event_id": event_id, "ok": False, "error": reason, "nbr_vs_cems_iou": None}

    try:
        _require_rasterio()
    except RuntimeError as exc:
        return {
            "event_id": event_id,
            "ok": False,
            "error": str(exc),
            "gap": "rasterio_or_gdal_missing",
            "nbr_vs_cems_iou": None,
        }

    meta_path = pack_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    labels = _label_refs(pack_dir, meta)
    s2_rows = _s2_refs(pack_dir, meta)
    if not labels:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "no_label_tif",
            "nbr_vs_cems_iou": None,
            "gap": "missing_labels",
        }
    if not s2_rows:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "no_s2_eo",
            "nbr_vs_cems_iou": None,
            "gap": "missing_s2",
        }

    removed = gc_nested_to_cems(pack_dir) if gc else []

    # Reference grid: first label (stable CRS/GSD)
    ref = labels[0]
    aligned_dir = pack_dir / "eo_aligned"
    aligned_dir.mkdir(parents=True, exist_ok=True)

    warped: list[dict[str, Any]] = []
    errors: list[str] = []
    n_skipped = 0
    for row in s2_rows:
        src = Path(row["path"])
        dest = aligned_dir / f"{src.stem}_to_cems.tif"
        if dest_matches_ref(dest, ref):
            winfo = {
                "dest": str(dest).replace("\\", "/"),
                "source_rel": row["rel"],
                "role": row["role"],
                "aligned_rel": f"eo_aligned/{dest.name}",
                "skipped": True,
                "skip_reason": "dest_exists_crs_shape_match",
            }
            try:
                import rasterio

                with rasterio.open(dest) as ds:
                    winfo["src_crs"] = str(ds.tags().get("warp_src_crs") or "")
                    winfo["dst_crs"] = str(ds.crs)
                    winfo["width"] = int(ds.width)
                    winfo["height"] = int(ds.height)
            except Exception:  # noqa: BLE001
                winfo["dst_crs"] = str(meta.get("crs") or "")
            warped.append(winfo)
            n_skipped += 1
            continue
        try:
            winfo = warp_to_reference(src, ref, dest)
            winfo["source_rel"] = row["rel"]
            winfo["role"] = row["role"]
            winfo["aligned_rel"] = f"eo_aligned/{dest.name}"
            winfo["skipped"] = False
            warped.append(winfo)
        except Exception as exc:  # noqa: BLE001 — record GAP, no fake IoU
            errors.append(f"{src.name}:{exc}")

    if not warped:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "all_warps_failed",
            "warp_errors": errors,
            "nbr_vs_cems_iou": None,
            "gap": "warp_failed",
            "gc_removed": removed,
        }

    # Pair S2 post (datetime > last label) if it exists; else nearest after first.
    post_pick = pick_post_s2_path(pack_dir, meta, aligned=True)
    pick = warped[-1]
    if post_pick is not None:
        want = Path(post_pick["path"]).name
        for w in warped:
            if Path(w.get("aligned_rel") or "").name == want or Path(w.get("dest") or "").name == want:
                pick = w
                pick["pair_rule"] = post_pick.get("pair_rule")
                break
        else:
            pick["pair_rule"] = post_pick.get("pair_rule")
    else:
        pick["pair_rule"] = "fallback_last_warped"

    label_recs = label_records_from_meta(pack_dir, meta)
    label_for_metric = Path(label_recs[-1]["path"]) if label_recs else labels[-1]
    holdout_label = Path(label_recs[0]["path"]) if len(label_recs) >= 2 else None
    nbr_path = Path(pick["dest"]) if Path(str(pick.get("dest") or "")).is_file() else pack_dir / pick["aligned_rel"]

    sweep_rows: list[dict[str, Any]] = []
    chosen_thr = -0.1 if nbr_threshold is None else float(nbr_threshold)
    sweep_best: float | None = None
    if nbr_threshold is None and holdout_label is not None:
        for thr in NBR_THRESHOLD_SWEEP:
            hold = measure_proxy_iou(nbr_path, holdout_label, thr=float(thr))
            val = hold.get("nbr_vs_cems_iou")
            sweep_rows.append({"threshold": float(thr), "holdout_iou": val, "status": hold.get("status")})
            if val is not None and (sweep_best is None or val > sweep_best):
                sweep_best = float(val)
                chosen_thr = float(thr)
    elif nbr_threshold is None:
        chosen_thr = -0.1

    metric = measure_proxy_iou(nbr_path, label_for_metric, thr=chosen_thr)
    metric["threshold_source"] = (
        "held_out_label_sweep_frozen" if nbr_threshold is None and holdout_label is not None else "cli_or_default"
    )
    metric["threshold_sweep"] = sweep_rows
    metric["s2_pair_rule"] = pick.get("pair_rule")
    metric["low_iou_reason"] = _proxy_low_reason(
        iou=metric.get("nbr_vs_cems_iou"),
        pair_rule=str(pick.get("pair_rule") or ""),
        nan_frac=pick.get("nan_frac"),
        pred_pos_frac=metric.get("pred_pos_frac"),
        sweep_best=sweep_best,
    )

    provenance = {
        "schema": WARP_SCHEMA,
        "as_of_utc": utc_now(),
        "event_id": event_id,
        "tool": "rasterio.warp.reproject",
        "resampling": "bilinear",
        "reference_label": str(ref.relative_to(pack_dir)).replace("\\", "/"),
        "reference_crs": meta.get("crs"),
        "warped": warped,
        "warp_errors": errors,
        "n_s2_sources": len(s2_rows),
        "n_warped": len(warped),
        "n_skipped_existing": n_skipped,
        "gc_removed": removed,
        "proxy_metric": metric,
        "label_for_metric": str(label_for_metric.relative_to(pack_dir)).replace("\\", "/"),
        "nbr_source_aligned": pick.get("aligned_rel"),
        "s2_pair_rule": pick.get("pair_rule"),
    }

    # Update meta.json (non-destructive add)
    meta["warp_s2_to_cems"] = {
        "as_of_utc": provenance["as_of_utc"],
        "schema": WARP_SCHEMA,
        "reference_label": provenance["reference_label"],
        "n_warped": len(warped),
        "n_s2_sources": len(s2_rows),
        "aligned_dir": "eo_aligned",
        "tool": provenance["tool"],
        "resampling": provenance["resampling"],
        "files": [
            {
                "rel": w["aligned_rel"],
                "source_rel": w["source_rel"],
                "src_crs": w["src_crs"],
                "dst_crs": w["dst_crs"],
            }
            for w in warped
        ],
        "proxy": {
            "metric": metric.get("metric"),
            "nbr_vs_cems_iou": metric.get("nbr_vs_cems_iou"),
            "status": metric.get("status"),
            "threshold": metric.get("threshold"),
            "threshold_source": metric.get("threshold_source"),
            "low_iou_reason": metric.get("low_iou_reason"),
            "s2_pair_rule": metric.get("s2_pair_rule"),
        },
    }
    # Drop nested *_to_cems_to_cems* geotiff records from prior buggy runs
    meta["geotiffs"] = [
        rec
        for rec in (meta.get("geotiffs") or [])
        if not is_nested_to_cems_name(str(rec.get("rel") or rec.get("file") or ""))
    ]
    meta = remap_pack_s2_roles(meta)
    # Append geotiff records for aligned rasters if not present
    existing_rels = {str(r.get("rel")) for r in (meta.get("geotiffs") or [])}
    for w in warped:
        rel = w["aligned_rel"]
        if rel in existing_rels:
            continue
        meta.setdefault("geotiffs", []).append(
            {
                "rel": rel,
                "file": Path(rel).name,
                "role": "eo_s2_nbr_aligned_to_cems",
                "crs": meta.get("crs"),
                "warp": {
                    "source_rel": w["source_rel"],
                    "src_crs": w["src_crs"],
                    "tool": "rasterio.warp.reproject",
                },
            }
        )
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    prov_path = pack_dir / "eo_aligned" / "WARP_PROVENANCE.json"
    prov_path.write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")

    report_root = report_root or DEFAULT_REPORT_ROOT
    report_root.mkdir(parents=True, exist_ok=True)
    report_path = report_root / f"{event_id}_warp_proxy.json"
    report = {
        "schema": WARP_SCHEMA,
        "as_of_utc": utc_now(),
        "event_id": event_id,
        "ok": True,
        "pack_dir": str(
            pack_dir.relative_to(ROOT) if pack_dir.is_relative_to(ROOT) else pack_dir
        ).replace("\\", "/"),
        "n_warped": len(warped),
        "n_s2_sources": len(s2_rows),
        "n_skipped_existing": n_skipped,
        "gc_removed": removed,
        "nbr_vs_cems_iou": metric.get("nbr_vs_cems_iou"),
        "proxy_status": metric.get("status"),
        "threshold": metric.get("threshold"),
        "low_iou_reason": metric.get("low_iou_reason"),
        "s2_pair_rule": metric.get("s2_pair_rule"),
        "honesty": metric.get("honesty"),
        "provenance_rel": str(
            prov_path.relative_to(ROOT) if prov_path.is_relative_to(ROOT) else prov_path
        ).replace("\\", "/"),
        "not_claims": [
            "not model IoU",
            "not transfer IoU",
            "not O2 España",
            "not CONAF official",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    return {
        "event_id": event_id,
        "ok": True,
        "n_warped": len(warped),
        "n_s2_sources": len(s2_rows),
        "n_skipped_existing": n_skipped,
        "gc_removed": removed,
        "nbr_vs_cems_iou": metric.get("nbr_vs_cems_iou"),
        "proxy_status": metric.get("status"),
        "low_iou_reason": metric.get("low_iou_reason"),
        "s2_pair_rule": metric.get("s2_pair_rule"),
        "report": str(
            report_path.relative_to(ROOT) if report_path.is_relative_to(ROOT) else report_path
        ).replace("\\", "/"),
        "provenance": str(
            prov_path.relative_to(ROOT) if prov_path.is_relative_to(ROOT) else prov_path
        ).replace("\\", "/"),
        "warp_errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Warp S2 NBR → CEMS CRS for audited proxy IoU")
    ap.add_argument("--event-id", action="append", dest="event_ids", default=None)
    ap.add_argument("--all", action="store_true", help="Warp every EMSR spec with a ready pack")
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    ap.add_argument(
        "--nbr-threshold",
        type=float,
        default=None,
        help="If set, freeze this NBR threshold. Default: held-out sweep then freeze.",
    )
    ap.add_argument(
        "--gc",
        action="store_true",
        default=True,
        help="Delete nested *_to_cems_to_cems*.tif (default on)",
    )
    ap.add_argument("--no-gc", action="store_true", help="Keep nested dest junk (tests only)")
    args = ap.parse_args(argv)

    if args.all:
        ids = list(EMSR_PACK_SPECS)
    elif args.event_ids:
        ids = list(args.event_ids)
    else:
        ids = ["AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"]
    rows: list[dict[str, Any]] = []
    any_fail = False
    for eid in ids:
        if eid not in EMSR_PACK_SPECS:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        src = pack_dir_for(Path(args.data_root), EMSR_PACK_SPECS[eid])
        skip_reason = None
        if args.all:
            ready, reason = source_pack_ready(src)
            if not ready:
                skip_reason = reason
            elif not s2_source_paths(src):
                skip_reason = "no_s2_eo"
        if skip_reason:
            row = {
                "event_id": eid,
                "ok": True,
                "skipped": True,
                "error": skip_reason,
                "nbr_vs_cems_iou": None,
            }
            rows.append(row)
            print(f"SKIP {eid}: {skip_reason} (no invented IoU)")
            continue
        row = warp_pack(
            eid,
            src,
            nbr_threshold=args.nbr_threshold,
            report_root=Path(args.report_root),
            gc=not bool(args.no_gc),
        )
        rows.append(row)
        if not row.get("ok"):
            any_fail = True
            print(
                f"FAIL {eid}: {row.get('error')} gap={row.get('gap')} "
                f"(nbr_vs_cems_iou=null)",
                file=sys.stderr,
            )
        else:
            print(
                f"OK {eid}: n_warped={row.get('n_warped')} "
                f"nbr_vs_cems_iou={row.get('nbr_vs_cems_iou')} → {row.get('report')}"
            )

    summary = {
        "schema": WARP_SCHEMA,
        "as_of_utc": utc_now(),
        "ok": not any_fail,
        "packs": rows,
        "not_claims": ["not model IoU", "not transfer IoU"],
    }
    sum_path = Path(args.report_root) / "warp_summary.json"
    sum_path.parent.mkdir(parents=True, exist_ok=True)
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {sum_path}")
    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
