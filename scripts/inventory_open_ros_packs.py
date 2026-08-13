#!/usr/bin/env python3
"""Write README + inventory JSON for staged PT-FireSprd / GOFER packs.

python scripts/inventory_open_ros_packs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.external_ros import (  # noqa: E402
    PACK_CATALOG,
    build_zip_inventory,
    inventory_gofer_hourly_counts,
    pack_root,
    parse_gofer_fire_catalog,
    write_pack_readme,
)
from wildfire_front.open_if.pt_firesprd import (  # noqa: E402
    default_extracted,
    inventory_l1_pack,
)


def write_pt(repo_root: Path) -> dict:
    inv = build_zip_inventory(repo_root, "pt_firesprd", hash_extracted=False)
    extracted = default_extracted(repo_root)
    l1 = None
    if extracted.is_dir():
        l1 = inventory_l1_pack(extracted)
        inv["l1"] = {
            "n_shapefiles": l1["n_shapefiles"],
            "n_fires_ok": l1["n_fires_ok"],
            "n_fires_r1": l1["n_fires_r1"],
            "not_product_ros": True,
            "fires": l1["fires"],
        }
    dest = pack_root(repo_root, "pt_firesprd")
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "inventory.json").write_text(json.dumps(inv, indent=2), encoding="utf-8")
    write_pack_readme(dest / "README.md", PACK_CATALOG["pt_firesprd"], inv)
    return inv


def write_gofer(repo_root: Path) -> dict:
    inv = build_zip_inventory(repo_root, "gofer", hash_extracted=False)
    root = pack_root(repo_root, "gofer")
    csv_path = root / "extracted" / "GOFER" / "fireData.csv"
    inv["fire_catalog"] = parse_gofer_fire_catalog(csv_path)
    shp = root / "extracted" / "GOFER" / "GOFER_Combined" / "GOFERC_fireProg.shp"
    inv["hourly"] = inventory_gofer_hourly_counts(shp)
    dest = root
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "inventory.json").write_text(json.dumps(inv, indent=2), encoding="utf-8")
    write_pack_readme(dest / "README.md", PACK_CATALOG["gofer"], inv)
    return inv


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="append", dest="packs", default=None)
    args = ap.parse_args(argv)
    packs = list(args.packs) if args.packs else ["pt_firesprd", "gofer"]
    for pack_id in packs:
        if pack_id == "pt_firesprd":
            inv = write_pt(ROOT)
        elif pack_id == "gofer":
            inv = write_gofer(ROOT)
        else:
            print(f"error: unknown pack {pack_id}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "pack_id": pack_id,
                    "zip_md5_ok": inv.get("zip_md5_ok"),
                    "n_extracted_files": inv.get("n_extracted_files"),
                    "l1_n_fires_r1": (inv.get("l1") or {}).get("n_fires_r1"),
                    "gofer_n_fires": len(inv.get("fire_catalog") or []),
                    "hourly_ok": (inv.get("hourly") or {}).get("ok"),
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
