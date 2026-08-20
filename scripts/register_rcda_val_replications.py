#!/usr/bin/env python3
"""Register fixed-seed RCDA validation replications before results arrive."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_rcda_kaggle_alt_continuation import (  # noqa: E402
    single_seed_run_source,
    utc_now,
    validate_single_run_val_summary,
    write_json,
)

SCHEMA = "wfd_rcda_val_replication_protocol_v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_replication_protocol(
    summary_path: Path,
    *,
    run_name: str,
    seeds: tuple[int, ...],
    kernel_template: str,
    runner_paths: dict[int, Path],
) -> dict[str, Any]:
    if len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("replication protocol requires at least three unique seeds")
    if any(seed < 0 for seed in seeds):
        raise ValueError("replication seeds must be non-negative")
    if set(runner_paths) != set(seeds):
        raise ValueError("replication protocol requires an exact runner for every seed")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    validate_single_run_val_summary(summary, run_name)
    reports = [
        row
        for row in summary.get("reports") or []
        if str((row.get("config") or {}).get("run_name")) == run_name
    ]
    ranking = [
        row for row in summary.get("ranking") or [] if row.get("run_name") == run_name
    ]
    if len(reports) != 1 or len(ranking) != 1:
        raise ValueError("source summary does not contain exactly one candidate report")
    source_checkpoint = Path(str(reports[0].get("checkpoint") or ""))
    if not source_checkpoint.is_file():
        downloaded_checkpoint = summary_path.parent / source_checkpoint.name
        if not downloaded_checkpoint.is_file():
            raise FileNotFoundError("source validation checkpoint is missing")
        source_checkpoint = downloaded_checkpoint
    replications = []
    for seed in seeds:
        expected_source = single_seed_run_source(run_name, seed)
        runner_path = runner_paths[seed]
        if not runner_path.is_file():
            raise FileNotFoundError(f"replication runner is missing for seed {seed}")
        runner_source = runner_path.read_text(encoding="utf-8")
        if (
            f"            seed={seed}," not in runner_source
            or "evaluate_test=False" not in runner_source
            or '"test_evaluated": False' not in runner_source
            or len(runner_source) != len(expected_source)
        ):
            raise ValueError(f"replication runner contract is invalid for seed {seed}")
        replications.append(
            {
                "seed": seed,
                "kernel": kernel_template.format(seed=seed),
                "runner_sha256": sha256_file(runner_path),
                "selection_split": "val",
                "test_evaluated": False,
            }
        )
    return {
        "schema": SCHEMA,
        "registered_at": utc_now(),
        "purpose": "fixed_seed_validation_reproducibility",
        "candidate": {
            "run_name": run_name,
            "configuration": reports[0]["config"],
            "seed0_val_event_macro_iou": ranking[0].get("val_event_macro_iou"),
            "seed0_selected_threshold": ranking[0].get(
                "selected_threshold", ranking[0].get("threshold")
            ),
            "source_summary_sha256": sha256_file(summary_path),
            "source_checkpoint_sha256": sha256_file(source_checkpoint),
        },
        "replications": replications,
        "selection_split": "val",
        "test_evaluated": False,
        "test_used_for_selection": False,
        "claims": {
            "limited_to_validation_reproducibility": True,
            "does_not_restore_historical_test_sealing": True,
            "eligible_for_untouched_prospective_external_selection": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", type=Path)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--seed", type=int, action="append", default=[])
    parser.add_argument("--kernel-template", required=True)
    parser.add_argument(
        "--runner",
        action="append",
        default=[],
        metavar="SEED=PATH",
        help="Exact staged runner that will be pushed; repeat once per seed.",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    seeds = tuple(args.seed or [11, 29, 47])
    runner_paths: dict[int, Path] = {}
    for value in args.runner:
        raw_seed, separator, raw_path = value.partition("=")
        if not separator:
            raise ValueError("--runner must use SEED=PATH")
        runner_paths[int(raw_seed)] = Path(raw_path)
    protocol = build_replication_protocol(
        args.summary,
        run_name=args.run_name,
        seeds=seeds,
        kernel_template=args.kernel_template,
        runner_paths=runner_paths,
    )
    write_json(args.output, protocol)
    print(json.dumps(protocol, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
