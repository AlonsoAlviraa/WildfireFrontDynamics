#!/usr/bin/env python3
"""Adapt LATAM/AU CEMS packs toward NDWS holdout NPZ shape.

clm_ensemble_v34 expects NDWS 17-channel sequences (legacy17). Modes:

* partial_fill (default): burned mask +/- optional NBR; other channels zero.
  compatible_with_clm_ensemble_v34=false; model_iou stays null.
* real_proxy: real meteo/DEM/veg covariates via build_legacy17_channels
  (Open-Meteo + SRTM + S2 NBR). schema_mode=real_proxy_fill. Still NOT
  NDWS-native satellite stack; complete model IoU is a separate script.

Requires covariates from:
  python scripts/fill_latam_au_ndws_covariates.py --event-id ...

  python scripts/adapt_latam_au_to_ndws_patches.py --event-id AU_EMSR500_PERTH
  python scripts/adapt_latam_au_to_ndws_patches.py --mode real_proxy --event-id AU_EMSR500_PERTH
  python scripts/adapt_latam_au_to_ndws_patches.py --zero-shot-eval

Exit codes:
  0 -- adapt ok (or zero-shot honestly blocked with null IoU written)
  1 -- pack missing / no labels / hard fail
  2 -- usage
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

from wildfire_front.ml.feature_schema import (  # noqa: E402
    build_legacy17_channels,
    schema_channel_count,
    schema_channel_names,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    ANNUAL_EVAL_STATUS,
    EMSR_PACK_SPECS,
    WEAK_PACK_SPECS,
    is_annual_l1_spec,
    pack_dir_for,
    source_pack_ready,
)

ADAPT_SCHEMA = "wfd_latam_au_ndws_adapt_v1"
DEFAULT_OUT = ROOT / "artifacts" / "latam_au_ndws_adapt"
DEFAULT_OUT_REAL = ROOT / "artifacts" / "latam_au_ndws_adapt_real_proxy"
NDWS_SCHEMA = "legacy17"
N_CH = schema_channel_count(NDWS_SCHEMA)  # 17


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rel(path: Path) -> str:
    if path.is_relative_to(ROOT):
        return str(path.relative_to(ROOT)).replace("\\", "/")
    return str(path).replace("\\", "/")


def _load_mask(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        arr = np.asarray(ds.read(1))
    return (arr > 0).astype(np.float32)


def _load_nbr_optional(path: Path) -> np.ndarray | None:
    try:
        import rasterio
    except ImportError:
        return None
    if not path.is_file():
        return None
    with rasterio.open(path) as ds:
        arr = np.asarray(ds.read(1), dtype=np.float32)
    return arr


def _center_crop_or_pad(arr: np.ndarray, size: int) -> np.ndarray:
    h, w = arr.shape[-2], arr.shape[-1]
    if h == size and w == size:
        return arr.astype(np.float32, copy=False)
    out = np.zeros((size, size), dtype=np.float32)
    src_y0 = max(0, (h - size) // 2)
    src_x0 = max(0, (w - size) // 2)
    src_y1 = min(h, src_y0 + size)
    src_x1 = min(w, src_x0 + size)
    tile = arr[src_y0:src_y1, src_x0:src_x1]
    th, tw = tile.shape
    dy = (size - th) // 2
    dx = (size - tw) // 2
    out[dy : dy + th, dx : dx + tw] = tile
    return out


def _tile_starts(length: int, patch: int, stride: int) -> list[int]:
    if length <= patch:
        return [0]
    starts = list(range(0, length - patch + 1, stride))
    if starts[-1] != length - patch:
        starts.append(length - patch)
    return starts


def extract_mask_tiles(
    mask: np.ndarray,
    *,
    patch_size: int = 64,
    stride: int | None = None,
    max_patches: int = 48,
    min_pos_frac: float = 0.01,
) -> list[dict[str, Any]]:
    h, w = mask.shape
    stride = int(stride or patch_size)
    out: list[dict[str, Any]] = []
    for y in _tile_starts(h, patch_size, stride):
        for x in _tile_starts(w, patch_size, stride):
            if len(out) >= max_patches:
                return out
            tile = mask[y : y + patch_size, x : x + patch_size]
            if tile.shape != (patch_size, patch_size):
                tile = _center_crop_or_pad(tile, patch_size)
            pos = float((tile > 0).mean())
            if pos < min_pos_frac:
                continue
            out.append({"y": int(y), "x": int(x), "pos_frac": pos, "mask": tile})
    if not out:
        tile = _center_crop_or_pad(mask, patch_size)
        out.append(
            {
                "y": 0,
                "x": 0,
                "pos_frac": float((tile > 0).mean()),
                "mask": tile,
                "fallback": "center_crop",
            }
        )
    return out


def build_partial_sequence(
    mask_tile: np.ndarray,
    *,
    nbr_tile: np.ndarray | None = None,
    n_channels: int = N_CH,
) -> tuple[np.ndarray, dict[str, Any]]:
    """(1, C, H, W) with honest channel map (partial_fill)."""
    h, w = mask_tile.shape
    seq = np.zeros((1, n_channels, h, w), dtype=np.float32)
    filled: list[dict[str, Any]] = []
    seq[0, 0] = (mask_tile > 0).astype(np.float32)
    filled.append({"index": 0, "name": "burned_mask_proxy", "source": "cems_label", "fill": "data"})
    if nbr_tile is not None and nbr_tile.shape == (h, w):
        nbr = np.nan_to_num(nbr_tile.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        seq[0, 1] = nbr
        filled.append({"index": 1, "name": "s2_nbr_optional", "source": "s2_or_aligned", "fill": "data"})
        zero_from = 2
    else:
        zero_from = 1
    for i in range(zero_from, n_channels):
        filled.append(
            {
                "index": i,
                "name": f"legacy_{i}" if NDWS_SCHEMA == "legacy17" else f"ch_{i}",
                "source": "zero_fill",
                "fill": "zero",
            }
        )
    channel_map = {
        "schema_name": NDWS_SCHEMA,
        "n_channels": n_channels,
        "schema_mode": "partial_fill",
        "channels": filled,
        "schema_channel_names_reference": list(schema_channel_names(NDWS_SCHEMA)),
        "note": (
            "Only burned mask (+/- optional NBR) are real data; remaining channels "
            "are zero. Not a valid NDWS feature stack for transfer IoU."
        ),
    }
    return seq, channel_map


def _read_tif(path: Path) -> np.ndarray | None:
    if not path.is_file():
        return None
    try:
        import rasterio
    except ImportError:
        return None
    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1), dtype=np.float32)


def load_covariates_for_pack(source_pack: Path) -> dict[str, Any]:
    """Load real meteo/DEM/veg from pack/covariates if ready."""
    cov = source_pack / "covariates"
    prov_p = cov / "PROVENANCE.json"
    if not prov_p.is_file():
        return {"ok": False, "error": "missing_covariates_provenance"}
    try:
        prov = json.loads(prov_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"bad_provenance:{exc}"}
    ready = prov.get("channels_ready") or {}
    if not all(ready.get(k) for k in ("meteo", "dem", "veg")):
        return {
            "ok": False,
            "error": "covariates_not_ready",
            "channels_ready": ready,
            "hint": "run scripts/fill_latam_au_ndws_covariates.py",
        }
    elev = _read_tif(cov / "elevation_m.tif")
    temp = _read_tif(cov / "temperature_c.tif")
    hum = _read_tif(cov / "humidity_pct.tif")
    wind = _read_tif(cov / "wind_speed_ms.tif")
    wdir = _read_tif(cov / "wind_dir_deg.tif")
    precip = _read_tif(cov / "precip_mm.tif")
    veg = _read_tif(cov / "vegetation_proxy.tif")
    if any(x is None for x in (elev, temp, hum, wind, wdir, precip, veg)):
        return {"ok": False, "error": "covariate_tif_missing"}
    return {
        "ok": True,
        "elevation": elev,
        "temperature": temp,
        "humidity": hum,
        "wind_speed": wind,
        "wind_dir": wdir,
        "precip": precip,
        "veg": veg,
        "provenance": prov,
    }


def build_real_proxy_sequence(
    mask_tile: np.ndarray,
    cov_tile: dict[str, np.ndarray],
    *,
    n_channels: int = N_CH,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Build legacy17 channels from real meteo/DEM/veg (normalized)."""
    h, w = mask_tile.shape
    humidity = cov_tile["humidity"]
    erc = np.clip(100.0 - humidity, 0.0, 100.0).astype(np.float32)
    temp = cov_tile["temperature"]
    ch = build_legacy17_channels(
        elevation=cov_tile["elevation"],
        wind_dir=cov_tile["wind_dir"],
        wind_speed=cov_tile["wind_speed"],
        max_temp=temp + 3.0,
        min_temp=temp - 3.0,
        humidity=humidity,
        precip=cov_tile["precip"],
        veg=cov_tile["veg"],
        erc=erc,
    )
    if ch.shape != (n_channels, h, w):
        raise ValueError(f"channel shape {ch.shape} != ({n_channels},{h},{w})")
    seq = ch[np.newaxis, ...].astype(np.float32)
    channel_map = {
        "schema_name": NDWS_SCHEMA,
        "n_channels": n_channels,
        "schema_mode": "real_proxy_fill",
        "builder": "build_legacy17_channels",
        "sources": {
            "elevation": "covariates/elevation_m.tif (SRTM90 OpenTopoData)",
            "meteo": "covariates/* from Open-Meteo ERA5 period means",
            "veg": "covariates/vegetation_proxy.tif (S2 NBR to [0,1])",
            "erc": "proxy 100-humidity (not GRIDMET ERC)",
            "prev_fire_separate": "current_fire mask in NPZ, not in 17-ch",
        },
        "schema_channel_names_reference": list(schema_channel_names(NDWS_SCHEMA)),
        "note": (
            "Real proxy covariates (meteo/DEM/veg), not NDWS-native multi-band EO. "
            "Compatible shape for clm_ensemble_v34 input; distribution shift remains."
        ),
        "mask_pos_frac": float((mask_tile > 0).mean()),
    }
    return seq, channel_map


