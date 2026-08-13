"""Open CC-BY progression/ROS pack catalog, inventory, and honesty helpers.

Downloads live under data/external/<pack>/ (gitignored rasters/zips).
Does not invent product Vp/ha/IoU/ROS, does not flip release flags,
does not treat CEMS/EFFIS/GOFER/PT-FireSprd as official ES cadastre.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

INVENTORY_SCHEMA = "wfd_external_ros_inventory_v1"
CALDOR_KML_RE = re.compile(
    r"Caldor_(\d{4})_(\d{2})_(\d{2})T(\d{2})_(\d{2})_(\d{2})",
    re.IGNORECASE,
)

PACK_CATALOG: dict[str, dict[str, Any]] = {
    "pt_firesprd": {
        "pack_id": "pt_firesprd",
        "title": "Portuguese Large Wildfire Spread Database (PT-FireSprd)",
        "requested_doi": "10.5281/zenodo.7495506",
        "requested_record": "7495506",
        "resolved_record": "7495506",
        "resolved_doi": "10.5281/zenodo.7495506",
        "url": "https://zenodo.org/records/7495506",
        "api_url": "https://zenodo.org/api/records/7495506",
        "download_url": (
            "https://zenodo.org/api/records/7495506/files/PT-FireSprd_v0.08.zip/content"
        ),
        "zip_name": "PT-FireSprd_v0.08.zip",
        "md5": "4d248b3f5c006c41dbaeae9e512493f6",
        "license_id": "cc-by-4.0",
        "version": "0.08",
        "role": "open_progression_ros_vectors",
        "class": "ml_weak",
        "not_official_es_cadastre": True,
        "not_tactical_ros": True,
        "dataset_ros_is_author_attribute": True,
    },
    "gofer": {
        "pack_id": "gofer",
        "title": "GOES-Observed Fire Event Representation (GOFER)",
        "requested_doi": "10.5281/zenodo.8327264",
        "requested_record": "8327264",
        "resolved_record": "14642378",
        "resolved_doi": "10.5281/zenodo.14642378",
        "url": "https://zenodo.org/records/14642378",
        "concept_url": "https://zenodo.org/records/8327264",
        "api_url": "https://zenodo.org/api/records/8327264",
        "download_url": ("https://zenodo.org/api/records/14642378/files/GOFER.zip/content"),
        "zip_name": "GOFER.zip",
        "md5": "8d495af1e4a0ed77df35b5a15d5ebb04",
        "license_id": "cc-by-4.0",
        "version": "0.2",
        "role": "open_hourly_goes_progression",
        "class": "ml_weak",
        "not_official_es_cadastre": True,
        "not_tactical_ros": True,
        "dataset_ros_is_author_attribute": True,
        "note": ("Concept DOI 10.5281/zenodo.8327264 resolves to version 0.2 record 14642378."),
    },
}

SKIP_NAME_PARTS = frozenset({"__macosx", ".ds_store"})


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def md5_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def pack_root(repo_root: Path, pack_id: str) -> Path:
    return Path(repo_root) / "data" / "external" / pack_id


def extracted_root(repo_root: Path, pack_id: str) -> Path:
    return pack_root(repo_root, pack_id) / "extracted"


def _skip_extracted(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & SKIP_NAME_PARTS:
        return True
    return path.name.startswith("._") or path.name.lower() == ".ds_store"


def list_extracted_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*") if p.is_file() and not _skip_extracted(p))


def file_record(
    path: Path,
    *,
    rel_root: Path,
    sha256: bool = True,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "rel": str(path.relative_to(rel_root)).replace("\\", "/"),
        "bytes": int(path.stat().st_size),
        "suffix": path.suffix.lower(),
    }
    if sha256:
        rec["sha256"] = sha256_file(path)
    if extra:
        rec.update(extra)
    return rec


def parse_gofer_fire_catalog(csv_path: Path) -> list[dict[str, Any]]:
    """Parse GOFER fireData.csv. acres_official is author/catalog, not our ha."""
    rows: list[dict[str, Any]] = []
    if not csv_path.is_file():
        return rows
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for raw in reader:
            name = str(raw.get("fname") or "").strip()
            if not name:
                continue
            year_raw = str(raw.get("fyear") or "").strip()
            try:
                year = int(year_raw)
            except ValueError:
                year = None
            acres_raw = str(raw.get("acres_official") or "").strip()
            try:
                acres = float(acres_raw)
            except ValueError:
                acres = None
            rows.append(
                {
                    "fname": name,
                    "fyear": year,
                    "acres_official_catalog": acres,
                    "acres_official_is_author_catalog": True,
                    "not_product_area_ha": True,
                    "goes_ig_utc": str(raw.get("GOESIg_UTC") or "").strip() or None,
                    "local_tz": str(raw.get("local_tz") or "").strip() or None,
                }
            )
    return rows


def inventory_gofer_hourly_counts(shp_path: Path) -> dict[str, Any]:
    """Count unique hourly tUTC per fire from fireProg dbf (no ROS invented)."""
    try:
        import shapefile
    except ImportError:
        return {"ok": False, "reason": "pyshp_missing", "fires": []}
    if not shp_path.is_file():
        return {"ok": False, "reason": f"missing:{shp_path}", "fires": []}

    by_fire: dict[str, set[str]] = {}
    n_records = 0
    reader = shapefile.Reader(str(shp_path))
    for rec in reader.iterRecords():
        data = rec.as_dict() if hasattr(rec, "as_dict") else {}
        fname = str(data.get("fname") or "").strip()
        t_utc = str(data.get("tUTC") or "").strip()
        if not fname:
            continue
        n_records += 1
        by_fire.setdefault(fname, set())
        if t_utc:
            by_fire[fname].add(t_utc)
    fires = [
        {
            "fname": name,
            "n_hourly_tutcs": len(times),
            "r1_ge3_hourly": len(times) >= 3,
        }
        for name, times in sorted(by_fire.items())
    ]
    return {
        "ok": True,
        "shp": str(shp_path),
        "n_records": n_records,
        "n_fires": len(fires),
        "n_fires_r1_ge3": sum(1 for f in fires if f["r1_ge3_hourly"]),
        "fires": fires,
        "not_product_ros": True,
        "not_geotiff_contract": True,
        "reason_no_geotiff": (
            "GOFER ships hourly WGS84 polygons (fireProg), not ≥3 aligned "
            "GeoTIFF scenes. Native rasters absent. Rasterizing 20k GOES "
            "polygons is out of this pass; PT-FireSprd L1 is the GeoTIFF path."
        ),
    }


def inventory_path_counts(root: Path, *, max_files: int = 64) -> dict[str, Any]:
    """Count files/bytes under a staged external tree without opening payloads."""
    if not root.is_dir():
        return {"ok": False, "reason": f"missing:{root}", "n_files": 0, "bytes": 0}
    n_files = 0
    total = 0
    sample: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        n_files += 1
        size = int(path.stat().st_size)
        total += size
        if len(sample) < max_files:
            sample.append(
                {
                    "rel": str(path.relative_to(root)).replace("\\", "/"),
                    "bytes": size,
                    "suffix": path.suffix.lower(),
                }
            )
    return {
        "ok": True,
        "path": str(root).replace("\\", "/"),
        "n_files": n_files,
        "bytes": total,
        "sample": sample,
    }


def inventory_cfsds_pack(repo_root: Path) -> dict[str, Any]:
    """Read staged CFSDS OSF inventory. Author sprdistm/firearea stay unused."""
    inv_path = Path(repo_root) / "data" / "external" / "cfsds" / "inventory.json"
    if not inv_path.is_file():
        return {
            "ok": False,
            "status": "not_staged",
            "reason": "data/external/cfsds/inventory.json missing",
            "not_product_ros": True,
        }
    try:
        inv = json.loads(inv_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "status": "unreadable", "reason": str(exc), "not_product_ros": True}
    groups = inv.get("used_groups_2023") or {}
    geotiff = inv.get("geotiff_contract") or {}
    return {
        "ok": True,
        "status": "catalogs_staged",
        "inventory": "data/external/cfsds/inventory.json",
        "url": inv.get("url"),
        "license_id": inv.get("license_id"),
        "osf_doi": inv.get("requested_doi"),
        "paper_doi": inv.get("paper_doi"),
        "n_downloaded_files": inv.get("n_downloaded_files"),
        "downloaded_bytes": inv.get("downloaded_bytes"),
        "n_raster_years_listed_not_downloaded": len(inv.get("osf_listing", {}).get("raster_years") or []),
        "groups_2023_n_rows": groups.get("n_rows"),
        "groups_2023_n_fires": groups.get("n_unique_ID"),
        "groups_2023_n_fires_ge3_days": groups.get("n_IDs_with_ge3_rows"),
        "geotiff_skipped": True,
        "skip_reason": geotiff.get("reason"),
        "used_as": "catalog_plus_2023_groups_count",
        "not_product_ros": True,
        "not_official_es_cadastre": True,
    }


def inventory_nirops_mendeley() -> dict[str, Any]:
    """Honest skip: Mendeley 95rj5d379g has no unauthenticated file list."""
    return {
        "ok": False,
        "status": "not_run",
        "dataset": "95rj5d379g",
        "doi": "10.17632/95rj5d379g.1",
        "url": "https://data.mendeley.com/datasets/95rj5d379g/1",
        "reason": (
            "Mendeley public-api /datasets/95rj5d379g/files returned HTTP 400; "
            "/1/files returned 404; api.mendeley.com/datasets/.../files returned "
            "401 oauth/NOT_AUTHORIZED. No unauthenticated file URL. Not downloaded."
        ),
        "not_product_ros": True,
    }


def inventory_ndws_kaggle_proxy(repo_root: Path) -> dict[str, Any]:
    """Inventory staged NDWS proxy (product smoke only; no retrain)."""
    root = Path(repo_root) / "data" / "external" / "wildfirespreadts"
    proxy = root / "ndws_kaggle_proxy"
    counts = inventory_path_counts(proxy)
    pdf = root / "WildfireSpreadTS_Documentation.pdf"
    return {
        "ok": counts.get("ok", False),
        "full_zip_staged": False,
        "full_zip_bytes_reported": 48_359_000_000,
        "reason_full_zip_not_staged": "WildfireSpreadTS.zip ~48 GB; not needed this pass",
        "documentation_pdf_exists": pdf.is_file(),
        "documentation_pdf_bytes": int(pdf.stat().st_size) if pdf.is_file() else 0,
        "proxy": counts,
        "used_as": "inventory_only_no_retrain",
        "not_product_ros": True,
        "not_clm_v34_retrain": True,
    }


def inventory_caldor_kml(kml_dir: Path) -> dict[str, Any]:
    """Inventory FireBench Caldor 2021 dated KMLs already on disk."""
    if not kml_dir.is_dir():
        return {"ok": False, "reason": f"missing:{kml_dir}", "files": []}
    files: list[dict[str, Any]] = []
    dated: list[str] = []
    for path in sorted(kml_dir.glob("*.kml")):
        match = CALDOR_KML_RE.search(path.name)
        stamp = None
        if match:
            y, mo, d, h, mi, s = match.groups()
            stamp = f"{y}-{mo}-{d}T{h}:{mi}:{s}"
            dated.append(stamp)
        files.append(
            {
                "file": path.name,
                "bytes": int(path.stat().st_size),
                "parsed_stamp": stamp,
                "is_mtbs_perimeter": "perimeter_mtbs" in path.name.lower(),
            }
        )
    return {
        "ok": True,
        "path": str(kml_dir).replace("\\", "/"),
        "n_kml": len(files),
        "n_dated": len(dated),
        "r1_ge3_dated_kml": len(dated) >= 3,
        "dates": dated,
        "files": files,
        "native_geotiff": False,
        "h5_is_benchmark_not_geotiff_contract": True,
        "not_product_ros": True,
        "class": "context_only",
        "note": (
            "Dated KMLs satisfy a vector R1 count; they are not aligned "
            "GeoTIFF scenes under GEOTIFF_INPUT_CONTRACT. Not used as Vp/ROS."
        ),
    }


def write_pack_readme(dest: Path, spec: dict[str, Any], inventory: dict[str, Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    zip_rec = inventory.get("zip") or {}
    lines = [
        f"# {spec['title']}",
        "",
        f"- Pack id: `{spec['pack_id']}`",
        f"- License: `{spec['license_id']}`",
        f"- Version: `{spec.get('version')}`",
        f"- Requested DOI: `{spec['requested_doi']}`",
        f"- Resolved DOI: `{spec.get('resolved_doi')}`",
        f"- URL: {spec.get('url')}",
        f"- Zip: `{spec['zip_name']}` · md5 `{spec['md5']}`",
        f"- Zip sha256: `{zip_rec.get('sha256')}`",
        f"- Zip bytes: {zip_rec.get('bytes')}",
        "",
        "## Use in WildfireFrontDynamics",
        "",
        "- Lab / research open data only.",
        "- Decision support ≠ tactical dispatch.",
        "- CEMS/EFFIS/GOFER/PT-FireSprd ≠ official ES cadastre / O2.",
        "- Author ROS / acres fields stay author attributes. Not product ROS/Vp/ha.",
        "- Does not lift FREEZE_ML, flip GO_Q, promote Hellín, or retrain v34.",
        "",
        "## Non-claims",
        "",
        "- Not field_ops GO from this pack.",
        "- Not official burned-area cadastre.",
        "- Not invented IoU/ROS.",
        "",
        f"Inventory schema: `{INVENTORY_SCHEMA}`",
        "",
    ]
    dest.write_text("\n".join(lines), encoding="utf-8")


def build_zip_inventory(
    repo_root: Path,
    pack_id: str,
    *,
    hash_extracted: bool = False,
) -> dict[str, Any]:
    spec = PACK_CATALOG[pack_id]
    root = pack_root(repo_root, pack_id)
    zip_path = root / spec["zip_name"]
    ext = extracted_root(repo_root, pack_id)
    zip_rec: dict[str, Any] | None = None
    md5_ok: bool | None = None
    if zip_path.is_file():
        zip_rec = file_record(zip_path, rel_root=root, extra={"role": "zenodo_zip"})
        zip_rec["md5"] = md5_file(zip_path)
        md5_ok = zip_rec["md5"] == spec["md5"]
        zip_rec["md5_matches_zenodo"] = md5_ok
    extracted = []
    for path in list_extracted_files(ext):
        extracted.append(
            file_record(
                path,
                rel_root=ext,
                sha256=hash_extracted and path.stat().st_size < 8_000_000,
            )
        )
    return {
        "schema": INVENTORY_SCHEMA,
        "pack_id": pack_id,
        "as_of_utc": utc_now(),
        "title": spec["title"],
        "license_id": spec["license_id"],
        "requested_doi": spec["requested_doi"],
        "resolved_doi": spec.get("resolved_doi"),
        "url": spec.get("url"),
        "download_url": spec["download_url"],
        "version": spec.get("version"),
        "class": spec.get("class"),
        "role": spec.get("role"),
        "not_official_es_cadastre": True,
        "not_tactical_ros": True,
        "not_product_ros": True,
        "zip": zip_rec,
        "zip_md5_ok": md5_ok,
        "extracted_root": (
            str(ext.resolve().relative_to(Path(repo_root).resolve())).replace("\\", "/")
            if ext.exists() and ext.resolve().is_relative_to(Path(repo_root).resolve())
            else (str(ext).replace("\\", "/") if ext.exists() else None)
        ),
        "n_extracted_files": len(extracted),
        "extracted_files": extracted,
    }
