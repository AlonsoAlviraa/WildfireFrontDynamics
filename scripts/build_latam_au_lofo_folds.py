#!/usr/bin/env python3
"""P1-C: LOFO fold definition including one non-CLM fire.

Writes a protocol fold JSON. Does not copy 98k NPZ. Does not run UNet.
model_iou stays null (blocked_incompatible_schema).

  python scripts/build_latam_au_lofo_folds.py
  python scripts/build_latam_au_lofo_folds.py --held-out AU_EMSR408_NSW
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    LOFO_FOLD_SCHEMA,
    build_lofo_fold_doc,
    pack_dir_for,
    utc_now,
    validate_lofo_fold,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build LATAM/AU LOFO fold including non-CLM fire")
    ap.add_argument(
        "--held-out",
        default="AU_EMSR408_NSW",
        help="Non-CLM event_id to hold out (default AU_EMSR408_NSW)",
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "latam_au_lofo" / "lofo_non_clm_v1.json",
    )
    args = ap.parse_args(argv)

    eid = args.held_out
    if eid not in ALL_PACK_SPECS:
        print(f"error: unknown event_id {eid}", file=sys.stderr)
        return 2
    spec = ALL_PACK_SPECS[eid]
    pack = pack_dir_for(args.data_root, spec)
    doc = build_lofo_fold_doc(repo_root=ROOT, non_clm_event_id=eid, pack_dir=pack)
    fails = validate_lofo_fold(doc)
    if fails:
        print(f"error: invalid lofo fold: {fails}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    md = args.output.with_suffix(".md")
    held = doc["held_out"]
    lines = [
        f"# LOFO fold — held-out `{eid}`",
        "",
        f"- Schema: `{LOFO_FOLD_SCHEMA}`",
        f"- Built: {doc['as_of_utc']}",
        f"- CLM train sources: {', '.join(doc['clm_train_pool']) or '(lofo_v1 manifest missing)'}",
        f"- Held-out pack ready: `{held['pack_ready']}` ({held['pack_reason']})",
        "- Compatible with clm_ensemble_v34: **false**",
        f"- model_iou: **null** (`{doc['folds'][eid]['eval_status']}`)",
        "",
        "This is a fold **definition**. It does not copy CLM NPZ and does not",
        "run the UNet on CEMS/weak rasters. Transfer IoU is not invented.",
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    print(
        json.dumps(
            {
                "wrote": str(args.output),
                "held_out": eid,
                "eval_status": doc["folds"][eid]["eval_status"],
                "model_iou": None,
                "pack_ready": held["pack_ready"],
                "as_of_utc": utc_now(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
