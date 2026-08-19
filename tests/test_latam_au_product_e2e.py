"""Product bridge + E2E + ML export for LATAM/AU EMSR packs."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    ML_EXPORT_SCHEMA,
    PRODUCT_E2E_SCHEMA,
    bridge_source_pack_to_open_if,
    build_pack_meta,
    build_pista_b_scorecard_from_meta,
    product_slug_for,
    rasterize_geom_to_geotiff,
    source_pack_ready,
    write_label_geojson,
)
from wildfire_front.product.decide_service import (  # noqa: E402
    decide_from_request,
    load_open_metrics_from_pack,
)


def _mini_source_pack(tmp_path: Path, event_id: str = "AU_EMSR500_PERTH") -> Path:
    """Build a minimal latam_au-like source pack on disk for bridge tests."""
    spec = EMSR_PACK_SPECS[event_id]
    pack = tmp_path / "src" / spec["region"] / event_id
    labels = pack / "labels"
    labels.mkdir(parents=True)
    poly = Polygon(
        [
            (116.17, -31.79),
            (116.19, -31.79),
            (116.19, -31.77),
            (116.17, -31.77),
            (116.17, -31.79),
        ]
    )
    geotiffs = []
    for prod in spec["products"]:
        stem = f"{event_id}_{prod['dated']}"
        tif = labels / f"{stem}.tif"
        rast = rasterize_geom_to_geotiff(poly, tif, epsg=int(spec["crs_epsg"]), gsd_m=30.0)
        gj = labels / f"{stem}.geojson"
        write_label_geojson(
            poly,
            gj,
            {
                "event_id": event_id,
                "product_id": prod["product_id"],
                "area_ha": 12.5,
                "not_national_cadastre": True,
            },
        )
        geotiffs.append(
            {
                "rel": f"labels/{tif.name}",
                "file": tif.name,
                "role": "label_burned_cems_rasterized",
                "product_id": prod["product_id"],
                "kind": prod["kind"],
                "delivery_utc": prod["delivery_utc"],
                "area_ha": 12.5,
                "positive_pixels": rast["positive_pixels"],
            }
        )
    meta = build_pack_meta(
        spec,
        geotiffs=geotiffs,
        labels=[{"rel": geotiffs[0]["rel"], "kind": "cems_observed_event_raster"}],
    )
    (pack / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return pack


def test_source_pack_ready_missing(tmp_path: Path) -> None:
    ok, reason = source_pack_ready(tmp_path / "nope")
    assert ok is False
    assert "missing_meta" in reason


def test_bridge_writes_scorecard_pista_b(tmp_path: Path) -> None:
    src = _mini_source_pack(tmp_path)
    out = tmp_path / "outputs" / "open_if" / "emsr500_perth"
    info = bridge_source_pack_to_open_if(src, out, repo_root=tmp_path)
    assert info["ok"] is True
    sc_path = out / "scorecard_pista_b.json"
    assert sc_path.is_file()
    sc = json.loads(sc_path.read_text(encoding="utf-8"))
    assert sc["activation"] == "EMSR500"
    assert sc["max_area_ha"] == pytest.approx(12.5)
    assert sc["n_timeline_steps"] == 3
    assert sc["vp_invented"] is False
    assert sc["firms_hull_is_official_burned_area"] is False
    assert sc["not_tactical_dispatch"] is True
    assert (out / "timeline_perimeters.geojson").is_file()
    assert (out / "manifest.json").is_file()
    assert (out / "operator_brief_open_if.md").is_file()


def test_bridged_pack_loads_open_metrics(tmp_path: Path) -> None:
    src = _mini_source_pack(tmp_path)
    out = tmp_path / "open_pack"
    bridge_source_pack_to_open_if(src, out, repo_root=tmp_path)
    m = load_open_metrics_from_pack(out, base=tmp_path, include_repo_root=False)
    assert m is not None
    assert m["max_area_ha"] == pytest.approx(12.5)
    assert m["n_timeline_steps"] == 3
    assert m["source_scorecard"] == "scorecard_pista_b.json"
    assert m["activation"] == "EMSR500"
    assert m.get("vp_invented") is False


def test_decide_from_bridged_pack_holds_or_abstains(tmp_path: Path) -> None:
    """Open-only + require_ops_for_go must never GO from CEMS alone."""
    src = _mini_source_pack(tmp_path)
    out = tmp_path / "open_pack"
    bridge_source_pack_to_open_if(src, out, repo_root=tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    card = decide_from_request(
        {
            "event_id": "AU_EMSR500_PERTH",
            "open_pack": str(out),
            "work_dir": str(work),
            "require_ops_for_go": True,
            "channel": "cli",
            "write_decision_log": True,
            "write_vv_scorecard": True,
        },
        base=tmp_path,
    )
    assert card["decision"] in {"HOLD", "ABSTAIN"}
    assert card["decision"] != "GO"
    reasons = " ".join(str(r) for r in (card.get("reasons") or []))
    assert "open_only_monitoring" in reasons or "open_cems_monitoring_only" in reasons or card[
        "decision"
    ] == "ABSTAIN"
    open_ok = any(
        isinstance(s, dict) and s.get("id") == "open_cems_perimeter" and s.get("available")
        for s in (card.get("sources") or [])
    )
    assert open_ok is True
    # decide_from_request writes V&V sidecar (eng_stub). Decision-log JSONL is
    # a separate append path; do not require it here.
    assert (work / "vv_scorecard.json").is_file()


def test_product_slug() -> None:
    assert product_slug_for("AU_EMSR500_PERTH") == "emsr500_perth"
    assert product_slug_for("CL_EMSR647_NACIMIENTO") == "emsr647_nacimiento"


def test_rails_snapshot_freeze_from_stamp() -> None:
    """freeze_intact must follow stamp tobarra_keep_reopen, not a hardcoded True."""
    import importlib.util

    mod_path = ROOT / "scripts" / "run_latam_au_product_e2e.py"
    spec = importlib.util.spec_from_file_location("run_latam_au_product_e2e", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rails = mod._rails_snapshot()
    stamp = json.loads((ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json").read_text(encoding="utf-8"))
    keep = bool((stamp.get("rails") or {}).get("tobarra_keep_reopen"))
    assert rails["tobarra_keep_reopen"] is keep
    assert rails["freeze_intact"] is (not keep)
    assert rails["stamp_freeze_ml"] is rails["freeze_intact"]
    assert rails["go_q"] in {False, "partial", "false"} or str(rails["go_q"]).lower() == "partial"


def test_pista_scorecard_builder_fields() -> None:
    meta = {
        "activation": "EMSR500",
        "event_id": "AU_EMSR500_PERTH",
        "region": "au",
        "country": "AU",
        "geotiffs": [
            {
                "role": "label_burned_cems_rasterized",
                "kind": "delineation",
                "area_ha": 100.0,
            },
            {
                "role": "label_burned_cems_rasterized",
                "kind": "delineation_monitoring",
                "area_ha": 120.0,
            },
        ],
        "label_level": "L2_proxy",
        "class": "ml_weak",
        "license_id": "copernicus_ems_reg_2021_696_open",
        "schema": "wfd_open_if_pack_meta_v1",
    }
    sc = build_pista_b_scorecard_from_meta(meta, pack_dir_rel="outputs/open_if/x", timeline_n=2)
    assert sc["max_area_ha"] == 120.0
    assert sc["O2_cems_delineation"] == "GO"
    assert sc["O2_national_official"] == "NO_GO_CEMS_PROXY"


def test_bridge_script_exit_missing_pack(tmp_path: Path) -> None:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "bridge_latam_au_to_open_if.py"),
            "--event-id",
            "AU_EMSR500_PERTH",
            "--data-root",
            str(tmp_path / "empty_data"),
            "--out-root",
            str(tmp_path / "out"),
            "--json",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "missing" in (p.stderr + p.stdout).lower() or "FAIL" in (p.stderr + p.stdout)


def test_e2e_script_exit_missing_pack(tmp_path: Path) -> None:
    """Product E2E runner must exit 1 when source packs are missing."""
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    report = tmp_path / "fail_report.json"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_latam_au_product_e2e.py"),
            "--event-id",
            "CL_EMSR647_NACIMIENTO",
            "--data-root",
            str(tmp_path / "empty_latam_au"),
            "--work-root",
            str(tmp_path / "work"),
            "--out-root",
            str(tmp_path / "open_if_out"),
            "--report",
            str(report),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert p.returncode == 1, p.stdout + p.stderr
    assert "missing" in (p.stderr + p.stdout).lower() or "error" in (p.stderr + p.stdout).lower()
    assert report.is_file(), "failure report must be written on missing pack"
    fail_doc = json.loads(report.read_text(encoding="utf-8"))
    assert fail_doc.get("ok") is False
    assert fail_doc.get("event_id") == "CL_EMSR647_NACIMIENTO"
    assert "error" in fail_doc


def test_export_ml_patches_intermediate(tmp_path: Path) -> None:
    import importlib.util

    src = _mini_source_pack(tmp_path)
    out = tmp_path / "ml_out"
    mod_path = ROOT / "scripts" / "export_latam_au_ml_patches.py"
    spec = importlib.util.spec_from_file_location("export_latam_au_ml_patches", mod_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    row = mod.export_pack("AU_EMSR500_PERTH", src, out, patch_size=32, max_patches=8)
    assert row["ok"] is True
    assert row["compatible_with_clm_ensemble_v34"] is False
    assert row["n_patches"] >= 1
    man = json.loads((out / "AU_EMSR500_PERTH" / "ml" / "manifest.json").read_text(encoding="utf-8"))
    assert man["schema"] == ML_EXPORT_SCHEMA
    assert man["compatible_with_clm_ensemble_v34"] is False
    assert man["train_ready"]["can_feed_clm_train"] is False
    # NPZ has mask, not NDWS sequence
    patch_files = list((out / "AU_EMSR500_PERTH" / "ml" / "patches").glob("*.npz"))
    assert patch_files
    data = np.load(patch_files[0])
    assert "mask" in data.files
    assert "sequence" not in data.files


def test_export_script_missing_exit(tmp_path: Path) -> None:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "export_latam_au_ml_patches.py"),
            "--event-id",
            "AU_EMSR500_PERTH",
            "--data-root",
            str(tmp_path / "empty"),
            "--out-root",
            str(tmp_path / "ml"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    assert p.returncode == 1, p.stdout + p.stderr


def test_live_e2e_if_packs_present() -> None:
    """When real packs exist, bridge + decide must load open metrics."""
    au = ROOT / "data" / "open_if" / "latam_au" / "au" / "AU_EMSR500_PERTH"
    cl = ROOT / "data" / "open_if" / "latam_au" / "cl" / "CL_EMSR647_NACIMIENTO"
    if not source_pack_ready(au)[0] or not source_pack_ready(cl)[0]:
        pytest.skip("live LATAM/AU packs not materialized")

    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_latam_au_product_e2e.py"),
            "--event-id",
            "AU_EMSR500_PERTH",
            "--event-id",
            "CL_EMSR647_NACIMIENTO",
            "--report",
            str(ROOT / "outputs" / "open_if" / "latam_au_e2e" / "product_e2e_report_pytest.json"),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    assert p.returncode == 0, p.stdout + p.stderr
    report_path = ROOT / "outputs" / "open_if" / "latam_au_e2e" / "product_e2e_report_pytest.json"
    assert report_path.is_file()
    doc = json.loads(report_path.read_text(encoding="utf-8"))
    assert doc["schema"] == PRODUCT_E2E_SCHEMA
    assert doc["ok"] is True
    assert doc["n_ok"] >= 2
    for pack in doc["packs"]:
        assert pack["decision"] in {"GO", "HOLD", "ABSTAIN"}
        assert pack["open_source_available"] is True
        # No invented model IoU in product report
        assert "model_iou" not in pack or pack.get("model_iou") is None
