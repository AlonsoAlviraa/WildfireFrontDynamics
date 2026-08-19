#!/usr/bin/env python3
"""Build the single allowed LATAM/AU ``lab_scratch`` training dataset.

Only temporal pairs classified ``usable`` by the complete-proxy protocol are
exported.  Static labels, short deltas, and incompatible FEP/GRA products are
recorded in the manifest but never written as training samples.  A bounded CLM
holdout sample is linked/copied into each split to retain the source-domain
anchor without changing the frozen product weights.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import run_latam_au_complete_model_iou as complete  # noqa: E402

DEFAULT_OUT = ROOT / "artifacts" / "mega_goal_model" / "lab_scratch_dataset"
DEFAULT_CLM = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
EVENT_IDS = (
    "AU_EMSR500_PERTH",
    "CL_EMSR647_NACIMIENTO",
    "AU_EMSR408_NSW",
    "CL_EMSR715_VALPARAISO",
)


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _link_or_copy(src: Path, dst: Path) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _write_npz(
    path: Path,
    *,
    sequence: np.ndarray,
    current: np.ndarray,
    target: np.ndarray,
    event_id: str,
    pair_id: str,
    y: int,
    x: int,
    stratum: str,
) -> None:
    growth = np.clip((target >= 0.5).astype(np.float32) - (current >= 0.5), 0, 1)
    np.savez_compressed(
        path,
        sequence=sequence[0].astype(np.float32),
        current_fire=current.astype(np.float32),
        target_fire=target.astype(np.float32),
        change_fraction=np.float32(growth.mean()),
        source=np.asarray(f"lab_scratch_{event_id}"),
        pair_id=np.asarray(pair_id),
        y=np.int32(y),
        x=np.int32(x),
        tile_stratum=np.asarray(stratum),
        pair_class=np.asarray("usable"),
    )


def build_dataset(
    *,
    data_root: Path,
    clm_root: Path,
    out_root: Path,
    max_train_tiles: int,
    max_val_tiles: int,
    clm_train: int,
    clm_val: int,
    clm_test: int,
) -> dict[str, Any]:
    for split in ("train", "val", "test"):
        (out_root / split).mkdir(parents=True, exist_ok=True)

    known = {**complete.EMSR_PACK_SPECS, **complete.WEAK_PACK_SPECS}
    pair_manifest: list[dict[str, Any]] = []
    latam_counts = {"train": 0, "val": 0, "test": 0}

    for event_id in EVENT_IDS:
        pack = complete.pack_dir_for(data_root, known[event_id])
        cov = complete.load_cov(pack)
        meta_path = pack / "meta.json"
        if cov is None or not meta_path.is_file():
            raise RuntimeError(f"complete covariates/meta missing for {event_id}")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        records = complete.label_records_from_meta(pack, meta)
        for pair_index in range(1, len(records)):
            prev_rec, next_rec = records[pair_index - 1], records[pair_index]
            prev = complete.load_mask(Path(prev_rec["path"]))
            target = complete.load_mask(Path(next_rec["path"]))
            if prev.shape != target.shape:
                pair_manifest.append(
                    {"event_id": event_id, "pair_index": pair_index, "pair_class": "label_shape_mismatch"}
                )
                continue
            delta = None
            if prev_rec.get("dt") is not None and next_rec.get("dt") is not None:
                delta = complete.hours_between(prev_rec["dt"], next_rec["dt"])
            label_iou = complete.binary_iou(prev > 0, target > 0)
            pair_class = complete.classify_temporal_pair(
                delta_hours=delta,
                label_mask_iou=label_iou,
                prev_kind=prev_rec.get("kind"),
                next_kind=next_rec.get("kind"),
            )
            pair_row: dict[str, Any] = {
                "event_id": event_id,
                "pair_index": pair_index,
                "from": prev_rec.get("name"),
                "to": next_rec.get("name"),
                "from_kind": prev_rec.get("kind"),
                "to_kind": next_rec.get("kind"),
                "delta_hours": delta,
                "label_mask_iou": label_iou,
                "pair_class": pair_class,
                "written": {"train": 0, "val": 0},
            }
            if pair_class != "usable":
                pair_manifest.append(pair_row)
                continue

            pair_cov = complete.cov_at_label(cov, str(prev_rec.get("name") or ""))
            train_tiles = complete.stratified_tiles(prev, max_n=max_train_tiles)
            train_coords = {(y, x) for y, x, _tile, _kind in train_tiles}
            candidates = complete.stratified_tiles(
                prev, max_n=max_train_tiles + max_val_tiles * 3
            )
            val_tiles = [row for row in candidates if (row[0], row[1]) not in train_coords][
                :max_val_tiles
            ]

            pair_id = f"{event_id}_p{pair_index:02d}"
            for split, selected in (("train", train_tiles), ("val", val_tiles)):
                for tile_index, (y, x, current, stratum) in enumerate(selected):
                    next_tile = complete.crop(target, y, x)
                    sequence = complete.build_seq_tile(pair_cov, y, x)
                    if next_tile is None or sequence is None:
                        continue
                    filename = f"latam_{pair_id}_{split}_{tile_index:03d}_{y}_{x}.npz"
                    _write_npz(
                        out_root / split / filename,
                        sequence=sequence,
                        current=current,
                        target=next_tile,
                        event_id=event_id,
                        pair_id=pair_id,
                        y=y,
                        x=x,
                        stratum=stratum,
                    )
                    pair_row["written"][split] += 1
                    latam_counts[split] += 1
            pair_manifest.append(pair_row)

    clm_limits = {"train": clm_train, "val": clm_val, "test": clm_test}
    clm_counts: dict[str, int] = {}
    for split, limit in clm_limits.items():
        sources = sorted((clm_root / split).glob("*.npz"))[:limit]
        if not sources:
            raise RuntimeError(f"no CLM holdout samples in {clm_root / split}")
        for index, src in enumerate(sources):
            _link_or_copy(src, out_root / split / f"clm_{index:04d}_{src.name}")
        clm_counts[split] = len(sources)

    usable = [row for row in pair_manifest if row["pair_class"] == "usable"]
    manifest = {
        "schema": "wfd_latam_au_lab_scratch_dataset_v1",
        "as_of_utc": _utc_now(),
        "seed": 42,
        "protocol": "same complete_proxy usable-pair classifier and 64x64 stratified tiles",
        "data_root": str(data_root),
        "clm_root": str(clm_root),
        "n_usable_pairs": len(usable),
        "latam_counts": latam_counts,
        "clm_counts": clm_counts,
        "pairs": pair_manifest,
        "exclusion_counts": {
            label: sum(row["pair_class"] == label for row in pair_manifest)
            for label in ("too_short_delta", "static_label_copy", "incompatible_product_kind")
        },
        "not_claims": [
            "lab_scratch only",
            "not sealed transfer IoU",
            "not clm_ensemble_v34",
            "not FREEZE lift",
            "not GO_Q complete",
        ],
    }
    (out_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    parser.add_argument("--clm-root", type=Path, default=DEFAULT_CLM)
    parser.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--max-train-tiles", type=int, default=32)
    parser.add_argument("--max-val-tiles", type=int, default=12)
    parser.add_argument("--clm-train", type=int, default=160)
    parser.add_argument("--clm-val", type=int, default=96)
    parser.add_argument("--clm-test", type=int, default=96)
    args = parser.parse_args(argv)
    manifest = build_dataset(
        data_root=args.data_root,
        clm_root=args.clm_root,
        out_root=args.out_root,
        max_train_tiles=max(1, args.max_train_tiles),
        max_val_tiles=max(0, args.max_val_tiles),
        clm_train=max(1, args.clm_train),
        clm_val=max(1, args.clm_val),
        clm_test=max(1, args.clm_test),
    )
    print(json.dumps({k: manifest[k] for k in ("n_usable_pairs", "latam_counts", "clm_counts", "exclusion_counts")}, indent=2))
    return 0 if manifest["n_usable_pairs"] >= 4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
