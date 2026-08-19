#!/usr/bin/env python3
"""P1-B: inventory + download NAFI annual fire-scar zips.

URLs contain spaces; they are percent-encoded. On network fail writes GAP log.
Does not invent IoU / ROS. Rasters stay gitignored.

  python scripts/download_nafi_scars.py
  python scripts/download_nafi_scars.py --years 2021 2022 2023 --skip-download
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    NAFI_IMAGE_ZIP,
    NAFI_SHAPE_ZIP,
    USER_AGENT,
    WEAK_INVENTORY_SCHEMA,
    WEAK_PACK_SPECS,
    quote_http_url,
    sha256_file,
    utc_now,
)

SPEC = WEAK_PACK_SPECS["AU_NAFI_NT_SEASON_2023"]
DEFAULT_OUT = ROOT / "data" / "open_if" / "latam_au" / "au" / "AU_NAFI_NT_SEASON_2023"


def _head_or_get_meta(url: str, timeout: int = 45) -> dict[str, Any]:
    encoded = quote_http_url(url)
    rec: dict[str, Any] = {
        "url": url,
        "encoded_url": encoded,
        "status": "unreachable",
        "http_code": "",
        "bytes": None,
        "error": "",
    }
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(encoded, method=method, headers=headers)
            if method == "GET":
                req.add_header("Range", "bytes=0-0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                rec["status"] = "reachable"
                rec["http_code"] = str(resp.status)
                cl = resp.headers.get("Content-Length")
                rec["bytes"] = int(cl) if cl and cl.isdigit() else None
                return rec
        except HTTPError as exc:
            rec["http_code"] = str(exc.code)
            rec["error"] = f"HTTPError:{exc.code}"
            if method == "HEAD" and exc.code in {403, 405, 501}:
                continue
            rec["status"] = "unreachable"
            return rec
        except (URLError, TimeoutError, OSError) as exc:
            rec["error"] = f"{type(exc).__name__}:{exc}"
            rec["status"] = "unreachable"
            return rec
    return rec


def _download(url: str, dest: Path, *, timeout: int = 300) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 200:
        return dest
    encoded = quote_http_url(url)
    req = urllib.request.Request(encoded, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    print(f"  GET {encoded}", flush=True)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    return dest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download NAFI annual fire-scar zips")
    ap.add_argument("--years", type=int, nargs="+", default=list(SPEC["years"]))
    ap.add_argument("--kind", choices=("image", "shapefile", "both"), default="image")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT / "raw_nafi")
    ap.add_argument(
        "--inventory",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au" / "inventories" / "nafi_inventory.csv",
    )
    ap.add_argument(
        "--log",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au" / "inventories" / "nafi_download.log",
    )
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    kinds = ["image", "shapefile"] if args.kind == "both" else [args.kind]
    rows: list[dict[str, Any]] = []
    log_lines = [f"nafi download {utc_now()}"]
    n_dl = 0
    for year in args.years:
        for kind in kinds:
            url = NAFI_IMAGE_ZIP.format(year=int(year)) if kind == "image" else NAFI_SHAPE_ZIP.format(year=int(year))
            meta = _head_or_get_meta(url, timeout=min(60, args.timeout))
            dest = args.out_dir / f"nafi_{year}_{kind}.zip"
            rec = {
                "source_id": f"NAFI_{year}_{kind}",
                "year": year,
                "kind": kind,
                "url": url,
                "encoded_url": quote_http_url(url),
                "license_id": SPEC["license_id"],
                "class": "ml_weak",
                "label_level": "L1_annual",
                "status": meta["status"],
                "http_code": meta.get("http_code") or "",
                "remote_bytes": meta.get("bytes") or "",
                "local_path": "",
                "local_bytes": "",
                "sha256": "",
                "error": meta.get("error") or "",
                "model_iou": "",
                "checked_at_utc": utc_now(),
            }
            if args.skip_download:
                rec["status"] = "inventoried_only" if meta["status"] == "reachable" else meta["status"]
            else:
                try:
                    _download(url, dest, timeout=args.timeout)
                    rec["local_path"] = (
                        str(dest.relative_to(ROOT)).replace("\\", "/") if dest.is_relative_to(ROOT) else str(dest)
                    )
                    rec["local_bytes"] = dest.stat().st_size
                    rec["sha256"] = sha256_file(dest)
                    rec["status"] = "downloaded"
                    n_dl += 1
                    log_lines.append(f"OK {year} {kind} bytes={rec['local_bytes']}")
                except Exception as exc:  # noqa: BLE001
                    rec["status"] = "gap"
                    rec["error"] = f"{type(exc).__name__}:{exc}"
                    log_lines.append(f"GAP {year} {kind} {rec['error']}")
            rows.append(rec)

    fields = [
        "source_id",
        "year",
        "kind",
        "url",
        "encoded_url",
        "license_id",
        "class",
        "label_level",
        "status",
        "http_code",
        "remote_bytes",
        "local_path",
        "local_bytes",
        "sha256",
        "error",
        "model_iou",
        "checked_at_utc",
    ]
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    with args.inventory.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    payload = {
        "schema": WEAK_INVENTORY_SCHEMA,
        "source": "nafi_firescar",
        "as_of_utc": utc_now(),
        "n": len(rows),
        "n_downloaded": n_dl,
        "honesty": "no IoU invented; NAFI 250m annual scar is L1 weak, not NSW/NT cadastre, not ROS",
        "rows": rows,
    }
    args.inventory.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    args.log.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print(json.dumps({"inventory": str(args.inventory), "n": len(rows), "downloaded": n_dl}, indent=2))
    if n_dl == 0 and not args.skip_download:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