def _crop_cov_tile(
    full: np.ndarray,
    mask_shape: tuple[int, int],
    y: int,
    x: int,
    patch_size: int,
) -> np.ndarray:
    if full.shape != mask_shape:
        full_pad = np.zeros(mask_shape, dtype=np.float32)
        hh = min(full.shape[0], mask_shape[0])
        ww = min(full.shape[1], mask_shape[1])
        full_pad[:hh, :ww] = full[:hh, :ww]
        full = full_pad
    piece = full[y : y + patch_size, x : x + patch_size]
    if piece.shape != (patch_size, patch_size):
        piece = _center_crop_or_pad(piece, patch_size)
    return piece.astype(np.float32)


def adapt_pack(
    event_id: str,
    source_pack: Path,
    out_root: Path,
    *,
    patch_size: int = 64,
    max_patches: int = 48,
    prefer_aligned_eo: bool = True,
    mode: str = "partial_fill",
) -> dict[str, Any]:
    ready, reason = source_pack_ready(source_pack)
    if not ready:
        return {"event_id": event_id, "ok": False, "error": reason}

    if mode not in {"partial_fill", "real_proxy", "annual_scar_only"}:
        return {"event_id": event_id, "ok": False, "error": f"unknown_mode:{mode}"}

    cov_pack: dict[str, Any] | None = None
    if mode == "real_proxy":
        cov_pack = load_covariates_for_pack(source_pack)
        if not cov_pack.get("ok"):
            return {
                "event_id": event_id,
                "ok": False,
                "error": cov_pack.get("error") or "covariates_failed",
                "hint": cov_pack.get("hint") or "run scripts/fill_latam_au_ndws_covariates.py",
            }

    meta = json.loads((source_pack / "meta.json").read_text(encoding="utf-8"))
    label_tifs = [
        source_pack / rec["rel"]
        for rec in (meta.get("geotiffs") or [])
        if str(rec.get("role") or "").startswith("label_")
        and rec.get("rel")
        and (source_pack / rec["rel"]).is_file()
    ]
    if not label_tifs:
        labels_dir = source_pack / "labels"
        label_tifs = sorted(labels_dir.glob("*.tif")) if labels_dir.is_dir() else []
    if not label_tifs:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "no_label_tif_on_disk",
            "hint": "re-run materialize_latam_au_emsr_packs.py",
        }

    nbr_path: Path | None = None
    if prefer_aligned_eo:
        aligned = source_pack / "eo_aligned"
        if aligned.is_dir():
            cands = sorted(aligned.glob("*NBR*.tif")) + sorted(aligned.glob("*.tif"))
            if cands:
                nbr_path = cands[-1]
    if nbr_path is None:
        eo = source_pack / "eo"
        if eo.is_dir():
            cands = sorted(eo.glob("*NBR*.tif")) + sorted(eo.glob("*.tif"))
            if cands:
                nbr_path = cands[-1]

    pack_out = out_root / event_id
    patches_dir = pack_out / "patches"
    patches_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, Any]] = []
    channel_map_doc: dict[str, Any] | None = None
    schema_mode = "partial_fill"
    compatible = False

    for tif in label_tifs:
        mask = _load_mask(tif)
        nbr_full = _load_nbr_optional(nbr_path) if nbr_path else None
        if nbr_full is not None and nbr_full.shape != mask.shape:
            nbr_full = None
        tiles = extract_mask_tiles(mask, patch_size=patch_size, max_patches=max_patches)
        for i, tile in enumerate(tiles):
            m = tile["mask"]
            nbr_tile = None
            if nbr_full is not None:
                y, x = tile["y"], tile["x"]
                nbr_tile = nbr_full[y : y + patch_size, x : x + patch_size]
                if nbr_tile.shape != (patch_size, patch_size):
                    nbr_tile = _center_crop_or_pad(nbr_tile, patch_size)

            if mode == "real_proxy":
                assert cov_pack is not None
                y, x = tile["y"], tile["x"]
                cov_tile: dict[str, np.ndarray] = {}
                for key in (
                    "elevation",
                    "temperature",
                    "humidity",
                    "wind_speed",
                    "wind_dir",
                    "precip",
                    "veg",
                ):
                    cov_tile[key] = _crop_cov_tile(
                        cov_pack[key], mask.shape, y, x, patch_size
                    )
                seq, channel_map_doc = build_real_proxy_sequence(m, cov_tile)
                schema_mode = "real_proxy_fill"
                compatible = True
            elif mode == "annual_scar_only":
                seq, channel_map_doc = build_partial_sequence(m, nbr_tile=nbr_tile)
                channel_map_doc["schema_mode"] = "annual_scar_only"
                channel_map_doc["note"] = (
                    "Annual/seasonal L1 scar tiles. target_fire is identity. "
                    "Not an intra-event next-mask. eval next-mask IoU is refused."
                )
                schema_mode = "annual_scar_only"
                compatible = False
            else:
                seq, channel_map_doc = build_partial_sequence(m, nbr_tile=nbr_tile)
                schema_mode = "partial_fill"
                compatible = False

            current = (m > 0).astype(np.float32)
            target = current.copy()
            fname = f"{tif.stem}_ndws_p{i:03d}.npz"
            path = patches_dir / fname
            np.savez_compressed(
                path,
                sequence=seq,
                current_fire=current,
                target_fire=target,
                change_fraction=np.float32(0.0),
                source=np.asarray(f"latam_au_{event_id}"),
                schema_mode=np.asarray(schema_mode),
                compatible_with_clm_ensemble_v34=np.asarray(compatible),
                pos_frac=np.float32(tile["pos_frac"]),
                y=np.int32(tile["y"]),
                x=np.int32(tile["x"]),
            )
            written.append(
                {
                    "file": f"patches/{fname}",
                    "source_tif": _rel(tif) if tif.is_relative_to(ROOT) else str(tif.name),
                    "pos_frac": tile["pos_frac"],
                    "y": tile["y"],
                    "x": tile["x"],
                    "sequence_shape": list(seq.shape),
                    "nbr_used": nbr_tile is not None,
                    "schema_mode": schema_mode,
                }
            )

    if mode == "real_proxy":
        zs_status = "shape_compatible_real_proxy"
        zs_reason = (
            "schema_mode=real_proxy_fill with real meteo/DEM/veg via "
            "build_legacy17_channels. Shape-compatible with clm_ensemble_v34; "
            "still domain-shifted vs NDWS-native. Complete model IoU via "
            "scripts/run_latam_au_complete_model_iou.py."
        )
        train_reason = "real_proxy covariates present; FREEZE forbids retrain without owner gate"
        not_ndws = "not NDWS-native multi-band EO"
    elif mode == "annual_scar_only":
        zs_status = ANNUAL_EVAL_STATUS
        zs_reason = (
            "schema_mode=annual_scar_only. Annual L1 scars have no intra-event "
            "next-mask. eval_status=blocked_annual_not_event."
        )
        train_reason = "annual_scar_only is not a next-mask train set"
        not_ndws = "not intra-event next-mask"
    else:
        zs_status = "blocked_partial_fill"
        zs_reason = (
            "schema_mode=partial_fill; zero-filled NDWS channels are not real "
            "covariates. Refusing clm_ensemble_v34 inference to avoid invented IoU."
        )
        train_reason = "partial_fill zero channels; FREEZE: no retrain"
        not_ndws = "not full NDWS 17-ch"

    manifest = {
        "schema": ADAPT_SCHEMA,
        "as_of_utc": utc_now(),
        "event_id": event_id,
        "source_pack": _rel(source_pack),
        "ndws_schema": NDWS_SCHEMA,
        "schema_mode": schema_mode,
        "compatible_with_clm_ensemble_v34": compatible,
        "channel_map": channel_map_doc,
        "n_label_tif": len(label_tifs),
        "n_patches": len(written),
        "patch_size": patch_size,
        "patches": written,
        "nbr_source": (
            _rel(nbr_path)
            if nbr_path and nbr_path.is_relative_to(ROOT)
            else (str(nbr_path) if nbr_path else None)
        ),
        "zero_shot": {
            "status": zs_status,
            "eval_status": zs_status,
            "model_iou": None,
            "reason": zs_reason,
        },
        "not_claims": [
            "not transfer IoU (sealed harness required for that claim)",
            not_ndws,
            "not FREEZE lift",
            "not GO_Q complete",
            "not retrain",
            "target_fire is identity placeholder (not next-day label)",
        ],
        "train_ready": {
            "can_feed_clm_train": False,
            "reason": train_reason,
        },
    }
    man_path = pack_out / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {
        "event_id": event_id,
        "ok": True,
        "n_patches": len(written),
        "manifest": _rel(man_path),
        "schema_mode": schema_mode,
        "compatible_with_clm_ensemble_v34": compatible,
        "model_iou": None,
    }


