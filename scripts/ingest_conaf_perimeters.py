#!/usr/bin/env python3
"""Ingest CONAF SHP/GPKG/GeoJSON into a CL_CONAF_* ml_weak pack.

Does not flip product rails. lab_ok_conaf stays false unless --cession-evidence
passes the same file-level rules as record_conaf_cession.py. Never writes
docs/data_campaigns/conaf_send/send_status.json.

  python scripts/ingest_conaf_perimeters.py --vector perimeters.shp --event NACIMIENTO2023
  python scripts/ingest_conaf_perimeters.py --vector p.gpkg --event X --cession-evidence oficio.txt

Exit:
  0 — pack written
  1 — missing vector / rasterize fail
  2 — usage
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    LICENSE_ID_CONAF_PENDING,
    RIGHTS_DOC,
    cession_evidence_ok,
    geoms_from_geojson,
    is_allowed_pack_path,
    pack_dir_for,
    rasterize_geom_to_geotiff,
    sha256_file,
    source_pack_ready,
    utc_now,
    write_label_geojson,
)

INGEST_SCHEMA = "wfd_conaf_ingest_v1"
DATED_RE = re.compile(r"^\d{8}_\d{6}$")


def _sanitize_event(raw: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in raw.strip())
    text = text.strip("_") or "EVENT"
    if not text.upper().startswith("CL_CONAF_"):
        text = f"CL_CONAF_{text}"
    return text.upper().replace("-", "_")


def sanitize_dated(raw: str) -> tuple[str | None, str]:
    """Accept YYYYMMDD_HHMMSS or [A-Za-z0-9_]. Reject path separators / `..`."""
    text = str(raw or "").strip()
    if not text:
        return None, "dated_empty"
    if ".." in text or "/" in text or "\\" in text:
        return None, "dated_path_unsafe"
    if DATED_RE.match(text):
        return text, "ok"
    cleaned = "".join(ch for ch in text if ch.isalnum() or ch == "_")
    if not cleaned or cleaned != text:
        return None, "dated_invalid"
    return cleaned, "ok"


def _dest_inside_pack(dest: Path, pack: Path) -> bool:
    try:
        dest.resolve().relative_to(pack.resolve())
        return True
    except (OSError, ValueError):
        return False


def _load_geoms(vector: Path) -> list[Any]:
    suffix = vector.suffix.lower()
    if suffix in {".json", ".geojson"}:
        data = json.loads(vector.read_text(encoding="utf-8"))
        return geoms_from_geojson(data)
    try:
        import fiona
        from shapely.geometry import shape
    except ImportError as exc:
        raise RuntimeError(
            "fiona_unavailable: SHP/GPKG ingest needs fiona. Use GeoJSON or install fiona."
        ) from exc
    geoms = []
    with fiona.open(vector) as src:
        for feat in src:
            if not feat:
                continue
            g = feat.get("geometry")
            if not g:
                continue
            try:
                geoms.append(shape(g))
            except Exception:
                continue
    return [g for g in geoms if g is not None and not g.is_empty]


def ingest_conaf(
    vector: Path,
    *,
    event: str,
    data_root: Path,
    cession_evidence: Path | None = None,
    signer: str = "",
    crs_epsg: int = 32719,
    gsd_m: float = 30.0,
    dated: str = "20230101_000000",
) -> dict[str, Any]:
    dated_ok, dated_reason = sanitize_dated(dated)
    if dated_ok is None:
        return {"ok": False, "error": dated_reason, "lab_ok_conaf": False}
    dated = dated_ok
    event_id = _sanitize_event(event)
    spec = {
        "event_id": event_id,
        "region": "cl",
        "country": "CL",
        "activation": "CONAF",
        "aoi": "CONAF",
        "aoi_name": event_id,
        "year": int(dated[:4]) if dated[:4].isdigit() else 2023,
        "class": "ml_weak",
        "label_level": "L2_pending_cession",
        "license_id": LICENSE_ID_CONAF_PENDING,
        "crs_epsg": int(crs_epsg),
        "gsd_m": float(gsd_m),
        "portal_url": "https://www.conaf.cl/",
    }
    pack = pack_dir_for(data_root, spec)
    try:
        under_repo = pack.resolve().is_relative_to(ROOT.resolve())
    except (OSError, ValueError):
        under_repo = False
    if under_repo and not is_allowed_pack_path(pack, repo_root=ROOT):
        return {"ok": False, "error": f"pack_path_not_allowlisted:{pack}", "lab_ok_conaf": False}
    if pack.name != event_id or pack.parent.name != spec["region"]:
        return {"ok": False, "error": f"bad_pack_layout:{pack}", "lab_ok_conaf": False}

    geoms = _load_geoms(Path(vector))
    if not geoms:
        return {"ok": False, "error": "no_geometry_in_vector", "lab_ok_conaf": False}

    from shapely.ops import unary_union

    union = unary_union(geoms)
    labels_dir = pack / "labels"
    tif_name = f"{event_id}_{dated}.tif"
    dest = labels_dir / tif_name
    gj_name = f"{event_id}_{dated}.geojson"
    gj_dest = labels_dir / gj_name
    if not _dest_inside_pack(dest, pack) or not _dest_inside_pack(gj_dest, pack):
        return {"ok": False, "error": "dated_escapes_pack", "lab_ok_conaf": False}
    labels_dir.mkdir(parents=True, exist_ok=True)
    rast = rasterize_geom_to_geotiff(union, dest, epsg=int(crs_epsg), gsd_m=float(gsd_m))
    write_label_geojson(
        union,
        labels_dir / gj_name,
        {
            "event_id": event_id,
            "source": "CONAF ingest stub",
            "not_national_cadastre": True,
            "lab_ok_conaf": False,
        },
    )

    ev_ok, ev_reason = cession_evidence_ok(cession_evidence)
    lab_ok = bool(ev_ok)
    evidence_rec: dict[str, Any] | None = None
    if cession_evidence is not None and ev_ok:
        ev_dir = pack / "cession"
        dest_ev = ev_dir / Path(cession_evidence).name
        if not _dest_inside_pack(dest_ev, pack):
            return {"ok": False, "error": "evidence_escapes_pack", "lab_ok_conaf": False}
        ev_dir.mkdir(parents=True, exist_ok=True)
        dest_ev.write_bytes(Path(cession_evidence).read_bytes())
        evidence_rec = {
            "rel": f"cession/{dest_ev.name}",
            "sha256": sha256_file(dest_ev),
            "bytes": dest_ev.stat().st_size,
            "signer": signer or None,
        }
    elif cession_evidence is not None:
        lab_ok = False

    geotiffs = [
        {
            "rel": f"labels/{tif_name}",
            "file": tif_name,
            "role": "label_burned_conaf_rasterized",
            "delivery_utc": f"{dated[:4]}-{dated[4:6]}-{dated[6:8]}T{dated[9:11]}:{dated[11:13]}:{dated[13:15]}Z"
            if len(dated) >= 15
            else None,
            "crs": rast["crs"],
            "gsd_m": rast["gsd_m"],
            "width": rast["width"],
            "height": rast["height"],
            "positive_pixels": rast["positive_pixels"],
            "sha256": sha256_file(dest),
        }
    ]
    meta = {
        "schema": "wfd_open_if_pack_meta_v1",
        "event_id": event_id,
        "region": "cl",
        "country": "CL",
        "activation": "CONAF",
        "license_id": LICENSE_ID_CONAF_PENDING,
        "rights_doc": RIGHTS_DOC,
        "crs": f"EPSG:{int(crs_epsg)}",
        "gsd_m": float(gsd_m),
        "class": "ml_weak",
        "label_level": "L2_pending_cession",
        "geotiffs": geotiffs,
        "labels": [{"rel": f"labels/{tif_name}", "kind": "conaf_perimeter_raster"}],
        "not_national_cadastre": True,
        "not_lwir": True,
        "not_o2_es": True,
        "not_grade_a": True,
        "not_tactical_ros": True,
        "lab_ok_conaf": lab_ok,
        "lab_ok_provisional": False,
        "cession_evidence_ok": ev_ok,
        "cession_evidence_reason": ev_reason,
        "cession_evidence": evidence_rec,
        "ingest_schema": INGEST_SCHEMA,
        "built_at_utc": utc_now(),
        "not_claims": [
            "not CONAF official until written cession + product rail",
            "not GO_Q complete",
            "not FREEZE lift",
            "this pack flag is not send_status.json / product lab_ok_conaf",
        ],
    }
    (pack / "meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (pack / "README.md").write_text(
        f"# {event_id}\n\nCONAF ingest stub. `lab_ok_conaf={str(lab_ok).lower()}`. "
        "Does not flip product rails. ml_weak only.\n",
        encoding="utf-8",
    )
    ready, ready_reason = source_pack_ready(pack)
    return {
        "ok": True,
        "event_id": event_id,
        "pack_dir": str(pack).replace("\\", "/"),
        "lab_ok_conaf": lab_ok,
        "cession_evidence_reason": ev_reason,
        "source_pack_ready": ready,
        "source_pack_reason": ready_reason,
        "n_geoms": len(geoms),
        "positive_pixels": rast["positive_pixels"],
        "product_rails_untouched": True,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest CONAF perimeters to CL_CONAF_* pack")
    ap.add_argument("--vector", type=Path, required=True, help="SHP / GPKG / GeoJSON")
    ap.add_argument("--event", required=True, help="Event slug → CL_CONAF_<EVENT>")
    ap.add_argument("--data-root", type=Path, default=ROOT / "data" / "open_if" / "latam_au")
    ap.add_argument("--cession-evidence", type=Path, default=None)
    ap.add_argument("--signer", default="")
    ap.add_argument("--crs-epsg", type=int, default=32719)
    ap.add_argument("--gsd-m", type=float, default=30.0)
    ap.add_argument("--dated", default="20230101_000000")
    args = ap.parse_args(argv)

    if not Path(args.vector).is_file():
        print(f"error: vector missing: {args.vector}", file=sys.stderr)
        return 1
    try:
        row = ingest_conaf(
            Path(args.vector),
            event=str(args.event),
            data_root=Path(args.data_root),
            cession_evidence=args.cession_evidence,
            signer=str(args.signer),
            crs_epsg=int(args.crs_epsg),
            gsd_m=float(args.gsd_m),
            dated=str(args.dated),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"error: {type(exc).__name__}:{exc}", file=sys.stderr)
        return 1
    print(json.dumps(row, indent=2))
    return 0 if row.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
