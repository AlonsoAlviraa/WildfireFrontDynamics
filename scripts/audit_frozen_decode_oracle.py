#!/usr/bin/env python3
"""Oracle ceiling of the frozen 8-ring k=1 @ 0.90 complete-proxy decode.

Writes outputs/ml_eval/mega_goal_model/FROZEN_DECODE_ORACLE.json.
Does not retune knobs. Optional --with-model reports product P on ring pixels.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_latam_au_complete_model_iou import (  # noqa: E402
    DEFAULT_EVENT_IDS,
    DEFAULT_OUT,
    OOD_GROWTH_THRESHOLD,
    WEIGHTS,
    binary_iou,
    fire_growth_ring,
    iter_usable_eval_tiles,
    oracle_frozen_decode_mask,
)


def _pair_key(tile: dict) -> tuple[str, str, str]:
    return str(tile["event_id"]), str(tile["from"]), str(tile["to"])


def summarize_tiles(tiles: list[dict]) -> dict:
    pairs: dict[tuple[str, str, str], list[dict]] = {}
    for tile in tiles:
        pairs.setdefault(_pair_key(tile), []).append(tile)
    pair_rows: list[dict] = []
    for (event_id, src, dst), group in pairs.items():
        copy_ious: list[float] = []
        oracle_ious: list[float] = []
        true_ring = 0
        false_ring = 0
        growth_outside = 0
        n_edge = 0
        for tile in group:
            prev = tile["prev"]
            tgt = tile["target"]
            ring = fire_growth_ring(prev)
            growth = (tgt >= 0.5) & (prev < 0.5)
            true_ring += int((ring & growth).sum())
            false_ring += int((ring & ~growth).sum())
            growth_outside += int((growth & ~ring).sum())
            if tile.get("kind") == "edge":
                n_edge += 1
            copy_ious.append(binary_iou(prev >= 0.5, tgt >= 0.5))
            oracle_ious.append(binary_iou(oracle_frozen_decode_mask(prev, tgt), tgt >= 0.5))
        pair_rows.append(
            {
                "event_id": event_id,
                "from": src,
                "to": dst,
                "n_tiles": len(group),
                "n_edge_tiles": n_edge,
                "true_ring_px": true_ring,
                "false_ring_px": false_ring,
                "growth_outside_ring_px": growth_outside,
                "copy_iou": float(np.mean(copy_ious)),
                "oracle_iou": float(np.mean(oracle_ious)),
                "oracle_delta_vs_copy": float(np.mean(oracle_ious) - np.mean(copy_ious)),
            }
        )
    deltas = [row["oracle_delta_vs_copy"] for row in pair_rows]
    return {
        "schema": "wfd_frozen_decode_oracle_v1",
        "as_of_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "decode": {
            "growth_threshold": OOD_GROWTH_THRESHOLD,
            "connectivity": 8,
            "min_fire_neighbors": 1,
            "keep_t0": True,
        },
        "n_tiles": len(tiles),
        "n_pairs": len(pair_rows),
        "mean_oracle_delta_vs_copy": float(np.mean(deltas)) if deltas else None,
        "min_oracle_delta_vs_copy": float(min(deltas)) if deltas else None,
        "pairs": pair_rows,
        "not_claims": [
            "oracle is not a model score",
            "not sealed transfer IoU",
            "not GO_Q complete",
            "not FREEZE lift",
        ],
    }


def _product_ring_probs(tiles: list[dict]) -> dict:
    import torch

    from wildfire_front.ml.unet_train import (
        UNetTrainConfig,
        build_model,
        model_forward,
        prepare_input,
    )

    device = torch.device("cpu")
    model = build_model(
        UNetTrainConfig(architecture="residual", model="small", target_mode="delta"),
        in_channels=18,
    )
    state = torch.load(WEIGHTS, map_location=device, weights_only=True)
    model.load_state_dict(state, strict=True)
    model.to(device)
    model.eval()
    true_ps: list[float] = []
    false_ps: list[float] = []
    true_hits = 0
    false_hits = 0
    with torch.no_grad():
        for tile in tiles:
            seq = torch.from_numpy(tile["seq"])
            cur = torch.from_numpy(tile["prev"][np.newaxis, ...].astype(np.float32))
            x_in = prepare_input(seq, cur).to(device)
            prob = torch.sigmoid(model_forward(model, x_in, cur.to(device), "residual"))[0, 0]
            p = prob.cpu().numpy()
            prev = tile["prev"]
            tgt = tile["target"]
            ring = fire_growth_ring(prev)
            growth = (tgt >= 0.5) & (prev < 0.5)
            tr = ring & growth
            fr = ring & ~growth
            if tr.any():
                vals = p[tr]
                true_ps.extend(float(v) for v in vals.ravel())
                true_hits += int((vals >= OOD_GROWTH_THRESHOLD).sum())
            if fr.any():
                vals = p[fr]
                false_ps.extend(float(v) for v in vals.ravel())
                false_hits += int((vals >= OOD_GROWTH_THRESHOLD).sum())
    return {
        "weights": "models/clm_ensemble/weights_multi_if.pt",
        "true_ring_n": len(true_ps),
        "false_ring_n": len(false_ps),
        "true_ring_mean_p": float(np.mean(true_ps)) if true_ps else None,
        "false_ring_mean_p": float(np.mean(false_ps)) if false_ps else None,
        "true_ring_max_p": float(np.max(true_ps)) if true_ps else None,
        "false_ring_max_p": float(np.max(false_ps)) if false_ps else None,
        "true_ring_ge_thr": true_hits,
        "false_ring_ge_thr": false_hits,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT / "FROZEN_DECODE_ORACLE.json")
    parser.add_argument("--with-model", action="store_true")
    args = parser.parse_args(argv)
    tiles = iter_usable_eval_tiles(args.data_root, event_ids=DEFAULT_EVENT_IDS)
    doc = summarize_tiles(tiles)
    if args.with_model:
        doc["product_ring_probs"] = _product_ring_probs(tiles)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(
        {
            "n_pairs": doc["n_pairs"],
            "n_tiles": doc["n_tiles"],
            "mean_oracle_delta_vs_copy": doc["mean_oracle_delta_vs_copy"],
            "min_oracle_delta_vs_copy": doc["min_oracle_delta_vs_copy"],
            "out": str(args.out),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
