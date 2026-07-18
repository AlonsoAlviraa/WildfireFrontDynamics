"""Lightweight 2D cellular automaton for fire spread (China-style research stack).

Chinese literature often pairs 王正非 ROS with a CA grid (元胞自动机). This is a
minimal, dependency-free CA for **sanity checks and demos**, inspired by open
CA fire demos (e.g. FireCellularAutomata / cellpylib fire rules) — not a
production FARSITE replacement.

States: 0 empty/burned-out, 1 fuel, 2 burning.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def init_fuel_map(
    rows: int,
    cols: int,
    *,
    fuel_prob: float = 0.85,
    seed: int = 0,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    grid = (rng.random((rows, cols)) < fuel_prob).astype(np.int8)
    return grid


def ignite(grid: np.ndarray, r: int, c: int) -> np.ndarray:
    g = grid.copy()
    g[r, c] = 2
    return g


def step_ca(
    grid: np.ndarray,
    *,
    p_spread: float = 0.35,
    wind_bias: tuple[int, int] = (0, 0),
    wind_boost: float = 0.15,
    seed: int | None = None,
) -> np.ndarray:
    """One CA step. ``wind_bias`` is (dr, dc) preferred neighbor for spread."""
    rng = np.random.default_rng(seed)
    rows, cols = grid.shape
    out = grid.copy()
    burning = list(zip(*np.where(grid == 2), strict=False))
    for r, c in burning:
        out[r, c] = 0  # burned out after this step
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    continue
                if grid[nr, nc] != 1:
                    continue
                p = p_spread
                if wind_bias != (0, 0) and (dr, dc) == wind_bias:
                    p = min(1.0, p + wind_boost)
                if rng.random() < p:
                    out[nr, nc] = 2
    return out


def run_ca(
    steps: int = 40,
    rows: int = 48,
    cols: int = 48,
    *,
    p_spread: float = 0.4,
    wind_bias: tuple[int, int] = (0, 1),
    seed: int = 42,
) -> dict[str, Any]:
    """Run CA from center ignition; return burned fraction curve."""
    g = init_fuel_map(rows, cols, seed=seed)
    g = ignite(g, rows // 2, cols // 2)
    history = []
    for t in range(steps):
        burned = int(np.sum(g == 0))
        burning = int(np.sum(g == 2))
        fuel = int(np.sum(g == 1))
        history.append(
            {
                "t": t,
                "burned": burned,
                "burning": burning,
                "fuel": fuel,
                "burned_frac": round(burned / (rows * cols), 4),
            }
        )
        g = step_ca(g, p_spread=p_spread, wind_bias=wind_bias, seed=seed + t)
        if burning == 0 and t > 0:
            break
    return {
        "model": "cellular_automata_2d_minimal",
        "label_es": "CA 2D mínimo (demo/investigación CN-style) — no despacho",
        "rows": rows,
        "cols": cols,
        "steps_run": len(history),
        "final": history[-1] if history else None,
        "history_tail": history[-5:],
        "history_full": history,
    }
