#!/usr/bin/env python3
"""Run the pre-registered WFIGS-only DEV follow-up controls.

This runner intentionally accepts one DEV dataset root and never receives a
confirmation or prospective-test path. Outputs are private training reports;
only aggregate metrics should be published.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.ml.wfigs_domain_adapt import (  # noqa: E402
    WFIGSAdaptConfig,
    adapt_frozen_rcda_on_wfigs,
)
from wildfire_front.open_if.regional.base import _atomic_write_json  # noqa: E402

RECIPES: tuple[dict[str, Any], ...] = (
    {
        "name": "hybrid_augmented_control",
        "target_mode": None,
        "augment": True,
    },
    {
        "name": "growth_only_augmented",
        "target_mode": "growth",
        "augment": True,
    },
    {
        "name": "growth_only_no_augmentation",
        "target_mode": "growth",
        "augment": False,
    },
)


def _assert_dev_only(dataset_root: Path) -> None:
    lowered = dataset_root.name.lower()
    forbidden = ("confirm", "test", "prospective")
    if any(token in lowered for token in forbidden):
        raise ValueError(
            f"follow-up runner accepts only the frozen DEV dataset; refusing path {dataset_root}"
        )
    for manifest_name in ("train.json", "validation.json"):
        if not (dataset_root / manifest_name).is_file():
            raise FileNotFoundError(dataset_root / manifest_name)


def _score(report: dict[str, Any]) -> float:
    ensemble = report.get("ensemble")
    if ensemble:
        return float(ensemble["validation"]["selected"]["event_macro_iou"])
    scores = [float(row["validation"]["selected"]["event_macro_iou"]) for row in report["reports"]]
    return sum(scores) / max(len(scores), 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("final_summary", type=Path)
    parser.add_argument("--wfigs-dev-root", type=Path, required=True)
    parser.add_argument("--rcda-normalization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=47)
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--patience", type=int, default=5)
    args = parser.parse_args()
    _assert_dev_only(args.wfigs_dev_root)

    args.output.mkdir(parents=True, exist_ok=True)
    ranking: list[dict[str, Any]] = []
    for recipe in RECIPES:
        recipe_output = args.output / recipe["name"]
        report = adapt_frozen_rcda_on_wfigs(
            final_summary_path=args.final_summary,
            wfigs_dataset_root=args.wfigs_dev_root,
            rcda_normalization_path=args.rcda_normalization,
            output_root=recipe_output,
            adaptation=WFIGSAdaptConfig(
                epochs=args.epochs,
                batch_size=4,
                lr=1e-4,
                patience=args.patience,
                trainable_scope="decoder",
                front_ring_bce_weight=0.05,
                target_mode=recipe["target_mode"],
                augment=recipe["augment"],
                source_seeds=(args.seed,),
            ),
        )
        if report["wfigs_test_loaded"] or report["test_used_for_selection"]:
            raise RuntimeError(f"DEV-only invariant violated by {recipe['name']}")
        ranking.append(
            {
                "name": recipe["name"],
                "target_mode": recipe["target_mode"] or "source_config",
                "augment": recipe["augment"],
                "event_macro_iou": _score(report),
                "output": str(recipe_output),
                "test_loaded": False,
            }
        )
    ranking.sort(key=lambda row: row["event_macro_iou"], reverse=True)
    aggregate = {
        "schema": "wfd_wfigs_followup_dev_v1",
        "dataset_scope": "frozen_wfigs_tuning_train_and_dev_only",
        "confirmation_loaded": False,
        "prospective_loaded": False,
        "selection_metric": "event_macro_iou",
        "seed": args.seed,
        "recipes": ranking,
        "interpretation": "directional_dev_only_no_new_confirmatory_claim",
    }
    _atomic_write_json(args.output / "FOLLOWUP_DEV_RANKING.json", aggregate)
    print(json.dumps(aggregate, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
