#!/usr/bin/env python3
"""In-sample same-fire frozen-decode scratch. Does not touch official LATAM JSON.

Trains residual weights on rasterized CEMS + Caldor usable tiles with the same
frozen ring loss as lab_scratch. Val is tile-macro Δ vs copy on those tiles.

  python scripts/run_same_fire_scratch.py
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_latam_au_complete_model_iou import OOD_GROWTH_THRESHOLD  # noqa: E402
from scripts.run_latam_au_lab_scratch import frozen_ring_decode_loss  # noqa: E402
from scripts.run_same_fire_multi_geometry import (  # noqa: E402
    DEFAULT_FIRE_IDS,
    ISOLATION_FIRE_IDS,
    cems_pack_dir,
    load_cems_geometries,
    pair_row,
    vector_copy_iou,
)
from wildfire_front.ml.unet_train import (  # noqa: E402
    UNetTrainConfig,
    build_model,
    model_forward,
    prepare_input,
)
from wildfire_front.ml.feature_schema import schema_channel_count  # noqa: E402
from wildfire_front.open_if.same_fire_model import (  # noqa: E402
    aoi_ref_geom,
    binary_iou,
    caldor_cov_at,
    collect_pair_tiles,
    decode_complete_proxy_pred,
    load_tif,
    point_cov_for_recs,
    rasterize_records,
)

N_CH = schema_channel_count("legacy17")
INIT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "lab_scratch_frozen" / "weights_pretrained_best.pt"
PRODUCT = ROOT / "models" / "clm_ensemble" / "weights_multi_if.pt"
OUT = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire_scratch"
OFFICIAL = ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "complete_proxy_model_iou.json"
CALDOR = ROOT / "data" / "open_if" / "external_bridge" / "US_FIREBENCH_CALDOR_2021"


def _tile_delta(model, device, tiles: list[dict[str, Any]]) -> float:
    if not tiles:
        return 0.0
    model.eval()
    deltas: list[float] = []
    with torch.no_grad():
        for tile in tiles:
            seq = np.asarray(tile["seq"], dtype=np.float32)
            if seq.ndim == 4:
                seq = seq[np.newaxis, ...]
            prev = np.asarray(tile["prev"], dtype=np.float32)
            tgt = np.asarray(tile["target"], dtype=np.float32)
            seq_t = torch.from_numpy(seq)
            cur_t = torch.from_numpy(prev[np.newaxis, ...])
            x_in = prepare_input(seq_t, cur_t).to(device)
            logits = model_forward(model, x_in, cur_t.to(device), "residual")
            prob = torch.sigmoid(logits)[0, 0].cpu().numpy()
            pred = decode_complete_proxy_pred(
                prob,
                prev,
                architecture="residual",
                target_mode="delta",
                threshold=0.5,
                growth_threshold=OOD_GROWTH_THRESHOLD,
                require_growth_ring=True,
            )
            model_iou = binary_iou(pred, tgt > 0.5)
            copy_iou = binary_iou(prev >= 0.5, tgt > 0.5)
            deltas.append(float(model_iou - copy_iou))
    model.train()
    return float(sum(deltas) / len(deltas))


def _collect_cems_tiles(fire_id: str, max_patches: int, cache: dict[str, Any]) -> list[dict[str, Any]]:
    activation, aoi = fire_id.split("_", 1)
    pack = cems_pack_dir(activation)
    recs = load_cems_geometries(pack, aoi)
    if len(recs) < 2:
        return []
    masks, meta = rasterize_records(
        recs,
        ref_geom=aoi_ref_geom(pack, aoi),
        skip_bytes=80_000_000,
    )
    if not meta.get("ok"):
        return []
    cov, _prov = point_cov_for_recs(
        recs,
        (int(meta["height"]), int(meta["width"])),
        meteo_mode="constant",
        cache=cache,
    )
    tiles: list[dict[str, Any]] = []
    for prev, nxt, prev_m, next_m in zip(recs, recs[1:], masks, masks[1:], strict=False):
        if prev_m is None or next_m is None:
            continue
        row = pair_row(prev, nxt, copy_iou=vector_copy_iou(prev.get("geom"), nxt.get("geom")))
        if row.get("copy_mask_iou") is None:
            row["pair_class"] = pair_row(prev, nxt, copy_iou=binary_iou(prev_m > 0, next_m > 0))["pair_class"]
        if row.get("pair_class") != "usable":
            continue
        for tile in collect_pair_tiles(prev_m, next_m, cov, max_patches=max_patches, caldor=False):
            tile["fire_id"] = fire_id
            tiles.append(tile)
    return tiles


def _collect_caldor_tiles(max_patches: int) -> list[dict[str, Any]]:
    meta_p = CALDOR / "meta.json"
    if not meta_p.is_file():
        return []
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    recs = []
    for item in meta.get("observations") or []:
        rel = item.get("cumulative_mask")
        path = CALDOR / rel if rel else None
        if path is None or not path.is_file():
            continue
        recs.append({"utc": item.get("timestamp_utc"), "path": path})
    tiles: list[dict[str, Any]] = []
    cache: dict[str, np.ndarray] = {}
    for prev, nxt in zip(recs, recs[1:]):
        if prev["path"] not in cache:
            cache[prev["path"]] = (load_tif(prev["path"]) > 0).astype(np.float32)
        if nxt["path"] not in cache:
            cache[nxt["path"]] = (load_tif(nxt["path"]) > 0).astype(np.float32)
        prev_m = cache[prev["path"]]
        next_m = cache[nxt["path"]]
        copy = binary_iou(prev_m > 0, next_m > 0)
        from wildfire_front.open_if.latam_au import classify_temporal_pair, hours_between, parse_iso_utc

        delta = None
        a = parse_iso_utc(str(prev.get("utc") or ""))
        b = parse_iso_utc(str(nxt.get("utc") or ""))
        if a is not None and b is not None:
            delta = hours_between(a, b)
        if classify_temporal_pair(
            delta_hours=delta,
            label_mask_iou=copy,
            prev_kind="delineation_monitoring",
            next_kind="delineation_monitoring",
        ) != "usable":
            continue
        cov = caldor_cov_at(CALDOR, str(prev.get("utc") or ""))
        if cov is None:
            continue
        for tile in collect_pair_tiles(prev_m, next_m, cov, max_patches=max_patches, caldor=True):
            tile["fire_id"] = "US_FIREBENCH_CALDOR_2021"
            tiles.append(tile)
    return tiles


def main(argv: list[str] | None = None) -> int:
    del argv
    init = INIT if INIT.is_file() else PRODUCT
    if not init.is_file():
        print("error: missing init weights", file=sys.stderr)
        return 1
    official_before = OFFICIAL.read_bytes() if OFFICIAL.is_file() else None
    cache: dict[str, Any] = {}
    tiles: list[dict[str, Any]] = []
    for fire_id in DEFAULT_FIRE_IDS:
        if fire_id in ISOLATION_FIRE_IDS:
            continue
        print(f"collect {fire_id}", flush=True)
        if fire_id == "US_FIREBENCH_CALDOR_2021":
            tiles.extend(_collect_caldor_tiles(max_patches=16))
        elif fire_id in {"TOBARRA_20240802", "EMSR898_AOI01"}:
            # 898 GeoJSON slivers are too heavy for the scratch tile collector.
            continue
        elif fire_id.startswith("EMSR"):
            tiles.extend(_collect_cems_tiles(fire_id, max_patches=16, cache=cache))
    if len(tiles) < 8:
        print(f"error: too few tiles ({len(tiles)})", file=sys.stderr)
        return 2
    print(f"training on {len(tiles)} tiles from {sorted({t['fire_id'] for t in tiles})}", flush=True)

    device = torch.device("cpu")
    cfg = UNetTrainConfig(architecture="residual", model="small", target_mode="delta")
    model = build_model(cfg, in_channels=N_CH + 1)
    model.load_state_dict(torch.load(init, map_location=device, weights_only=True), strict=True)
    model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-4)

    seqs = []
    curs = []
    tgts = []
    for tile in tiles:
        seq = np.asarray(tile["seq"], dtype=np.float32)
        if seq.ndim == 5:
            seq = seq[0]
        seqs.append(torch.from_numpy(seq))
        curs.append(torch.from_numpy(np.asarray(tile["prev"], dtype=np.float32)))
        tgts.append(torch.from_numpy(np.asarray(tile["target"], dtype=np.float32)))
    seq_all = torch.stack(seqs)
    cur_all = torch.stack(curs)
    tgt_all = torch.stack(tgts)

    OUT.mkdir(parents=True, exist_ok=True)
    best = -1e9
    best_epoch = -1
    best_path = OUT / "weights_pretrained_best.pt"
    history: list[dict[str, Any]] = []
    epochs = 8
    batch_size = 8
    model.train()
    n = seq_all.shape[0]
    for epoch in range(1, epochs + 1):
        order = torch.randperm(n)
        losses: list[float] = []
        for start in range(0, n, batch_size):
            idx = order[start : start + batch_size]
            seq = seq_all[idx].to(device)
            cur = cur_all[idx].to(device)
            tgt = tgt_all[idx].to(device)
            if seq.ndim == 4:
                seq_in = seq.unsqueeze(1)
            else:
                seq_in = seq
            x = prepare_input(seq_in, cur)
            logits = model_forward(model, x, cur, "residual")
            loss = frozen_ring_decode_loss(logits, cur, tgt, fp_weight=4.0)
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.item()))
        val_delta = _tile_delta(model, device, tiles)
        row = {
            "epoch": epoch,
            "train_loss": float(sum(losses) / max(len(losses), 1)),
            "tile_delta_vs_copy": val_delta,
            "n_tiles": n,
        }
        history.append(row)
        print(
            f"same-fire scratch epoch {epoch}/{epochs} loss={row['train_loss']:.4f} "
            f"tile_delta={val_delta:+.6f}",
            flush=True,
        )
        if val_delta > best:
            best = val_delta
            best_epoch = epoch
            torch.save(model.state_dict(), best_path)

    record = {
        "schema": "wfd_same_fire_scratch_v1",
        "as_of_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "label": "same_fire_scratch_in_sample",
        "in_sample": True,
        "init_weights": str(init.relative_to(ROOT)).replace("\\", "/"),
        "n_tiles": n,
        "fires": sorted({str(t["fire_id"]) for t in tiles}),
        "config": {
            "epochs": epochs,
            "batch_size": batch_size,
            "lr": 1e-4,
            "fp_weight": 4.0,
            "growth_threshold": OOD_GROWTH_THRESHOLD,
            "loss": "true_ring_hinge_plus_false_ring_residual_leak",
        },
        "best_epoch": best_epoch,
        "best_tile_delta_vs_copy": best,
        "history": history,
        "not_claims": [
            "in-sample same-fire scratch — not official LATAM complete-proxy",
            "not sealed transfer IoU",
            "not GO_Q",
            "not clm_ensemble_v34",
            "does not overwrite lab_scratch_frozen weights",
        ],
    }
    (OUT / "SCRATCH_MANIFEST.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if official_before is not None and OFFICIAL.read_bytes() != official_before:
        print("error: official LATAM JSON changed", file=sys.stderr)
        return 3
    print(json.dumps({"best_epoch": best_epoch, "best_tile_delta": best, "n_tiles": n}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