def run_zero_shot_eval(adapt_rows: list[dict[str, Any]], out_root: Path) -> dict[str, Any]:
    """Null IoU here; complete path is run_latam_au_complete_model_iou.py."""
    any_compat = any(r.get("compatible_with_clm_ensemble_v34") is True for r in adapt_rows)
    any_real = any(r.get("schema_mode") == "real_proxy_fill" for r in adapt_rows)
    any_annual = any(r.get("schema_mode") == "annual_scar_only" for r in adapt_rows)
    if any_annual and not any_real:
        eval_status = ANNUAL_EVAL_STATUS
        reason = (
            "Next-mask IoU refused: pack is annual/seasonal L1 "
            f"({ANNUAL_EVAL_STATUS}). NPZ may exist; dynamics eval must not run."
        )
    elif any_compat and any_real:
        eval_status = "ready_for_complete_model_iou"
        reason = (
            "real_proxy_fill shape-compatible. Measure complete model IoU with "
            "scripts/run_latam_au_complete_model_iou.py (not invented here)."
        )
    elif any_compat:
        eval_status = "blocked_needs_sealed_harness"
        reason = (
            "Compatible flag set — model path not auto-invoked in this script; "
            "measure via sealed eval harness or complete IoU script."
        )
    else:
        eval_status = "blocked_partial_fill"
        reason = (
            "Would run clm_ensemble_v34 only when schema_mode is real_proxy_fill "
            "or full NDWS. Current adapt is partial_fill; model_iou stays null."
        )
    doc = {
        "schema": "wfd_latam_au_ndws_zero_shot_v1",
        "as_of_utc": utc_now(),
        "product_id": "clm_ensemble_v34",
        "compatible_with_clm_ensemble_v34": any_compat,
        "eval_status": eval_status,
        "model_iou": None,
        "n": 0,
        "packs": [
            {
                "event_id": r.get("event_id"),
                "ok": r.get("ok"),
                "compatible_with_clm_ensemble_v34": r.get("compatible_with_clm_ensemble_v34"),
                "schema_mode": r.get("schema_mode"),
                "model_iou": None,
                "n_patches": r.get("n_patches"),
            }
            for r in adapt_rows
        ],
        "reason": reason,
        "not_claims": ["not invented IoU", "not FREEZE lift", "not GO_Q complete"],
    }
    path = out_root / "zero_shot_eval.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    doc["path"] = _rel(path)
    return doc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LATAM/AU -> NDWS NPZ adapter")
    ap.add_argument("--event-id", action="append", dest="event_ids", default=None)
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument("--out-root", type=Path, default=None)
    ap.add_argument("--patch-size", type=int, default=64)
    ap.add_argument("--max-patches", type=int, default=48)
    ap.add_argument(
        "--zero-shot-eval",
        action="store_true",
        help="Write zero-shot status; model_iou null unless truly compatible",
    )
    ap.add_argument(
        "--mode",
        choices=("partial_fill", "real_proxy", "annual_scar_only"),
        default="partial_fill",
        help="partial_fill (zeros), real_proxy (meteo/DEM/veg), or annual_scar_only (L1)",
    )
    args = ap.parse_args(argv)

    out_root = Path(args.out_root) if args.out_root else (
        DEFAULT_OUT_REAL if args.mode == "real_proxy" else DEFAULT_OUT
    )

    catalog = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS, **ALL_PACK_SPECS}
    ids = list(args.event_ids) if args.event_ids else ["AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"]
    rows: list[dict[str, Any]] = []
    any_fail = False
    for eid in ids:
        if eid not in catalog:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        spec = catalog[eid]
        mode = str(args.mode)
        if is_annual_l1_spec(spec):
            mode = "annual_scar_only"
        src = pack_dir_for(Path(args.data_root), spec)
        ready, reason = source_pack_ready(src)
        if not ready:
            print(f"error: {eid}: {reason}", file=sys.stderr)
            rows.append({"event_id": eid, "ok": False, "error": reason, "model_iou": None})
            any_fail = True
            continue
        row = adapt_pack(
            eid,
            src,
            out_root,
            patch_size=int(args.patch_size),
            max_patches=int(args.max_patches),
            mode=mode,
        )
        rows.append(row)
        if not row.get("ok"):
            any_fail = True
            print(f"FAIL {eid}: {row.get('error')}", file=sys.stderr)
        else:
            print(
                f"OK {eid}: n_patches={row.get('n_patches')} "
                f"schema_mode={row.get('schema_mode')} "
                f"compatible={row.get('compatible_with_clm_ensemble_v34')}"
            )

    any_compat = any(r.get("compatible_with_clm_ensemble_v34") is True for r in rows)
    if any(r.get("schema_mode") == "annual_scar_only" for r in rows):
        schema_mode = "annual_scar_only"
    elif args.mode == "real_proxy":
        schema_mode = "real_proxy_fill"
    else:
        schema_mode = "partial_fill"
    summary = {
        "schema": ADAPT_SCHEMA,
        "as_of_utc": utc_now(),
        "ok": not any_fail,
        "compatible_with_clm_ensemble_v34": any_compat and args.mode == "real_proxy",
        "schema_mode": schema_mode,
        "mode": args.mode,
        "model_iou": None,
        "packs": rows,
    }
    out_root.mkdir(parents=True, exist_ok=True)
    sum_path = out_root / "adapt_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {sum_path}")

    if args.zero_shot_eval:
        zs = run_zero_shot_eval(rows, out_root)
        print(
            f"zero-shot: status={zs.get('eval_status')} model_iou={zs.get('model_iou')} "
            f"-> {zs.get('path')}"
        )
        summary["zero_shot"] = {
            "eval_status": zs.get("eval_status"),
            "model_iou": zs.get("model_iou"),
            "path": zs.get("path"),
        }
        sum_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    return 1 if any_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
