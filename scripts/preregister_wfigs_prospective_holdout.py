#!/usr/bin/env python3
"""Freeze a second event-disjoint WFIGS holdout before materialization."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.regional.base import _atomic_write_json, utc_now  # noqa: E402
from wildfire_front.open_if.regional.wfigs_campaign import (  # noqa: E402
    select_campaign_pairs,
)


def _digest(values: list[str]) -> str:
    canonical = "\n".join(sorted(values)).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_preregistration(
    *,
    history_root: Path,
    prior_test_inventory: Path,
    output_path: Path,
    events_per_region: int = 3,
    event_offset_per_region: int = 3,
) -> dict[str, Any]:
    """Select the next input-ranked TEST events and prove prior-test disjointness."""

    history_root = Path(history_root)
    pairs = (
        json.loads((history_root / "temporal_pairs/PAIRS.json").read_text(encoding="utf-8")).get(
            "pairs"
        )
        or []
    )
    enriched_rows = (
        json.loads(
            (history_root / "enrichment/PAIR_ENRICHMENT.json").read_text(encoding="utf-8")
        ).get("pairs")
        or []
    )
    enrichment = {str(row["pair_id"]): row for row in enriched_rows}
    selected = select_campaign_pairs(
        pairs,
        enrichment,
        split="test",
        events_per_region=events_per_region,
        event_offset_per_region=event_offset_per_region,
    )
    prior_inventory = json.loads(Path(prior_test_inventory).read_text(encoding="utf-8"))
    prior_events = sorted(
        {str(row["event_id"]) for row in prior_inventory.get("rows") or [] if row.get("event_id")}
    )
    event_ids = sorted({str(row["event_id"]) for row in selected})
    pair_ids = sorted(str(row["pair_id"]) for row in selected)
    overlap = sorted(set(event_ids) & set(prior_events))
    if overlap:
        raise ValueError("prospective holdout overlaps the previously evaluated TEST")
    payload = {
        "schema": "wfd_wfigs_prospective_holdout_v1",
        "generated_at": utc_now(),
        "selection_split": "test",
        "selection_uses_t1_or_growth": False,
        "test_evaluated": False,
        "target_statistics_observed": False,
        "configuration": {
            "events_per_region": events_per_region,
            "event_offset_per_region": event_offset_per_region,
            "ranking_inputs": ["region", "sentinel2_cloud_cover", "pair_id"],
        },
        "counts": {
            "events": len(event_ids),
            "pairs": len(pair_ids),
            "regions": dict(sorted(Counter(str(row["region"]) for row in selected).items())),
        },
        "event_ids": event_ids,
        "pair_ids": pair_ids,
        "event_ids_sha256": _digest(event_ids),
        "pair_ids_sha256": _digest(pair_ids),
        "prior_test_event_ids_sha256": _digest(prior_events),
        "assertions": {
            "prior_test_event_overlap": overlap,
            "event_disjoint_from_prior_test": True,
            "one_pair_per_event": len(event_ids) == len(pair_ids),
        },
    }
    _atomic_write_json(Path(output_path), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--history-root",
        type=Path,
        default=ROOT / "data/open_if/wfigs_history_2020_2026",
    )
    parser.add_argument(
        "--prior-test-inventory",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_test_campaign_20260819/INVENTORY.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs/ml_eval/wfigs_prospective_holdout_20260820/PREREGISTRATION.json",
    )
    parser.add_argument("--events-per-region", type=int, default=3)
    parser.add_argument("--event-offset-per-region", type=int, default=3)
    args = parser.parse_args()
    result = build_preregistration(
        history_root=args.history_root,
        prior_test_inventory=args.prior_test_inventory,
        output_path=args.output,
        events_per_region=args.events_per_region,
        event_offset_per_region=args.event_offset_per_region,
    )
    print(
        json.dumps(
            {
                "counts": result["counts"],
                "event_ids_sha256": result["event_ids_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
