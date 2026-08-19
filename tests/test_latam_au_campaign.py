"""F1 rights + F2 EMSR pack schema + F4 domain-gap (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    ALL_PACK_SPECS,
    DOMAIN_GAP_SCHEMA,
    EMSR_PACK_SPECS,
    LICENSE_ID,
    PACK_META_SCHEMA,
    RIGHTS_DOC,
    S3_BASE,
    binary_iou,
    build_pack_meta,
    cems_product_url_ok,
    dated_geotiff_ok,
    empty_domain_row,
    is_allowed_pack_path,
    load_clm_sealed_test,
    pack_dir_for,
    rasterize_geom_to_geotiff,
    successive_mask_ious,
    validate_domain_gap,
    validate_pack_meta,
)


def test_rights_doc_exists_and_cites_cems() -> None:
    path = ROOT / RIGHTS_DOC
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "terms-and-conditions" in text
    assert "EMSR500" in text
    assert "EMSR647" in text
    assert "Reg. (EU) 2021/696" in text or "2021/696" in text
    assert "lab_ok" in text.lower()
    assert "not" in text.lower() and "GO_Q" in text
    assert "CONAF" in text
    assert f"{S3_BASE}/EMSR500/" in text
    assert f"{S3_BASE}/EMSR647/" in text
    assert "EMSR408" in text
    assert "EMSR715" in text


def test_emsr_url_catalog_has_three_products_each() -> None:
    assert "AU_EMSR500_PERTH" in EMSR_PACK_SPECS
    assert "CL_EMSR647_NACIMIENTO" in EMSR_PACK_SPECS
    assert "AU_EMSR408_NSW" in EMSR_PACK_SPECS
    assert "CL_EMSR715_VALPARAISO" in EMSR_PACK_SPECS
    for eid, spec in EMSR_PACK_SPECS.items():
        assert len(spec["products"]) >= 3, eid
        for prod in spec["products"]:
            assert cems_product_url_ok(prod["url"]), (eid, prod["url"])
            assert dated_geotiff_ok(prod["dated"])
        assert spec["license_id"] == LICENSE_ID
        assert spec["class"] == "ml_weak"
    # Legacy S3 vector zips still present for P0 packs
    for eid in ("AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO", "AU_EMSR408_NSW"):
        for prod in EMSR_PACK_SPECS[eid]["products"]:
            assert prod["url"].startswith(S3_BASE)
            assert prod["url"].endswith("_vector.zip")


def test_pack_path_allowlist() -> None:
    good = ROOT / "data" / "open_if" / "latam_au" / "au" / "AU_EMSR500_PERTH"
    assert is_allowed_pack_path(good, repo_root=ROOT)
    bad = ROOT / "outputs" / "open_if" / "emsr500"
    assert not is_allowed_pack_path(bad, repo_root=ROOT)
    escape = ROOT / "data" / "real_if" / "raw_dropbox" / "x"
    assert not is_allowed_pack_path(escape, repo_root=ROOT)


def test_rasterize_and_meta_offline(tmp_path: Path) -> None:
    poly = Polygon([(116.17, -31.79), (116.19, -31.79), (116.19, -31.77), (116.17, -31.77), (116.17, -31.79)])
    spec = EMSR_PACK_SPECS["AU_EMSR500_PERTH"]
    geotiffs = []
    for prod in spec["products"]:
        dest = tmp_path / f"{spec['event_id']}_{prod['dated']}.tif"
        rast = rasterize_geom_to_geotiff(poly, dest, epsg=32750, gsd_m=30.0)
        assert dest.is_file()
        assert rast["positive_pixels"] > 0
        geotiffs.append(
            {
                "rel": dest.name,
                "role": "label_burned_cems_rasterized",
                "delivery_utc": prod["delivery_utc"],
            }
        )
    meta = build_pack_meta(
        spec,
        geotiffs=geotiffs,
        labels=[{"rel": geotiffs[0]["rel"], "kind": "cems_observed_event_raster"}],
    )
    assert meta["schema"] == PACK_META_SCHEMA
    assert validate_pack_meta(meta) == []


def test_meta_rejects_undated_or_too_few() -> None:
    spec = EMSR_PACK_SPECS["CL_EMSR647_NACIMIENTO"]
    meta = build_pack_meta(
        spec,
        geotiffs=[{"rel": "foo.tif", "role": "label"}],
        labels=[],
    )
    fails = validate_pack_meta(meta)
    assert any("need_ge3" in f for f in fails)
    assert any("label" in f for f in fails)


def test_binary_and_successive_iou() -> None:
    a = np.array([[1, 1, 0], [1, 0, 0]], dtype=np.uint8)
    b = np.array([[1, 0, 0], [1, 1, 0]], dtype=np.uint8)
    iou = binary_iou(a, b)
    assert iou is not None
    assert 0.4 < iou < 0.7
    rows = successive_mask_ious([a, b])
    assert rows[0]["mask_iou"] == iou


def test_domain_gap_schema_honest() -> None:
    clm = load_clm_sealed_test()
    assert clm["iou"] is not None
    assert clm["source"]
    au = empty_domain_row("AU_EMSR500_PERTH", "au")
    au["eval_status"] = "blocked_incompatible_schema"
    au["reason"] = "schema"
    latam = empty_domain_row("CL_EMSR647_NACIMIENTO", "cl")
    latam["eval_status"] = "blocked_incompatible_schema"
    latam["reason"] = "schema"
    doc = {
        "schema": DOMAIN_GAP_SCHEMA,
        "as_of_utc": "2026-08-13T00:00:00Z",
        "product_id": "clm_ensemble_v34",
        "clm_test": {"iou": clm["iou"], "n": clm["n"], "source": clm["source"]},
        "au": au,
        "latam": latam,
        "zero_shot": {"status": "not_run", "model_iou": None},
        "not_claims": ["not ROS"],
        "rails": {"go_q": "partial", "tobarra_keep_reopen": False},
    }
    assert validate_domain_gap(doc) == []


def test_domain_gap_rejects_invented_iou() -> None:
    doc = {
        "schema": DOMAIN_GAP_SCHEMA,
        "as_of_utc": "2026-08-13T00:00:00Z",
        "product_id": "clm_ensemble_v34",
        "clm_test": {"iou": 0.85, "n": 200, "source": "docs/ML_PRODUCT_SCORECARD.json"},
        "au": {
            "event_id": "AU_EMSR500_PERTH",
            "eval_status": "not_run",
            "model_iou": 0.91,
            "n": 0,
        },
        "latam": empty_domain_row("CL_EMSR647_NACIMIENTO", "cl"),
        "zero_shot": {"status": "not_run"},
        "not_claims": [],
        "rails": {"go_q": "partial", "tobarra_keep_reopen": False},
    }
    fails = validate_domain_gap(doc)
    assert any("invented_iou" in f for f in fails)


def test_domain_gap_rejects_ros_and_goq_true() -> None:
    doc = {
        "schema": DOMAIN_GAP_SCHEMA,
        "as_of_utc": "x",
        "product_id": "clm_ensemble_v34",
        "clm_test": {"iou": 0.8, "source": "s"},
        "au": empty_domain_row("A", "au"),
        "latam": empty_domain_row("B", "cl"),
        "zero_shot": {"status": "not_run"},
        "not_claims": [],
        "rails": {"go_q": "true", "tobarra_keep_reopen": False},
        "primary_ros": 1.2,
    }
    fails = validate_domain_gap(doc)
    assert any("forbidden_key" in f for f in fails)
    assert any("go_q" in f for f in fails)


def test_gitignore_covers_latam_au_rasters() -> None:
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "data/open_if/latam_au/**/*.tif" in gi
    assert "data/open_if/latam_au/**/*.zip" in gi
    assert "data/open_if/latam_au/**/raw_mapbiomas/" in gi
    assert "data/open_if/latam_au/**/raw_nafi/" in gi


def test_pack_dir_layout() -> None:
    root = ROOT / "data" / "open_if" / "latam_au"
    p = pack_dir_for(root, EMSR_PACK_SPECS["CL_EMSR647_NACIMIENTO"])
    assert p.as_posix().endswith("latam_au/cl/CL_EMSR647_NACIMIENTO")


def test_live_packs_if_present_meet_contract() -> None:
    root = ROOT / "data" / "open_if" / "latam_au"
    found = 0
    for spec in ALL_PACK_SPECS.values():
        meta_p = pack_dir_for(root, spec) / "meta.json"
        if not meta_p.is_file():
            continue
        found += 1
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        assert validate_pack_meta(meta) == []
        n_on_disk = 0
        for rec in meta.get("geotiffs") or []:
            rel = rec.get("rel")
            if rel and (meta_p.parent / rel).is_file():
                n_on_disk += 1
        if n_on_disk < 3:
            pytest.skip(f"{spec['event_id']} meta present but rasters gitignored/missing")
        assert n_on_disk >= 3
    if found == 0:
        pytest.skip("packs not materialized on this machine")


def test_r6_only_one_for_materialized_shortlist() -> None:
    csv_path = ROOT / "docs" / "data_campaigns" / "LATAM_AU_CANDIDATES.csv"
    import csv

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if (r.get("event_id") or "").strip()]
    allowed_r6 = {
        eid
        for eid, spec in ALL_PACK_SPECS.items()
        if (pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec) / "meta.json").is_file()
    }
    # P0 packs are always allowed to be 0 or 1 (meta may be gitignored on CI)
    allowed_r6 |= {"AU_EMSR500_PERTH", "CL_EMSR647_NACIMIENTO"}
    for row in rows:
        r6 = (row.get("r6") or "0").strip() or "0"
        if row["event_id"] in allowed_r6:
            assert r6 in {"0", "1"}
        else:
            assert r6 == "0"
