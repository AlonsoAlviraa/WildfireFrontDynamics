"""P1–P2 LATAM/AU: weak specs, LOFO, ERA5, AL ranking, campaign docs (offline)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    AL_RANK_SCHEMA,
    ALL_PACK_SPECS,
    DOMAIN_GAP_SCHEMA,
    ERA5_ALIGN_SCHEMA,
    LICENSE_ID_MAPBIOMAS,
    LICENSE_ID_NAFI,
    LOFO_FOLD_SCHEMA,
    WEAK_PACK_SPECS,
    assign_s2_roles_by_datetime,
    build_era5_request_template,
    build_lofo_fold_doc,
    build_pack_meta,
    cems_product_url_ok,
    dated_geotiff_ok,
    distinct_s2_windows,
    empty_domain_row,
    pack_dir_for,
    quote_http_url,
    rank_active_learning_tiles,
    remap_pack_s2_roles,
    validate_al_ranking,
    validate_domain_gap,
    validate_era5_align,
    validate_lofo_fold,
    validate_pack_meta,
)


def test_p1_pack_specs_have_three_dated_products() -> None:
    for eid in (
        "AU_EMSR408_NSW",
        "CL_EMSR715_VALPARAISO",
        "BR_PANTANAL_2020_MAPBIOMAS",
        "AU_NAFI_NT_SEASON_2023",
    ):
        spec = ALL_PACK_SPECS[eid]
        assert len(spec["products"]) >= 3, eid
        for prod in spec["products"]:
            assert dated_geotiff_ok(prod["dated"]), (eid, prod["dated"])
            assert str(prod["url"]).startswith("http")
        assert spec["class"] == "ml_weak"


def test_weak_licenses_and_nafi_url_encoding() -> None:
    assert WEAK_PACK_SPECS["BR_PANTANAL_2020_MAPBIOMAS"]["license_id"] == LICENSE_ID_MAPBIOMAS
    assert WEAK_PACK_SPECS["AU_NAFI_NT_SEASON_2023"]["license_id"] == LICENSE_ID_NAFI
    raw = WEAK_PACK_SPECS["AU_NAFI_NT_SEASON_2023"]["products"][0]["url"]
    assert " " in raw
    enc = quote_http_url(raw)
    assert " " not in enc
    assert "%20" in enc
    assert cems_product_url_ok(ALL_PACK_SPECS["CL_EMSR715_VALPARAISO"]["products"][0]["url"])


def test_weak_pack_meta_allows_mapbiomas_license() -> None:
    spec = WEAK_PACK_SPECS["BR_PANTANAL_2020_MAPBIOMAS"]
    geotiffs = [
        {"rel": f"labels/{spec['event_id']}_{p['dated']}.tif", "role": "label_burned_mapbiomas_annual"}
        for p in spec["products"]
    ]
    meta = build_pack_meta(spec, geotiffs=geotiffs, labels=[{"rel": geotiffs[0]["rel"], "kind": "l1"}])
    assert validate_pack_meta(meta) == []
    assert meta["license_id"] == LICENSE_ID_MAPBIOMAS


def test_lofo_fold_includes_non_clm_and_null_iou() -> None:
    doc = build_lofo_fold_doc(
        repo_root=ROOT,
        non_clm_event_id="AU_EMSR408_NSW",
        pack_dir=ROOT / "data" / "open_if" / "latam_au" / "au" / "AU_EMSR408_NSW",
    )
    assert doc["schema"] == LOFO_FOLD_SCHEMA
    assert validate_lofo_fold(doc) == []
    fold = doc["folds"]["AU_EMSR408_NSW"]
    assert fold["model_iou"] is None
    assert fold["eval_status"] == "blocked_incompatible_schema"
    assert doc["held_out"]["compatible_with_clm_ensemble_v34"] is False
    assert "AU_EMSR408_NSW" in fold["test"]


def test_lofo_rejects_invented_iou() -> None:
    doc = build_lofo_fold_doc(repo_root=ROOT, non_clm_event_id="AU_EMSR500_PERTH")
    doc["folds"]["AU_EMSR500_PERTH"]["model_iou"] = 0.91
    fails = validate_lofo_fold(doc)
    assert any("invented_iou" in f for f in fails)


def test_era5_template_not_ros() -> None:
    spec = ALL_PACK_SPECS["CL_EMSR715_VALPARAISO"]
    tmpl = build_era5_request_template(spec)
    doc = {
        "schema": ERA5_ALIGN_SCHEMA,
        "not_ros": True,
        "request": tmpl,
        "event_id": spec["event_id"],
    }
    assert validate_era5_align(doc) == []
    assert tmpl["not_ros"] is True
    assert "2m_temperature" in tmpl["variables"]
    bad = dict(doc)
    bad["primary_ros"] = 1.2
    assert any("forbidden" in f for f in validate_era5_align(bad))


def test_active_learning_ranking_no_model_iou() -> None:
    tiles = [
        {"tile_id": "a", "file": "same.tif", "pos_frac": 0.48, "successive_disagreement": 0.2},
        {"tile_id": "b", "file": "same.tif", "pos_frac": 0.99, "successive_disagreement": 0.0},
        {"tile_id": "c", "file": "same.tif", "pos_frac": 0.10, "successive_disagreement": 0.4},
    ]
    ranked = rank_active_learning_tiles(tiles, event_id="AU_EMSR408_NSW")
    assert ranked[0]["rank"] == 1
    assert ranked[0]["tile_id"] == "a"  # mixed pos_frac; not collapsed to filename
    assert {r["tile_id"] for r in ranked} == {"a", "b", "c"}
    assert all(r["model_iou"] is None for r in ranked)
    doc = {
        "schema": AL_RANK_SCHEMA,
        "model_iou": None,
        "tiles": ranked,
    }
    assert validate_al_ranking(doc) == []
    invented = {"schema": AL_RANK_SCHEMA, "model_iou": 0.8, "tiles": ranked}
    assert any("invented" in f for f in validate_al_ranking(invented))


def test_p2_docs_exist() -> None:
    status = ROOT / "docs" / "data_campaigns" / "LATAM_AU_CAMPAIGN_STATUS.md"
    conaf = ROOT / "docs" / "data_campaigns" / "CONAF_DATA_REQUEST_TEMPLATE.md"
    paper = ROOT / "docs" / "data_campaigns" / "LATAM_AU_PAPER_DATASETS.md"
    assert status.is_file()
    assert conaf.is_file()
    assert paper.is_file()
    st = status.read_text(encoding="utf-8")
    for token in ("P0-A", "P0-B", "P0-C", "P0-D", "P1-A", "P1-B", "P1-C", "P1-D", "P2-A", "P2-B", "P2-C"):
        assert token in st
    assert "model_iou" in st.lower() or "IoU" in st
    assert "GO_Q" in st
    cf = conaf.read_text(encoding="utf-8")
    assert "CONAF" in cf
    assert "SHP" in cf or "GPKG" in cf
    assert "no" in cf.lower() and "táctico" in cf.lower() or "tactical" in cf.lower()
    pr = paper.read_text(encoding="utf-8")
    assert "FLAME" in pr or "FireBench" in pr
    assert "pretrain" in pr.lower()
    assert "not" in pr.lower()


def test_live_p1_packs_have_three_dated_labels_if_present() -> None:
    import json

    for eid in (
        "AU_EMSR408_NSW",
        "CL_EMSR715_VALPARAISO",
        "BR_PANTANAL_2020_MAPBIOMAS",
        "AU_NAFI_NT_SEASON_2023",
    ):
        spec = ALL_PACK_SPECS[eid]
        pack = pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec)
        meta_p = pack / "meta.json"
        if not meta_p.is_file():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        assert validate_pack_meta(meta) == [], eid
        labels = [
            rec
            for rec in (meta.get("geotiffs") or [])
            if str(rec.get("role") or "").startswith("label_")
        ]
        assert len(labels) >= 3, eid
        on_disk = sum(1 for rec in labels if rec.get("rel") and (pack / rec["rel"]).is_file())
        if on_disk:
            assert on_disk >= 3, eid
        assert meta.get("model_iou") is None


def test_p1_scripts_exist() -> None:
    for rel in (
        "scripts/download_mapbiomas_fogo.py",
        "scripts/download_nafi_scars.py",
        "scripts/materialize_latam_au_weak_packs.py",
        "scripts/build_latam_au_lofo_folds.py",
        "scripts/align_latam_au_era5.py",
        "scripts/rank_latam_au_active_learning.py",
    ):
        assert (ROOT / rel).is_file(), rel


def test_distinct_s2_windows_do_not_overlap() -> None:
    wins = distinct_s2_windows("2020-08-01")
    assert [role for role, _rng in wins] == ["pre", "mid", "post"]
    ends = []
    for _role, rng in wins:
        start, end = rng.split("/")
        assert start < end
        ends.append((start, end))
    assert ends[0][1] < ends[1][0]
    assert ends[1][1] < ends[2][0]


def test_s2_roles_assigned_by_datetime_not_search_order() -> None:
    recs = [
        {"role": "eo_s2_nbr_post", "datetime": "2019-11-16T00:05:23Z", "file": "b.tif"},
        {"role": "eo_s2_nbr_mid", "datetime": "2019-11-21T00:05:25Z", "file": "c.tif"},
        {"role": "eo_s2_nbr_pre", "datetime": "2019-11-06T00:05:24Z", "file": "a.tif"},
        {"role": "label_burned_cems_rasterized", "datetime": "2019-11-14T21:15:50Z"},
    ]
    out = assign_s2_roles_by_datetime(recs)
    s2 = [r for r in out if str(r["role"]).startswith("eo_s2_nbr_")]
    assert [r["role"] for r in s2] == ["eo_s2_nbr_pre", "eo_s2_nbr_mid", "eo_s2_nbr_post"]
    assert [r["file"] for r in s2] == ["a.tif", "b.tif", "c.tif"]
    assert all(r.get("s2_role_assigned_by") == "datetime" for r in s2)
    remapped = remap_pack_s2_roles({"geotiffs": recs, "stac_eo": recs[:3]})
    stac_roles = [r["role"] for r in remapped["stac_eo"]]
    assert stac_roles == ["eo_s2_nbr_pre", "eo_s2_nbr_mid", "eo_s2_nbr_post"]


def test_live_s2_roles_are_chronological_if_present() -> None:
    import json

    for eid, spec in ALL_PACK_SPECS.items():
        pack = pack_dir_for(ROOT / "data" / "open_if" / "latam_au", spec)
        meta_p = pack / "meta.json"
        if not meta_p.is_file():
            continue
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        s2 = [
            rec
            for rec in (meta.get("geotiffs") or [])
            if str(rec.get("role") or "") in {"eo_s2_nbr_pre", "eo_s2_nbr_mid", "eo_s2_nbr_post"}
        ]
        if len(s2) < 2:
            continue
        keys = [
            str(rec.get("datetime") or rec.get("delivery_utc") or rec.get("file") or "")
            for rec in s2
        ]
        assert keys == sorted(keys), eid
        roles = [rec["role"] for rec in s2]
        assert roles[0] == "eo_s2_nbr_pre", eid
        assert roles[-1] == "eo_s2_nbr_post", eid


def test_extra_packs_reject_invented_iou() -> None:
    extra = empty_domain_row("AU_EMSR408_NSW", "au")
    extra["eval_status"] = "blocked_incompatible_schema"
    extra["model_iou"] = 0.77
    extra["n"] = 0
    doc = {
        "schema": DOMAIN_GAP_SCHEMA,
        "as_of_utc": "2026-08-13T00:00:00Z",
        "product_id": "clm_ensemble_v34",
        "clm_test": {"iou": 0.85, "n": 200, "source": "docs/ML_PRODUCT_SCORECARD.json"},
        "au": empty_domain_row("AU_EMSR500_PERTH", "au"),
        "latam": empty_domain_row("CL_EMSR647_NACIMIENTO", "cl"),
        "extra_packs": [extra],
        "zero_shot": {"status": "not_run", "model_iou": None},
        "not_claims": ["not ROS"],
        "rails": {"go_q": "partial", "tobarra_keep_reopen": False},
    }
    fails = validate_domain_gap(doc)
    assert any("invented_iou" in f for f in fails)


def test_l1_domain_row_does_not_claim_cems_utm() -> None:
    """Honesty: MapBiomas/NAFI are L1 annual windows, not CEMS UTM stacks."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "eval_latam_au_domain_gap", ROOT / "scripts" / "eval_latam_au_domain_gap.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    meta = {
        "geotiffs": [
            {"rel": "eo/x.tif", "role": "eo_s2_nbr_pre", "status": "ok"},
        ],
        "stac_eo": [{"status": "ok"}],
        "crs": "EPSG:4326",
        "label_level": "L1_annual",
        "class": "ml_weak",
    }
    proxy = mod.attempt_dnbr_proxy(ROOT / "data" / "open_if" / "latam_au", meta)
    assert proxy["value"] is None
    assert proxy["status"] == "blocked_no_audited_threshold"
    assert "UTM" not in (proxy.get("reason") or "")
    geom = mod.pack_geometry_metrics(ROOT / "data" / "open_if" / "latam_au", meta)
    assert "annual" in geom["note"].lower()
    assert "NOT transfer" in geom["note"]


def test_binary_iou_not_used_as_transfer_in_al() -> None:
    # Guard: ranking helper must not accept/emit transfer_iou
    ranked = rank_active_learning_tiles(
        [{"pos_frac": float(np.mean([0.4, 0.5])), "file": "x.tif"}],
        event_id="X",
    )
    assert "transfer_iou" not in ranked[0]
    assert ranked[0]["not_transfer_iou"] is True
