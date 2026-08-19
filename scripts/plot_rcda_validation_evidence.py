#!/usr/bin/env python3
"""Plot VAL-only RCDA ranking and paired leader/runner-up evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _read_val_only(path: Path) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if not (
        document.get("selection_split") == "val"
        and document.get("test_evaluated") is False
        and document.get("test_used_for_selection") is False
    ):
        raise ValueError(f"artifact is not VAL-only: {path}")
    return document


def build_figure(
    scorecard_path: Path,
    combined_summary_path: Path,
    output_path: Path,
    *,
    top_n: int = 10,
) -> Path:
    scorecard = _read_val_only(scorecard_path)
    combined = _read_val_only(combined_summary_path)
    ranking = list(scorecard.get("ranking") or [])[:top_n]
    if len(ranking) < 2:
        raise ValueError("ranking needs at least two VAL candidates")
    reports = {
        str(row["config"]["run_name"]): row for row in combined.get("reports") or []
    }
    leader_name = str(ranking[0]["run_name"])
    runner_name = str(ranking[1]["run_name"])
    if leader_name not in reports or runner_name not in reports:
        raise ValueError("leader and runner-up reports are missing")

    names = [str(row["run_name"]) for row in reversed(ranking)]
    means = np.asarray(
        [float(row["event_macro_iou"]) for row in reversed(ranking)],
        dtype=np.float64,
    )
    intervals = [row["event_bootstrap_95_ci"] for row in reversed(ranking)]
    lower = means - np.asarray([float(row[0]) for row in intervals])
    upper = np.asarray([float(row[1]) for row in intervals]) - means

    fig, (rank_ax, paired_ax) = plt.subplots(1, 2, figsize=(13.5, 5.6))
    y = np.arange(len(names))
    colors = ["#2b6cb0" if name == leader_name else "#718096" for name in names]
    rank_ax.errorbar(
        means,
        y,
        xerr=np.vstack([lower, upper]),
        fmt="none",
        ecolor="#a0aec0",
        elinewidth=1.5,
        capsize=3,
        zorder=1,
    )
    rank_ax.scatter(means, y, c=colors, s=42, zorder=2)
    rank_ax.axvline(0.20, color="#c53030", linestyle="--", linewidth=1.2)
    rank_ax.set_yticks(y, labels=names)
    rank_ax.set_xlabel("Event-macro growth IoU on validation")
    rank_ax.set_title("Candidate ranking with event-bootstrap 95% CI")
    rank_ax.grid(axis="x", alpha=0.2)

    leader_events = reports[leader_name]["val"]["selected"]["per_event"]
    runner_events = reports[runner_name]["val"]["selected"]["per_event"]
    events = sorted(set(leader_events).intersection(runner_events))
    if set(events) != set(leader_events) or set(events) != set(runner_events):
        raise ValueError("leader and runner-up event sets differ")
    leader_values = np.asarray(
        [float(leader_events[event]["iou"]) for event in events], dtype=np.float64
    )
    runner_values = np.asarray(
        [float(runner_events[event]["iou"]) for event in events], dtype=np.float64
    )
    limit = max(0.05, float(max(leader_values.max(), runner_values.max())))
    paired_ax.scatter(
        runner_values,
        leader_values,
        s=24,
        alpha=0.65,
        color="#2b6cb0",
        edgecolors="none",
    )
    paired_ax.plot([0.0, limit], [0.0, limit], color="#718096", linewidth=1.2)
    paired_ax.set_xlim(0.0, limit * 1.02)
    paired_ax.set_ylim(0.0, limit * 1.02)
    paired_ax.set_aspect("equal", adjustable="box")
    paired_ax.set_xlabel(f"{runner_name} event IoU")
    paired_ax.set_ylabel(f"{leader_name} event IoU")
    paired_ax.set_title(f"Paired validation fires (n={len(events)})")
    paired_ax.grid(alpha=0.2)
    comparison = ranking[1]
    delta = float(comparison["leader_minus_candidate_paired_delta"])
    delta_ci = comparison["leader_minus_candidate_bootstrap_95_ci"]
    paired_ax.text(
        0.03,
        0.97,
        f"Mean paired delta {delta:+.4f}\n95% CI [{float(delta_ci[0]):+.4f}, {float(delta_ci[1]):+.4f}]",
        transform=paired_ax.transAxes,
        va="top",
        fontsize=9,
    )

    fig.suptitle("RCDA validation evidence — TEST remains sealed", fontsize=14)
    fig.tight_layout()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scorecard", type=Path, required=True)
    parser.add_argument("--combined-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()
    output = build_figure(
        args.scorecard,
        args.combined_summary,
        args.output,
        top_n=args.top_n,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
