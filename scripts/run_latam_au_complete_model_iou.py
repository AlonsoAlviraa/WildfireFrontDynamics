#!/usr/bin/env python3
"""Complete (non-experimental) model IoU with real meteo/DEM/veg NDWS channels.

Requires:
  1) scripts/fill_latam_au_ndws_covariates.py  (meteo/DEM/veg on pack)
  2) models/clm_ensemble/weights_multi_if.pt
  3) Packs with >=2 successive CEMS labels (same grid)

Builds full legacy17 via build_legacy17_channels + prev_fire, runs clm UNet
in delta mode, measures IoU of predicted next mask vs next CEMS product.

Reported as complete_proxy_model_iou — NOT sealed transfer IoU / NOT GO_Q.

  python scripts/run_latam_au_complete_model_iou.py
  python scripts/run_latam_au_complete_model_iou.py --event-id AU_EMSR500_PERTH

Exit:
  0 -- measured
  1 -- missing weights / no packs measured
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
)
from wildfire_front.ml.unet_train import (  # noqa: E402
    UNetTrainConfig,
    build_model,
    model_forward,
    prepare_input,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    ANNUAL_EVAL_STATUS,
    EMSR_PACK_SPECS,
    WEAK_PACK_SPECS,
    classify_temporal_pair,
    hours_between,
    is_annual_l1_spec,
    label_records_from_meta,
    mean_usable_pair_ious,
    pack_dir_for,
)

N_CH = schema_channel_count("legacy17")
DEFAULT_OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model"
WEIGHTS = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
SCHEMA = "wfd_latam_au_complete_proxy_model_iou_v1"
PATCH = 64
# Frozen before inspecting LATAM pair-level Δ signs. Do not retune to flip MET.
OOD_GROWTH_THRESHOLD = 0.90
GROWTH_RING_CONNECTIVITY = 8
GROWTH_RING_MIN_NEIGHBORS = 1


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def binary_iou(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 1.0


def copy_safety_use_model(
    probability: np.ndarray,
    prev_fire: np.ndarray,
    min_mean_outside_prob: float | None,
) -> tuple[bool, float]:
    """Apply the target-blind lab gate and return its observable score."""
    outside = prev_fire < 0.5
    mean_outside = float(probability[outside].mean()) if outside.any() else 0.0
    return (
        min_mean_outside_prob is None or mean_outside >= min_mean_outside_prob,
        mean_outside,
    )


def fire_growth_ring(
    prev_fire: np.ndarray,
    *,
    connectivity: int = GROWTH_RING_CONNECTIVITY,
    min_fire_neighbors: int = GROWTH_RING_MIN_NEIGHBORS,
) -> np.ndarray:
    """Dilation ring of t0 fire. Defaults are the frozen a priori knobs."""
    prev = prev_fire >= 0.5
    h, w = prev.shape
    offsets = (
        ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
        if int(connectivity) == 8
        else ((-1, 0), (1, 0), (0, -1), (0, 1))
    )
    counts = np.zeros((h, w), dtype=np.int32)
    for dy, dx in offsets:
        ys = slice(max(0, dy), h + min(0, dy))
        xs = slice(max(0, dx), w + min(0, dx))
        counts[ys, xs] += prev[
            ys.start - dy : ys.stop - dy, xs.start - dx : xs.stop - dx
        ].astype(np.int32)
    return (~prev) & (counts >= int(min_fire_neighbors))


def decode_complete_proxy_pred(
    probability: np.ndarray,
    prev_fire: np.ndarray,
    *,
    architecture: str,
    target_mode: str,
    threshold: float,
    growth_threshold: float | None = None,
    require_growth_ring: bool = True,
) -> np.ndarray:
    """Target-blind mask decode. Never reads label_t1.

    Residual P(abs) is not calibrated on burned pixels out of domain (thresholding
    it extinguishes t0). Complete-proxy therefore never drops t0 fire and only
    accepts expansion on unburned pixels at ``growth_threshold``. The default
    ring prior rejects growth that is not 8-adjacent to t0 fire.
    """
    prev = prev_fire >= 0.5
    gthr = float(threshold if growth_threshold is None else growth_threshold)
    if architecture == "residual" or target_mode == "delta":
        cand = (~prev) & (probability >= gthr)
        if require_growth_ring:
            cand &= fire_growth_ring(prev_fire)
        return prev | cand
    return probability >= threshold


def load_mask(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        return (ds.read(1) > 0).astype(np.float32)


def cov_at_label(cov: dict[str, Any], label_name: str) -> dict[str, Any]:
    """Override constant meteo rasters with the nearest label-timestamp sample."""
    prov = cov.get("provenance") or {}
    rows = list(prov.get("meteo_by_label") or [])
    hit: dict[str, Any] | None = None
    for row in rows:
        if str(row.get("label") or "") == label_name:
            hit = row
            break
    if hit is None:
        return cov
    out = dict(cov)
    h, w = None, None
    for key in ("temperature", "humidity", "wind_speed", "wind_dir", "precip"):
        arr = cov.get(key)
        if isinstance(arr, np.ndarray) and arr.ndim == 2:
            h, w = arr.shape
            break
    if h is None or w is None:
        return cov
    mapping = {
        "temperature": hit.get("temperature_c"),
        "humidity": hit.get("humidity_pct"),
        "wind_speed": hit.get("wind_speed_ms"),
        "wind_dir": hit.get("wind_dir_deg"),
        "precip": hit.get("precip_mm"),
    }
    for key, val in mapping.items():
        if val is None or key not in cov:
            continue
        out[key] = np.full((h, w), float(val), dtype=np.float32)
    out["meteo_sample_at"] = hit.get("sample_at")
    out["meteo_label"] = label_name
    return out


def load_cov(pack: Path) -> dict[str, Any] | None:
    cov = pack / "covariates"
    prov = cov / "PROVENANCE.json"
    if not prov.is_file():
        return None
    try:
        doc = json.loads(prov.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ready = doc.get("channels_ready") or {}
    if not all(ready.get(k) for k in ("meteo", "dem", "veg")):
        return None
    import rasterio

    def _r(name: str) -> np.ndarray:
        with rasterio.open(cov / name) as ds:
            return np.asarray(ds.read(1), dtype=np.float32)

    try:
        return {
            "elevation": _r("elevation_m.tif"),
            "temperature": _r("temperature_c.tif"),
            "humidity": _r("humidity_pct.tif"),
            "wind_speed": _r("wind_speed_ms.tif"),
            "wind_dir": _r("wind_dir_deg.tif"),
            "precip": _r("precip_mm.tif"),
            "veg": _r("vegetation_proxy.tif"),
            "provenance": doc,
        }
    except Exception:  # noqa: BLE001
        return None


def crop(arr: np.ndarray, y: int, x: int, size: int = PATCH) -> np.ndarray | None:
    h, w = arr.shape[-2], arr.shape[-1]
    if y + size > h or x + size > w:
        return None
    return arr[y : y + size, x : x + size].astype(np.float32)


def _tile_bucket(tile: np.ndarray) -> str:
    pos = float(tile.mean())
    if pos < 0.12:
        return "low_density"
    # edge: mixed burned/unburned
    if 0.12 <= pos <= 0.85:
        return "edge"
    return "interior"


def stratified_tiles(
    mask: np.ndarray,
    max_n: int = 32,
    min_pos: float = 0.02,
    patch: int = PATCH,
) -> list[tuple[int, int, np.ndarray, str]]:
    """Stratify edge / interior / low-density instead of first-N scanline tiles."""
    h, w = mask.shape
    if h < 1 or w < 1:
        return []
    step = max(1, patch // 2)
    y_stop = max(1, h - patch + 1)
    x_stop = max(1, w - patch + 1)
    buckets: dict[str, list[tuple[int, int, np.ndarray, str]]] = {
        "edge": [],
        "interior": [],
        "low_density": [],
    }
    for y in range(0, y_stop, step):
        for x in range(0, x_stop, step):
            if y + patch > h or x + patch > w:
                continue
            t = mask[y : y + patch, x : x + patch]
            pos = float(t.mean())
            if pos < min_pos:
                continue
            kind = _tile_bucket(t)
            buckets[kind].append((y, x, t, kind))
    names = ("edge", "interior", "low_density")
    per = max(1, max_n // len(names))
    out: list[tuple[int, int, np.ndarray, str]] = []
    leftover: list[tuple[int, int, np.ndarray, str]] = []
    for name in names:
        pool = buckets[name]
        take = pool[:per]
        out.extend(take)
        leftover.extend(pool[per:])
    if len(out) < max_n:
        out.extend(leftover[: max_n - len(out)])
    if not out:
        y = max(0, (h - patch) // 2)
        x = max(0, (w - patch) // 2)
        t = np.zeros((patch, patch), np.float32)
        yy = min(patch, max(0, h - y))
        xx = min(patch, max(0, w - x))
        if yy > 0 and xx > 0:
            t[:yy, :xx] = mask[y : y + yy, x : x + xx]
        out.append((y, x, t, "fallback_center"))
    return out[:max_n]


def tiles(mask: np.ndarray, max_n: int = 32, min_pos: float = 0.02) -> list[tuple[int, int, np.ndarray]]:
    return [(y, x, t) for y, x, t, _k in stratified_tiles(mask, max_n=max_n, min_pos=min_pos)]


def build_seq_tile(cov: dict[str, np.ndarray], y: int, x: int) -> np.ndarray | None:
    keys = (
        "elevation",
        "temperature",
        "humidity",
        "wind_speed",
        "wind_dir",
        "precip",
        "veg",
    )
    parts: dict[str, np.ndarray] = {}
    for k in keys:
        piece = crop(cov[k], y, x)
        if piece is None:
            return None
        parts[k] = piece
    humidity = parts["humidity"]
    erc = np.clip(100.0 - humidity, 0.0, 100.0).astype(np.float32)
    temp = parts["temperature"]
    ch = build_legacy17_channels(
        elevation=parts["elevation"],
        wind_dir=parts["wind_dir"],
        wind_speed=parts["wind_speed"],
        max_temp=temp + 3.0,
        min_temp=temp - 3.0,
        humidity=humidity,
        precip=parts["precip"],
        veg=parts["veg"],
        erc=erc,
    )
    # (1, T=1, C, H, W)
    return ch[np.newaxis, np.newaxis, ...].astype(np.float32)


def eval_pack(
    event_id: str,
    pack: Path,
    model,
    device,
    *,
    thr: float = 0.5,
    max_patches: int = 32,
    architecture: str = "residual",
    target_mode: str = "delta",
    copy_safety_min_mean_outside_prob: float | None = None,
    growth_threshold: float | None = None,
    require_growth_ring: bool = True,
    keep_t0: bool = False,
    cov: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if cov is None:
        cov = load_cov(pack)
    if cov is None:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "covariates_not_ready",
            "hint": "run scripts/fill_latam_au_ndws_covariates.py",
            "complete_proxy_model_iou": None,
        }
    spec = ALL_PACK_SPECS.get(event_id) or EMSR_PACK_SPECS.get(event_id) or {}
    if is_annual_l1_spec(spec):
        return {
            "event_id": event_id,
            "ok": False,
            "eval_status": ANNUAL_EVAL_STATUS,
            "error": ANNUAL_EVAL_STATUS,
            "complete_proxy_model_iou": None,
            "n_pairs_used": 0,
            "pairs": [],
        }

    meta_p = pack / "meta.json"
    if not meta_p.is_file():
        return {
            "event_id": event_id,
            "ok": False,
            "error": "missing_meta",
            "complete_proxy_model_iou": None,
            "n_pairs_used": 0,
        }
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    label_recs = label_records_from_meta(pack, meta)
    if len(label_recs) < 2:
        disk = sorted((pack / "labels").glob("*.tif"))
        label_recs = [
            {"path": p, "name": p.name, "delivery_utc": None, "dt": None, "rel": f"labels/{p.name}"}
            for p in disk
        ]
    if len(label_recs) < 2:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "need_ge2_labels",
            "complete_proxy_model_iou": None,
            "n_pairs_used": 0,
        }

    import torch

    pair_rows: list[dict[str, Any]] = []
    for i in range(1, len(label_recs)):
        prev_rec, next_rec = label_recs[i - 1], label_recs[i]
        prev_m = load_mask(Path(prev_rec["path"]))
        next_m = load_mask(Path(next_rec["path"]))
        if prev_m.shape != next_m.shape:
            pair_rows.append(
                {
                    "from": prev_rec.get("name"),
                    "to": next_rec.get("name"),
                    "pair_class": "label_shape_mismatch",
                    "delta_hours": None,
                    "label_mask_iou": None,
                    "complete_proxy_model_iou": None,
                    "n_tiles": 0,
                }
            )
            continue
        delta = None
        if prev_rec.get("dt") is not None and next_rec.get("dt") is not None:
            delta = hours_between(prev_rec["dt"], next_rec["dt"])
        label_iou = binary_iou(prev_m > 0, next_m > 0)
        pair_class = classify_temporal_pair(
            delta_hours=delta,
            label_mask_iou=label_iou,
            prev_kind=prev_rec.get("kind"),
            next_kind=next_rec.get("kind"),
        )
        row: dict[str, Any] = {
            "from": prev_rec.get("name"),
            "to": next_rec.get("name"),
            "from_kind": prev_rec.get("kind"),
            "to_kind": next_rec.get("kind"),
            "from_utc": prev_rec.get("delivery_utc"),
            "to_utc": next_rec.get("delivery_utc"),
            "delta_hours": delta,
            "label_mask_iou": label_iou,
            "copy_mask_iou": label_iou,
            "pair_class": pair_class,
            "complete_proxy_model_iou": None,
            "n_tiles": 0,
        }
        if pair_class != "usable":
            pair_rows.append(row)
            continue
        pair_cov = cov_at_label(cov, str(prev_rec.get("name") or ""))
        ious: list[float] = []
        copy_ious: list[float] = []
        strata: list[str] = []
        model_tiles = 0
        copy_fallback_tiles = 0
        gate_scores: list[float] = []
        for y, x, prev_t, kind in stratified_tiles(prev_m, max_n=max_patches):
            tgt = crop(next_m, y, x)
            if tgt is None:
                continue
            seq = build_seq_tile(pair_cov, y, x)
            if seq is None:
                continue
            seq_t = torch.from_numpy(seq)
            cur_t = torch.from_numpy(prev_t[np.newaxis, ...].astype(np.float32))
            x_in = prepare_input(seq_t, cur_t).to(device)
            with torch.no_grad():
                logits = model_forward(model, x_in, cur_t.to(device), architecture)
                probability = torch.sigmoid(logits)[0, 0].cpu().numpy()
            use_model, mean_outside = copy_safety_use_model(
                probability, prev_t, copy_safety_min_mean_outside_prob
            )
            gate_scores.append(mean_outside)
            if use_model:
                pred_mask = decode_complete_proxy_pred(
                    probability,
                    prev_t,
                    architecture=architecture,
                    target_mode=target_mode,
                    threshold=thr,
                    growth_threshold=growth_threshold,
                    require_growth_ring=require_growth_ring,
                )
                if keep_t0:
                    pred_mask = (prev_t >= 0.5) | pred_mask
                model_tiles += 1
            else:
                pred_mask = prev_t >= 0.5
                copy_fallback_tiles += 1
            ious.append(binary_iou(pred_mask, tgt > 0.5))
            copy_ious.append(binary_iou(prev_t >= 0.5, tgt > 0.5))
            strata.append(kind)
        if ious:
            row["complete_proxy_model_iou"] = float(np.mean(ious))
            row["copy_mask_iou"] = float(np.mean(copy_ious)) if copy_ious else label_iou
            row["delta_vs_copy"] = float(row["complete_proxy_model_iou"] - row["copy_mask_iou"])
            row["n_tiles"] = len(ious)
            row["tile_strata"] = {
                k: strata.count(k) for k in ("edge", "interior", "low_density", "fallback_center")
            }
            row["copy_safety_gate"] = {
                "enabled": copy_safety_min_mean_outside_prob is not None,
                "feature": "mean_growth_probability_outside_t0",
                "min_feature": copy_safety_min_mean_outside_prob,
                "n_model_tiles": model_tiles,
                "n_copy_fallback_tiles": copy_fallback_tiles,
                "score_min": min(gate_scores),
                "score_max": max(gate_scores),
            }
        else:
            row["pair_class"] = "no_valid_tiles"
        pair_rows.append(row)

    used = [
        p
        for p in pair_rows
        if p.get("pair_class") == "usable"
        and p.get("complete_proxy_model_iou") is not None
    ]
    mean_iou = mean_usable_pair_ious(pair_rows)
    mean_copy_iou = (
        float(np.mean([float(p["copy_mask_iou"]) for p in used])) if used else None
    )
    return {
        "event_id": event_id,
        "ok": True,
        "n_pairs": len(pair_rows),
        "n_pairs_used": len(used),
        "pairs": pair_rows,
        "delta_hours": [p.get("delta_hours") for p in pair_rows],
        "label_mask_iou": [p.get("label_mask_iou") for p in pair_rows],
        "complete_proxy_model_iou": mean_iou,
        "copy_baseline_iou": mean_copy_iou,
        "delta_vs_copy": (
            float(mean_iou - mean_copy_iou)
            if mean_iou is not None and mean_copy_iou is not None
            else None
        ),
        "excluded": [
            {
                "from": p.get("from"),
                "to": p.get("to"),
                "pair_class": p.get("pair_class"),
                "delta_hours": p.get("delta_hours"),
                "label_mask_iou": p.get("label_mask_iou"),
            }
            for p in pair_rows
            if p.get("pair_class") != "usable"
        ],
        "schema_mode": "real_proxy_fill",
        "compatible_with_clm_ensemble_v34": True,
        "threshold": thr,
        "in_channels": N_CH + 1,
        "architecture": architecture,
        "target_mode": target_mode,
        "copy_safety_min_mean_outside_prob": copy_safety_min_mean_outside_prob,
        "growth_threshold": growth_threshold,
        "require_growth_ring": require_growth_ring,
        "not_claims": [
            "not sealed transfer IoU",
            "not GO_Q complete",
            "not FREEZE lift",
            "not NDWS-native stack",
            "meteo is Open-Meteo point field (see covariates provenance)",
            "mean excludes too_short_delta (<12h) and static_label_copy (mask IoU>0.98)",
        ],
    }


DEFAULT_EVENT_IDS = (
    "AU_EMSR500_PERTH",
    "CL_EMSR647_NACIMIENTO",
    "AU_EMSR408_NSW",
    "CL_EMSR715_VALPARAISO",
)


def iter_usable_eval_tiles(
    data_root: Path,
    *,
    max_patches: int = 32,
    event_ids: tuple[str, ...] | list[str] = DEFAULT_EVENT_IDS,
) -> list[dict[str, Any]]:
    """Same usable tiles as ``eval_pack`` (32 stratified 64px). Target-blind coords."""
    tiles: list[dict[str, Any]] = []
    known = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS}
    for event_id in event_ids:
        spec = known.get(event_id) or {}
        pack = pack_dir_for(data_root, spec)
        cov = load_cov(pack)
        if cov is None:
            continue
        meta_p = pack / "meta.json"
        if not meta_p.is_file():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        label_recs = label_records_from_meta(pack, meta)
        if len(label_recs) < 2:
            continue
        for i in range(1, len(label_recs)):
            prev_rec, next_rec = label_recs[i - 1], label_recs[i]
            prev_m = load_mask(Path(prev_rec["path"]))
            next_m = load_mask(Path(next_rec["path"]))
            if prev_m.shape != next_m.shape:
                continue
            delta = None
            if prev_rec.get("dt") is not None and next_rec.get("dt") is not None:
                delta = hours_between(prev_rec["dt"], next_rec["dt"])
            label_iou = binary_iou(prev_m > 0, next_m > 0)
            pair_class = classify_temporal_pair(
                delta_hours=delta,
                label_mask_iou=label_iou,
                prev_kind=prev_rec.get("kind"),
                next_kind=next_rec.get("kind"),
            )
            if pair_class != "usable":
                continue
            pair_cov = cov_at_label(cov, str(prev_rec.get("name") or ""))
            for y, x, prev_t, kind in stratified_tiles(prev_m, max_n=max_patches):
                tgt = crop(next_m, y, x)
                seq = build_seq_tile(pair_cov, y, x)
                if tgt is None or seq is None:
                    continue
                tiles.append(
                    {
                        "event_id": event_id,
                        "from": prev_rec.get("name"),
                        "to": next_rec.get("name"),
                        "y": int(y),
                        "x": int(x),
                        "kind": kind,
                        "prev": prev_t.astype(np.float32),
                        "target": tgt.astype(np.float32),
                        "seq": seq.astype(np.float32),
                    }
                )
    return tiles


def oracle_frozen_decode_mask(prev: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Best mask frozen decode can emit: keep t0, add only true 8-ring growth."""
    prev_b = prev >= 0.5
    tgt_b = target >= 0.5
    return prev_b | (fire_growth_ring(prev) & tgt_b)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Complete proxy model IoU on real_proxy NDWS")
    ap.add_argument("--event-id", action="append", dest="event_ids", default=None)
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--weights", type=Path, default=WEIGHTS)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--max-patches", type=int, default=32)
    ap.add_argument("--architecture", choices=("standard", "residual"), default="residual")
    ap.add_argument("--target-mode", choices=("absolute", "delta"), default="delta")
    ap.add_argument(
        "--growth-thr",
        type=float,
        default=OOD_GROWTH_THRESHOLD,
        help=(
            "Target-blind threshold for unburned pixels (a priori OOD conservative "
            f"default {OOD_GROWTH_THRESHOLD}). Not fit on scored LATAM pairs."
        ),
    )
    ap.add_argument(
        "--no-growth-ring",
        action="store_true",
        help="Disable the a priori 8-connected t0 growth-ring prior.",
    )
    ap.add_argument("--model-label", default=None)
    ap.add_argument(
        "--copy-safety-min-mean-outside-prob",
        type=float,
        default=None,
        help=(
            "Lab-only abstention gate: use model for a tile only when mean growth "
            "probability outside t0 is at least this value; otherwise use copy."
        ),
    )
    args = ap.parse_args(argv)

    if not Path(args.weights).is_file():
        print(
            f"error: missing weights {args.weights} — refusing invented complete_proxy IoU",
            file=sys.stderr,
        )
        return 1

    import torch

    device = torch.device("cpu")
    cfg = UNetTrainConfig(
        architecture=str(args.architecture),
        model="small",
        target_mode=str(args.target_mode),
    )
    model = build_model(cfg, in_channels=N_CH + 1)
    state = torch.load(Path(args.weights), map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()

    known = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS}
    ids = list(args.event_ids) if args.event_ids else list(DEFAULT_EVENT_IDS)
    rows: list[dict[str, Any]] = []
    all_ious: list[float] = []
    all_copy_ious: list[float] = []
    all_pair_ious: list[float] = []
    all_pair_copy_ious: list[float] = []
    for eid in ids:
        if eid not in known:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        spec = known[eid]
        pack = pack_dir_for(Path(args.data_root), spec)
        row = eval_pack(
            eid,
            pack,
            model,
            device,
            thr=float(args.thr),
            max_patches=int(args.max_patches),
            architecture=str(args.architecture),
            target_mode=str(args.target_mode),
            copy_safety_min_mean_outside_prob=args.copy_safety_min_mean_outside_prob,
            growth_threshold=float(args.growth_thr),
            require_growth_ring=not bool(args.no_growth_ring),
        )
        rows.append(row)
        if row.get("complete_proxy_model_iou") is not None and int(row.get("n_pairs_used") or 0) > 0:
            all_ious.append(float(row["complete_proxy_model_iou"]))
            all_copy_ious.append(float(row["copy_baseline_iou"]))
        for pair in row.get("pairs") or []:
            if pair.get("pair_class") != "usable":
                continue
            if pair.get("complete_proxy_model_iou") is None:
                continue
            all_pair_ious.append(float(pair["complete_proxy_model_iou"]))
            all_pair_copy_ious.append(float(pair["copy_mask_iou"]))
        print(
            f"{eid}: ok={row.get('ok')} n_pairs_used={row.get('n_pairs_used')} "
            f"complete_proxy_model_iou={row.get('complete_proxy_model_iou')} "
            f"eval_status={row.get('eval_status')}"
        )

    summary = {
        "schema": SCHEMA,
        "as_of_utc": utc_now(),
        "product_id": args.model_label or "clm_ensemble_weights_multi_if_complete_proxy",
        "weights": str(Path(args.weights).resolve().relative_to(ROOT)).replace("\\", "/")
        if Path(args.weights).resolve().is_relative_to(ROOT)
        else str(args.weights),
        "schema_mode": "real_proxy_fill",
        "architecture": str(args.architecture),
        "target_mode": str(args.target_mode),
        "copy_safety_gate": {
            "enabled": args.copy_safety_min_mean_outside_prob is not None,
            "feature": "mean_growth_probability_outside_t0",
            "min_feature": args.copy_safety_min_mean_outside_prob,
            "lab_only": True,
        },
        "growth_threshold": float(args.growth_thr),
        "require_growth_ring": not bool(args.no_growth_ring),
        "mean_complete_proxy_model_iou": (
            float(np.mean(all_pair_ious)) if all_pair_ious else None
        ),
        "mean_copy_baseline_iou": (
            float(np.mean(all_pair_copy_ious)) if all_pair_copy_ious else None
        ),
        "mean_delta_vs_copy": (
            float(np.mean(all_pair_ious) - np.mean(all_pair_copy_ious))
            if all_pair_ious and all_pair_copy_ious
            else None
        ),
        "pack_macro_complete_proxy_model_iou": float(np.mean(all_ious)) if all_ious else None,
        "pack_macro_copy_baseline_iou": float(np.mean(all_copy_ious)) if all_copy_ious else None,
        "pair_macro_complete_proxy_model_iou": (
            float(np.mean(all_pair_ious)) if all_pair_ious else None
        ),
        "pair_macro_copy_baseline_iou": (
            float(np.mean(all_pair_copy_ious)) if all_pair_copy_ious else None
        ),
        "pair_macro_delta_vs_copy": (
            float(np.mean(all_pair_ious) - np.mean(all_pair_copy_ious))
            if all_pair_ious and all_pair_copy_ious
            else None
        ),
        "n_pairs_used": len(all_pair_ious),
        "n_pairs_measured": len(all_pair_ious),
        "n_pairs_beating_copy": sum(
            model_iou > copy_iou
            for model_iou, copy_iou in zip(
                all_pair_ious, all_pair_copy_ious, strict=True
            )
        ),
        "n_packs_measured": len(all_ious),
        "pair_protocol": {
            "min_delta_hours": 12.0,
            "static_label_copy_iou_gt": 0.98,
            "growth_product_kinds": ["delineation", "delineation_monitoring"],
            "excluded_classes": [
                "too_short_delta",
                "static_label_copy",
                "incompatible_product_kind",
            ],
            "emsr715_fep_to_del_reintroduced": False,
        },
        "packs": rows,
        "not_claims": [
            "not sealed transfer IoU",
            "not experimental_partial_fill_model_iou",
            "not GO_Q complete",
            "not FREEZE lift",
            "not NDWS-native stack",
        ],
        "rails": {
            "go_q": "partial",
            "freeze_intact": True,
            "no_retrain": Path(args.weights).resolve() == WEIGHTS.resolve(),
            "model_label": args.model_label,
        },
    }
    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    path = out_root / "complete_proxy_model_iou.json"
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("wrote", path, "mean=", summary["mean_complete_proxy_model_iou"])
    return 0 if all_ious else 1


if __name__ == "__main__":
    raise SystemExit(main())
