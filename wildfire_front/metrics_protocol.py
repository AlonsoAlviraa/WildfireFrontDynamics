"""Labeled experiment metrics protocol — anti vanity / anti apples-oranges.

Every reported number must carry a protocol tag so loops cannot compare
incompatible splits, filters, or baselines.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class MetricProtocol:
    """Identity of how a metric was computed."""

    domain: str  # "observatorio" | "ml_ndws" | "ml_clm"
    metric_name: str
    value: float | int | str | None
    unit: str = ""
    protocol: str = ""  # e.g. "any_fire_979", "front_dynamics_v1_window_early"
    baseline_name: str | None = None
    baseline_value: float | None = None
    delta: float | None = None
    n_samples: int | None = None
    higher_is_better: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentRecord:
    experiment_id: str
    hypothesis: str
    leap_ids: list[str]
    status: str  # running | completed | killed
    go: bool | None = None
    verdict: str = ""
    primary_metric: str = ""
    metrics: list[MetricProtocol] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    started_at_utc: str = ""
    finished_at_utc: str = ""
    single_change: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def score_ratio_band(
    value: float | None,
    ref: float,
    low: float = 0.5,
    high: float = 2.0,
) -> MetricProtocol:
    ratio = None if value is None or ref <= 0 else float(value) / float(ref)
    passed = ratio is not None and low <= ratio <= high
    return MetricProtocol(
        domain="observatorio",
        metric_name="ratio_vs_anchor",
        value=ratio,
        unit="1",
        protocol=f"primary_ros / {ref}",
        baseline_name="anchor_vp",
        baseline_value=ref,
        delta=None if ratio is None else ratio - 1.0,
        higher_is_better=False,  # closeness to 1 matters
        notes="PASS" if passed else "FAIL/ABSTAIN",
    )


def o3_window_summary(windows: list[dict[str, Any]], ref_vp: float = 7.0) -> dict[str, Any]:
    """Aggregate temporal window results into protocol-labeled metrics."""
    metrics: list[MetricProtocol] = []
    n_pass = 0
    for w in windows:
        if w.get("status") != "ok":
            continue
        ros = w.get("primary_ros_m_min")
        ratio = w.get("ratio_infocam")
        if ratio is None and isinstance(ros, (int, float)) and ref_vp > 0:
            ratio = float(ros) / ref_vp
        passed = isinstance(ratio, (int, float)) and 0.5 <= float(ratio) <= 2.0
        if passed:
            n_pass += 1
        metrics.append(
            MetricProtocol(
                domain="observatorio",
                metric_name="primary_ros_m_min",
                value=ros,
                unit="m/min",
                protocol=f"window:{w.get('window')}",
                baseline_name="INFOCAM_vp",
                baseline_value=ref_vp,
                delta=None if ratio is None else float(ratio) - 1.0,
                n_samples=w.get("n_frames"),
                notes=f"ratio={ratio} grade={w.get('quality_grade')}",
            )
        )
    n_ok = sum(1 for w in windows if w.get("status") == "ok")
    go = n_pass >= 2 and n_ok >= 3
    return {
        "n_windows_ok": n_ok,
        "n_pass_ratio_band": n_pass,
        "go": go,
        "verdict": "GO" if go else "NO_GO",
        "metrics": [m.to_dict() for m in metrics],
    }
