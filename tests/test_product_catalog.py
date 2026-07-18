"""Dual-product catalog readiness."""

from __future__ import annotations

from pathlib import Path

import pytest

from wildfire_front.ml.product_catalog import get_product, list_products, load_catalog

ROOT = Path(__file__).resolve().parents[1]

_PRODUCT_IDS = ("ndws_v21", "clm_v28", "clm_ensemble_v34", "clm_ensemble_v30")


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


def test_list_products_ready_matches_resolve():
    """Always-on: list_products()['ready'] must match resolve_existing()[0].

    On clean clones without .pt weights, this still asserts ready is False
    rather than skipping the whole readiness contract.
    """
    products = {p["id"]: p for p in list_products()}
    for pid in _PRODUCT_IDS:
        assert pid in products, f"missing product in list_products: {pid}"
        ok, _msg = get_product(pid).resolve_existing()
        assert products[pid]["ready"] is ok, (
            f"{pid}: ready={products[pid]['ready']} but resolve_existing()={ok}"
        )


@pytest.mark.requires_weights
def test_list_products_ready_when_weights_present():
    """When all weight artifacts exist, every product reports ready=True."""
    missing = []
    for pid in _PRODUCT_IDS:
        ok, msg = get_product(pid).resolve_existing()
        if not ok:
            missing.append(f"{pid}: {msg}")
    if missing:
        pytest.skip("requires_weights: " + "; ".join(missing))
    products = {p["id"]: p for p in list_products()}
    for pid in _PRODUCT_IDS:
        assert products[pid]["ready"] is True


@pytest.mark.requires_weights
def test_get_product_paths_exist():
    """Per-product path checks; skip only products whose weights are missing."""
    any_checked = False
    for pid in _PRODUCT_IDS:
        spec = get_product(pid)
        ok, msg = spec.resolve_existing()
        if not ok:
            continue
        any_checked = True
        assert spec.manifest_path.is_file()
        if pid.startswith("clm_ensemble"):
            assert spec.product_type == "ensemble"
            assert len(spec.member_paths) >= 2
            assert all(p.is_file() for p in spec.member_paths)
        else:
            assert spec.weights_path.is_file()
    if not any_checked:
        pytest.skip("requires_weights: no product weight artifacts present")


def test_ensemble_manifest_has_v34_temps():
    import json

    m = json.loads((ROOT / "models" / "clm_ensemble" / "manifest.json").read_text(encoding="utf-8"))
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
