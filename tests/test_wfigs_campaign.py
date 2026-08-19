"""Selection tests for the WFIGS tensor campaign."""

from __future__ import annotations

from wildfire_front.open_if.regional.wfigs_campaign import select_campaign_pairs


def test_campaign_is_event_disjoint_and_excludes_alaska_hrrr_mismatch() -> None:
    pairs = [
        {
            "pair_id": "az-1",
            "event_id": "az-event",
            "region": "SWCC",
            "split": "train",
            "approved": True,
        },
        {
            "pair_id": "az-2",
            "event_id": "az-event",
            "region": "SWCC",
            "split": "train",
            "approved": True,
        },
        {
            "pair_id": "ak-1",
            "event_id": "ak-event",
            "region": "AICC",
            "split": "train",
            "approved": True,
        },
    ]

    def enriched(bbox):
        return {
            "t0_bbox": bbox,
            "weather": {"status": "resolved", "available_by_t0_verified": True},
            "eo": {
                "sentinel2": {
                    "candidates": [
                        {
                            "id": "scene",
                            "cloud_cover_pct": 1.0,
                            "stac_created_at_or_before_t0": True,
                        }
                    ]
                }
            },
        }

    enrichment = {
        "az-1": enriched([-111.0, 33.0, -110.98, 33.02]),
        "az-2": enriched([-111.0, 33.0, -110.98, 33.02]),
        "ak-1": enriched([-150.0, 64.0, -149.0, 65.0]),
    }
    selected = select_campaign_pairs(
        pairs, enrichment, split="train", events_per_region=2
    )
    assert [row["pair_id"] for row in selected] == ["az-1"]


def test_campaign_rejects_oversize_t0_without_reading_t1_metrics() -> None:
    pair = {
        "pair_id": "large",
        "event_id": "event",
        "region": "SWCC",
        "split": "train",
        "approved": True,
        "metrics": {"growth_ha": 999999},
    }
    enriched = {
        "large": {
            "t0_bbox": [-111.0, 33.0, -110.0, 34.0],
            "weather": {"status": "resolved", "available_by_t0_verified": True},
            "eo": {
                "sentinel2": {
                    "candidates": [
                        {
                            "stac_created_at_or_before_t0": True,
                            "cloud_cover_pct": 0.0,
                        }
                    ]
                }
            },
        }
    }
    assert select_campaign_pairs(
        [pair], enriched, split="train", events_per_region=1
    ) == []
