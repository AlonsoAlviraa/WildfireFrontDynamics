from __future__ import annotations
import json, sys
from datetime import datetime, UTC
from pathlib import Path
import numpy as np
import torch
import rasterio
from rasterio.warp import reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.ml.feature_schema import schema_channel_count
from wildfire_front.ml.unet_train import UNetTrainConfig, build_model, prepare_input
from wildfire_front.open_if.latam_au import (
    EMSR_PACK_SPECS,
    classify_temporal_pair,
    hours_between,
    label_records_from_meta,
    mean_usable_pair_ious,
    pack_dir_for,
    parse_iso_utc,
)

N_CH = schema_channel_count("legacy17")
OUT = ROOT / "outputs" / "ml_eval" / "latam_au_experimental_iou"
EVENTS = ["AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"]
WEIGHTS = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
PATCH = 64


def utc():
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_mask(p: Path):
    with rasterio.open(p) as ds:
        return (ds.read(1) > 0).astype(np.float32), ds.transform, ds.crs


def load_aligned_nbr(pack: Path, ref_shape, ref_transform, ref_crs):
    aligned = pack / "eo_aligned"
    if not aligned.is_dir():
        return None
    cands = sorted(aligned.glob("*NBR*.tif")) or sorted(aligned.glob("*.tif"))
    if not cands:
        return None
    with rasterio.open(cands[-1]) as src:
        dst = np.zeros(ref_shape, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear,
        )
    return np.nan_to_num(dst, nan=0.0)


