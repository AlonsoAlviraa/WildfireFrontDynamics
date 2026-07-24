"""Protocol integrity rails for CLM holdout / VAL-only tuning (ML focus v1).

Hard rule: mix/temperature/uncertainty fitting only on VAL (or train for train).
Test / LOFO may report and gate, never tune.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

SplitName = Literal["train", "val", "test", "lofo"]
ActionName = Literal[
    "train",
    "fit",
    "optimize",
    "select",
    "calibrate",
    "tune_mix",
    "tune_temperature",
    "fit_uncertainty",
    "report",
    "scorecard",
    "gate",
    "stress",
]

ALLOWED_ACTIONS: Final[dict[str, frozenset[str]]] = {
    "train": frozenset({"train", "fit", "optimize"}),
    "val": frozenset(
        {
            "select",
            "calibrate",
            "tune_mix",
            "tune_temperature",
            "fit_uncertainty",
            "report",
            "scorecard",
            "gate",
        }
    ),
    "test": frozenset({"report", "scorecard", "gate"}),
    "lofo": frozenset({"report", "stress", "scorecard", "gate"}),
}

# Actions that must never run on test/lofo
TUNE_ACTIONS: Final[frozenset[str]] = frozenset(
    {
        "tune_mix",
        "tune_temperature",
        "calibrate",
        "fit_uncertainty",
        "select",
        "train",
        "fit",
        "optimize",
    }
)

DEFAULT_PROTOCOL: Final = "clm_holdout_test_seed42_v1"

# Forbidden keys in ML primary scorecard (ops ROS leakage)
ROS_FORBIDDEN_KEYS: Final[frozenset[str]] = frozenset(
    {
        "primary_ros_m_min",
        "ros_area_m_min",
        "ros_equiv_radius_m_min",
        "vp_tactical",
        "ros_m_min",
    }
)


@dataclass(frozen=True)
class SplitContext:
    split: SplitName
    action: ActionName
    protocol: str = DEFAULT_PROTOCOL

    def __post_init__(self) -> None:
        if self.split not in ALLOWED_ACTIONS:
            raise ValueError(f"unknown split {self.split!r}")


class ProtocolRailError(ValueError):
    """Raised when an action is not allowed on a split."""


def assert_split_role(split: str, action: str) -> None:
    """Raise ProtocolRailError if action is not allowed on split."""
    allowed = ALLOWED_ACTIONS.get(str(split))
    if allowed is None:
        raise ProtocolRailError(f"unknown split {split!r}")
    if str(action) not in allowed:
        raise ProtocolRailError(
            f"action {action!r} not allowed on split {split!r}; allowed={sorted(allowed)}"
        )
    if str(action) in TUNE_ACTIONS and str(split) in ("test", "lofo"):
        raise ProtocolRailError(
            f"refusing tune/calibrate action {action!r} on {split!r} (VAL-only protocol integrity)"
        )


def assert_split_context(ctx: SplitContext) -> None:
    assert_split_role(ctx.split, ctx.action)


def reject_ros_keys_in_primary(primary: dict) -> None:
    """Fail if primary metrics contain ops ROS keys (dual-product honesty)."""
    if not isinstance(primary, dict):
        return
    bad: set[str] = set(ROS_FORBIDDEN_KEYS.intersection(primary.keys()))
    # also scan one level of nested dicts
    for k, v in primary.items():
        if isinstance(v, dict):
            bad |= set(ROS_FORBIDDEN_KEYS.intersection(v.keys()))
        if k in ROS_FORBIDDEN_KEYS:
            bad.add(k)
    if bad:
        raise ProtocolRailError(f"ROS/ops keys forbidden in ML primary scorecard: {sorted(bad)}")


def validate_scorecard_tuning(tuning: dict | None) -> list[str]:
    """Return gate failure reasons; empty list = pass."""
    fails: list[str] = []
    if not tuning:
        fails.append("missing_tuning_block")
        return fails
    for key in ("mix_split", "temperature_split", "uncertainty_calibration_split"):
        val = tuning.get(key)
        if val is None:
            fails.append(f"missing_{key}")
        elif str(val) != "val":
            fails.append(f"{key}_not_val:{val}")
    return fails
