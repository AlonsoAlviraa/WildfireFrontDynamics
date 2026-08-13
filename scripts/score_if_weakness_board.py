#!/usr/bin/env python3
"""Fail-closed IF weakness / candidate board (no retrain, no Vp/ha invention).

Reads infocam_anchors.json plus on-disk trees and scores R1–R6 / H1–H7.
Unknown bits are 0. Missing cite cannot become confirmed. Missing ≥3 dated
scenes cannot become ml_strong. Never writes data/infocam_anchors.json.

python scripts/score_if_weakness_board.py
python scripts/score_if_weakness_board.py --fire-id tobarra_20240802
# subset query prints JSON to stdout; does not overwrite docs/WEAKNESS_BOARD.*
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from inventory_real_if_material import infer_timestamp, sha256_of_file  # noqa: E402

SCHEMA = "wfd_if_weakness_board_v1"
HONESTY_CLASSES = ("ml_strong", "ml_weak", "proxy", "context_only", "discard")
R_KEYS = ("R1", "R2", "R3", "R4", "R5", "R6")
H_KEYS = ("H1", "H2", "H3", "H4", "H5", "H6", "H7")
TIF_SUFFIXES = {".tif", ".tiff"}
GEOM_SUFFIXES = {".tif", ".tiff", ".kmz", ".kml", ".geojson", ".shp", ".gpkg"}
INVENTORY_SUFFIXES = GEOM_SUFFIXES | {".json", ".csv", ".md"}
CITE_RE = re.compile(
    r"infocam|observatorio|parte operativo|bolet[ií]n|geacam",
    re.IGNORECASE,
)

# process_one_fire / batch_process_fires IDs plus the sealed Tobarra anchor.
PROCESS_ONE_FIRE_FALLBACK = (
    "tobarra_20240802",
    "cardoso_2025",
    "la_estrella_acom1_2024",
    "la_estrella_acom2_2024",
    "hellin_2024",
    "retuerta_2025",
    "brazatortas_2025",
    "polan_2025",
)

ALIGN_DIR_TO_FIRE = {
    "tobarra_20240802": "tobarra_20240802",
    "CARDOSO": "cardoso_2025",
    "cardoso_2025_extra_reproj": "cardoso_2025",
    "hellin_2024": "hellin_2024",
    "LA_ESTRELLA_ACOM1": "la_estrella_acom1_2024",
    "LA_ESTRELLA_ACOM2": "la_estrella_acom2_2024",
    "retuerta_2025": "retuerta_2025",
    "brazatortas_2025": "brazatortas_2025",
}

# Historical NO_USE: Retuerta FOV; Polán single-frame. Do not silently promote.
NO_USE_REASONS = {
    "retuerta_2025": "FOV",
    "polan_2025": ">=3 frames",
}

OPEN_PROXY_IDS = {
    "pt_firesprd",
    "AU_EMSR500_PERTH",
    "CL_EMSR647_NACIMIENTO",
    "AU_EMSR408_NSW",
    "CL_EMSR715_VALPARAISO",
    "BR_PANTANAL_2020_MAPBIOMAS",
    "AU_NAFI_NT_SEASON_2023",
    "extremadura_rai_2025",
}

TREE_MAP: dict[str, tuple[str, ...]] = {
    "tobarra_20240802": (
        "artifacts/aligned_spatial_v1/tobarra_20240802",
        "artifacts/tobarra_reprojected_lwir",
        "artifacts/tobarra_lwir_masks",
        "data/real_if/pablo_geacam_20260730_tobarra",
    ),
    "cardoso_2025": (
        "artifacts/aligned_spatial_v1/CARDOSO",
        "artifacts/aligned_spatial_v1/cardoso_2025_extra_reproj",
        "artifacts/cardoso_2025_reprojected_lwir",
        "artifacts/cardoso_2025_lwir_masks",
        "data/real_if/raw_dropbox/organized/CARDOSO",
    ),
    "hellin_2024": (
        "artifacts/aligned_spatial_v1/hellin_2024",
        "artifacts/hellin_2024_reprojected_lwir",
        "artifacts/hellin_2024_lwir_masks",
        "data/real_if/raw_dropbox/organized/HELLIN20240719",
    ),
    "la_estrella_acom1_2024": (
        "artifacts/aligned_spatial_v1/LA_ESTRELLA_ACOM1",
        "artifacts/la_estrella_acom1_2024_reprojected_lwir",
        "artifacts/la_estrella_acom1_2024_lwir_masks",
        "data/real_if/raw_dropbox/organized/LA_ESTRELLA_ACOM1",
    ),
    "la_estrella_acom2_2024": (
        "artifacts/aligned_spatial_v1/LA_ESTRELLA_ACOM2",
        "artifacts/la_estrella_acom2_2024_reprojected_lwir",
        "artifacts/la_estrella_acom2_2024_lwir_masks",
        "data/real_if/raw_dropbox/organized/LA_ESTRELLA_ACOM2",
    ),
    "retuerta_2025": (
        "artifacts/aligned_spatial_v1/retuerta_2025",
        "artifacts/retuerta_2025_reprojected_lwir",
        "artifacts/retuerta_2025_lwir_masks",
        "data/real_if/raw_dropbox/organized/04_09_2025_IF.RETUERTA",
    ),
    "brazatortas_2025": (
        "artifacts/aligned_spatial_v1/brazatortas_2025",
        "artifacts/brazatortas_2025_reprojected_lwir",
        "artifacts/brazatortas_2025_lwir_masks",
        "data/real_if/raw_dropbox/organized/05_10_2025_IF.BRAZATORTAS",
    ),
    "polan_2025": (
        "artifacts/polan_2025_reprojected_lwir",
        "artifacts/polan_2025_lwir_masks",
        "data/real_if/raw_dropbox/organized/13_09_2025_IF.POLAN",
    ),
    "pt_firesprd": (
        "data/external/pt_firesprd",
    ),
    "AU_EMSR500_PERTH": (
        "data/open_if/latam_au/au/AU_EMSR500_PERTH",
    ),
    "CL_EMSR647_NACIMIENTO": (
        "data/open_if/latam_au/cl/CL_EMSR647_NACIMIENTO",
    ),
    "AU_EMSR408_NSW": (
        "data/open_if/latam_au/au/AU_EMSR408_NSW",
    ),
    "CL_EMSR715_VALPARAISO": (
        "data/open_if/latam_au/cl/CL_EMSR715_VALPARAISO",
    ),
    "BR_PANTANAL_2020_MAPBIOMAS": (
        "data/open_if/latam_au/br/BR_PANTANAL_2020_MAPBIOMAS",
    ),
    "AU_NAFI_NT_SEASON_2023": (
        "data/open_if/latam_au/au/AU_NAFI_NT_SEASON_2023",
    ),
    "extremadura_rai_2025": (
        "data/open_if/extremadura_rai_2025",
    ),
}

DEFAULT_OUT_JSON = ROOT / "docs" / "WEAKNESS_BOARD.json"
DEFAULT_OUT_MD = ROOT / "docs" / "WEAKNESS_BOARD.md"
DEFAULT_INV_JSON = ROOT / "docs" / "IF_ONDISK_INVENTORY.json"
DEFAULT_INV_CSV = ROOT / "docs" / "IF_ONDISK_INVENTORY.csv"


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix().replace("\\", "/")


def _bit(ok: bool) -> int:
    return 1 if ok else 0


def process_one_fire_ids() -> tuple[str, ...]:
    ids = ["tobarra_20240802"]
    try:
        from batch_process_fires import FIRES

        ids.extend(str(row[0]) for row in FIRES)
    except Exception:
        ids.extend(PROCESS_ONE_FIRE_FALLBACK[1:])
    out: list[str] = []
    for fid in ids:
        if fid not in out:
            out.append(fid)
    return tuple(out)


def load_anchors(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"anchors file missing: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"anchors file is not valid JSON: {path}") from exc
    if not isinstance(doc, dict):
        raise ValueError(f"anchors file must be a JSON object: {path}")
    anchors = doc.get("anchors")
    if not isinstance(anchors, dict) or not anchors:
        raise ValueError(f"anchors file has no usable anchors: {path}")
    return doc


def discover_open_if_ids(root: Path) -> list[str]:
    found: list[str] = []
    latam = root / "data" / "open_if" / "latam_au"
    if latam.is_dir():
        for meta in latam.glob("*/*/meta.json"):
            event_id = meta.parent.name
            if event_id and event_id not in found:
                found.append(event_id)
    if (root / "data" / "external" / "pt_firesprd").exists():
        found.append("pt_firesprd")
    if (root / "data" / "open_if" / "extremadura_rai_2025").exists():
        found.append("extremadura_rai_2025")
    return found


def discover_fire_ids(root: Path, anchors: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for fid in anchors.keys():
        if fid not in ids:
            ids.append(str(fid))
    for fid in process_one_fire_ids():
        if fid not in ids:
            ids.append(fid)
    align_root = root / "artifacts" / "aligned_spatial_v1"
    if align_root.is_dir():
        for child in sorted(align_root.iterdir()):
            if not child.is_dir():
                continue
            mapped = ALIGN_DIR_TO_FIRE.get(child.name, child.name)
            if mapped not in ids:
                ids.append(mapped)
    for fid in discover_open_if_ids(root):
        if fid not in ids:
            ids.append(fid)
    return ids


def trees_for_fire(root: Path, fire_id: str) -> list[Path]:
    rels = list(TREE_MAP.get(fire_id, ()))
    for dirname, mapped in ALIGN_DIR_TO_FIRE.items():
        if mapped == fire_id:
            rels.append(f"artifacts/aligned_spatial_v1/{dirname}")
    if fire_id in OPEN_PROXY_IDS and fire_id not in TREE_MAP:
        for region in ("au", "br", "cl"):
            rels.append(f"data/open_if/latam_au/{region}/{fire_id}")
    seen: set[str] = set()
    out: list[Path] = []
    for rel in rels:
        path = root / rel
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            out.append(path)
    return out


def _iter_inventory_files(tree: Path) -> list[Path]:
    if tree.is_file():
        return [tree]
    files: list[Path] = []
    for path in tree.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in INVENTORY_SUFFIXES:
            files.append(path)
    return files


def _is_mask(path: Path) -> bool:
    name = path.name.lower()
    return "mask" in name or path.parent.name.lower() == "masks"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _meta_docs(root: Path, trees: list[Path]) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    candidates: list[Path] = []
    for tree in trees:
        if tree.is_file() and tree.suffix.lower() == ".json":
            candidates.append(tree)
            continue
        if not tree.is_dir():
            continue
        candidates.extend(tree.glob("align_manifest.json"))
        candidates.extend(tree.glob("meta.json"))
        candidates.extend(tree.glob("inventory.json"))
        candidates.extend(tree.glob("**/align_manifest.json"))
        candidates.extend(tree.glob("**/meta.json"))
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        docs.append(_read_json(path))
    return docs


def _has_crs_bbox_dates(docs: list[dict[str, Any]], dated_scene_count: int) -> bool:
    has_crs = False
    has_bbox = False
    has_dates = dated_scene_count >= 1
    for doc in docs:
        if doc.get("crs") or (isinstance(doc.get("grid"), dict) and doc["grid"].get("crs")):
            has_crs = True
        params = doc.get("params") if isinstance(doc.get("params"), dict) else {}
        if params.get("crs"):
            has_crs = True
        chains = doc.get("chains")
        if isinstance(chains, list):
            for chain in chains:
                if not isinstance(chain, dict):
                    continue
                grid = chain.get("grid") if isinstance(chain.get("grid"), dict) else {}
                if grid.get("crs"):
                    has_crs = True
                if all(k in grid for k in ("left", "bottom", "right", "top")):
                    has_bbox = True
                images = chain.get("images")
                if isinstance(images, list) and images:
                    has_dates = True
        if isinstance(doc.get("bbox_wgs84"), list) and len(doc["bbox_wgs84"]) == 4:
            has_bbox = True
        if isinstance(doc.get("dates"), list) and doc["dates"]:
            has_dates = True
        if isinstance(doc.get("bbox"), (list, dict)) and doc.get("bbox"):
            has_bbox = True
    return has_crs and has_bbox and has_dates


def _has_documented_rights(root: Path, fire_id: str, trees: list[Path], docs: list[dict[str, Any]]) -> bool:
    """R4=1 only from pack-local license fields or a rights sheet that names fire_id."""
    local_docs = list(docs)
    for tree in trees:
        if not tree.is_dir():
            continue
        for name in ("meta.json", "inventory.json"):
            cand = tree / name
            if cand.is_file():
                local_docs.append(_read_json(cand))
    for doc in local_docs:
        for key in ("license_id", "license", "licence", "rights_doc"):
            val = doc.get(key)
            if isinstance(val, str) and val.strip():
                return True
    rights_docs = (
        root / "docs" / "data_campaigns" / "LATAM_AU_RIGHTS.md",
        root / "docs" / "data_campaigns" / "LATAM_AU_LICENSE_MATRIX.md",
    )
    needle = fire_id.lower()
    for path in rights_docs:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        if needle and needle in text:
            return True
    return False


def inventory_fire(root: Path, fire_id: str) -> dict[str, Any]:
    trees = trees_for_fire(root, fire_id)
    files: list[Path] = []
    for tree in trees:
        files.extend(_iter_inventory_files(tree))
    tifs = [p for p in files if p.suffix.lower() in TIF_SUFFIXES]
    kmz = [p for p in files if p.suffix.lower() == ".kmz"]
    geom = [p for p in files if p.suffix.lower() in {".kmz", ".kml", ".geojson", ".shp", ".gpkg"}]
    masks = [p for p in tifs if _is_mask(p)]
    scene_tifs = [p for p in tifs if not _is_mask(p)] or tifs
    dated: set[str] = set()
    usable_dated: set[str] = set()
    for path in scene_tifs:
        observed_at, quality = infer_timestamp(path)
        if not observed_at or quality == "missing":
            continue
        dated.add(observed_at)
        rel = _rel(path, root).lower()
        if "aligned_spatial_v1" in rel or "reprojected" in rel:
            usable_dated.add(observed_at)

    fingerprint_src = hashlib.sha256()
    for path in sorted(files, key=lambda p: _rel(p, root).lower()):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        fingerprint_src.update(f"{_rel(path, root)}\t{size}\n".encode("utf-8"))

    manifest_hashes: dict[str, str] = {}
    for tree in trees:
        for name in ("align_manifest.json", "meta.json", "inventory.json"):
            cand = tree / name if tree.is_dir() else None
            if cand and cand.is_file() and cand.stat().st_size <= 2_000_000:
                try:
                    manifest_hashes[_rel(cand, root)] = sha256_of_file(cand)
                except OSError:
                    continue

    docs = _meta_docs(root, trees)
    aligned_tifs = [
        p
        for p in tifs
        if "aligned_spatial_v1" in _rel(p, root)
    ]
    return {
        "fire_id": fire_id,
        "trees_present": [_rel(t, root) for t in trees],
        "on_disk_tif_count": len(tifs),
        "dated_scene_count": len(dated),
        "usable_dated_scene_count": len(usable_dated),
        "on_disk_kmz_count": len(kmz),
        "geometry_file_count": len(geom) + len(masks),
        "mask_tif_count": len(masks),
        "aligned_tif_count": len(aligned_tifs),
        "inventory_file_count": len(files),
        "tree_fingerprint": fingerprint_src.hexdigest() if files else "",
        "manifest_sha256": manifest_hashes,
        "has_geometry": bool(geom or masks or any("label" in _rel(p, root).lower() for p in tifs)),
        "has_crs_bbox_dates": _has_crs_bbox_dates(docs, len(dated)),
        "has_documented_rights": _has_documented_rights(root, fire_id, trees, docs),
        "has_weather": any("weather" in _rel(p, root).lower() or "era5" in _rel(p, root).lower() for p in files),
        "pack_kind": "open_proxy" if fire_id in OPEN_PROXY_IDS else "clm",
    }


def score_h_bits(fire_id: str, anchor: dict[str, Any] | None, stable_ids: set[str]) -> dict[str, int]:
    source = str((anchor or {}).get("source") or "").strip()
    status = str((anchor or {}).get("status") or "").strip().lower()
    vp = (anchor or {}).get("vp_m_min")
    ha = (anchor or {}).get("area_ha")
    h1 = _bit(bool(source) and CITE_RE.search(source) is not None)
    h2 = _bit(
        isinstance(vp, (int, float))
        and isinstance(ha, (int, float))
        and float(vp) > 0
        and float(ha) > 0
    )
    declared_id = str((anchor or {}).get("fire_id") or fire_id)
    h3 = _bit(declared_id == fire_id and (fire_id in stable_ids or anchor is not None))
    h4 = _bit(bool(source))
    h5 = _bit(status == "confirmed" and h2 == 1 and h4 == 1)
    h6 = _bit(status == "confirmed" and h1 == 1)
    h7 = 1
    return {"H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5, "H6": h6, "H7": h7}


def score_r_bits(inv: dict[str, Any]) -> dict[str, int]:
    dated = int(inv["dated_scene_count"])
    usable = int(inv.get("usable_dated_scene_count") or 0)
    # Prefer aligned/reprojected timestamps when that stack exists (Polán: 1 reproj).
    scene_n = usable if usable > 0 else dated
    r1 = _bit(scene_n >= 3)
    r2 = _bit(bool(inv["has_geometry"]))
    r3 = _bit(bool(inv["has_crs_bbox_dates"]))
    r4 = _bit(bool(inv["has_documented_rights"]))
    r5 = 1
    r6 = _bit(bool(inv["tree_fingerprint"]) and int(inv["inventory_file_count"]) > 0)
    return {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6}


def _blocking_gap(
    fire_id: str,
    r: dict[str, int],
    h: dict[str, int],
    honesty_class: str,
) -> str:
    if fire_id in NO_USE_REASONS:
        return NO_USE_REASONS[fire_id]
    if h["H1"] == 0:
        return "cite"
    if r["R1"] == 0:
        return ">=3 frames"
    if r["R4"] == 0:
        return "rights"
    if honesty_class == "discard":
        return "FOV"
    if honesty_class != "ml_strong":
        if r["R2"] == 0:
            return "geometry"
        if r["R3"] == 0:
            return "crs/bbox/dates"
        if r["R6"] == 0:
            return "inventory"
        return "cite"
    return "none"


def classify_row(
    fire_id: str,
    *,
    r: dict[str, int],
    h: dict[str, int],
    inv: dict[str, Any],
    anchor: dict[str, Any] | None,
) -> tuple[str, str, str, str]:
    """Return honesty_class, status, blocking_gap, owner. Fail-closed."""
    pack_kind = str(inv.get("pack_kind") or "clm")
    tif_count = int(inv["on_disk_tif_count"])
    dated = int(inv["dated_scene_count"])
    usable = int(inv.get("usable_dated_scene_count") or 0)

    if fire_id in NO_USE_REASONS:
        honesty = "discard"
    elif pack_kind == "open_proxy":
        honesty = "ml_weak" if r["R1"] == 1 and r["R2"] == 1 else "proxy"
    elif usable <= 1 and tif_count <= 1:
        honesty = "discard"
    elif r["R1"] == 1 and r["R2"] == 1:
        honesty = "ml_weak"
    elif dated == 0 and not inv.get("has_geometry"):
        honesty = "context_only" if inv.get("has_weather") else "discard"
    else:
        honesty = "context_only"

    r_all = all(r[k] == 1 for k in R_KEYS)
    aligned_ok = int(inv.get("aligned_tif_count") or 0) >= 3 or int(inv.get("mask_tif_count") or 0) >= 3
    if (
        honesty != "discard"
        and r_all
        and h["H1"] == 1
        and aligned_ok
        and fire_id not in NO_USE_REASONS
    ):
        honesty = "ml_strong"

    if honesty == "ml_strong" and (r["R1"] == 0 or h["H1"] == 0):
        honesty = "ml_weak" if r["R2"] == 1 else "proxy"

    if honesty not in HONESTY_CLASSES:
        honesty = "discard"

    anchor_status = str((anchor or {}).get("status") or "").strip().lower()
    if honesty == "discard":
        status = "NO_USE"
    elif anchor_status == "confirmed" and h["H1"] == 1:
        status = "confirmed"
    elif anchor_status == "confirmed" and h["H1"] == 0:
        status = "pending_external"
    elif anchor_status == "pending_external":
        status = "pending_external"
    elif pack_kind == "open_proxy":
        status = "inventory_only"
    else:
        status = "inventory_only"

    if status == "confirmed" and h["H1"] == 0:
        status = "pending_external"
    if honesty == "ml_strong" and (r["R1"] == 0 or h["H1"] == 0):
        honesty = "ml_weak"

    gap = _blocking_gap(fire_id, r, h, honesty)
    owner = "human" if gap in {"cite", "rights", "FOV", ">=3 frames"} else "eng"
    return honesty, status, gap, owner


def _cite_sealed_json(path: Path, keys: tuple[str, ...]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return {k: data.get(k) for k in keys}


def tobarra_lofo_section(root: Path, inv: dict[str, Any] | None) -> dict[str, Any]:
    v29_path = root / "docs" / "V29_LOFO_TOBARRA_VERDICT.json"
    folds_path = root / "docs" / "CLM_LOFO_ALL_FOLDS_REPORT.json"
    v29 = _cite_sealed_json(
        v29_path,
        ("held_out", "test_iou", "copy_baseline_iou", "improvement_vs_copy_iou", "verdict", "n_test"),
    )
    folds_raw = None
    if folds_path.is_file():
        try:
            folds_raw = json.loads(folds_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            folds_raw = None
    fold_rows = []
    if isinstance(folds_raw, dict):
        for fold in folds_raw.get("folds") or []:
            if not isinstance(fold, dict):
                continue
            fold_rows.append(
                {
                    "held": fold.get("held"),
                    "test_iou": fold.get("test_iou"),
                    "copy_baseline_iou": fold.get("copy_baseline_iou"),
                    "source": "docs/CLM_LOFO_ALL_FOLDS_REPORT.json",
                }
            )
    decide_honesty: dict[str, Any] | None = None
    try:
        from wildfire_front.open_if.external_ros import honesty_row

        decide_honesty = honesty_row("tobarra_aligned_decide")
    except Exception:
        decide_honesty = None

    aligned_root = root / "artifacts" / "aligned_spatial_v1" / "tobarra_20240802"
    aligned_tifs = list(aligned_root.rglob("*.tif")) if aligned_root.is_dir() else []
    dated = set()
    for path in aligned_tifs:
        if _is_mask(path):
            continue
        ts, quality = infer_timestamp(path)
        if ts and quality != "missing":
            dated.add(ts)
    return {
        "schema": "wfd_tobarra_lofo_cite_v1",
        "new_iou_invented": False,
        "keep_reopened": False,
        "retrained": False,
        "blocker": (
            "domain gap: sealed Tobarra LOFO IoU is cited from "
            "docs/V29_LOFO_TOBARRA_VERDICT.json vs non-Tobarra folds in "
            "docs/CLM_LOFO_ALL_FOLDS_REPORT.json — not a 'need more epochs' problem"
        ),
        "sealed_v29": v29,
        "sealed_folds": fold_rows,
        "on_disk_aligned": {
            "path": "artifacts/aligned_spatial_v1/tobarra_20240802",
            "on_disk_tif_count": len(aligned_tifs),
            "dated_scene_count": len(dated),
            "present": aligned_root.is_dir(),
        },
        "inventory_row": {
            "on_disk_tif_count": None if inv is None else inv.get("on_disk_tif_count"),
            "dated_scene_count": None if inv is None else inv.get("dated_scene_count"),
        },
        "decide_tobarra_aligned": decide_honesty,
        "sources": [
            "docs/V29_LOFO_TOBARRA_VERDICT.json",
            "docs/CLM_LOFO_ALL_FOLDS_REPORT.json",
        ],
    }


def score_fire(
    root: Path,
    fire_id: str,
    *,
    anchors: dict[str, Any],
    stable_ids: set[str],
) -> dict[str, Any]:
    anchor = anchors.get(fire_id)
    if anchor is not None and not isinstance(anchor, dict):
        anchor = None
    inv = inventory_fire(root, fire_id)
    r = score_r_bits(inv)
    h = score_h_bits(fire_id, anchor, stable_ids)
    honesty, status, gap, owner = classify_row(
        fire_id, r=r, h=h, inv=inv, anchor=anchor
    )
    vp = (anchor or {}).get("vp_m_min") if isinstance(anchor, dict) else None
    ha = (anchor or {}).get("area_ha") if isinstance(anchor, dict) else None
    return {
        "fire_id": fire_id,
        "status": status,
        "anchor_status": None if not isinstance(anchor, dict) else anchor.get("status"),
        "honesty_class": honesty,
        "R1": r["R1"],
        "R2": r["R2"],
        "R3": r["R3"],
        "R4": r["R4"],
        "R5": r["R5"],
        "R6": r["R6"],
        "H1": h["H1"],
        "H2": h["H2"],
        "H3": h["H3"],
        "H4": h["H4"],
        "H5": h["H5"],
        "H6": h["H6"],
        "H7": h["H7"],
        "on_disk_tif_count": inv["on_disk_tif_count"],
        "dated_scene_count": inv["dated_scene_count"],
        "usable_dated_scene_count": inv["usable_dated_scene_count"],
        "on_disk_kmz_count": inv["on_disk_kmz_count"],
        "aligned_tif_count": inv["aligned_tif_count"],
        "mask_tif_count": inv["mask_tif_count"],
        "blocking_gap": gap,
        "owner": owner,
        "use_flag": "NO_USE" if honesty == "discard" else "review",
        "vp_m_min_cited": vp if isinstance(vp, (int, float)) else None,
        "area_ha_cited": ha if isinstance(ha, (int, float)) else None,
        "trees_present": inv["trees_present"],
        "tree_fingerprint": inv["tree_fingerprint"],
        "manifest_sha256": inv["manifest_sha256"],
        "pack_kind": inv["pack_kind"],
        "invented_vp_ha": False,
        "retrained": False,
        "keep_reopened": False,
        "anchors_written": False,
    }


def build_board(
    *,
    root: Path,
    anchors_path: Path,
    fire_ids: list[str] | None = None,
) -> dict[str, Any]:
    doc = load_anchors(anchors_path)
    anchors = doc["anchors"]
    stable = set(process_one_fire_ids()) | set(anchors.keys()) | set(OPEN_PROXY_IDS)
    if fire_ids is None:
        selected = discover_fire_ids(root, anchors)
    else:
        selected = list(fire_ids)
    rows = [score_fire(root, fid, anchors=anchors, stable_ids=stable) for fid in selected]
    by_id = {row["fire_id"]: row for row in rows}
    tobarra_inv = None
    if "tobarra_20240802" in by_id:
        tobarra_inv = {
            "on_disk_tif_count": by_id["tobarra_20240802"]["on_disk_tif_count"],
            "dated_scene_count": by_id["tobarra_20240802"]["dated_scene_count"],
        }
    n_confirmed = sum(1 for row in rows if row["status"] == "confirmed")
    n_ml_strong = sum(1 for row in rows if row["honesty_class"] == "ml_strong")
    return {
        "schema": SCHEMA,
        "as_of_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "rails": {
            "freeze_ml": True,
            "tobarra_keep_reopen": False,
            "go_q": "partial",
            "field_ops_ml_fusion": "ON",
            "fusion_note": "human 2026-08-13; not despacho",
            "hellin_status_ssot": "pending_external",
            "invented_vp_ha": False,
            "new_iou_invented": False,
            "retrained_clm_ensemble_v34": False,
            "anchors_written": False,
            "catalog_iou_0_8963": "provenance_only",
            "product": "decision_support",
        },
        "summary": {
            "n_fires": len(rows),
            "n_confirmed": n_confirmed,
            "n_ml_strong": n_ml_strong,
            "n_pending_external": sum(1 for row in rows if row["status"] == "pending_external"),
            "n_no_use": sum(1 for row in rows if row["status"] == "NO_USE"),
            "grade_a_ops_anchors": n_confirmed,
            "note": "only confirmed+H1 rows count as grade-A ops anchors; do not invent a 2nd",
        },
        "fires": rows,
        "tobarra_lofo": tobarra_lofo_section(root, tobarra_inv),
        "sources": {
            "anchors": _rel(anchors_path, root) if anchors_path.exists() else str(anchors_path),
            "protocol": [
                "docs/PLAN_ML_DATA_LATAM_AU_2026-08-13.md",
                "docs/REAL_IF_INTAKE_PROTOCOL.md",
                "docs/DATA_ANCHOR_SSOT.md",
            ],
        },
    }


def _assert_fail_closed(board: dict[str, Any]) -> None:
    for row in board.get("fires") or []:
        if not isinstance(row, dict):
            raise ValueError("board row is not an object")
        for key in (*R_KEYS, *H_KEYS):
            val = row.get(key)
            if val not in (0, 1):
                raise ValueError(f"{row.get('fire_id')} {key} must be 0/1, got {val!r}")
        if row.get("H1") == 0 and row.get("status") == "confirmed":
            raise ValueError(f"{row.get('fire_id')} confirmed with H1=0")
        if (row.get("H1") == 0 or row.get("R1") == 0) and row.get("honesty_class") == "ml_strong":
            raise ValueError(f"{row.get('fire_id')} ml_strong with H1/R1=0")
        if row.get("honesty_class") not in HONESTY_CLASSES:
            raise ValueError(f"{row.get('fire_id')} bad honesty_class")
        if row.get("invented_vp_ha") is not False:
            raise ValueError("board must not invent Vp/ha")


def render_markdown(board: dict[str, Any]) -> str:
    rows = board.get("fires") or []
    lines = [
        "# IF weakness / candidate board",
        "",
        "> Fail-closed inventory. **Does not** invent Vp/ha, flip `infocam_anchors.json`,",
        "> retrain `clm_ensemble_v34`, reopen Tobarra KEEP, or close GO_Q.",
        "> Fusion SSOT stays **ON** (human 2026-08-13) ≠ despacho. IoU ≠ ROS.",
        f"> Schema `{board.get('schema')}` · `{board.get('as_of_utc')}`.",
        "",
        "## Rails",
        "",
        "| Rail | Value |",
        "|------|--------|",
        "| FREEZE_ML | intact — no v34 retrain |",
        "| Tobarra KEEP reopen | **false** |",
        "| GO_Q | **partial** |",
        "| field_ops ML fusion | **ON** (not despacho) |",
        "| Hellín | `pending_external` until cite + Alonso |",
        "| Catalog IoU 0.8963 | provenance only |",
        "",
        "## Fires",
        "",
        "| fire_id | status | honesty_class | R1 | R2 | R3 | R4 | R5 | R6 | H1 | H2 | H3 | H4 | H5 | H6 | H7 | tifs | dated | gap | owner |",
        "|---------|--------|---------------|----|----|----|----|----|----|----|----|----|----|----|----|----|-----:|------:|-----|-------|",
    ]
    for row in rows:
        lines.append(
            "| `{fire_id}` | `{status}` | `{honesty_class}` | {R1} | {R2} | {R3} | {R4} | {R5} | {R6} | "
            "{H1} | {H2} | {H3} | {H4} | {H5} | {H6} | {H7} | {on_disk_tif_count} | {dated_scene_count} | "
            "{blocking_gap} | {owner} |".format(**row)
        )
    summary = board.get("summary") or {}
    lines.extend(
        [
            "",
            f"- n_fires: **{summary.get('n_fires')}** · confirmed: **{summary.get('n_confirmed')}** · "
            f"ml_strong: **{summary.get('n_ml_strong')}** · NO_USE: **{summary.get('n_no_use')}**",
            "- Unknown R/H bits are **0**. Missing cite ⇒ not `confirmed`. Missing ≥3 dated scenes ⇒ not `ml_strong`.",
            "- Open packs (PT-FireSprd, Perth, Nacimiento, …) stay `ml_weak` / `proxy` — not a 2nd INFOCAM grade A.",
            "",
            "## Tobarra LOFO (sealed cites only)",
            "",
        ]
    )
    lofo = board.get("tobarra_lofo") or {}
    v29 = lofo.get("sealed_v29") or {}
    lines.append(
        f"- New IoU invented: `{lofo.get('new_iou_invented')}` · KEEP reopened: `{lofo.get('keep_reopened')}` · "
        f"retrained: `{lofo.get('retrained')}`"
    )
    if v29:
        lines.append(
            f"- Sealed V29 (`docs/V29_LOFO_TOBARRA_VERDICT.json`): held `{v29.get('held_out')}` "
            f"test_iou **{v29.get('test_iou')}** vs copy {v29.get('copy_baseline_iou')} "
            f"(n_test={v29.get('n_test')})."
        )
    for fold in lofo.get("sealed_folds") or []:
        lines.append(
            f"- Sealed fold `{fold.get('held')}`: test_iou **{fold.get('test_iou')}** "
            f"(source `docs/CLM_LOFO_ALL_FOLDS_REPORT.json`)."
        )
    on_disk = lofo.get("on_disk_aligned") or {}
    lines.append(
        f"- On-disk aligned `{on_disk.get('path')}`: tifs={on_disk.get('on_disk_tif_count')} "
        f"dated_scenes={on_disk.get('dated_scene_count')} present={on_disk.get('present')}."
    )
    decide = lofo.get("decide_tobarra_aligned") or {}
    if decide:
        lines.append(
            f"- `decide_tobarra_aligned` honesty_class=`{decide.get('honesty_class')}` "
            f"(existing helper; not a new IoU)."
        )
    lines.extend(
        [
            f"- Blocker: {lofo.get('blocker')}",
            "",
            "## How to run",
            "",
            "```powershell",
            "python scripts/score_if_weakness_board.py",
            "python scripts/score_if_weakness_board.py --fire-id hellin_2024",
            "# --fire-id alone prints JSON to stdout; it does not overwrite docs/WEAKNESS_BOARD.*",
            "```",
            "",
            "Missing anchors or unknown `--fire-id` exit **1**. Does not write `data/infocam_anchors.json`.",
            "A `--fire-id` subset without `--out-json` / `--out-md` / `--inventory-*` does not rewrite the SSOT docs.",
            "",
            "Human leftovers (cite / 2nd grade A / H1 acta) stay in `docs/HANDOFF_HUMAN_P0_2026-08-13.md`.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def write_inventory_sidecar(board: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    fires = board.get("fires") or []
    payload = {
        "schema": "wfd_if_ondisk_inventory_v1",
        "as_of_utc": board.get("as_of_utc"),
        "hash_mode": "tree_fingerprint_path_size_plus_small_manifests",
        "note": "Does not hash raw GeoTIFF payloads (too large; not committed). Counts are measured.",
        "fires": [
            {
                "fire_id": row["fire_id"],
                "on_disk_tif_count": row["on_disk_tif_count"],
                "dated_scene_count": row["dated_scene_count"],
                "usable_dated_scene_count": row["usable_dated_scene_count"],
                "on_disk_kmz_count": row["on_disk_kmz_count"],
                "aligned_tif_count": row["aligned_tif_count"],
                "mask_tif_count": row["mask_tif_count"],
                "tree_fingerprint": row["tree_fingerprint"],
                "manifest_sha256": row["manifest_sha256"],
                "trees_present": row["trees_present"],
            }
            for row in fires
        ],
    }
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "fire_id",
        "on_disk_tif_count",
        "dated_scene_count",
        "usable_dated_scene_count",
        "on_disk_kmz_count",
        "aligned_tif_count",
        "mask_tif_count",
        "tree_fingerprint",
        "trees_present",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in payload["fires"]:
            writer.writerow(
                {
                    "fire_id": row["fire_id"],
                    "on_disk_tif_count": row["on_disk_tif_count"],
                    "dated_scene_count": row["dated_scene_count"],
                    "usable_dated_scene_count": row["usable_dated_scene_count"],
                    "on_disk_kmz_count": row["on_disk_kmz_count"],
                    "aligned_tif_count": row["aligned_tif_count"],
                    "mask_tif_count": row["mask_tif_count"],
                    "tree_fingerprint": row["tree_fingerprint"],
                    "trees_present": ";".join(row["trees_present"]),
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score on-disk IF material with fail-closed R1–R6 / H1–H7 (no retrain)."
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="Repo root (injectable for tests)")
    parser.add_argument("--anchors", type=Path, default=None, help="Path to infocam_anchors.json")
    parser.add_argument("--fire-id", action="append", dest="fire_ids", default=None)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-md", type=Path, default=None)
    parser.add_argument("--inventory-json", type=Path, default=None)
    parser.add_argument("--inventory-csv", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    anchors_path = (args.anchors or (root / "data" / "infocam_anchors.json")).resolve()
    explicit_out = any(
        path is not None
        for path in (args.out_json, args.out_md, args.inventory_json, args.inventory_csv)
    )
    subset_query = bool(args.fire_ids)
    write_ssot = (not subset_query) or explicit_out

    if not anchors_path.is_file():
        print(f"error: missing anchors file: {anchors_path}", file=sys.stderr)
        return 1

    try:
        doc = load_anchors(anchors_path)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    known = set(discover_fire_ids(root, doc["anchors"]))
    if args.fire_ids:
        unknown = [fid for fid in args.fire_ids if fid not in known]
        if unknown:
            print(
                f"error: unknown fire_id {unknown!r}. known: {', '.join(sorted(known))}",
                file=sys.stderr,
            )
            return 1
        selected = list(args.fire_ids)
    else:
        selected = None

    try:
        board = build_board(root=root, anchors_path=anchors_path, fire_ids=selected)
        _assert_fail_closed(board)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not write_ssot:
        print(json.dumps(board, indent=2, ensure_ascii=False))
        return 0

    if subset_query:
        out_json = args.out_json
        out_md = args.out_md
        inv_json = args.inventory_json
        inv_csv = args.inventory_csv
    else:
        out_json = args.out_json or (root / "docs" / "WEAKNESS_BOARD.json")
        out_md = args.out_md or (root / "docs" / "WEAKNESS_BOARD.md")
        inv_json = args.inventory_json or (root / "docs" / "IF_ONDISK_INVENTORY.json")
        inv_csv = args.inventory_csv or (root / "docs" / "IF_ONDISK_INVENTORY.csv")

    written: dict[str, str] = {}
    if out_json is not None:
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(board, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written["out_json"] = str(out_json)
    if out_md is not None:
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(board), encoding="utf-8")
        written["out_md"] = str(out_md)
    if inv_json is not None or inv_csv is not None:
        write_json = inv_json if inv_json is not None else inv_csv.with_suffix(".json")
        write_csv = inv_csv if inv_csv is not None else inv_json.with_suffix(".csv")
        write_inventory_sidecar(board, write_json, write_csv)
        written["inventory_json"] = str(write_json)
        written["inventory_csv"] = str(write_csv)

    print(
        json.dumps(
            {
                "ok": True,
                "schema": board["schema"],
                "n_fires": board["summary"]["n_fires"],
                "n_confirmed": board["summary"]["n_confirmed"],
                "n_ml_strong": board["summary"]["n_ml_strong"],
                **written,
                "anchors_written": False,
                "retrained": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
