"""Align multi-frame LWIR (+ masks) to a common local grid for training patches.

Drone LWIR frames are often independently georeferenced with different footprints.
A global union grid is usually unusable; this module:

1. Matches LWIR ↔ mask pairs
2. Builds consecutive temporal chains with sufficient spatial overlap
3. Warps each chain to a local common grid (intersection preferred, union fallback)
4. Auto-coarsens resolution if the grid would exceed a max side in pixels

Dual-product rails (W3 external align path — architecture, not ad-hoc)
----------------------------------------------------------------------
* **Lab ML** rail only (``clm_ensemble_v34`` prep). Not field_ops fusion.
* IoU ≠ ROS; ``ml_product_go`` never auto-flips; field fusion stays **OFF**.
* Multi-fire honesty first-class: W3 external fires are eval-only probes
  (report/gate with frozen thr/cal upstream); Tobarra = hard transfer.
* Does **not** use ``allow_unaligned_crop``. Does not retrain or retune thr/ECE.
* Rails payload reuses :mod:`wildfire_front.ml.protocol_rails` (same dual-product
  defaults as product facade / LOFO / reject surfaces).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final, Literal

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

from wildfire_front.ingestion.geotiff import TIFF_EXTENSIONS, _find_mask
from wildfire_front.ml.protocol_rails import (
    LAB_ML_BANNER,
    dual_product_rails_dict,
    multi_fire_honesty_dict,
)

GridMode = Literal["intersection", "union"]

_BANNER: Final = LAB_ML_BANNER
_SCHEMA: Final = "w3_align_fire_chains_v1"


def align_stack_rails() -> dict[str, Any]:
    """Canonical dual-product rails for W3 external-fire align manifests.

    Shared with product facade / protocol rails: fusion OFF, no ml_product_go
    auto-flip, IoU ≠ ROS. Site-specific: no ``allow_unaligned_crop``.
    """
    base = dual_product_rails_dict()
    base.update(
        {
            "banner": _BANNER,
            "product_rail": "lab_ml",
            "field_rail": "field_ops",
            "field_ops_ml_live_fusion": "OFF",
            "ml_product_go": True,
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "no_allow_unaligned_crop": True,
            "w3_external_align": True,
            "eval_only_prep": True,
            "thr_not_retuned_here": True,
            "no_ece_retune_same_holdout": True,
        }
    )
    return base


def align_multi_fire_honesty() -> dict[str, Any]:
    """First-class multi-fire honesty for align manifests (Tobarra hard, W3 external)."""
    mf = multi_fire_honesty_dict()
    return {
        **mf,
        "role": "w3_external_align_prep",
        "lab_only": True,
        "note": (
            "W3 external-fire align is lab prep for multi-fire honesty probes "
            "(frozen thr/cal eval-only upstream). Tobarra = hard; fusion OFF; "
            "no ml_product_go auto-flip."
        ),
    }


@dataclass(frozen=True)
class FrameRef:
    """One matched LWIR + mask frame with geographic bounds."""

    image_path: str
    mask_path: str
    left: float
    bottom: float
    right: float
    top: float
    width: int
    height: int
    res_m: float
    crs: str


@dataclass(frozen=True)
class CommonGrid:
    crs: str
    left: float
    bottom: float
    right: float
    top: float
    resolution_m: float
    width: int
    height: int
    mode: str


def list_tiffs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in TIFF_EXTENSIONS
    )


def overlap_ratio(a: FrameRef, b: FrameRef) -> float:
    """Intersection area / min(area_a, area_b)."""
    ix = max(0.0, min(a.right, b.right) - max(a.left, b.left))
    iy = max(0.0, min(a.top, b.top) - max(a.bottom, b.bottom))
    inter = ix * iy
    aa = max(0.0, (a.right - a.left) * (a.top - a.bottom))
    bb = max(0.0, (b.right - b.left) * (b.top - b.bottom))
    denom = min(aa, bb)
    return float(inter / denom) if denom > 0 else 0.0


def load_matched_frames(images_dir: Path, masks_dir: Path) -> list[FrameRef]:
    """Match LWIR frames to masks; skip unmatched."""
    frames: list[FrameRef] = []
    for img in list_tiffs(images_dir):
        mask = _find_mask(img, masks_dir)
        if mask is None or not mask.is_file():
            continue
        with rasterio.open(img) as src:
            if src.crs is None:
                continue
            b = src.bounds
            res = float((abs(src.transform.a) + abs(src.transform.e)) / 2.0)
            frames.append(
                FrameRef(
                    image_path=str(img.resolve()),
                    mask_path=str(mask.resolve()),
                    left=float(b.left),
                    bottom=float(b.bottom),
                    right=float(b.right),
                    top=float(b.top),
                    width=int(src.width),
                    height=int(src.height),
                    res_m=res if res > 0 else 0.5,
                    crs=str(src.crs),
                )
            )
    return frames


def consecutive_overlap_chains(
    frames: list[FrameRef],
    *,
    min_overlap: float = 0.4,
) -> list[list[int]]:
    """Split time-sorted frames into chains with consecutive spatial overlap."""
    if not frames:
        return []
    chains: list[list[int]] = [[0]]
    for i in range(1, len(frames)):
        if overlap_ratio(frames[i - 1], frames[i]) >= float(min_overlap):
            chains[-1].append(i)
        else:
            chains.append([i])
    return chains


def _extent(
    frames: list[FrameRef],
    mode: GridMode,
) -> tuple[float, float, float, float] | None:
    if not frames:
        return None
    if mode == "intersection":
        left = max(f.left for f in frames)
        bottom = max(f.bottom for f in frames)
        right = min(f.right for f in frames)
        top = min(f.top for f in frames)
        if right <= left or top <= bottom:
            return None
        return left, bottom, right, top
    left = min(f.left for f in frames)
    bottom = min(f.bottom for f in frames)
    right = max(f.right for f in frames)
    top = max(f.top for f in frames)
    if right <= left or top <= bottom:
        return None
    return left, bottom, right, top


def build_common_grid(
    frames: list[FrameRef],
    *,
    mode: GridMode = "intersection",
    resolution_m: float | None = None,
    max_side_px: int = 4096,
    min_side_m: float = 30.0,
) -> CommonGrid:
    """Build a common grid for a frame group; auto-coarsen if too large."""
    if not frames:
        raise ValueError("no frames for common grid")
    crs0 = frames[0].crs
    if any(f.crs != crs0 for f in frames):
        raise ValueError("mixed CRS in frame group — reproject to one CRS first")

    used_mode: str = mode
    ext = _extent(frames, mode)
    if ext is None and mode == "intersection":
        ext = _extent(frames, "union")
        used_mode = "union_fallback"
    if ext is None:
        raise ValueError("empty extent for frame group")

    left, bottom, right, top = ext
    width_m = right - left
    height_m = top - bottom
    if width_m < min_side_m or height_m < min_side_m:
        raise ValueError(
            f"common extent too small: {width_m:.1f}m x {height_m:.1f}m (need >= {min_side_m}m)"
        )

    res = (
        float(resolution_m)
        if resolution_m and resolution_m > 0
        else float(np.median([f.res_m for f in frames]))
    )
    if res <= 0:
        res = 0.5

    def dims(r: float) -> tuple[int, int]:
        w = max(1, int(math.ceil(width_m / r)))
        h = max(1, int(math.ceil(height_m / r)))
        return w, h

    w, h = dims(res)
    # Auto-coarsen until both sides fit max_side_px
    guard = 0
    while max(w, h) > int(max_side_px) and guard < 32:
        scale = max(w, h) / float(max_side_px)
        res = res * scale
        w, h = dims(res)
        guard += 1

    # Snap right/top to exact pixel grid
    right = left + w * res
    top = bottom + h * res
    return CommonGrid(
        crs=crs0,
        left=left,
        bottom=bottom,
        right=right,
        top=top,
        resolution_m=res,
        width=w,
        height=h,
        mode=used_mode,
    )


def _resampling(name: str) -> Resampling:
    try:
        return Resampling[name]
    except KeyError as exc:
        valid = ", ".join(item.name for item in Resampling)
        raise ValueError(f"unknown resampling '{name}'. Valid: {valid}") from exc


def warp_to_grid(
    source: Path,
    destination: Path,
    grid: CommonGrid,
    *,
    resampling: str = "bilinear",
    is_mask: bool = False,
    overwrite: bool = True,
) -> dict[str, Any]:
    """Warp one GeoTIFF onto ``grid``."""
    destination = Path(destination)
    if destination.exists() and not overwrite:
        return {"path": str(destination), "skipped_existing": True}

    destination.parent.mkdir(parents=True, exist_ok=True)
    rs = _resampling("nearest" if is_mask else resampling)
    dst_transform = from_bounds(
        grid.left, grid.bottom, grid.right, grid.top, grid.width, grid.height
    )

    with rasterio.open(source) as src:
        dtype = "uint8" if is_mask else src.dtypes[0]
        count = 1 if is_mask else src.count
        profile = src.profile.copy()
        profile.update(
            crs=grid.crs,
            transform=dst_transform,
            width=grid.width,
            height=grid.height,
            count=count,
            dtype=dtype,
        )
        nodata = 0 if is_mask else src.nodata
        if nodata is not None:
            profile["nodata"] = nodata

        with rasterio.open(destination, "w", **profile) as dst:
            for band in range(1, count + 1):
                dest = np.zeros((grid.height, grid.width), dtype=np.dtype(dtype))
                reproject(
                    source=rasterio.band(src, band),
                    destination=dest,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=grid.crs,
                    resampling=rs,
                    dst_nodata=0 if is_mask else (src.nodata if src.nodata is not None else 0),
                )
                if is_mask:
                    dest = (dest > 0).astype(np.uint8)
                dst.write(dest, band)

    return {
        "source": str(source),
        "destination": str(destination),
        "width": grid.width,
        "height": grid.height,
        "resolution_m": grid.resolution_m,
        "is_mask": is_mask,
    }


def align_chain_to_common_grid(
    frames: list[FrameRef],
    out_images: Path,
    out_masks: Path,
    *,
    mode: GridMode = "intersection",
    resolution_m: float | None = None,
    max_side_px: int = 4096,
    lwir_resampling: str = "bilinear",
    overwrite: bool = True,
) -> dict[str, Any]:
    """Align one chain of frames; write LWIR + masks on the same grid."""
    grid = build_common_grid(
        frames,
        mode=mode,
        resolution_m=resolution_m,
        max_side_px=max_side_px,
    )
    out_images = Path(out_images)
    out_masks = Path(out_masks)
    out_images.mkdir(parents=True, exist_ok=True)
    out_masks.mkdir(parents=True, exist_ok=True)

    written_img: list[dict[str, Any]] = []
    written_msk: list[dict[str, Any]] = []
    for fr in frames:
        img_src = Path(fr.image_path)
        msk_src = Path(fr.mask_path)
        img_dst = out_images / img_src.name
        # Keep mask naming discoverable via _find_mask (stem_mask or same name)
        if msk_src.name.startswith(img_src.stem):
            msk_name = msk_src.name
        else:
            msk_name = f"{img_src.stem}_mask.tif"
        msk_dst = out_masks / msk_name
        written_img.append(
            warp_to_grid(
                img_src,
                img_dst,
                grid,
                resampling=lwir_resampling,
                is_mask=False,
                overwrite=overwrite,
            )
        )
        written_msk.append(
            warp_to_grid(
                msk_src,
                msk_dst,
                grid,
                resampling="nearest",
                is_mask=True,
                overwrite=overwrite,
            )
        )

    return {
        "ok": True,
        "n_frames": len(frames),
        "grid": asdict(grid),
        "images_dir": str(out_images.resolve()),
        "masks_dir": str(out_masks.resolve()),
        "images": written_img,
        "masks": written_msk,
        # Verify alignment for WildfireDataset
        "aligned_shape": [grid.height, grid.width],
    }


def align_fire_chains(
    images_dir: Path,
    masks_dir: Path,
    out_root: Path,
    *,
    min_overlap: float = 0.4,
    min_chain_len: int = 2,
    mode: GridMode = "intersection",
    resolution_m: float | None = None,
    max_side_px: int = 4096,
    lwir_resampling: str = "bilinear",
    overwrite: bool = True,
    pair_fallback: bool = True,
) -> dict[str, Any]:
    """Align all viable chains for a fire; write under ``out_root/chains/chain_XX/``.

    When a long chain has empty intersection, falls back to sliding pairs if
    ``pair_fallback`` is True.
    """
    images_dir = Path(images_dir)
    masks_dir = Path(masks_dir)
    out_root = Path(out_root)
    frames = load_matched_frames(images_dir, masks_dir)
    if len(frames) < min_chain_len:
        return {
            "ok": False,
            "error": f"only {len(frames)} matched frames (need >= {min_chain_len})",
            "n_matched": len(frames),
            "chains": [],
            "banner": _BANNER,
            "rails": align_stack_rails(),
            "multi_fire_honesty": align_multi_fire_honesty(),
        }

    raw_chains = consecutive_overlap_chains(frames, min_overlap=min_overlap)
    work_units: list[list[int]] = []
    for ch in raw_chains:
        if len(ch) < min_chain_len:
            continue
        group = [frames[i] for i in ch]
        # Prefer full chain if extent works
        try:
            build_common_grid(group, mode=mode, resolution_m=resolution_m, max_side_px=max_side_px)
            work_units.append(ch)
        except ValueError:
            if pair_fallback and len(ch) >= 2:
                for j in range(len(ch) - 1):
                    work_units.append([ch[j], ch[j + 1]])
            # else drop

    # Deduplicate identical pair units
    seen: set[tuple[int, ...]] = set()
    unique_units: list[list[int]] = []
    for u in work_units:
        key = tuple(u)
        if key not in seen:
            seen.add(key)
            unique_units.append(u)

    chain_results: list[dict[str, Any]] = []
    for idx, unit in enumerate(unique_units):
        group = [frames[i] for i in unit]
        chain_dir = out_root / "chains" / f"chain_{idx:02d}"
        try:
            result = align_chain_to_common_grid(
                group,
                chain_dir / "lwir",
                chain_dir / "masks",
                mode=mode,
                resolution_m=resolution_m,
                max_side_px=max_side_px,
                lwir_resampling=lwir_resampling,
                overwrite=overwrite,
            )
            result["chain_id"] = f"chain_{idx:02d}"
            result["frame_indices"] = unit
            result["source_images"] = [frames[i].image_path for i in unit]
            chain_results.append(result)
        except Exception as exc:  # noqa: BLE001 — collect per-chain errors
            chain_results.append(
                {
                    "ok": False,
                    "chain_id": f"chain_{idx:02d}",
                    "frame_indices": unit,
                    "error": str(exc),
                }
            )

    ok_chains = [c for c in chain_results if c.get("ok")]
    rails = align_stack_rails()
    multi_fire = align_multi_fire_honesty()
    manifest = {
        "schema": _SCHEMA,
        "banner": _BANNER,
        "ok": len(ok_chains) > 0,
        "images_dir": str(images_dir.resolve()),
        "masks_dir": str(masks_dir.resolve()),
        "out_root": str(out_root.resolve()),
        "n_matched_frames": len(frames),
        "n_raw_chains": len(raw_chains),
        "raw_chain_lengths": [len(c) for c in raw_chains],
        "n_work_units": len(unique_units),
        "n_aligned_ok": len(ok_chains),
        "params": {
            "min_overlap": min_overlap,
            "min_chain_len": min_chain_len,
            "mode": mode,
            "resolution_m": resolution_m,
            "max_side_px": max_side_px,
            "pair_fallback": pair_fallback,
        },
        "chains": chain_results,
        # Dual-product rails: lab ML vs field_ops; fusion OFF; no go auto-flip.
        # Multi-fire honesty first-class (W3 external align prep).
        "rails": rails,
        "multi_fire_honesty": multi_fire,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "align_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def verify_dir_aligned(images_dir: Path, masks_dir: Path) -> dict[str, Any]:
    """Check that matched frames share identical shape + geotransform."""
    frames = load_matched_frames(images_dir, masks_dir)
    if not frames:
        return {"ok": False, "error": "no matched frames", "n": 0}
    shapes = {(f.height, f.width) for f in frames}
    # transform equality via re-open
    transforms: list[tuple[float, ...]] = []
    for f in frames:
        with rasterio.open(f.image_path) as src:
            t = src.transform
            transforms.append(
                (float(t.a), float(t.b), float(t.c), float(t.d), float(t.e), float(t.f))
            )
    t0 = transforms[0]
    t_ok = all(
        all(
            abs(a - b) <= 0.5 * max(abs(t0[0]), abs(t0[4]), 1e-9)
            for a, b in zip(t0, ti, strict=True)
        )
        for ti in transforms
    )
    return {
        "ok": len(shapes) == 1 and t_ok,
        "n": len(frames),
        "unique_shapes": [list(s) for s in shapes],
        "transform_aligned": t_ok,
    }
