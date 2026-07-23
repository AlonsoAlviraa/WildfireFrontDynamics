"""Area-fraction schedules and stage count validation for PSB."""

from __future__ import annotations

import math
from typing import Sequence

from .schemas import N_STAGES_DEFAULT, N_STAGES_MAX, N_STAGES_MIN


def validate_n_stages(n_stages: int) -> int:
    n = int(n_stages)
    if not (N_STAGES_MIN <= n <= N_STAGES_MAX):
        raise ValueError(f"n_stages must be in [{N_STAGES_MIN}, {N_STAGES_MAX}], got {n}")
    return n


def fraction_schedule(
    name: str,
    n_stages: int,
    *,
    custom: Sequence[float] | None = None,
) -> list[float]:
    """Return strictly increasing fractions ending at 1.0 (length n_stages)."""
    n = validate_n_stages(n_stages)
    key = (name or "sqrt").strip().lower()

    if key == "custom":
        if custom is None:
            raise ValueError("custom schedule requires custom fractions")
        fracs = [float(x) for x in custom]
        if len(fracs) != n:
            raise ValueError(f"custom schedule length {len(fracs)} != n_stages {n}")
        if abs(fracs[-1] - 1.0) > 1e-9:
            raise ValueError("custom schedule must end at 1.0")
        for i in range(1, n):
            if fracs[i] < fracs[i - 1] - 1e-12:
                raise ValueError("custom schedule must be non-decreasing")
        return fracs

    if key == "linear":
        fracs = [(i + 1) / n for i in range(n)]
    elif key == "sqrt":
        # radius-linear caricature: f = ((i+1)/N)^2
        fracs = [((i + 1) / n) ** 2 for i in range(n)]
    elif key == "early_fast":
        # p = 0.5
        fracs = [((i + 1) / n) ** 0.5 for i in range(n)]
    elif key == "late_fast":
        # p = 2 (same curve as sqrt; alias kept for schedule name)
        fracs = [((i + 1) / n) ** 2 for i in range(n)]
    elif key == "logistic":
        # Separate named logistic; renormalize to (0,1] ending at 1
        xs = [(i + 1) / n for i in range(n)]
        k, x0 = 8.0, 0.5
        raw = [1.0 / (1.0 + math.exp(-k * (x - x0))) for x in xs]
        lo, hi = raw[0], raw[-1]
        span = hi - lo if hi > lo else 1.0
        fracs = [(r - lo) / span for r in raw]
        fracs[-1] = 1.0
    else:
        raise ValueError(
            f"unknown schedule {name!r}; "
            "use linear|sqrt|early_fast|late_fast|logistic|custom"
        )

    # Ensure positive first fraction and exact terminal 1.0
    fracs = [max(f, 1e-9) for f in fracs]
    fracs[-1] = 1.0
    return fracs


def uniform_times_s(n_stages: int, total_duration_s: float) -> list[float]:
    n = validate_n_stages(n_stages)
    if total_duration_s <= 0:
        raise ValueError("total_duration_s must be positive")
    if n == 1:
        return [0.0]
    step = float(total_duration_s) / (n - 1)
    return [i * step for i in range(n)]
