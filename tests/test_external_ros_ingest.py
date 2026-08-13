"""Offline tests for open ROS pack inventory + PT-FireSprd ingest adapter."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from shapely.geometry import Polygon

from wildfire_front.open_if.external_ros import (
    INVENTORY_SCHEMA,
    PACK_CATALOG,
    build_zip_inventory,
    inventory_caldor_kml,
    inventory_ndws_kaggle_proxy,
    inventory_path_counts,
    parse_gofer_fire_catalog,
    write_pack_readme,
)
from wildfire_front.open_if.pt_firesprd import (
    _rel_or_posix,
    _safe_union,
    aligned_bounds,
    epsg_from_prj,
    evaluate_r1_contract,
    parse_date_hour,
    rasterize_projected,
    run_geotiff_ingest,
    scenes_aligned,
    scenes_from_features,
    select_ingest_fire,
    write_decide_open_pack,
)


def test_rel_or_posix_strips_repo_prefix() -> None:
    raw = Path("C:/Users/x/WildfireFrontDynamics/data/external/pt_firesprd/extracted/a.shp")
    assert _rel_or_posix(raw).startswith("data/external/")


def test_pack_catalog_dois_and_licenses() -> None:
    assert PACK_CATALOG["pt_firesprd"]["requested_doi"] == "10.5281/zenodo.7495506"
    assert PACK_CATALOG["gofer"]["requested_doi"] == "10.5281/zenodo.8327264"
    assert PACK_CATALOG["gofer"]["resolved_record"] == "14642378"
    for spec in PACK_CATALOG.values():
        assert spec["license_id"] == "cc-by-4.0"
        assert spec["not_tactical_ros"] is True
        assert spec["not_official_es_cadastre"] is True


def test_parse_date_hour_does_not_invent() -> None:
    ok = parse_date_hour("2016-08-09 14:00")
    assert ok is not None
    assert ok["filename_stamp"] == "20160809_140000"
    assert ok["tz"] == "unspecified_in_source"
    assert ok["not_verified_utc"] is True
    assert parse_date_hour("uncertain") is None
    assert parse_date_hour("na") is None
    assert parse_date_hour("") is None
    assert parse_date_hour("2016/08/09") is None


def test_epsg_from_prj_utm29n() -> None:
    prj = (
        'PROJCS["WGS_1984_UTM_Zone_29N",GEOGCS["GCS_WGS_1984",'
        'DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]]]'
    )
    assert epsg_from_prj(prj) == 32629
    assert epsg_from_prj("not a crs") is None


def _poly(x0: float, y0: float, size: float = 200.0) -> Polygon:
    return Polygon([(x0, y0), (x0 + size, y0), (x0 + size, y0 + size), (x0, y0 + size), (x0, y0)])


def test_safe_union_repairs_invalid_bowtie() -> None:
    bowtie = Polygon([(0, 0), (1, 1), (0, 1), (1, 0), (0, 0)])
    other = _poly(0.5, 0.5, 1.0)
    union = _safe_union([bowtie, other])
    assert union is not None
    assert not union.is_empty


def test_scenes_and_r1_contract() -> None:
    loaded = {
        "epsg": 32629,
        "features": [
            {
                "type": "p",
                "parsed": parse_date_hour("2015-08-03 14:30"),
                "geom": _poly(500_000, 4_400_000),
            },
            {
                "type": "p",
                "parsed": parse_date_hour("2015-08-04 03:00"),
                "geom": _poly(500_050, 4_400_050, 300.0),
            },
            {
                "type": "z",
                "parsed": parse_date_hour("2015-08-04 12:30"),
                "geom": _poly(500_000, 4_400_000, 400.0),
            },
            {
                "type": "p",
                "parsed": parse_date_hour("uncertain"),
                "geom": _poly(500_000, 4_400_000),
            },
        ],
    }
    scenes = scenes_from_features(loaded)
    assert len(scenes) == 3
    assert all(s["not_official_ha"] for s in scenes)
    contract = evaluate_r1_contract(scenes, epsg=32629)
    assert contract["meets_geotiff_r1"] is True
    assert contract["R1_ge3_dated_scenes"] is True

    two = scenes[:2]
    bad = evaluate_r1_contract(two, epsg=32629)
    assert bad["meets_geotiff_r1"] is False
    assert bad["skip_reason"] == "r1_lt_3_dated"


def test_geotiff_ingest_accepts_three_aligned_masks(tmp_path: Path) -> None:
    scenes = [
        {"geom": _poly(500_000, 4_400_000, 200.0), "stamp": "20150803_143000"},
        {"geom": _poly(500_100, 4_400_000, 300.0), "stamp": "20150804_030000"},
        {"geom": _poly(500_000, 4_400_100, 250.0), "stamp": "20150804_123000"},
    ]
    bounds = aligned_bounds(scenes, pad_m=50.0)
    images = tmp_path / "images"
    masks = tmp_path / "masks"
    for scene in scenes:
        fname = f"demo_{scene['stamp']}.tif"
        rast = rasterize_projected(
            scene["geom"], images / fname, epsg=32629, gsd_m=10.0, ref_bounds=bounds
        )
        (masks / fname).parent.mkdir(parents=True, exist_ok=True)
        Path(rast["path"]).parent.mkdir(parents=True, exist_ok=True)
        (masks / fname).write_bytes((images / fname).read_bytes())
    rec = run_geotiff_ingest(tmp_path, fire_id="demo")
    assert rec["n_accepted"] == 3
    assert rec["n_observations"] == 3
    assert rec["ok"] is True


def test_rasterize_three_aligned_scenes(tmp_path: Path) -> None:
    scenes = [
        {"geom": _poly(500_000, 4_400_000, 200.0)},
        {"geom": _poly(500_100, 4_400_000, 300.0)},
        {"geom": _poly(500_000, 4_400_100, 250.0)},
    ]
    bounds = aligned_bounds(scenes, pad_m=50.0)
    rasters = []
    for i, scene in enumerate(scenes):
        dest = tmp_path / f"scene_{i}_2015080{i + 3}_120000.tif"
        rast = rasterize_projected(scene["geom"], dest, epsg=32629, gsd_m=10.0, ref_bounds=bounds)
        assert rast["positive_pixels"] > 0
        rasters.append(rast)
    assert scenes_aligned(rasters)
    with rasterio.open(rasters[0]["path"]) as a, rasterio.open(rasters[1]["path"]) as b:
        assert a.width == b.width
        assert a.height == b.height
        assert a.crs == b.crs
        assert a.transform == b.transform
        assert a.read(1).dtype == np.uint8


def test_select_ingest_fire_prefers_band() -> None:
    fires = [
        {
            "ok": True,
            "meets_geotiff_r1": True,
            "n_dated_scenes": 40,
            "n_records": 9,
            "fire_id": "big",
        },
        {
            "ok": True,
            "meets_geotiff_r1": True,
            "n_dated_scenes": 7,
            "n_records": 12,
            "fire_id": "mid",
        },
        {
            "ok": True,
            "meets_geotiff_r1": False,
            "n_dated_scenes": 2,
            "n_records": 3,
            "fire_id": "tiny",
        },
    ]
    picked = select_ingest_fire(fires)
    assert picked is not None
    assert picked["fire_id"] == "mid"
    assert select_ingest_fire([fires[2]]) is None


def test_gofer_catalog_does_not_promote_acres(tmp_path: Path) -> None:
    csv_path = tmp_path / "fireData.csv"
    csv_path.write_text(
        "fname,fyear,acres_official,GOESIg_UTC,local_tz,local_tzGMT\n"
        "Kincade,2019,77758,2019-10-24 04,America/Los_Angeles,Etc/GMT+8\n",
        encoding="utf-8",
    )
    rows = parse_gofer_fire_catalog(csv_path)
    assert len(rows) == 1
    assert rows[0]["acres_official_catalog"] == 77758.0
    assert rows[0]["not_product_area_ha"] is True
    assert rows[0]["acres_official_is_author_catalog"] is True


def test_caldor_kml_inventory(tmp_path: Path) -> None:
    kml = tmp_path / "kml"
    kml.mkdir()
    (kml / "Caldor_2021_08_17T20_20_07_00.kml").write_text("<kml/>", encoding="utf-8")
    (kml / "Caldor_2021_08_18T20_30_07_00.kml").write_text("<kml/>", encoding="utf-8")
    (kml / "Caldor_2021_08_19T20_45_07_00.kml").write_text("<kml/>", encoding="utf-8")
    (kml / "Caldor_perimeter_mtbs.kml").write_text("<kml/>", encoding="utf-8")
    inv = inventory_caldor_kml(kml)
    assert inv["ok"] is True
    assert inv["n_dated"] == 3
    assert inv["r1_ge3_dated_kml"] is True
    assert inv["native_geotiff"] is False
    assert inv["not_product_ros"] is True


def test_zip_inventory_and_readme(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    pack = repo / "data" / "external" / "pt_firesprd"
    pack.mkdir(parents=True)
    zpath = pack / "PT-FireSprd_v0.08.zip"
    payload = b"not-a-real-zip-but-hashed"
    zpath.write_bytes(payload)
    inv = build_zip_inventory(repo, "pt_firesprd", hash_extracted=False)
    assert inv["schema"] == INVENTORY_SCHEMA
    assert inv["zip"]["bytes"] == len(payload)
    assert inv["zip_md5_ok"] is False
    assert inv["not_product_ros"] is True
    readme = pack / "README.md"
    write_pack_readme(readme, PACK_CATALOG["pt_firesprd"], inv)
    text = readme.read_text(encoding="utf-8")
    assert "cc-by-4.0" in text
    assert "tactical dispatch" in text.lower()


def test_decide_open_pack_honest_scorecard(tmp_path: Path) -> None:
    ingest = tmp_path / "ingest"
    labels = ingest / "labels"
    labels.mkdir(parents=True)
    stamp = "20150803_143000"
    (labels / f"demo_{stamp}.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (ingest / "meta.json").write_text(
        json.dumps(
            {
                "geotiffs": [
                    {
                        "rel_image": f"images/demo_{stamp}.tif",
                        "filename_stamp": stamp,
                        "area_ha_from_vector": 12.5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "open_pack"
    rec = write_decide_open_pack(ingest, out, fire_id="demo")
    assert rec["ok"] is True
    score = json.loads((out / "scorecard_pista_b.json").read_text(encoding="utf-8"))
    assert score["vp_invented"] is False
    assert score["not_ops_ros"] is True
    assert score["O2_cems_delineation"] == "NO_GO_NOT_CEMS"
    assert score["max_area_ha"] == 12.5
    assert (out / "timeline_perimeters.geojson").is_file()


def test_path_counts_and_ndws_inventory(tmp_path: Path) -> None:
    missing = inventory_path_counts(tmp_path / "nope")
    assert missing["ok"] is False
    assert missing["n_files"] == 0
    staged = tmp_path / "proxy"
    (staged / "extracted").mkdir(parents=True)
    (staged / "extracted" / "next_day_wildfire_spread_eval_00.tfrecord").write_bytes(b"tf")
    (staged / "next-day-wildfire-spread.zip").write_bytes(b"zip")
    counts = inventory_path_counts(staged)
    assert counts["ok"] is True
    assert counts["n_files"] == 2
    assert counts["bytes"] == 5

    repo = tmp_path / "repo"
    wsts = repo / "data" / "external" / "wildfirespreadts"
    wsts.mkdir(parents=True)
    (wsts / "WildfireSpreadTS_Documentation.pdf").write_bytes(b"%PDF-fake")
    proxy = wsts / "ndws_kaggle_proxy"
    proxy.mkdir()
    (proxy / "next-day-wildfire-spread.zip").write_bytes(b"abc")
    rec = inventory_ndws_kaggle_proxy(repo)
    assert rec["full_zip_staged"] is False
    assert rec["not_clm_v34_retrain"] is True
    assert rec["documentation_pdf_bytes"] == 9
    assert rec["proxy"]["n_files"] == 1


def test_live_flags_untouched() -> None:
    root = Path(__file__).resolve().parents[1]
    stamp = json.loads((root / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    assert stamp.get("GO_Q") == "partial"
    assert stamp.get("GO_MES_plus") is False
    assert (stamp.get("rails") or {}).get("tobarra_keep_reopen") is False
    anchors = json.loads((root / "data" / "infocam_anchors.json").read_text(encoding="utf-8"))
    assert anchors["anchors"]["hellin_2024"]["status"] == "pending_external"
    assert anchors["anchors"]["hellin_2024"]["vp_m_min"] is None
