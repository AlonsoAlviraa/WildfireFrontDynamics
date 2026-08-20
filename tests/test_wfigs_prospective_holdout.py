from __future__ import annotations

import json
from pathlib import Path

from scripts.preregister_wfigs_prospective_holdout import build_preregistration


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _enriched(pair_id: str, cloud: float) -> dict:
    return {
        "pair_id": pair_id,
        "t0_bbox": [-111.0, 33.0, -110.98, 33.02],
        "weather": {"status": "resolved", "available_by_t0_verified": True},
        "eo": {
            "sentinel2": {
                "candidates": [
                    {
                        "cloud_cover_pct": cloud,
                        "stac_created_at_or_before_t0": True,
                    }
                ]
            }
        },
    }


def test_preregistration_freezes_next_disjoint_test_events(tmp_path: Path) -> None:
    history = tmp_path / "history"
    pairs = [
        {
            "pair_id": f"pair-{index}",
            "event_id": f"event-{index}",
            "region": "SWCC",
            "split": "test",
            "approved": True,
        }
        for index in range(5)
    ]
    _write(history / "temporal_pairs/PAIRS.json", {"pairs": pairs})
    _write(
        history / "enrichment/PAIR_ENRICHMENT.json",
        {"pairs": [_enriched(f"pair-{index}", float(index)) for index in range(5)]},
    )
    prior = tmp_path / "prior.json"
    _write(prior, {"rows": [{"event_id": "event-0"}, {"event_id": "event-1"}]})

    result = build_preregistration(
        history_root=history,
        prior_test_inventory=prior,
        output_path=tmp_path / "preregistered.json",
        events_per_region=2,
        event_offset_per_region=2,
    )

    assert result["event_ids"] == ["event-2", "event-3"]
    assert result["assertions"]["event_disjoint_from_prior_test"] is True
    assert result["assertions"]["prior_test_event_overlap"] == []
    assert result["test_evaluated"] is False
    assert result["target_statistics_observed"] is False
