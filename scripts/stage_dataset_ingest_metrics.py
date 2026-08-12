#!/usr/bin/env python3
"""Stage external wildfire datasets + integrate usable NDWS patches + real eval metrics.

Rails (non-negotiable):
  * thr iter1 reject = 0.795 (frozen VAL surface)
  * dual product: lab ML vs field_ops; field fusion OFF
  * no Tobarra KEEP reopen
  * do not invent metrics — only write numbers from real eval outputs

Stages:
  1. Write manifests under data/external/ and artifacts/datasets/
  2. Convert usable FireBench Caldor KML progression → NDWS NPZ patches
  3. Optionally preprocess NDWS TFRecords sample when local cache present
  4. Re-eval clm_ensemble_v34 on holdout TEST (baseline) + external patches (after)
  5. Emit outputs/ml_eval/lab_loop/DATASET_INGEST_METRICS.json

Usage::

  $env:PYTHONPATH = "."
  python scripts/stage_dataset_ingest_metrics.py
  python scripts/stage_dataset_ingest_metrics.py --skip-eval   # manifests only
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import re
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ITER1_THR = 0.795
PRODUCT_ID = "clm_ensemble_v34"
PROTOCOL = "clm_holdout_test_seed42_v1"
LAB_SURFACE = "iter1_reject_only"

EXT = ROOT / "data" / "external"
ART_DS = ROOT / "artifacts" / "datasets"
ART_PATCH = ROOT / "artifacts" / "clm_ndws_patches" / "external_ingest_v1"
OUT_METRICS = ROOT / "outputs" / "ml_eval" / "lab_loop" / "DATASET_INGEST_METRICS.json"
HOLDOUT_TEST = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1" / "test"
REJECT_LATEST = ROOT / "outputs" / "ml_eval" / "lab_loop" / "lab_loop_v34_reject_latest.json"
U1_SCORECARD = ROOT / "outputs" / "ml_eval" / "scorecards" / "ml_scorecard_u1_test.json"
MANIFEST_ENSEMBLE = ROOT / "models" / "clm_ensemble" / "manifest.json"

KML_NS = {
    "kml": "http://www.opengis.net/kml/2.2",
    "gx": "http://www.google.com/kml/ext/2.2",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _dir_stats(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "n_files": 0, "bytes": 0}
    n = 0
    b = 0
    for p in path.rglob("*"):
        if p.is_file():
            n += 1
            with contextlib.suppress(OSError):
                b += p.stat().st_size
    return {"exists": True, "n_files": n, "bytes": b, "path": str(path)}


def _count_images(path: Path) -> int:
    if not path.exists():
        return 0
    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
    return sum(1 for p in path.rglob("*") if p.is_file() and p.suffix.lower() in exts)


# ── Manifests ───────────────────────────────────────────────────────────────


def write_dataset_manifests() -> dict[str, Any]:
    """Inventory staged external datasets and write per-dataset + hub manifests."""
    EXT.mkdir(parents=True, exist_ok=True)
    ART_DS.mkdir(parents=True, exist_ok=True)

    wfts_root = EXT / "wildfirespreadts"
    firebench_root = EXT / "firebench"
    uav_root = EXT / "uav_smoke_flame"
    ndws_proxy = wfts_root / "ndws_kaggle_proxy"
    caldor = firebench_root / "caldor_2021" / "v2026.1"

    wfts = {
        "schema": "external_dataset_manifest_v1",
        "dataset_id": "WildfireSpreadTS",
        "role": "satellite_weather_fire_spread_ts",
        "promote": "lab",
        "field_ops_fusion": "OFF",
        "primary_source": {
            "name": "Zenodo",
            "doi": "10.5281/zenodo.8006177",
            "url": "https://zenodo.org/records/8006177",
            "full_zip_bytes_reported": 48359000000,
            "full_zip_staged": False,
            "reason_partial": (
                "Full WildfireSpreadTS.zip ~48 GB; staged documentation + "
                "NDWS (Huot) satellite+weather companion for NDWS-compatible patches."
            ),
        },
        "mirrors": [
            {"host": "kaggle", "ref": "linh825/wildfirespreadts", "size_bytes": 48425594725},
            {"host": "kaggle", "ref": "ehteshamashraf/wildfirespreadts", "size_bytes": 48426255463},
            {"host": "github", "url": "https://github.com/SebastianGer/WildfireSpreadTS"},
        ],
        "staged": {
            "documentation_pdf": _dir_stats(wfts_root / "WildfireSpreadTS_Documentation.pdf")
            if (wfts_root / "WildfireSpreadTS_Documentation.pdf").is_file()
            else {
                "exists": (wfts_root / "WildfireSpreadTS_Documentation.pdf").is_file(),
                "path": str(wfts_root / "WildfireSpreadTS_Documentation.pdf"),
                "bytes": (
                    (wfts_root / "WildfireSpreadTS_Documentation.pdf").stat().st_size
                    if (wfts_root / "WildfireSpreadTS_Documentation.pdf").is_file()
                    else 0
                ),
            },
            "ndws_kaggle_proxy": _dir_stats(ndws_proxy),
            "ndws_note": (
                "Next Day Wildfire Spread (fantineh/next-day-wildfire-spread) — "
                "same ML lineage (satellite+weather next-day mask); usable with "
                "kaggle_job/preprocess_ndws.py → NPZ for clm_ensemble_v34 / ndws_v21 path."
            ),
        },
        "license": "CC-BY-4.0 (WildfireSpreadTS Zenodo)",
        "created_utc": _utc_now(),
    }
    # fix documentation stats
    pdf = wfts_root / "WildfireSpreadTS_Documentation.pdf"
    if pdf.is_file():
        wfts["staged"]["documentation_pdf"] = {
            "exists": True,
            "path": str(pdf),
            "bytes": pdf.stat().st_size,
        }

    firebench = {
        "schema": "external_dataset_manifest_v1",
        "dataset_id": "FireBench",
        "role": "historical_fire_images_benchmarks",
        "promote": "lab",
        "field_ops_fusion": "OFF",
        "primary_source": {
            "name": "Zenodo FireBench Caldor 2021 benchmarks",
            "doi": "10.5281/zenodo.19041000",
            "url": "https://zenodo.org/records/19041000",
            "package": "v2026.1.zip",
        },
        "mirrors": [
            {"host": "github", "url": "https://github.com/google-research/firebench"},
            {
                "host": "kaggle",
                "ref": "blastnet/firebench-u10-*",
                "note": "HPC ensemble sim slices 20–38 GB each; not staged",
            },
            {
                "host": "google_research_blog",
                "url": "https://research.google/blog/firebench-using-high-performance-computing-to-advance-machine-learning-and-wildfire-research/",
            },
        ],
        "staged": {
            "caldor_package": _dir_stats(caldor),
            "kml_progression_count": len(list((caldor / "kml").glob("*.kml")))
            if (caldor / "kml").is_dir()
            else 0,
            "h5": {
                "exists": (caldor / "Caldor.h5").is_file(),
                "bytes": (caldor / "Caldor.h5").stat().st_size
                if (caldor / "Caldor.h5").is_file()
                else 0,
            },
            "firebench_src": _dir_stats(firebench_root / "firebench_src"),
        },
        "license": "see DATA_LICENSES in package",
        "created_utc": _utc_now(),
    }

    uav_subsets = {}
    for name in ("flamevision_detection", "long_distance_smoke", "the_wildfire_dataset"):
        p = uav_root / name
        uav_subsets[name] = {
            **_dir_stats(p),
            "n_images": _count_images(p),
        }

    uav = {
        "schema": "external_dataset_manifest_v1",
        "dataset_id": "wildfire_drone_uav_smoke_flame",
        "role": "uav_smoke_flame_detection",
        "promote": "lab",
        "field_ops_fusion": "OFF",
        "note": (
            "RGB/UAV detection corpora — inventory + detection lab only; "
            "not NDWS 17-ch spread patches without thermal masks."
        ),
        "sources": [
            {
                "host": "kaggle",
                "ref": "warcoder/flamevision-dataset-for-wildfire-detection",
                "staged_as": "flamevision_detection",
            },
            {
                "host": "kaggle",
                "ref": "simuletic/long-distance-wildfire-and-smoke-detection-dataset",
                "staged_as": "long_distance_smoke",
            },
            {
                "host": "kaggle",
                "ref": "elmadafri/the-wildfire-dataset",
                "staged_as": "the_wildfire_dataset",
            },
            {
                "host": "kaggle",
                "ref": "brycehopkins/flame-3-computer-vision-subset-sycan-marsh",
                "staged": False,
                "size_bytes": 6684789464,
                "note": "FLAME 3 CV subset ~6.7 GB — optional follow-up",
            },
        ],
        "staged": uav_subsets,
        "created_utc": _utc_now(),
    }

    _write_json(wfts_root / "manifest.json", wfts)
    _write_json(firebench_root / "manifest.json", firebench)
    _write_json(uav_root / "manifest.json", uav)

    hub = {
        "schema": "artifacts_datasets_hub_v1",
        "created_utc": _utc_now(),
        "product_id": PRODUCT_ID,
        "rails": {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "locked_reject_thr": ITER1_THR,
            "recommended_lab_surface": LAB_SURFACE,
            "tobarra_keep_reopen": False,
            "label": "lab / research_open only",
        },
        "datasets": {
            "WildfireSpreadTS": {
                "manifest": str(wfts_root / "manifest.json"),
                "status": "partial_stage_docs_plus_ndws_proxy",
            },
            "FireBench": {
                "manifest": str(firebench_root / "manifest.json"),
                "status": "caldor_2021_staged",
            },
            "uav_smoke_flame": {
                "manifest": str(uav_root / "manifest.json"),
                "status": "kaggle_subsets_staged",
            },
        },
        "patch_integration_root": str(ART_PATCH),
        "metrics_out": str(OUT_METRICS),
    }
    _write_json(ART_DS / "EXTERNAL_DATASETS_HUB.json", hub)
    _write_json(EXT / "EXTERNAL_DATASETS_HUB.json", hub)
    return hub


# ── FireBench KML → NDWS patches ─────────────────────────────────────────────


def _parse_kml_coords(kml_path: Path) -> list[list[tuple[float, float]]]:
    """Extract exterior rings as lists of (lon, lat)."""
    text = kml_path.read_text(encoding="utf-8", errors="ignore")
    # strip default ns for easier parsing
    text = re.sub(r'\sxmlns="[^"]+"', "", text, count=1)
    text = re.sub(r'\sxmlns:gx="[^"]+"', "", text)
    root = ET.fromstring(text)
    rings: list[list[tuple[float, float]]] = []
    for coord_el in root.iter("coordinates"):
        raw = (coord_el.text or "").strip()
        if not raw:
            continue
        pts: list[tuple[float, float]] = []
        for token in re.split(r"\s+", raw):
            if not token:
                continue
            parts = token.split(",")
            if len(parts) < 2:
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            pts.append((lon, lat))
        if len(pts) >= 3:
            rings.append(pts)
    return rings


def _bbox_union(
    all_rings: list[list[list[tuple[float, float]]]],
) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for rings in all_rings:
        for ring in rings:
            for x, y in ring:
                xs.append(x)
                ys.append(y)
    if not xs:
        raise ValueError("no coordinates in KML set")
    pad_x = (max(xs) - min(xs)) * 0.05 + 1e-6
    pad_y = (max(ys) - min(ys)) * 0.05 + 1e-6
    return min(xs) - pad_x, min(ys) - pad_y, max(xs) + pad_x, max(ys) + pad_y


def _rasterize_rings(
    rings: list[list[tuple[float, float]]],
    bbox: tuple[float, float, float, float],
    size: int = 64,
) -> np.ndarray:
    """Rasterize lon/lat rings onto a size×size grid (row0 = north)."""
    from matplotlib.path import Path as MplPath

    minx, miny, maxx, maxy = bbox
    mask = np.zeros((size, size), dtype=np.float32)
    if maxx <= minx or maxy <= miny:
        return mask
    xs = minx + (np.arange(size) + 0.5) * (maxx - minx) / size
    ys = maxy - (np.arange(size) + 0.5) * (maxy - miny) / size  # row0 = north
    xx, yy = np.meshgrid(xs, ys)
    pts = np.column_stack([xx.ravel(), yy.ravel()])
    inside = np.zeros(pts.shape[0], dtype=bool)
    for ring in rings:
        if len(ring) < 3:
            continue
        path = MplPath(np.asarray(ring, dtype=np.float64), closed=True)
        inside |= path.contains_points(pts)
    mask = inside.reshape(size, size).astype(np.float32)
    return mask


def _legacy17_static_channels(size: int = 64) -> np.ndarray:
    """Neutral legacy17 static stack (compatible with ensemble in_channels)."""
    ch = np.zeros((17, size, size), dtype=np.float32)
    # mild terrain / meteo placeholders in normalized space (~0)
    ch[0] = 0.2  # slope
    ch[1] = 0.0  # aspect
    ch[2] = 0.5  # temp
    ch[3] = 0.3  # humidity
    ch[4] = 0.2  # wind speed
    ch[5] = 0.0  # wind dir
    ch[11] = 0.4  # vegetation
    ch[16] = 0.5  # drought/erc-ish
    return ch


def convert_firebench_caldor_to_ndws(
    *,
    max_pairs: int = 40,
    patch_size: int = 64,
) -> dict[str, Any]:
    """Rasterize consecutive Caldor KML perimeters into NDWS-compatible NPZ."""
    kml_dir = EXT / "firebench" / "caldor_2021" / "v2026.1" / "kml"
    out_dir = ART_PATCH / "firebench_caldor"
    out_dir.mkdir(parents=True, exist_ok=True)

    kmls = sorted(p for p in kml_dir.glob("Caldor_2021_*.kml") if "perimeter" not in p.name.lower())
    if len(kmls) < 2:
        return {
            "status": "skip",
            "reason": f"need >=2 progression KMLs, found {len(kmls)}",
            "n_patches": 0,
            "out_dir": str(out_dir),
        }

    parsed: list[tuple[Path, list[list[tuple[float, float]]]]] = []
    for p in kmls:
        rings = _parse_kml_coords(p)
        if rings:
            parsed.append((p, rings))

    if len(parsed) < 2:
        return {
            "status": "skip",
            "reason": "could not parse enough KML rings",
            "n_patches": 0,
            "out_dir": str(out_dir),
        }

    bbox = _bbox_union([r for _, r in parsed])
    static = _legacy17_static_channels(patch_size)
    written: list[dict[str, Any]] = []

    n_pairs = min(max_pairs, len(parsed) - 1)
    for i in range(n_pairs):
        p_cur, rings_cur = parsed[i]
        p_tgt, rings_tgt = parsed[i + 1]
        cur = _rasterize_rings(rings_cur, bbox, patch_size)
        tgt = _rasterize_rings(rings_tgt, bbox, patch_size)
        # require some fire activity
        if float(cur.sum()) < 1.0 and float(tgt.sum()) < 1.0:
            continue
        change = float(np.mean(np.abs(tgt - cur)))
        seq = static[None, ...].astype(np.float32)  # (1, 17, H, W)
        out_path = out_dir / f"ext_firebench_caldor_{i:04d}.npz"
        np.savez_compressed(
            out_path,
            sequence=seq,
            current_fire=cur.astype(np.float32),
            target_fire=tgt.astype(np.float32),
            change_fraction=np.float32(change),
            source=np.array("ext_FIREBENCH_CALDOR"),
        )
        written.append(
            {
                "file": out_path.name,
                "from_kml": p_cur.name,
                "to_kml": p_tgt.name,
                "cur_fire_frac": float(cur.mean()),
                "tgt_fire_frac": float(tgt.mean()),
                "change_fraction": change,
            }
        )

    manifest = {
        "schema": "external_ndws_patch_manifest_v1",
        "source_dataset": "FireBench_Caldor_2021",
        "created_utc": _utc_now(),
        "product_path": "clm_ensemble_v34 / NDWS lab",
        "field_ops_fusion": "OFF",
        "n_patches": len(written),
        "patch_size": patch_size,
        "bbox_lonlat": {
            "minx": bbox[0],
            "miny": bbox[1],
            "maxx": bbox[2],
            "maxy": bbox[3],
        },
        "patches": written,
        "note": (
            "Historical perimeter progression rasterized to 64x64 NDWS NPZ. "
            "Static channels are neutral placeholders — transfer IoU is domain-stress, "
            "not a product claim. Lab only."
        ),
    }
    _write_json(out_dir / "patch_manifest.json", manifest)
    _write_json(ART_DS / "firebench_caldor_patches.json", manifest)
    return {
        "status": "ok",
        "n_patches": len(written),
        "out_dir": str(out_dir),
        "manifest": str(out_dir / "patch_manifest.json"),
    }


# ── NDWS TFRecord sample → NPZ (when cache present) ─────────────────────────


def convert_ndws_sample_to_npz(
    *,
    max_patches: int = 48,
    patch_size: int = 64,
) -> dict[str, Any]:
    """Convert a small NDWS TFRecord sample to NPZ if local zip/dir exists."""
    proxy = EXT / "wildfirespreadts" / "ndws_kaggle_proxy"
    out_dir = ART_PATCH / "ndws_sample"
    out_dir.mkdir(parents=True, exist_ok=True)

    # locate tfrecords
    tfr_files: list[Path] = []
    zip_path = proxy / "next-day-wildfire-spread.zip"
    extract_dir = proxy / "extracted"
    if zip_path.is_file() and zip_path.stat().st_size > 100_000_000:
        extract_dir.mkdir(parents=True, exist_ok=True)
        # extract only a few tfrecords if not already
        existing = list(extract_dir.rglob("*.tfrecord*"))
        if not existing:
            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    names = [
                        n for n in zf.namelist() if "tfrecord" in n.lower() or n.endswith(".tfrec")
                    ]
                    # prefer test/eval shards (smaller)
                    names_sorted = sorted(
                        names,
                        key=lambda n: (
                            0 if "test" in n.lower() or "eval" in n.lower() else 1,
                            len(n),
                        ),
                    )
                    for n in names_sorted[:3]:
                        zf.extract(n, extract_dir)
            except (zipfile.BadZipFile, OSError) as exc:
                return {
                    "status": "skip",
                    "reason": f"zip not ready/corrupt: {exc}",
                    "n_patches": 0,
                    "zip_bytes": zip_path.stat().st_size,
                }
        tfr_files = list(extract_dir.rglob("*.tfrecord*"))
    else:
        tfr_files = list(proxy.rglob("*.tfrecord*"))

    if not tfr_files:
        return {
            "status": "skip",
            "reason": "no TFRecords available yet (NDWS download may still be running)",
            "n_patches": 0,
            "proxy": str(proxy),
            "zip_bytes": zip_path.stat().st_size if zip_path.is_file() else 0,
        }

    try:
        import tensorflow as tf  # type: ignore
    except ImportError:
        return {
            "status": "skip",
            "reason": "tensorflow not installed locally; use kaggle_job/preprocess_ndws.py on Kaggle",
            "n_patches": 0,
            "n_tfrecords_found": len(tfr_files),
        }

    # Minimal parse aligned with preprocess_ndws feature map
    feature_description = {
        "elevation": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "th": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "vs": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "t": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "q": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "precipitation": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "NDVI": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "PrevFireMask": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
        "FireMask": tf.io.FixedLenFeature([64 * 64], tf.float32, default_value=[0.0] * 4096),
    }

    def _parse(ex):
        return tf.io.parse_single_example(ex, feature_description)

    written = 0
    meta: list[dict[str, Any]] = []
    for tfr in tfr_files:
        if written >= max_patches:
            break
        try:
            ds = tf.data.TFRecordDataset(str(tfr))
            for raw in ds.take(max_patches - written):
                rec = _parse(raw)
                prev = rec["PrevFireMask"].numpy().reshape(64, 64)
                fire = rec["FireMask"].numpy().reshape(64, 64)
                # keep only active
                if float((prev > 0).sum() + (fire > 0).sum()) < 1.0:
                    continue
                elev = rec["elevation"].numpy().reshape(64, 64)
                wind_dir = rec["th"].numpy().reshape(64, 64)
                wind_sp = rec["vs"].numpy().reshape(64, 64)
                temp = rec["t"].numpy().reshape(64, 64)
                # humidity proxy from q
                humid = rec["q"].numpy().reshape(64, 64)
                precip = rec["precipitation"].numpy().reshape(64, 64)
                ndvi = rec["NDVI"].numpy().reshape(64, 64)

                # crude legacy17 from fields (same spirit as preprocess_ndws)
                channels = np.zeros((17, 64, 64), dtype=np.float32)
                dy, dx = np.gradient(elev.astype(np.float64))
                slope = np.sqrt(dx * dx + dy * dy)
                aspect = np.arctan2(-dx, dy)
                channels[0] = ((slope - 0.0) / 1.5708).astype(np.float32)
                channels[1] = ((aspect + math.pi) / (2 * math.pi)).astype(np.float32)
                channels[2] = ((temp - 15.0) / 20.0).astype(np.float32)
                channels[3] = (humid / 100.0).astype(np.float32)
                channels[4] = (wind_sp / 20.0).astype(np.float32)
                channels[5] = (wind_dir / 360.0).astype(np.float32)
                channels[6] = (precip / 10.0).astype(np.float32)
                channels[11] = ndvi.astype(np.float32)
                channels = np.clip(np.nan_to_num(channels, nan=0.0), -10, 10).astype(np.float32)

                cur = (prev > 0.5).astype(np.float32)
                tgt = (fire > 0.5).astype(np.float32)
                change = float(np.mean(np.abs(tgt - cur)))
                out_path = out_dir / f"ext_ndws_{written:04d}.npz"
                np.savez_compressed(
                    out_path,
                    sequence=channels[None, ...],
                    current_fire=cur,
                    target_fire=tgt,
                    change_fraction=np.float32(change),
                    source=np.array("ext_NDWS"),
                )
                meta.append(
                    {
                        "file": out_path.name,
                        "tfrecord": tfr.name,
                        "cur_fire_frac": float(cur.mean()),
                        "tgt_fire_frac": float(tgt.mean()),
                        "change_fraction": change,
                    }
                )
                written += 1
                if written >= max_patches:
                    break
        except Exception as exc:  # noqa: BLE001 — continue other shards
            meta.append({"tfrecord": tfr.name, "error": str(exc)})
            continue

    man = {
        "schema": "external_ndws_patch_manifest_v1",
        "source_dataset": "NDWS_Huot_kaggle_proxy_for_WildfireSpreadTS_lineage",
        "created_utc": _utc_now(),
        "n_patches": written,
        "patches": meta,
        "field_ops_fusion": "OFF",
        "product_path": "clm_ensemble_v34 / ndws_v21 lab",
    }
    _write_json(out_dir / "patch_manifest.json", man)
    _write_json(ART_DS / "ndws_sample_patches.json", man)
    return {
        "status": "ok" if written else "empty",
        "n_patches": written,
        "out_dir": str(out_dir),
        "n_tfrecords": len(tfr_files),
    }


# ── Real eval ───────────────────────────────────────────────────────────────


def _load_reject_baseline() -> dict[str, Any]:
    """Frozen lab reject numbers already on disk (real, not invented)."""
    if not REJECT_LATEST.is_file():
        return {}
    doc = json.loads(REJECT_LATEST.read_text(encoding="utf-8"))
    tuned = doc.get("tuned") or {}
    return {
        "source": str(REJECT_LATEST),
        "product_id": doc.get("product_id"),
        "protocol": doc.get("protocol"),
        "rails": doc.get("rails"),
        "reject_thr": float(
            (tuned.get("test_metrics_tuned") or {}).get("threshold")
            or tuned.get("abstain_threshold")
            or ITER1_THR
        ),
        "test_metrics_baseline": tuned.get("test_metrics_baseline"),
        "test_metrics_tuned": tuned.get("test_metrics_tuned"),
        "val_metrics": tuned.get("val_metrics"),
    }


def _load_u1_scorecard() -> dict[str, Any]:
    if not U1_SCORECARD.is_file():
        return {}
    doc = json.loads(U1_SCORECARD.read_text(encoding="utf-8"))
    return {
        "source": str(U1_SCORECARD),
        "primary": doc.get("primary"),
        "uncertainty": doc.get("uncertainty"),
        "gates": doc.get("gates"),
    }


def run_ensemble_eval(
    data_dir: Path,
    *,
    max_patches: int = 200,
    label: str = "eval",
) -> dict[str, Any]:
    """Run clm_ensemble_v34 soft-vote IoU on an NPZ directory (real numbers)."""
    from wildfire_front.ml.clm_eval import evaluate_clm_weights

    if not data_dir.is_dir() or not list(data_dir.glob("*.npz")):
        return {
            "status": "skip",
            "label": label,
            "reason": f"no npz in {data_dir}",
            "n_patches": 0,
        }

    man = json.loads(MANIFEST_ENSEMBLE.read_text(encoding="utf-8"))
    members = [ROOT / m for m in man["members"]]
    missing = [str(m) for m in members if not m.is_file()]
    if missing:
        return {
            "status": "skip",
            "label": label,
            "reason": f"missing weights: {missing}",
            "n_patches": 0,
        }

    result = evaluate_clm_weights(
        members,
        data_dir,
        max_patches=max_patches,
        threshold=0.5,
        ensemble_mode=str(man.get("ensemble_mode") or "mean_prob"),
        member_weights=list(man.get("member_weights") or []),
        temperatures=list(man.get("member_temperatures") or []),
        fold=None,
        split_context=None,
    )
    # normalize key metrics
    agg = result if isinstance(result, dict) else {}
    # evaluate_clm_weights returns model_iou / copy_baseline_iou at top level
    iou = None
    for key in (
        "model_iou",
        "iou_mean",
        "mean_iou",
        "micro_iou",
        "iou",
    ):
        if key in agg and isinstance(agg[key], (int, float)):
            iou = float(agg[key])
            break
    if iou is None:
        for nest in ("metrics", "aggregate", "summary"):
            sub = agg.get(nest) or {}
            if isinstance(sub, dict):
                for key in ("model_iou", "iou_mean", "mean_iou", "micro_iou"):
                    if key in sub and isinstance(sub[key], (int, float)):
                        iou = float(sub[key])
                        break
            if iou is not None:
                break

    copy_iou = None
    for key in (
        "copy_baseline_iou",
        "copy_iou_mean",
        "iou_copy_mean",
        "copy_iou",
    ):
        if key in agg and isinstance(agg[key], (int, float)):
            copy_iou = float(agg[key])
            break
    if copy_iou is None:
        for nest in ("metrics", "aggregate", "summary"):
            sub = agg.get(nest) or {}
            if isinstance(sub, dict):
                for key in ("copy_baseline_iou", "copy_iou_mean", "iou_copy_mean"):
                    if key in sub and isinstance(sub[key], (int, float)):
                        copy_iou = float(sub[key])
                        break
            if copy_iou is not None:
                break

    delta_vs_copy = None
    if "improvement_vs_copy_iou" in agg and isinstance(
        agg["improvement_vs_copy_iou"], (int, float)
    ):
        delta_vs_copy = float(agg["improvement_vs_copy_iou"])
    elif iou is not None and copy_iou is not None:
        delta_vs_copy = iou - copy_iou

    n = int(agg.get("n_patches") or agg.get("n") or max_patches)
    out = {
        "status": "ok",
        "label": label,
        "data_dir": str(data_dir),
        "n_patches_requested": max_patches,
        "n_patches": n,
        "model_iou": iou,
        "copy_iou": copy_iou,
        "delta_vs_copy": delta_vs_copy,
        "rails": {
            "product_id": PRODUCT_ID,
            "field_ops_allow_ml_live_in_fusion": False,
            "locked_reject_thr": ITER1_THR,
            "recommended_lab_surface": LAB_SURFACE,
            "tobarra_keep_reopen": False,
            "iou_is_not_ros": True,
        },
        "raw_keys": sorted(agg.keys())[:40],
    }
    # attach a few more numeric fields if present
    for k in (
        "precision_mean",
        "recall_mean",
        "f1_mean",
        "growth_iou_mean",
        "iou_mean",
        "mean_iou",
    ):
        if k in agg and isinstance(agg[k], (int, float)):
            out[k] = float(agg[k])
    # store compact raw metrics subset
    compact = {}
    for k, v in agg.items():
        if isinstance(v, (int, float, bool, str)) and k not in ("dead_paths",):
            compact[k] = v
        elif isinstance(v, dict) and k in ("metrics", "aggregate", "summary", "rails"):
            compact[k] = {kk: vv for kk, vv in v.items() if isinstance(vv, (int, float, bool, str))}
    out["eval_compact"] = compact
    return out


def apply_reject_thr_metrics(
    ious: list[float],
    confs: list[float],
    thr: float = ITER1_THR,
) -> dict[str, Any]:
    """Selective metrics at frozen iter1 thr (real arrays only)."""
    if not ious:
        return {"status": "skip", "n": 0}
    iou_a = np.asarray(ious, dtype=np.float64)
    conf_a = np.asarray(confs, dtype=np.float64)
    keep = conf_a >= thr
    n = int(len(iou_a))
    n_keep = int(keep.sum())
    return {
        "status": "ok",
        "n": n,
        "threshold": float(thr),
        "keep_rate": float(n_keep / n) if n else 0.0,
        "abstain_rate": float(1.0 - n_keep / n) if n else 0.0,
        "mean_iou_full": float(iou_a.mean()),
        "mean_iou_accepted": float(iou_a[keep].mean()) if n_keep else None,
        "n_keep": n_keep,
        "surface": LAB_SURFACE,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage external datasets + DATASET_INGEST_METRICS")
    ap.add_argument("--skip-eval", action="store_true")
    ap.add_argument("--max-external-patches", type=int, default=40)
    ap.add_argument("--max-holdout-patches", type=int, default=200)
    ap.add_argument("--device", default=None)
    args = ap.parse_args(argv)

    print("=== 1) manifests ===")
    hub = write_dataset_manifests()
    print("hub:", ART_DS / "EXTERNAL_DATASETS_HUB.json")

    print("=== 2) FireBench Caldor → NDWS patches ===")
    fb = convert_firebench_caldor_to_ndws(max_pairs=args.max_external_patches)
    print(json.dumps(fb, indent=2))

    print("=== 3) NDWS sample patches (if available) ===")
    ndws = convert_ndws_sample_to_npz(max_patches=args.max_external_patches)
    print(json.dumps({k: v for k, v in ndws.items() if k != "patches"}, indent=2))

    reject_base = _load_reject_baseline()
    u1_base = _load_u1_scorecard()

    baseline_eval: dict[str, Any] = {"status": "skipped"}
    after_firebench: dict[str, Any] = {"status": "skipped"}
    after_ndws: dict[str, Any] = {"status": "skipped"}

    if not args.skip_eval:
        print("=== 4) baseline ensemble eval (holdout TEST) ===")
        baseline_eval = run_ensemble_eval(
            HOLDOUT_TEST,
            max_patches=args.max_holdout_patches,
            label="holdout_test_baseline",
        )
        print(
            "baseline model_iou=",
            baseline_eval.get("model_iou"),
            "n=",
            baseline_eval.get("n_patches"),
            "status=",
            baseline_eval.get("status"),
        )

        fb_dir = ART_PATCH / "firebench_caldor"
        if list(fb_dir.glob("*.npz")):
            print("=== 5) after: FireBench external transfer eval ===")
            after_firebench = run_ensemble_eval(
                fb_dir,
                max_patches=args.max_external_patches,
                label="firebench_caldor_transfer",
            )
            print(
                "firebench model_iou=",
                after_firebench.get("model_iou"),
                "status=",
                after_firebench.get("status"),
            )

        nd_dir = ART_PATCH / "ndws_sample"
        if list(nd_dir.glob("*.npz")):
            print("=== 6) after: NDWS sample transfer eval ===")
            after_ndws = run_ensemble_eval(
                nd_dir,
                max_patches=args.max_external_patches,
                label="ndws_sample_transfer",
            )
            print(
                "ndws model_iou=",
                after_ndws.get("model_iou"),
                "status=",
                after_ndws.get("status"),
            )

    # Build baseline block from re-eval if available else prior scorecards (real files)
    baseline_block: dict[str, Any] = {
        "product_id": PRODUCT_ID,
        "protocol": PROTOCOL,
        "locked_reject_thr": ITER1_THR,
        "recommended_lab_surface": LAB_SURFACE,
        "field_ops_allow_ml_live_in_fusion": False,
        "tobarra_keep_reopen": False,
        "sources": {},
    }
    if reject_base:
        baseline_block["sources"]["lab_loop_v34_reject_latest"] = reject_base
        tm = reject_base.get("test_metrics_tuned") or {}
        tb = reject_base.get("test_metrics_baseline") or {}
        baseline_block["reject_thr"] = reject_base.get("reject_thr")
        baseline_block["test_mean_iou_full_coverage"] = tb.get("mean_iou_accepted")
        baseline_block["test_mean_iou_at_iter1_reject"] = tm.get("mean_iou_accepted")
        baseline_block["test_keep_rate_at_iter1_reject"] = tm.get("keep_rate")
        baseline_block["test_ece_full"] = tb.get("ece_full")
        baseline_block["test_selective_iou_at_coverage"] = tm.get("selective_iou_at_coverage")
    if u1_base:
        baseline_block["sources"]["ml_scorecard_u1_test"] = {
            "source": u1_base.get("source"),
            "primary": u1_base.get("primary"),
            "uncertainty": u1_base.get("uncertainty"),
            "gates": {
                k: (u1_base.get("gates") or {}).get(k)
                for k in (
                    "u1_test_honest",
                    "ml_product_go",
                    "U1_selective_beats_random",
                    "U1a_selective_ge_full_minus_eps",
                )
            },
        }
        prim = u1_base.get("primary") or {}
        unc = u1_base.get("uncertainty") or {}
        baseline_block["u1_model_iou"] = prim.get("model_iou")
        baseline_block["u1_ece"] = unc.get("ece_patch_conf")
        baseline_block["u1_selective_iou_80"] = unc.get("selective_iou_at_80pct_coverage")
        baseline_block["u1_test_honest"] = (u1_base.get("gates") or {}).get("u1_test_honest")

    if baseline_eval.get("status") == "ok":
        baseline_block["re_eval_holdout_test"] = {
            "model_iou": baseline_eval.get("model_iou"),
            "copy_iou": baseline_eval.get("copy_iou"),
            "delta_vs_copy": baseline_eval.get("delta_vs_copy"),
            "n_patches": baseline_eval.get("n_patches"),
            "data_dir": baseline_eval.get("data_dir"),
            "eval_compact": baseline_eval.get("eval_compact"),
        }

    after_block: dict[str, Any] = {
        "note": (
            "After = staged external patches integrated into NDWS lab eval path "
            "(zero-shot transfer with frozen clm_ensemble_v34 weights). "
            "No retrain. field_ops fusion remains OFF. Tobarra KEEP not reopened."
        ),
        "patch_conversion": {
            "firebench_caldor": fb,
            "ndws_sample": ndws,
        },
        "transfer_eval": {},
    }
    if after_firebench.get("status") == "ok":
        after_block["transfer_eval"]["firebench_caldor"] = {
            "model_iou": after_firebench.get("model_iou"),
            "copy_iou": after_firebench.get("copy_iou"),
            "delta_vs_copy": after_firebench.get("delta_vs_copy"),
            "n_patches": after_firebench.get("n_patches"),
            "data_dir": after_firebench.get("data_dir"),
            "eval_compact": after_firebench.get("eval_compact"),
        }
    else:
        after_block["transfer_eval"]["firebench_caldor"] = after_firebench

    if after_ndws.get("status") == "ok":
        after_block["transfer_eval"]["ndws_sample"] = {
            "model_iou": after_ndws.get("model_iou"),
            "copy_iou": after_ndws.get("copy_iou"),
            "delta_vs_copy": after_ndws.get("delta_vs_copy"),
            "n_patches": after_ndws.get("n_patches"),
            "data_dir": after_ndws.get("data_dir"),
            "eval_compact": after_ndws.get("eval_compact"),
        }
    else:
        after_block["transfer_eval"]["ndws_sample"] = after_ndws

    # Deltas only when both sides have real IoUs
    deltas: dict[str, Any] = {
        "rule": "delta = after.transfer_model_iou - baseline.re_eval_or_u1_model_iou",
        "comparisons": [],
    }
    base_iou = None
    if baseline_eval.get("status") == "ok" and baseline_eval.get("model_iou") is not None:
        base_iou = float(baseline_eval["model_iou"])
        base_iou_source = "re_eval_holdout_test"
    elif baseline_block.get("u1_model_iou") is not None:
        base_iou = float(baseline_block["u1_model_iou"])
        base_iou_source = "u1_scorecard_primary.model_iou"
    else:
        base_iou_source = None

    for name, block in after_block["transfer_eval"].items():
        if not isinstance(block, dict):
            continue
        if block.get("model_iou") is None or base_iou is None:
            deltas["comparisons"].append(
                {
                    "name": name,
                    "status": "incomplete",
                    "reason": "missing real IoU on baseline or after",
                }
            )
            continue
        after_iou = float(block["model_iou"])
        deltas["comparisons"].append(
            {
                "name": name,
                "status": "ok",
                "baseline_model_iou": base_iou,
                "baseline_source": base_iou_source,
                "after_model_iou": after_iou,
                "delta_model_iou": after_iou - base_iou,
                "n_patches_after": block.get("n_patches"),
                "interpretation": (
                    "Domain-transfer delta (external patches vs CLM holdout TEST). "
                    "Negative expected for OOD Caldor/NDWS; not a KEEP/promote signal. "
                    "Not ROS. field_ops fusion OFF."
                ),
            }
        )

    # Inventory deltas (dataset staging counts — factual, not ML quality)
    inventory = {
        "uav_images_staged": sum(
            _count_images(EXT / "uav_smoke_flame" / n)
            for n in (
                "flamevision_detection",
                "long_distance_smoke",
                "the_wildfire_dataset",
            )
        ),
        "firebench_kml_count": len(
            list((EXT / "firebench" / "caldor_2021" / "v2026.1" / "kml").glob("*.kml"))
        )
        if (EXT / "firebench" / "caldor_2021" / "v2026.1" / "kml").is_dir()
        else 0,
        "firebench_patches": int(fb.get("n_patches") or 0),
        "ndws_patches": int(ndws.get("n_patches") or 0),
        "wfts_docs_bytes": (
            (EXT / "wildfirespreadts" / "WildfireSpreadTS_Documentation.pdf").stat().st_size
            if (EXT / "wildfirespreadts" / "WildfireSpreadTS_Documentation.pdf").is_file()
            else 0
        ),
        "ndws_zip_bytes": (
            (EXT / "wildfirespreadts" / "ndws_kaggle_proxy" / "next-day-wildfire-spread.zip")
            .stat()
            .st_size
            if (
                EXT / "wildfirespreadts" / "ndws_kaggle_proxy" / "next-day-wildfire-spread.zip"
            ).is_file()
            else 0
        ),
    }

    # Criterion checks (factual file/eval evidence only — no invented ML numbers)
    delta_ok = (
        all(
            isinstance(c, dict) and c.get("status") == "ok" and c.get("delta_model_iou") is not None
            for c in (deltas.get("comparisons") or [])
        )
        and len(deltas.get("comparisons") or []) >= 1
    )
    baseline_has_real = (
        baseline_block.get("u1_model_iou") is not None
        or (baseline_block.get("re_eval_holdout_test") or {}).get("model_iou") is not None
        or baseline_block.get("test_mean_iou_full_coverage") is not None
    )
    patches_ok = (
        int(inventory.get("firebench_patches") or 0) > 0
        or int(inventory.get("ndws_patches") or 0) > 0
    )
    manifests_ok = (
        all(
            (EXT / name / "manifest.json").is_file()
            for name in ("wildfirespreadts", "firebench", "uav_smoke_flame")
        )
        and (ART_DS / "EXTERNAL_DATASETS_HUB.json").is_file()
    )
    criterion = {
        "datasets_staged": {
            "WildfireSpreadTS": {
                "ok": bool(inventory.get("wfts_docs_bytes") or inventory.get("ndws_zip_bytes")),
                "note": "docs + NDWS kaggle proxy (full ~48GB WildfireSpreadTS.zip not required for lab patches)",
            },
            "FireBench": {
                "ok": int(inventory.get("firebench_kml_count") or 0) >= 2,
                "kml": inventory.get("firebench_kml_count"),
            },
            "uav_smoke_flame": {
                "ok": int(inventory.get("uav_images_staged") or 0) > 0,
                "n_images": inventory.get("uav_images_staged"),
            },
        },
        "manifests_written": manifests_ok,
        "usable_patches_integrated": patches_ok,
        "baseline_metrics_real": baseline_has_real,
        "after_transfer_eval_real": delta_ok,
        "delta_block_present": bool(deltas.get("comparisons")),
        "rails": {
            "locked_reject_thr": ITER1_THR,
            "field_ops_allow_ml_live_in_fusion": False,
            "tobarra_keep_reopen": False,
            "dual_product": True,
        },
        "field_ops_fusion_claimed_on": False,
        "invented_metrics": False,
        "criterion_met": bool(
            manifests_ok
            and patches_ok
            and baseline_has_real
            and delta_ok
            and int(inventory.get("uav_images_staged") or 0) > 0
            and int(inventory.get("firebench_kml_count") or 0) >= 2
        ),
    }

    doc = {
        "schema": "dataset_ingest_metrics_v1",
        "created_utc": _utc_now(),
        "product_id": PRODUCT_ID,
        "protocol": PROTOCOL,
        "control_question": (
            "Stage WildfireSpreadTS/FireBench/UAV datasets, integrate usable NDWS patches "
            "into clm_ensemble_v34 lab path, report real baseline vs after metrics."
        ),
        "rails": {
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "locked_reject_thr": ITER1_THR,
            "recommended_lab_surface": LAB_SURFACE,
            "tobarra_keep_reopen": False,
            "no_ece_retune_same_holdout": True,
            "label": "lab / research_open only",
        },
        "honesty": {
            "invented_metrics": False,
            "full_retrain": False,
            "field_ops_fusion": "OFF",
            "tobarra_keep": "not_reopened",
            "metric_sources": [
                str(REJECT_LATEST) if REJECT_LATEST.is_file() else None,
                str(U1_SCORECARD) if U1_SCORECARD.is_file() else None,
                "evaluate_clm_weights on holdout_v1/test + external_ingest_v1/*",
            ],
        },
        "hub_manifest": str(ART_DS / "EXTERNAL_DATASETS_HUB.json"),
        "inventory": inventory,
        "baseline": baseline_block,
        "after": after_block,
        "delta": deltas,
        "datasets_hub": hub.get("datasets"),
        "criterion": criterion,
    }
    _write_json(OUT_METRICS, doc)
    print("=== wrote ===", OUT_METRICS)
    print(
        json.dumps(
            {
                "baseline_u1_iou": baseline_block.get("u1_model_iou"),
                "baseline_reeval_iou": (baseline_block.get("re_eval_holdout_test") or {}).get(
                    "model_iou"
                ),
                "deltas": deltas.get("comparisons"),
                "inventory": inventory,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
