"""Dual-product catalog readiness."""

from __future__ import annotations

from pathlib import Path

from wildfire_front.ml.product_catalog import get_product, list_products, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def test_catalog_has_both_products():
    data = load_catalog()
    assert "ndws_v21" in data["products"]
    assert "clm_v28" in data["products"]
    # Emergency primary is CLM specialist; NDWS remains research baseline.
    assert data.get("default_product") == "clm_v28"
    assert data.get("emergency_ml_product") == "clm_v28"
    assert data.get("research_ml_product") == "ndws_v21"


def test_list_products_ready():
    products = {p["id"]: p for p in list_products()}
    assert products["ndws_v21"]["ready"] is True
    assert products["clm_v28"]["ready"] is True


def test_get_product_paths_exist():
    for pid in ("ndws_v21", "clm_v28"):
        spec = get_product(pid)
        ok, msg = spec.resolve_existing()
        assert ok, msg
        assert spec.manifest_path.is_file()
        assert spec.weights_path.is_file()


def test_infocam_anchors_schema():
    import json

    doc = json.loads((ROOT / "data" / "infocam_anchors.json").read_text(encoding="utf-8"))
    assert "tobarra_20240802" in doc["anchors"]
    assert doc["anchors"]["tobarra_20240802"]["status"] == "confirmed"
    assert doc["anchors"]["tobarra_20240802"]["vp_m_min"] == 7.0
    for pending in ("cardoso_2025", "hellin_2024", "la_estrella_acom1_2024"):
        assert doc["anchors"][pending]["status"] == "pending_external"
