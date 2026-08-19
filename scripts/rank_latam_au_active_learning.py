#!/usr/bin/env python3
"""P2-C: rank new-domain tiles for review (not transfer IoU).

Uses label geometry: mixed pos_frac and successive CEMS/weak mask disagreement.
Does **not** run clm_ensemble_v34 softmax. Does not invent model IoU.

  python scripts/rank_latam_au_active_learning.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    AL_RANK_SCHEMA,
    ALL_PACK_SPECS,
    pack_dir_for,
    rank_active_learning_tiles,
    successive_mask_ious,
    utc_now,
    validate_al_ranking,
)


def _load_uint(path: Path):
    import numpy as np
    import rasterio

    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1))


def tiles_from_pack(pack_dir: Path, event_id: str, patch_size: int = 64) -> list[dict[str, Any]]:
    import numpy as np

    meta_p = pack_dir / "meta.json"
    if not meta_p.is_file():
        return []
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    label_tifs = [
        pack_dir / rec["rel"]
        for rec in (meta.get("geotiffs") or [])
        if str(rec.get("role") or "").startswith("label_")
        and rec.get("rel")
        and (pack_dir / rec["rel"]).is_file()
    ]
    if not label_tifs:
        return []
    arrays = []
    for p in label_tifs:
        try:
            arrays.append(_load_uint(p) > 0)
        except Exception:
            continue
    if not arrays:
        return []
    # Pairwise disagreement of last two masks (label change), not model IoU.
    disagree_map = None
    if len(arrays) >= 2 and arrays[0].shape == arrays[-1].shape:
        disagree_map = np.logical_xor(arrays[0], arrays[-1])
    mask = arrays[-1]
    h, w = mask.shape
    out: list[dict[str, Any]] = []
    for y in range(0, max(1, h - patch_size + 1), patch_size):
        for x in range(0, max(1, w - patch_size + 1), patch_size):
            tile = mask[y : y + patch_size, x : x + patch_size]
            if tile.shape != (patch_size, patch_size):
                continue
            pos = float(tile.mean())
            if pos <= 0.0:
                continue
            dfrac = 0.0
            if disagree_map is not None:
                dfrac = float(disagree_map[y : y + patch_size, x : x + patch_size].mean())
            out.append(
                {
                    "tile_id": f"{event_id}_y{y:04d}_x{x:04d}",
                    "file": label_tifs[-1].name,
                    "y": int(y),
                    "x": int(x),
                    "pos_frac": pos,
                    "successive_disagreement": dfrac,
                }
            )
    # Also cite successive whole-mask IoU in the report (not transfer).
    _ = successive_mask_ious(arrays)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Active-learning ranking for LATAM/AU packs")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "latam_au_active_learning" / "ranking.json",
    )
    ap.add_argument("--max-tiles", type=int, default=40)
    args = ap.parse_args(argv)

    all_tiles: list[dict[str, Any]] = []
    per_pack: list[dict[str, Any]] = []
    for eid, spec in ALL_PACK_SPECS.items():
        pack = pack_dir_for(args.data_root, spec)
        raw = tiles_from_pack(pack, eid)
        ranked = rank_active_learning_tiles(raw, event_id=eid)[: args.max_tiles]
        all_tiles.extend(ranked)
        per_pack.append(
            {
                "event_id": eid,
                "n_candidate_tiles": len(raw),
                "n_ranked": len(ranked),
                "pack_present": (pack / "meta.json").is_file(),
            }
        )

    all_tiles.sort(key=lambda r: (-float(r["al_score"]), str(r["tile_id"])))
    for i, row in enumerate(all_tiles, start=1):
        row["global_rank"] = i

    doc = {
        "schema": AL_RANK_SCHEMA,
        "as_of_utc": utc_now(),
        "protocol": "latam_au_al_label_disagreement_v1",
        "model_iou": None,
        "compatible_with_clm_ensemble_v34": False,
        "method": (
            "Tiles ranked by mixed burned fraction (pos_frac near 0.5) plus "
            "successive label-mask disagreement. Not v34 softmax, not transfer IoU."
        ),
        "packs": per_pack,
        "tiles": all_tiles[: max(args.max_tiles * 2, 20)],
        "not_claims": [
            "not transfer IoU",
            "not model confidence from clm_ensemble_v34",
            "not ROS",
            "not FREEZE lift",
        ],
    }
    fails = validate_al_ranking(doc)
    if fails:
        print(f"error: invalid ranking: {fails}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    md = args.output.with_suffix(".md")
    lines = [
        "# Active-learning ranking — LATAM/AU (label geometry)",
        "",
        f"- Schema: `{AL_RANK_SCHEMA}`",
        f"- Built: {doc['as_of_utc']}",
        f"- Tiles listed: {len(doc['tiles'])}",
        "- **model_iou: null** (not transfer IoU)",
        "",
        "| global_rank | event_id | tile_id | al_score | pos_frac | disagreement |",
        "|-------------|----------|---------|----------|----------|--------------|",
    ]
    for row in doc["tiles"][:25]:
        lines.append(
            f"| {row.get('global_rank')} | `{row['event_id']}` | `{row['tile_id']}` | "
            f"{row['al_score']:.3f} | {row['pos_frac']:.3f} | {row['successive_disagreement']:.3f} |"
        )
    lines += [
        "",
        "Review these tiles first if labelling L3. This ranking is **not** a model scorecard.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"wrote": str(args.output), "n_tiles": len(doc["tiles"]), "model_iou": None}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