def tiles(mask, max_n=32, min_pos=0.02):
    h, w = mask.shape
    out = []
    step = max(1, PATCH // 2)
    for y in range(0, max(1, h - PATCH + 1), step):
        for x in range(0, max(1, w - PATCH + 1), step):
            if len(out) >= max_n:
                return out
            if y + PATCH > h or x + PATCH > w:
                continue
            t = mask[y : y + PATCH, x : x + PATCH]
            if float(t.mean()) < min_pos:
                continue
            out.append((y, x, t))
    if not out:
        y = max(0, (h - PATCH) // 2)
        x = max(0, (w - PATCH) // 2)
        t = np.zeros((PATCH, PATCH), np.float32)
        yy = min(PATCH, h - y)
        xx = min(PATCH, w - x)
        t[:yy, :xx] = mask[y : y + yy, x : x + xx]
        out.append((y, x, t))
    return out


def iou(a, b):
    a = a.astype(bool)
    b = b.astype(bool)
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 1.0


def main():
    if not WEIGHTS.is_file():
        print("error: missing weights", WEIGHTS)
        return 1
    device = torch.device("cpu")
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    # prepare_input: T*C + 1 fire = 17 + 1 = 18
    model = build_model(cfg, in_channels=N_CH + 1)
    state = torch.load(WEIGHTS, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()

    pack_rows = []
    all_ious = []
    for eid in EVENTS:
        pack = pack_dir_for(ROOT / "data/open_if/latam_au", EMSR_PACK_SPECS[eid])
        meta_p = pack / "meta.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.is_file() else {}
        recs = label_records_from_meta(pack, meta) if meta else []
        if len(recs) < 2:
            labels = sorted((pack / "labels").glob("*.tif"))
            recs = [{"path": p, "name": p.name, "dt": None, "delivery_utc": None} for p in labels]
        if len(recs) < 2:
            pack_rows.append({"event_id": eid, "ok": False, "error": "need_ge2_labels"})
            continue
        # First *usable* pair only; too_short / static reported separately
        chosen = None
        excluded = []
        for i in range(1, len(recs)):
            a, b = recs[i - 1], recs[i]
            prev_m, transform, crs = load_mask(Path(a["path"]))
            next_m, _, _ = load_mask(Path(b["path"]))
            if prev_m.shape != next_m.shape:
                continue
            delta = (
                hours_between(a["dt"], b["dt"])
                if a.get("dt") is not None and b.get("dt") is not None
                else None
            )
            lab_iou = iou(prev_m > 0, next_m > 0)
            klass = classify_temporal_pair(
                delta_hours=delta,
                label_mask_iou=lab_iou,
                prev_kind=a.get("kind"),
                next_kind=b.get("kind"),
            )
            info = {
                "from": a.get("name"),
                "to": b.get("name"),
                "delta_hours": delta,
                "label_mask_iou": lab_iou,
                "pair_class": klass,
            }
            if klass != "usable":
                excluded.append(info)
                continue
            chosen = (a, b, prev_m, next_m, transform, crs, info)
            break
        if chosen is None:
            pack_rows.append(
                {
                    "event_id": eid,
                    "ok": True,
                    "n_pairs_used": 0,
                    "experimental_partial_fill_model_iou": None,
                    "excluded": excluded,
                    "note": "no usable pair after too_short_delta / static_label_copy filters",
                }
            )
            continue
        _a, _b, prev_m, next_m, transform, crs, pair_info = chosen
        nbr = load_aligned_nbr(pack, prev_m.shape, transform, crs)
        ious = []
        for y, x, prev_t in tiles(prev_m):
            tgt = next_m[y : y + PATCH, x : x + PATCH]
            if tgt.shape != (PATCH, PATCH):
                continue
            nbr_t = None
            if nbr is not None:
                nbr_t = nbr[y : y + PATCH, x : x + PATCH]
                if nbr_t.shape != (PATCH, PATCH):
                    nbr_t = None
            seq = np.zeros((1, 1, N_CH, PATCH, PATCH), np.float32)
            seq[0, 0, 0] = prev_t
            if nbr_t is not None:
                seq[0, 0, 1] = nbr_t
            # also put prev fire as vegetation slot is already partial
            seq_t = torch.from_numpy(seq)
            cur_t = torch.from_numpy(prev_t[None].astype(np.float32))
            x_in = prepare_input(seq_t, cur_t).to(device)
            with torch.no_grad():
                logits = model(x_in, cur_t.to(device))
            # delta growth
            prob = torch.sigmoid(logits)
            growth = prob[0, 0].cpu().numpy()
            pred_abs = np.clip(prev_t + growth, 0, 1)
            pred = pred_abs > 0.5
            ious.append(iou(pred, tgt > 0))
        mean_iou = float(np.mean(ious)) if ious else None
        if mean_iou is not None:
            all_ious.append(mean_iou)
        pack_rows.append(
            {
                "event_id": eid,
                "ok": mean_iou is not None,
                "n_tiles": len(ious),
                "experimental_partial_fill_model_iou": mean_iou,
                "label_pair": [pair_info.get("from"), pair_info.get("to")],
                "n_pairs_used": 1,
                "delta_hours": pair_info.get("delta_hours"),
                "label_mask_iou": pair_info.get("label_mask_iou"),
                "pair_class": pair_info.get("pair_class"),
                "excluded": excluded,
                "nbr_used": nbr is not None,
                "weights": str(WEIGHTS.relative_to(ROOT)).replace("\\", "/"),
                "in_channels": N_CH + 1,
                "schema_mode": "partial_fill",
                "compatible_with_clm_ensemble_v34": False,
                "note": (
                    "Measured experimental IoU under partial_fill (mask+optional warped NBR). "
                    "NOT sealed transfer IoU / NOT field validation."
                ),
            }
        )
        print(f"{eid}: experimental_partial_fill_model_iou={mean_iou} n={len(ious)}")

    OUT.mkdir(parents=True, exist_ok=True)
    summary = {
        "schema": "wfd_latam_au_experimental_partial_fill_iou_v1",
        "as_of_utc": utc(),
        "ok": all(r.get("ok") for r in pack_rows),
        "product_id": "clm_ensemble_weights_multi_if_experimental_partial_fill",
        "mean_experimental_partial_fill_model_iou": float(np.mean(all_ious)) if all_ious else None,
        "packs": pack_rows,
        "authority": "owner session authorized experimental inference (no retrain)",
        "not_claims": [
            "not full NDWS transfer IoU",
            "not sealed U1 TEST IoU",
            "not field GO",
            "not FREEZE lift / not retrain",
            "not GO_Q complete",
        ],
        "rails": {"go_q": "partial", "freeze_intact": True, "no_retrain": True},
    }
    path = OUT / "experimental_iou_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("wrote", path, "mean=", summary["mean_experimental_partial_fill_model_iou"])
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

