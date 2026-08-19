#!/usr/bin/env python3
"""Honest ML intermediate export for LATAM/AU CEMS packs.

clm_ensemble_v34 expects NDWS 17-channel sequences. These packs are
CEMS rasterized burned masks (+ optional S2 NBR). This script:

1. Exports binary mask patches + inventory (NOT UNet train IoU).
2. Writes schema note: compatible_with_clm_ensemble_v34=false.
3. Optional dry-run train inventory that would feed a future schema bridge.
4. Does NOT retrain, does NOT claim transfer IoU.

  python scripts/export_latam_au_ml_patches.py
  python scripts/export_latam_au_ml_patches.py --dry-run-train-inventory

Exit codes:
  0 — export ok (or dry-run inventory only)
  1 — pack missing / no label tifs
  2 — usage
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    ML_EXPORT_SCHEMA,
    ML_PATCH_CONTRACT,
    default_source_pack_dir,
    pack_dir_for,
    sha256_file,
    source_pack_ready,
    successive_mask_ious,
    utc_now,
)

DEFAULT_OUT = ROOT / "artifacts" / "latam_au_ml_export"


def _load_mask(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        arr = np.asarray(ds.read(1))
    return (arr > 0).astype(np.uint8)


def _tile_mask(
    mask: np.ndarray,
    *,
    patch_size: int = 64,
    stride: int | None = None,
    max_patches: int = 64,
    min_pos_frac: float = 0.01,
) -> list[dict[str, Any]]:
    """Extract positive-containing patches (binary mask only)."""
    h, w = mask.shape
    stride = int(stride or patch_size)
    out: list[dict[str, Any]] = []
    for y in range(0, max(1, h - patch_size + 1), stride):
        for x in range(0, max(1, w - patch_size + 1), stride):
            if len(out) >= max_patches:
                return out
            tile = mask[y : y + patch_size, x : x + patch_size]
            if tile.shape != (patch_size, patch_size):
                continue
            pos = float(tile.mean())
            if pos < min_pos_frac:
                continue
            out.append(
                {
                    "y": int(y),
                    "x": int(x),
                    "patch_size": int(patch_size),
                    "pos_frac": pos,
                    "mask": tile,
                }
            )
    # If no positive tiles (tiny fire vs large empty), take center crop
    if not out and h >= patch_size and w >= patch_size:
        cy = max(0, (h - patch_size) // 2)
        cx = max(0, (w - patch_size) // 2)
        tile = mask[cy : cy + patch_size, cx : cx + patch_size]
        out.append(
            {
                "y": int(cy),
                "x": int(cx),
                "patch_size": int(patch_size),
                "pos_frac": float(tile.mean()),
                "mask": tile,
                "fallback": "center_crop",
            }
        )
    return out


def export_pack(
    event_id: str,
    source_pack: Path,
    out_root: Path,
    *,
    patch_size: int = 64,
    max_patches: int = 48,
) -> dict[str, Any]:
    ready, reason = source_pack_ready(source_pack)
    if not ready:
        return {"event_id": event_id, "ok": False, "error": reason}

    meta = json.loads((source_pack / "meta.json").read_text(encoding="utf-8"))
    label_tifs = [
        source_pack / rec["rel"]
        for rec in (meta.get("geotiffs") or [])
        if str(rec.get("role") or "").startswith("label_")
        and rec.get("rel")
        and (source_pack / rec["rel"]).is_file()
    ]
    if not label_tifs:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "no_label_tif_on_disk",
            "hint": "rasters may be gitignored; re-run materialize_latam_au_emsr_packs.py",
        }

    pack_out = out_root / event_id / "ml"
    pack_out.mkdir(parents=True, exist_ok=True)
    patches_dir = pack_out / "patches"
    patches_dir.mkdir(exist_ok=True)

    arrays: list[np.ndarray] = []
    written: list[dict[str, Any]] = []
    for tif in label_tifs:
        mask = _load_mask(tif)
        arrays.append(mask)
        tiles = _tile_mask(mask, patch_size=patch_size, max_patches=max_patches)
        for i, tile in enumerate(tiles):
            fname = f"{tif.stem}_p{i:03d}.npz"
            path = patches_dir / fname
            # Intermediate contract: burned mask only — NOT NDWS sequence.
            np.savez_compressed(
                path,
                mask=tile["mask"].astype(np.uint8),
                pos_frac=np.float32(tile["pos_frac"]),
                y=np.int32(tile["y"]),
                x=np.int32(tile["x"]),
            )
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            written.append(
                {
                    "file": f"patches/{fname}",
                    "source_tif": str(tif.relative_to(source_pack)).replace("\\", "/"),
                    "sha256": h,
                    "pos_frac": tile["pos_frac"],
                    "y": tile["y"],
                    "x": tile["x"],
                    "patch_size": tile["patch_size"],
                }
            )

    succ = successive_mask_ious(arrays) if len(arrays) >= 2 else []
    manifest = {
        "schema": ML_EXPORT_SCHEMA,
        "contract": ML_PATCH_CONTRACT,
        "as_of_utc": utc_now(),
        "event_id": event_id,
        "source_pack": str(
            source_pack.relative_to(ROOT) if source_pack.is_relative_to(ROOT) else source_pack
        ).replace("\\", "/"),
        "compatible_with_clm_ensemble_v34": False,
        "clm_expected": "NDWS 17-channel sequences (legacy17 / holdout_v1 NPZ)",
        "this_export": "uint8 binary burned-mask patches from CEMS rasterized vectors",
        "class": meta.get("class"),
        "label_level": meta.get("label_level"),
        "n_label_tif": len(label_tifs),
        "n_patches": len(written),
        "patch_size": patch_size,
        "patches": written,
        "geometry": {
            "successive_cems_mask_iou": succ,
            "note": "label-vs-label only; not model IoU",
        },
        "train_ready": {
            "status": "inventory_only",
            "can_feed_clm_train": False,
            "reason": (
                "Schema mismatch: mask patches are not NDWS 17-ch. "
                "A future schema bridge would need multi-date EO + weather + align. "
                "FREEZE: no retrain on this export."
            ),
        },
        "not_claims": [
            "not UNet IoU",
            "not transfer IoU",
            "not NDWS 17-ch",
            "not FREEZE lift",
            "not GO_Q complete",
            "not retrain",
        ],
        "hashes": {
            "manifest_inputs": [p["sha256"] for p in written[:8]],
            "n_files": len(written),
        },
    }
    man_path = pack_out / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    schema_note = pack_out / "SCHEMA_NOTE.md"
    schema_note.write_text(
        "\n".join(
            [
                f"# ML export — {event_id}",
                "",
                f"- Contract: `{ML_PATCH_CONTRACT}`",
                "- **Not** compatible with `clm_ensemble_v34` NDWS 17-ch input.",
                "- Patches are CEMS burned-mask tiles only (intermediate).",
                "- Do not report model IoU from this export.",
                "- FREEZE respected: no retrain from this path.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "event_id": event_id,
        "ok": True,
        "n_patches": len(written),
        "n_label_tif": len(label_tifs),
        "manifest": str(
            man_path.relative_to(ROOT) if man_path.is_relative_to(ROOT) else man_path
        ).replace("\\", "/"),
        "compatible_with_clm_ensemble_v34": False,
        "train_ready_status": "inventory_only",
    }


def build_train_inventory(export_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Dry-run inventory that *would* feed train if schema were bridged."""
    return {
        "schema": "wfd_latam_au_train_inventory_v1",
        "as_of_utc": utc_now(),
        "would_feed_train": False,
        "freeze_blocks_retrain": True,
        "reason": (
            "Packs exported as CEMS mask intermediate only. "
            "clm_ensemble_v34 train requires NDWS 17-ch. No retrain."
        ),
        "packs": [
            {
                "event_id": r.get("event_id"),
                "n_patches": r.get("n_patches"),
                "manifest": r.get("manifest"),
                "ok": r.get("ok"),
            }
            for r in export_rows
        ],
        "dry_run_command": (
            "python scripts/export_latam_au_ml_patches.py --dry-run-train-inventory"
        ),
        "not_claims": ["not actual train", "not IoU", "not FREEZE lift"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LATAM/AU ML intermediate patch export")
    ap.add_argument(
        "--event-id",
        action="append",
        dest="event_ids",
        default=None,
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument(
        "--out-root",
        type=Path,
        default=DEFAULT_OUT,
        help="Default: artifacts/latam_au_ml_export (gitignored preferred)",
    )
    ap.add_argument("--patch-size", type=int, default=64)
    ap.add_argument("--max-patches", type=int, default=48)
    ap.add_argument(
        "--dry-run-train-inventory",
        action="store_true",
        help="Write train inventory JSON without claiming train ran",
    )
    ap.add_argument(
        "--update-domain-gap",
        action="store_true",
        help="Merge ml_export section into domain-gap scorecard",
    )
    args = ap.parse_args(argv)

    ids = list(args.event_ids) if args.event_ids else list(EMSR_PACK_SPECS.keys())
    rows: list[dict[str, Any]] = []
    any_fail = False
    for eid in ids:
        if eid not in EMSR_PACK_SPECS:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        src = pack_dir_for(Path(args.data_root), EMSR_PACK_SPECS[eid])
        ready, reason = source_pack_ready(src)
        if not ready:
            print(f"error: {eid}: {reason}", file=sys.stderr)
            rows.append({"event_id": eid, "ok": False, "error": reason})
            any_fail = True
            continue
        row = export_pack(
            eid,
            src,
            Path(args.out_root),
            patch_size=int(args.patch_size),
            max_patches=int(args.max_patches),
        )
        rows.append(row)
        if not row.get("ok"):
            any_fail = True
            print(f"FAIL {eid}: {row.get('error')}", file=sys.stderr)
        else:
            print(f"OK {eid}: n_patches={row.get('n_patches')} → {row.get('manifest')}")

    inv = build_train_inventory(rows)
    inv_path = Path(args.out_root) / "train_inventory.json"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print(f"wrote {inv_path}")

    summary = {
        "schema": ML_EXPORT_SCHEMA,
        "as_of_utc": utc_now(),
        "ok": not any_fail,
        "packs": rows,
        "train_inventory": str(
            inv_path.relative_to(ROOT) if inv_path.is_relative_to(ROOT) else inv_path
        ).replace("\\", "/"),
        "compatible_with_clm_ensemble_v34": False,
        "dry_run_train_inventory": bool(args.dry_run_train_inventory),
    }
    sum_path = Path(args.out_root) / "export_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {sum_path}")

    if args.update_domain_gap:
        _merge_ml_export(summary)

    if args.dry_run_train_inventory:
        print(json.dumps({"train_inventory": inv}, indent=2)[:2000])

    return 1 if any_fail else 0


def _merge_ml_export(summary: dict[str, Any]) -> None:
    paths = [
        ROOT / "docs" / "data_campaigns" / "LATAM_AU_DOMAIN_GAP_SCORECARD.json",
        ROOT / "outputs" / "ml_eval" / "scorecards" / "wfd_ml_domain_gap_v1.json",
    ]
    section = {
        "status": "exported_intermediate" if summary.get("ok") else "failed",
        "as_of_utc": summary.get("as_of_utc"),
        "compatible_with_clm_ensemble_v34": False,
        "contract": ML_PATCH_CONTRACT,
        "schema": ML_EXPORT_SCHEMA,
        "packs": summary.get("packs"),
        "train_inventory": summary.get("train_inventory"),
        "note": (
            "Intermediate CEMS mask patches only. model_iou remains null. "
            "No retrain (FREEZE)."
        ),
    }
    for path in paths:
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        doc["ml_export"] = section
        doc["as_of_utc"] = utc_now()
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"updated domain-gap: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
