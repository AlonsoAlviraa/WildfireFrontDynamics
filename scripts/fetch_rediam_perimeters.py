#!/usr/bin/env python3
"""Fetch Andalucía REDIAM wildfire perimeters via WFS → GeoJSON cache.

Source: Junta de Andalucía / REDIAM
  https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_perimetros_incendios_forestales
Layers: ms:perim_incendios_YYYY  (IF >10 ha, 2008–2025)
Native CRS: EPSG:3042

Attribution (required): REDIAM — Junta de Andalucía

Examples:
  python scripts/fetch_rediam_perimeters.py --years 2024,2025
  python scripts/fetch_rediam_perimeters.py --years 2024 --count 5 --out data/open_if/rediam_andalucia/wfs_cache
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

WFS_BASE = (
    "https://www.juntadeandalucia.es/medioambiente/mapwms/REDIAM_perimetros_incendios_forestales"
)
ATTRIBUTION = (
    "Fuente: REDIAM — Junta de Andalucía. Uso libre con mención de autores y propietarios."
)
DEFAULT_OUT = ROOT / "data" / "open_if" / "rediam_andalucia" / "wfs_cache"
UA = "WildfireFrontDynamics/1.0 (research; rediam intake; contact alonso.alvbal@gmail.com)"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def build_wfs_url(
    year: int,
    *,
    count: int | None = None,
    output_format: str = "geojson",
) -> str:
    params: dict[str, str] = {
        "SERVICE": "WFS",
        "VERSION": "2.0.0",
        "REQUEST": "GetFeature",
        "TYPENAMES": f"ms:perim_incendios_{year}",
        "OUTPUTFORMAT": output_format,
    }
    if count is not None and count > 0:
        params["COUNT"] = str(int(count))
    return f"{WFS_BASE}?{urllib.parse.urlencode(params)}"


def _dest_paths(out_root: Path, year: int, count: int | None) -> tuple[Path, Path, bool]:
    """Return (dest_geojson, meta_json, is_smoke).

    Smoke/count fetches NEVER write to the full-year cache path.
    """
    if count is not None and count > 0:
        smoke_dir = out_root / "_smoke" / str(year)
        smoke_dir.mkdir(parents=True, exist_ok=True)
        dest = smoke_dir / f"perim_incendios_{year}_count{count}.geojson"
        meta = smoke_dir / f"perim_incendios_{year}_count{count}.fetch.json"
        return dest, meta, True
    year_dir = out_root / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    dest = year_dir / f"perim_incendios_{year}.geojson"
    meta = year_dir / f"perim_incendios_{year}.fetch.json"
    return dest, meta, False


def fetch_year(
    year: int,
    out_root: Path,
    *,
    count: int | None = None,
    timeout: int = 180,
    force: bool = False,
) -> dict[str, Any]:
    dest, meta_path, is_smoke = _dest_paths(out_root, year, count)

    result: dict[str, Any] = {
        "year": year,
        "layer": f"ms:perim_incendios_{year}",
        "url": build_wfs_url(year, count=count),
        "path": _relpath(dest),
        "is_smoke": is_smoke,
        "count_limit": count,
        "attribution": ATTRIBUTION,
        "crs_expected": "EPSG:3042",
        "fetched_at_utc": _utc(),
        "ok": False,
    }

    # Full-year cache reuse only (never reuse smoke as industrial source)
    if (
        not is_smoke
        and dest.is_file()
        and dest.stat().st_size > 100
        and not force
        and count is None
    ):
        try:
            fc = json.loads(dest.read_text(encoding="utf-8"))
            n = len(fc.get("features") or [])
            result.update(
                {
                    "ok": True,
                    "cached": True,
                    "n_features": n,
                    "bytes": dest.stat().st_size,
                    "sha256": _sha256(dest),
                    "path": _relpath(dest),
                }
            )
            return result
        except (OSError, json.JSONDecodeError):
            pass

    url = build_wfs_url(year, count=count)
    result["url"] = url
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Accept": "application/json,application/geo+json,*/*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result["error"] = f"{type(exc).__name__}:{exc}"
        meta_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    # Reject HTML/error payloads
    head = raw[:200].lstrip().lower()
    if head.startswith(b"<") or b"exception" in head[:500].lower():
        result["error"] = "wfs_returned_non_geojson"
        result["content_type"] = content_type
        result["body_head"] = raw[:300].decode("utf-8", "replace")
        meta_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    try:
        fc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        result["error"] = f"json_decode:{exc}"
        meta_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    if not isinstance(fc, dict) or fc.get("type") not in {"FeatureCollection", "Feature"}:
        result["error"] = "unexpected_geojson_type"
        meta_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    # Normalize Feature → FeatureCollection
    if fc.get("type") == "Feature":
        fc = {"type": "FeatureCollection", "features": [fc]}

    # Stamp provenance on collection properties
    props = dict(fc.get("properties") or {})
    props.update(
        {
            "source": "REDIAM",
            "owner": "Junta de Andalucía",
            "attribution": ATTRIBUTION,
            "layer": f"ms:perim_incendios_{year}",
            "wfs_base": WFS_BASE,
            "crs_native": "EPSG:3042",
            "fetched_at_utc": _utc(),
            "count_limit": count,
            "is_smoke": is_smoke,
        }
    )
    fc["properties"] = props

    dest.write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    n = len(fc.get("features") or [])
    result.update(
        {
            "ok": True,
            "cached": False,
            "n_features": n,
            "bytes": dest.stat().st_size,
            "sha256": _sha256(dest),
            "path": _relpath(dest),
            "content_type": content_type,
        }
    )
    meta_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"  year={year} n={n} smoke={is_smoke} bytes={result['bytes']} → {result['path']}",
        flush=True,
    )
    return result


def write_file_inventory(out_root: Path, results: list[dict[str, Any]]) -> Path:
    """Light file_inventory.csv from fetch results (hashes, sizes)."""
    inv_dir = out_root.parent / "inventory"
    inv_dir.mkdir(parents=True, exist_ok=True)
    path = inv_dir / "file_inventory.csv"
    fields = [
        "year",
        "path",
        "is_smoke",
        "ok",
        "n_features",
        "bytes",
        "sha256",
        "cached",
        "fetched_at_utc",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(
                {
                    "year": r.get("year"),
                    "path": r.get("path"),
                    "is_smoke": r.get("is_smoke"),
                    "ok": r.get("ok"),
                    "n_features": r.get("n_features", ""),
                    "bytes": r.get("bytes", ""),
                    "sha256": r.get("sha256", ""),
                    "cached": r.get("cached", ""),
                    "fetched_at_utc": r.get("fetched_at_utc", ""),
                }
            )
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch REDIAM IF perimeters via WFS")
    ap.add_argument(
        "--years",
        default="2022,2023,2024,2025",
        help="Comma-separated years (default 2022-2025)",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Cache root directory",
    )
    ap.add_argument(
        "--count",
        type=int,
        default=None,
        help="Optional WFS COUNT limit (smoke only; writes under _smoke/, never full year)",
    )
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--force", action="store_true", help="Re-download even if cached")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any requested year failed (default: any year fail → non-zero)",
    )
    args = ap.parse_args()

    years = [int(y.strip()) for y in args.years.split(",") if y.strip()]
    out_root = args.out if args.out.is_absolute() else ROOT / args.out
    out_root.mkdir(parents=True, exist_ok=True)

    print(f"REDIAM WFS fetch → {out_root}", flush=True)
    print(f"Attribution: {ATTRIBUTION}", flush=True)

    results: list[dict[str, Any]] = []
    for y in years:
        results.append(
            fetch_year(
                y,
                out_root,
                count=args.count,
                timeout=args.timeout,
                force=args.force,
            )
        )

    inv_path = write_file_inventory(out_root, results)

    summary = {
        "schema": "rediam_wfs_fetch_v1",
        "built_at_utc": _utc(),
        "wfs_base": WFS_BASE,
        "attribution": ATTRIBUTION,
        "years": years,
        "out": _relpath(out_root),
        "results": results,
        "n_ok": sum(1 for r in results if r.get("ok")),
        "n_fail": sum(1 for r in results if not r.get("ok")),
        "file_inventory": _relpath(inv_path),
    }
    summary_path = out_root / "fetch_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "n_ok": summary["n_ok"],
                "n_fail": summary["n_fail"],
                "summary": str(summary_path),
                "file_inventory": summary["file_inventory"],
            },
            indent=2,
        )
    )
    # Strict multi-year: any fail → non-zero (industrial default)
    if not years:
        return 1
    if summary["n_fail"] > 0:
        return 1
    if summary["n_ok"] == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
