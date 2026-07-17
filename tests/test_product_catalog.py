"""Dual-product catalog readiness."""

from __future__ import annotations

from pathlib import Path

from wildfire_front.ml.product_catalog import get_product, list_products, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_has_both_products():
    data = load_catalog()
    assert "ndws_v21" in data["products"]
    assert "clm_v28" in data["products"]
    assert "clm_ensemble_v34" in data["products"]
    # Backward-compat alias
    assert "clm_ensemble_v30" in data["products"]
    assert data.get("default_product") in ("clm_v28", "clm_ensemble_v34", "clm_ensemble_v30")
    assert data.get("emergency_ml_product") in (
        "clm_v28",
        "clm_ensemble_v34",
        "clm_ensemble_v30",
    )
    assert data.get("research_ml_product") == "ndws_v21"
    assert data.get("fallback_ml_product") == "clm_v28"


def test_list_products_ready():
    products = {p["id"]: p for p in list_products()}
    assert products["ndws_v21"]["ready"] is True
    assert products["clm_v28"]["ready"] is True
    assert products["clm_ensemble_v34"]["ready"] is True
    assert products["clm_ensemble_v30"]["ready"] is True


def test_get_product_paths_exist():
    for pid in ("ndws_v21", "clm_v28", "clm_ensemble_v34", "clm_ensemble_v30"):
        spec = get_product(pid)
        ok, msg = spec.resolve_existing()
        assert ok, msg
        assert spec.manifest_path.is_file()
        if pid.startswith("clm_ensemble"):
            assert spec.product_type == "ensemble"
            assert len(spec.member_paths) >= 2
            assert all(p.is_file() for p in spec.member_paths)
        else:
            assert spec.weights_path.is_file()


def test_ensemble_manifest_has_v34_temps():
    import json

    m = json.loads(
        (ROOT / "models" / "clm_ensemble" / "manifest.json").read_text(encoding="utf-8")
    )
    assert m.get("version") == "clm_ensemble_v34"
    assert m.get("member_temperatures") == [0.7, 0.7, 1.3]
    assert len(m.get("member_weights") or []) == 3


def test_infocam_anchors_schema():
    import json

    doc = json.loads((ROOT / "data" / "infocam_anchors.json").read_text(encoding="utf-8"))
    assert "tobarra_20240802" in doc["anchors"]
    assert doc["anchors"]["tobarra_20240802"]["status"] == "confirmed"
    assert doc["anchors"]["tobarra_20240802"]["vp_m_min"] == 7.0
    for pending in ("cardoso_2025", "hellin_2024", "la_estrella_acom1_2024"):
        assert doc["anchors"][pending]["status"] == "pending_external"
