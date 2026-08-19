"""WFIGS research-use and publication-policy tests."""

from __future__ import annotations

import pytest

from wildfire_front.open_if.regional.wfigs_rights import (
    WFIGSPublicationBlocked,
    assert_wfigs_publication_allowed,
    refresh_wfigs_rights_artifacts,
    wfigs_rights_summary,
)


def test_internal_research_allowed_without_enabling_redistribution() -> None:
    rights = wfigs_rights_summary(event_count=12)
    assert rights["internal_noncommercial_training_allowed"] is True
    assert rights["raw_data_redistribution_allowed"] is False
    assert rights["checkpoint_publication_allowed"] is False
    assert rights["n_eventos_habilitados_investigacion_interna"] == 12


def test_publication_guard_is_allow_listed_and_fails_closed() -> None:
    assert_wfigs_publication_allowed("code")
    assert_wfigs_publication_allowed("aggregate-metrics")
    with pytest.raises(WFIGSPublicationBlocked):
        assert_wfigs_publication_allowed("raw_data")
    with pytest.raises(WFIGSPublicationBlocked):
        assert_wfigs_publication_allowed("future_artifact_type")


def test_rights_refresh_migrates_manifests_without_recomputing_pairs(tmp_path) -> None:
    pair_root = tmp_path / "temporal_pairs"
    enrichment_root = tmp_path / "enrichment"
    ml_root = tmp_path / "ml"
    pair_root.mkdir()
    enrichment_root.mkdir()
    ml_root.mkdir()
    (pair_root / "INVENTORY.json").write_text(
        '{"n_eventos_descargados":7,"n_pares_aprobados":3,'
        '"claims":{"event_disjoint_splits":true}}',
        encoding="utf-8",
    )
    (pair_root / "PAIRS.json").write_text('{"pairs":[{"pair_id":"p1"}]}', encoding="utf-8")
    pairs_before = (pair_root / "PAIRS.json").read_bytes()
    (enrichment_root / "INVENTORY.json").write_text('{"counts":{"pairs":3}}', encoding="utf-8")
    (ml_root / "GEOMETRY_BASELINE.json").write_text(
        '{"claims":{"wfigs_training_rights_resolved":false}}', encoding="utf-8"
    )

    report = refresh_wfigs_rights_artifacts(tmp_path)

    assert report["geometry_pairs_or_splits_recomputed"] is False
    assert (pair_root / "PAIRS.json").read_bytes() == pairs_before
    inventory = __import__("json").loads((pair_root / "INVENTORY.json").read_text())
    assert inventory["claims"]["training_blocked_until_rights_resolved"] is False
    assert inventory["derechos_resueltos"]["n_eventos_habilitados_investigacion_interna"] == 7
    baseline = __import__("json").loads((ml_root / "GEOMETRY_BASELINE.json").read_text())
    assert "wfigs_training_rights_resolved" not in baseline["claims"]
