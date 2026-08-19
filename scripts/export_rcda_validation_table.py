#!/usr/bin/env python3
"""Export the VAL-only RCDA candidate table for the paper."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

FIELDS = (
    "rank",
    "run_name",
    "event_macro_iou",
    "event_bootstrap_ci_low",
    "event_bootstrap_ci_high",
    "event_median_iou",
    "selected_threshold",
    "best_epoch",
    "leader_minus_candidate_paired_delta",
    "leader_minus_candidate_ci_low",
    "leader_minus_candidate_ci_high",
    "leader_wins_event_fraction",
)


def export_validation_table(scorecard_path: Path, output_dir: Path) -> tuple[Path, Path]:
    document = json.loads(Path(scorecard_path).read_text(encoding="utf-8"))
    if not (
        document.get("selection_split") == "val"
        and document.get("test_evaluated") is False
        and document.get("test_used_for_selection") is False
    ):
        raise ValueError("validation table requires a VAL-only scorecard")
    rows = []
    for source in document.get("ranking") or []:
        score_ci = source.get("event_bootstrap_95_ci") or (None, None)
        delta_ci = source.get("leader_minus_candidate_bootstrap_95_ci") or (
            None,
            None,
        )
        rows.append(
            {
                "rank": source.get("rank"),
                "run_name": source.get("run_name"),
                "event_macro_iou": source.get("event_macro_iou"),
                "event_bootstrap_ci_low": score_ci[0],
                "event_bootstrap_ci_high": score_ci[1],
                "event_median_iou": source.get("event_median_iou"),
                "selected_threshold": source.get("selected_threshold"),
                "best_epoch": source.get("best_epoch"),
                "leader_minus_candidate_paired_delta": source.get(
                    "leader_minus_candidate_paired_delta"
                ),
                "leader_minus_candidate_ci_low": delta_ci[0],
                "leader_minus_candidate_ci_high": delta_ci[1],
                "leader_wins_event_fraction": source.get(
                    "leader_wins_event_fraction"
                ),
            }
        )
    if not rows:
        raise ValueError("validation scorecard has no ranked candidates")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "rcda_validation_results_20260819.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    markdown_path = output_dir / "rcda_validation_results_20260819.md"
    lines = [
        "# RCDA validation results",
        "",
        "> Selection and uncertainty are event-level on VAL; TEST remains sealed.",
        "",
        "| Rank | Candidate | Event-macro IoU (95% CI) | Median | Threshold | Epoch | Leader delta (95% CI) | Leader wins |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        delta = row["leader_minus_candidate_paired_delta"]
        delta_text = "—"
        if delta is not None:
            delta_text = (
                f"{float(delta):+.5f} "
                f"[{float(row['leader_minus_candidate_ci_low']):+.5f}, "
                f"{float(row['leader_minus_candidate_ci_high']):+.5f}]"
            )
        wins = row["leader_wins_event_fraction"]
        wins_text = "—" if wins is None else f"{100.0 * float(wins):.2f}%"
        lines.append(
            "| "
            f"{row['rank']} | `{row['run_name']}` | "
            f"{float(row['event_macro_iou']):.5f} "
            f"[{float(row['event_bootstrap_ci_low']):.5f}, "
            f"{float(row['event_bootstrap_ci_high']):.5f}] | "
            f"{float(row['event_median_iou']):.5f} | "
            f"{float(row['selected_threshold']):.2f} | "
            f"{int(row['best_epoch'])} | {delta_text} | {wins_text} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return csv_path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    outputs = export_validation_table(args.scorecard, args.output_dir)
    print("\n".join(str(path) for path in outputs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
