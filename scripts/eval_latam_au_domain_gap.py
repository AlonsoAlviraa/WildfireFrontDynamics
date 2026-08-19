#!/usr/bin/env python3
"""F4 domain-gap scorecard (wfd_ml_domain_gap_v1). Honesty first.

CLM ensemble expects NDWS 17-ch sequences. CEMS rasterized burned masks
(and optional S2 NBR windows) are a different input contract. This script:

1. Cites sealed CLM TEST IoU from docs/ML_PRODUCT_SCORECARD.json.
2. Measures pack geometry (n GeoTIFF, area_ha, successive CEMS mask IoU).
3. Attempts STAC dNBR vs last CEMS mask only if S2 NBR + CEMS raster exist
   and can be compared without inventing alignment — otherwise records blocked.
4. Does **not** run clm_ensemble_v34 on these rasters (would invent IoU).
5. Does **not** flip GO_Q / FREEZE / fusion.

  python scripts/eval_latam_au_domain_gap.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    DOMAIN_GAP_SCHEMA,
    empty_domain_row,
    load_clm_sealed_test,
    pack_dir_for,
    successive_mask_ious,
    utc_now,
    validate_domain_gap,
    warp_proxy_from_pack,
)

P0_AU = "AU_EMSR500_PERTH"
P0_LATAM = "CL_EMSR647_NACIMIENTO"
P1_EXTRA = (
    "AU_EMSR408_NSW",
    "CL_EMSR715_VALPARAISO",
    "BR_PANTANAL_2020_MAPBIOMAS",
    "AU_NAFI_NT_SEASON_2023",
)


def _read_meta(pack_dir: Path) -> dict[str, Any] | None:
    p = pack_dir / "meta.json"
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _load_uint_mask(path: Path) -> np.ndarray:
    import rasterio

    with rasterio.open(path) as ds:
        return np.asarray(ds.read(1))


def pack_geometry_metrics(pack_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    label_tifs = [
        pack_dir / rec["rel"]
        for rec in (meta.get("geotiffs") or [])
        if str(rec.get("role") or "").startswith("label_")
        and rec.get("rel")
        and (pack_dir / rec["rel"]).is_file()
    ]
    arrays = []
    areas = []
    for rec in meta.get("geotiffs") or []:
        if rec.get("area_ha") is not None:
            areas.append(float(rec["area_ha"]))
    for p in label_tifs:
        try:
            arrays.append(_load_uint_mask(p))
        except Exception:
            continue
    succ = successive_mask_ious(arrays) if len(arrays) >= 2 else []
    label_level = str(meta.get("label_level") or "")
    if label_level.startswith("L1"):
        iou_note = (
            "successive_mask_iou is label-vs-label on annual/seasonal windows "
            "(MapBiomas/NAFI), NOT model IoU and NOT transfer performance."
        )
    else:
        iou_note = (
            "successive_cems_mask_iou is label-vs-label (same CEMS stack), "
            "NOT model IoU and NOT transfer performance."
        )
    return {
        "n_geotiff_meta": len(meta.get("geotiffs") or []),
        "n_label_tif_on_disk": len(label_tifs),
        "area_ha_by_product": areas,
        "area_ha_max": max(areas) if areas else None,
        "area_ha_min": min(areas) if areas else None,
        "successive_cems_mask_iou": succ,
        "mean_successive_mask_iou": (
            float(np.mean([r["mask_iou"] for r in succ if r.get("mask_iou") is not None]))
            if any(r.get("mask_iou") is not None for r in succ)
            else None
        ),
        "note": iou_note,
    }


def attempt_dnbr_proxy(pack_dir: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """Optional S2 NBR vs CEMS mask overlap. Not model IoU."""
    label_crs = str(meta.get("crs") or "")
    label_level = str(meta.get("label_level") or "")
    # Same-CRS L1 annual windows still have no audited NBR threshold or date match.
    if label_level.startswith("L1") or (
        "4326" in label_crs and label_level.startswith("L1")
    ):
        return {
            "status": "blocked_no_audited_threshold",
            "reason": (
                "S2 NBR and L1 annual burned windows may share a geographic CRS, "
                "but there is no audited NBR threshold / resample / date-match. "
                "Refusing proxy IoU rather than invent one."
            ),
            "metric": "nbr_vs_annual_burned_iou",
            "value": None,
            "n_s2_windows": len([r for r in (meta.get("stac_eo") or []) if r.get("status") == "ok"]),
        }
    stored = warp_proxy_from_pack(pack_dir)
    if stored is not None:
        return stored
    eo = [r for r in (meta.get("stac_eo") or []) if r.get("status") == "ok"]
    if not eo:
        return {
            "status": "not_run",
            "reason": "no_stac_s2_nbr_in_pack",
            "metric": "dnbr_or_nbr_vs_cems",
            "value": None,
        }
    # Comparing S2 NBR (EPSG:4326 window) to UTM CEMS raster without a
    # controlled warp would invent an IoU. Refuse rather than fake alignment.
    return {
        "status": "blocked_crs_mismatch",
        "reason": (
            "S2 NBR windows are EPSG:4326; CEMS labels are projected UTM. "
            "No audited warp/resample in this F4 pass. Refusing proxy IoU."
        ),
        "metric": "nbr_vs_cems_iou",
        "value": None,
        "n_s2_windows": len(eo),
    }


def domain_row(event_id: str, data_root: Path) -> dict[str, Any]:
    spec = ALL_PACK_SPECS[event_id]
    row = empty_domain_row(event_id, spec["region"])
    pack_dir = pack_dir_for(data_root, spec)
    meta = _read_meta(pack_dir)
    if meta is None:
        row["eval_status"] = "blocked_pack_missing"
        row["reason"] = f"missing {pack_dir / 'meta.json'}"
        return row
    geom = pack_geometry_metrics(pack_dir, meta)
    proxy = attempt_dnbr_proxy(pack_dir, meta)
    n_tif = int(geom["n_label_tif_on_disk"])
    kind = str(spec.get("source_kind") or "cems")
    if kind.startswith("mapbiomas") or kind.startswith("nafi"):
        tensor_note = "L1 annual/seasonal burned GeoTIFF (MapBiomas/NAFI window) ± optional S2 NBR"
    else:
        tensor_note = "CEMS rasterized burned-area GeoTIFF (± optional S2 NBR)"
    row.update(
        {
            "eval_status": "blocked_incompatible_schema",
            "model_iou": None,
            "n": 0,
            "reason": (
                "clm_ensemble_v34 expects NDWS 17-channel sequences "
                f"(legacy17 / holdout_v1 NPZ). This pack is {tensor_note}. "
                "Running the UNet on these rasters would invent IoU. Geometry metrics only."
            ),
            "class": meta.get("class"),
            "label_level": meta.get("label_level"),
            "source_kind": kind,
            "n_geotiff": geom["n_geotiff_meta"],
            "n_label_tif": n_tif,
            "pack_dir": str(
                pack_dir.relative_to(ROOT) if pack_dir.is_relative_to(ROOT) else pack_dir
            ).replace("\\", "/"),
            "pack_metrics": geom,
            "stac_proxy": proxy,
        }
    )
    return row


def build_scorecard(data_root: Path) -> dict[str, Any]:
    clm = load_clm_sealed_test()
    au = domain_row(P0_AU, data_root)
    latam = domain_row(P0_LATAM, data_root)
    extra = [domain_row(eid, data_root) for eid in P1_EXTRA]
    doc: dict[str, Any] = {
        "schema": DOMAIN_GAP_SCHEMA,
        "as_of_utc": utc_now(),
        "product_id": clm.get("product_id") or "clm_ensemble_v34",
        "protocol": "latam_au_domain_gap_v1",
        "campaign": "LATAM_AU",
        "rails": {
            "freeze_intact": True,
            "go_q": "partial",
            "field_ops_fusion": "ON",
            "tobarra_keep_reopen": False,
            "iou_is_not_ros": True,
            "no_retrain": True,
        },
        "clm_test": {
            "region": "CLM",
            "eval_status": "sealed",
            "iou": clm.get("iou"),
            "n": clm.get("n"),
            "selective_iou_80": clm.get("selective_iou_80"),
            "ece_patch_conf": clm.get("ece_patch_conf"),
            "source": clm.get("source"),
            "split": "test",
            "protocol": clm.get("protocol"),
            "note": clm.get("note"),
        },
        "au": au,
        "latam": latam,
        "extra_packs": extra,
        "zero_shot": {
            "status": "not_run",
            "model": "clm_ensemble_v34",
            "model_iou": None,
            "attempted": False,
            "reason": (
                "Input contract mismatch (NDWS 17-ch vs CEMS 1-band burned mask). "
                "Honesty: do not zero-shot the UNet on incompatible tensors."
            ),
        },
        "gap_table": {
            "iou_clm_test": clm.get("iou"),
            "iou_au": None,
            "iou_latam": None,
            "note": (
                "AU/LATAM/P1 extra model IoU are null by design in this F4 pass. "
                "Do not fill with successive CEMS/weak mask IoU or dNBR."
            ),
            "extra_event_ids": list(P1_EXTRA),
        },
        "not_claims": [
            "not model IoU on AU/LATAM",
            "not ROS / Vp",
            "not FREEZE lift",
            "not GO_Q complete",
            "not fusion change",
            "not O2 / grade A / CONAF official",
            "not ml_strong",
            "successive CEMS mask IoU is not transfer IoU",
        ],
    }
    fails = validate_domain_gap(doc)
    if fails:
        raise RuntimeError(f"domain-gap scorecard invalid: {fails}")
    return doc


def _preserve_product_sections(doc: dict[str, Any], existing_paths: list[Path]) -> dict[str, Any]:
    """Keep product_e2e / ml_export measured sections if already written by E2E scripts."""
    for path in existing_paths:
        if not path.is_file():
            continue
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for key in ("product_e2e", "ml_export"):
            if key not in prev:
                continue
            if key not in doc or (isinstance(prev[key], dict) and not doc.get(key)):
                doc[key] = prev[key]
    return doc


def main() -> int:
    ap = argparse.ArgumentParser(description="LATAM/AU domain-gap scorecard")
    ap.add_argument(
        "--data-root",
        type=Path,
        default=ROOT / "data" / "open_if" / "latam_au",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "scorecards" / "wfd_ml_domain_gap_v1.json",
    )
    ap.add_argument(
        "--docs-copy",
        type=Path,
        default=ROOT / "docs" / "data_campaigns" / "LATAM_AU_DOMAIN_GAP_SCORECARD.json",
    )
    args = ap.parse_args()
    doc = build_scorecard(args.data_root)
    doc = _preserve_product_sections(doc, [args.docs_copy, args.output])
    # Also pull from product E2E report if present and section missing
    e2e_report = ROOT / "outputs" / "open_if" / "latam_au_e2e" / "product_e2e_report.json"
    if "product_e2e" not in doc and e2e_report.is_file():
        try:
            pe = json.loads(e2e_report.read_text(encoding="utf-8"))
            doc["product_e2e"] = {
                "schema": pe.get("schema"),
                "as_of_utc": pe.get("as_of_utc"),
                "ok": pe.get("ok"),
                "n_ok": pe.get("n_ok"),
                "n_packs": pe.get("n_packs"),
                "rails": pe.get("rails"),
                "decisions": [
                    {
                        "event_id": p.get("event_id"),
                        "decision": p.get("decision"),
                        "latency_ms": p.get("latency_ms"),
                        "open_pack": p.get("open_pack"),
                        "open_source_available": p.get("open_source_available"),
                        "max_area_ha": (p.get("open_metrics") or {}).get("max_area_ha"),
                        "sidecars": p.get("sidecars"),
                    }
                    for p in pe.get("packs") or []
                ],
                "note": (
                    "Measured product decide path on bridged open_if packs. "
                    "HOLD/ABSTAIN without ops is valid. Not field validation."
                ),
            }
        except (OSError, json.JSONDecodeError):
            pass
    ml_sum = ROOT / "artifacts" / "latam_au_ml_export" / "export_summary.json"
    if "ml_export" not in doc and ml_sum.is_file():
        try:
            ms = json.loads(ml_sum.read_text(encoding="utf-8"))
            doc["ml_export"] = {
                "status": "exported_intermediate" if ms.get("ok") else "failed",
                "as_of_utc": ms.get("as_of_utc"),
                "compatible_with_clm_ensemble_v34": False,
                "contract": "cems_label_mask_patches_v1",
                "schema": ms.get("schema"),
                "packs": ms.get("packs"),
                "train_inventory": ms.get("train_inventory"),
                "note": (
                    "Intermediate CEMS mask patches only. model_iou remains null. "
                    "No retrain (FREEZE)."
                ),
            }
        except (OSError, json.JSONDecodeError):
            pass
    for dest in (args.output, args.docs_copy):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"wrote {dest}")
    print(
        json.dumps(
            {
                "schema": doc["schema"],
                "clm_iou": doc["clm_test"]["iou"],
                "au_status": doc["au"]["eval_status"],
                "latam_status": doc["latam"]["eval_status"],
                "zero_shot": doc["zero_shot"]["status"],
                "au_area_ha_max": (doc["au"].get("pack_metrics") or {}).get("area_ha_max"),
                "latam_area_ha_max": (doc["latam"].get("pack_metrics") or {}).get("area_ha_max"),
                "product_e2e_ok": (doc.get("product_e2e") or {}).get("ok"),
                "ml_export_status": (doc.get("ml_export") or {}).get("status"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
