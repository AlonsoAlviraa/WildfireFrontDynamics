#!/usr/bin/env python3
"""Download PT-FireSprd + GOFER (Zenodo CC-BY) into data/external/<pack>/.

Does not git-add rasters/zips. Does not flip release flags or retrain.

  python scripts/download_open_ros_packs.py
  python scripts/download_open_ros_packs.py --pack pt_firesprd
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.external_ros import (  # noqa: E402
    PACK_CATALOG,
    md5_file,
    pack_root,
    utc_now,
)

USER_AGENT = "WildfireFrontDynamics-AgentB/1.0 (+lab; zenodo CC-BY)"


def download(url: str, dest: Path, *, timeout: int = 300) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    print(f"GET {url}", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, tmp.open("wb") as out:  # noqa: S310
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)", flush=True)
    return dest


def extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    out = dest_dir / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    marker = out / ".extracted_ok"
    if marker.is_file():
        return out
    print(f"extract {zip_path.name} -> {out}", flush=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(out)
    marker.write_text(utc_now(), encoding="utf-8")
    return out


def stage_pack(pack_id: str) -> dict:
    spec = PACK_CATALOG[pack_id]
    root = pack_root(ROOT, pack_id)
    zip_path = download(spec["download_url"], root / spec["zip_name"])
    got = md5_file(zip_path)
    ok = got == spec["md5"]
    rec = {
        "pack_id": pack_id,
        "zip": str(zip_path),
        "bytes": zip_path.stat().st_size,
        "md5": got,
        "md5_ok": ok,
        "extracted": None,
        "error": None,
    }
    if not ok:
        rec["error"] = f"md5_mismatch expected={spec['md5']}"
        return rec
    rec["extracted"] = str(extract_zip(zip_path, root))
    return rec


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download open ROS/progression packs")
    ap.add_argument("--pack", action="append", dest="packs", default=None)
    args = ap.parse_args(argv)
    packs = list(args.packs) if args.packs else ["pt_firesprd", "gofer"]
    reports = []
    exit_code = 0
    for pack_id in packs:
        if pack_id not in PACK_CATALOG:
            print(f"error: unknown pack {pack_id}", file=sys.stderr)
            return 2
        rec = stage_pack(pack_id)
        reports.append(rec)
        print(json.dumps({k: rec[k] for k in rec if k != "extracted"}, indent=2))
        if rec.get("error"):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
