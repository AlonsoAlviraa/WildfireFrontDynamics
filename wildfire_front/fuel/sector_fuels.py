"""Sector-aware fuel mix from spatial fuel maps (head / flank / rear wedges).

Samples fuel_id_grid in polar wedges about the map center relative to
``head_bearing_deg`` (0=N, 90=E). Majority fuel per sector drives physics ROS
when a real fuel map is present; UNKNOWN is ignored when it is a minority.

Honesty: landcover→fuel is an engineering crosswalk, not field inventory.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np

from .fuel_map import FuelMapProduct
from .models import FUEL_CATALOG


def is_catalog_fuel_id(fuel_id: str | None) -> bool:
    """True if ``fuel_id`` is a key in FUEL_CATALOG (including UNKNOWN)."""
    if fuel_id is None:
        return False
    raw = str(fuel_id).strip()
    if not raw:
        return False
    key = raw.upper()
    return key in FUEL_CATALOG or raw in FUEL_CATALOG


def canonicalize_fuel_id(fuel_id: str | None) -> str:
    """Map id to catalog key, or ``UNKNOWN`` if not in catalog / empty.

    ``get_fuel`` never raises and maps garbage → UNKNOWN model; this helper
    makes that explicit for majority validation and audit notes.
    """
    if fuel_id is None:
        return "UNKNOWN"
    raw = str(fuel_id).strip()
    if not raw:
        return "UNKNOWN"
    key = raw.upper()
    if key in FUEL_CATALOG:
        return FUEL_CATALOG[key].id
    if raw in FUEL_CATALOG:
        return FUEL_CATALOG[raw].id
    return "UNKNOWN"


def angular_delta_deg(a: float, b: float) -> float:
    """Smallest signed angle a−b in (−180, 180]."""
    return ((float(a) - float(b) + 180.0) % 360.0) - 180.0


def absolute_angular_delta_deg(a: float, b: float) -> float:
    return abs(angular_delta_deg(a, b))


def cell_bearing_deg(
    row: int | np.ndarray,
    col: int | np.ndarray,
    *,
    center_row: float,
    center_col: float,
) -> np.ndarray | float:
    """Bearing from grid center to cell (0=N, 90=E). North = decreasing row."""
    dy = center_row - np.asarray(row, dtype=float)  # +north
    dx = np.asarray(col, dtype=float) - center_col  # +east
    # atan2(east, north)
    br = (np.degrees(np.arctan2(dx, dy)) + 360.0) % 360.0
    if np.isscalar(row) and np.isscalar(col):
        return float(br)
    return br


def majority_fuel_id(
    fuel_ids: Sequence[str],
    *,
    ignore_unknown_if_minority: bool = True,
    fallback: str = "UNKNOWN",
) -> str:
    """Mode / majority fuel id.

    When ``ignore_unknown_if_minority`` is True, drop UNKNOWN unless it is a
    **strict majority** (``n_unk > n_other``). Equal counts (ties) also drop
    UNKNOWN so burnable fuels win — not only strict minority cases.
    """
    ids = [str(x) for x in fuel_ids if x is not None and str(x)]
    if not ids:
        return fallback
    counts = Counter(ids)
    if ignore_unknown_if_minority and "UNKNOWN" in counts:
        n_unk = counts["UNKNOWN"]
        n_other = sum(v for k, v in counts.items() if k != "UNKNOWN")
        # ignore UNKNOWN unless it is a strict majority over all non-unknown
        if n_other > 0 and n_unk <= n_other:
            counts = Counter({k: v for k, v in counts.items() if k != "UNKNOWN"})
    # stable tie-break: highest count, then alphabetically
    best = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return str(best)


def fuel_mix_fractions(fuel_ids: Sequence[str]) -> dict[str, float]:
    ids = [str(x) for x in fuel_ids]
    if not ids:
        return {}
    counts = Counter(ids)
    total = float(sum(counts.values())) or 1.0
    return {
        k: round(v / total, 4)
        for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
    }


@dataclass
class SectorFuelSummary:
    """Representative fuel per head/flank/rear wedge + mix audit."""

    head_fuel_id: str
    flank_fuel_id: str
    rear_fuel_id: str
    head_mix: dict[str, float]
    flank_mix: dict[str, float]
    rear_mix: dict[str, float]
    head_bearing_deg: float
    n_cells: dict[str, int]
    method: str = "wedge_majority_v1"
    center_rc: list[float] = field(default_factory=list)
    head_half_width_deg: float = 45.0
    rear_half_width_deg: float = 45.0
    notes: list[str] = field(default_factory=list)
    dominant_fallback: str | None = None

    def fuel_for(self, sector: str) -> str:
        s = sector.lower()
        if s == "head":
            return self.head_fuel_id
        if s == "flank":
            return self.flank_fuel_id
        if s in ("rear", "back"):
            return self.rear_fuel_id
        raise KeyError(sector)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SectorTerrainSummary:
    """Mean slope (and optional aspect) per head/flank/rear wedge from DEM."""

    head_slope_deg: float
    flank_slope_deg: float
    rear_slope_deg: float
    head_bearing_deg: float
    n_cells: dict[str, int]
    method: str = "wedge_mean_slope_v1"
    global_mean_slope_deg: float | None = None
    notes: list[str] = field(default_factory=list)

    def slope_for(self, sector: str) -> float:
        s = sector.lower()
        if s == "head":
            return float(self.head_slope_deg)
        if s == "flank":
            return float(self.flank_slope_deg)
        if s in ("rear", "back"):
            return float(self.rear_slope_deg)
        raise KeyError(sector)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sector_labels_for_grid(
    n_rows: int,
    n_cols: int,
    *,
    head_bearing_deg: float,
    center_rc: tuple[float, float] | None = None,
    head_half_width_deg: float = 45.0,
    rear_half_width_deg: float = 45.0,
) -> tuple[np.ndarray, float, float]:
    """Return (labels HxW, center_row, center_col)."""
    if center_rc is None:
        cr, cc = (n_rows - 1) / 2.0, (n_cols - 1) / 2.0
    else:
        cr, cc = float(center_rc[0]), float(center_rc[1])
    rr, cc_idx = np.meshgrid(
        np.arange(n_rows, dtype=float),
        np.arange(n_cols, dtype=float),
        indexing="ij",
    )
    dy = cr - rr
    dx = cc_idx - cc
    at_center = (np.abs(dx) < 1e-9) & (np.abs(dy) < 1e-9)
    bearings = (np.degrees(np.arctan2(dx, dy)) + 360.0) % 360.0
    labels = classify_sector_mask(
        bearings,
        head_bearing_deg,
        head_half_width_deg=head_half_width_deg,
        rear_half_width_deg=rear_half_width_deg,
    )
    labels[at_center] = "head"
    return labels, cr, cc


def sector_slope_summary_from_grid(
    slope_deg_grid: np.ndarray,
    *,
    head_bearing_deg: float,
    center_rc: tuple[float, float] | None = None,
    head_half_width_deg: float = 45.0,
    rear_half_width_deg: float = 45.0,
    fallback_slope_deg: float | None = None,
) -> SectorTerrainSummary:
    """Mean slope degrees per wedge from a 2D slope map."""
    slope = np.asarray(slope_deg_grid, dtype=float)
    if slope.ndim != 2:
        raise ValueError("slope_deg_grid must be 2D")
    n_rows, n_cols = slope.shape
    labels, _, _ = sector_labels_for_grid(
        n_rows,
        n_cols,
        head_bearing_deg=head_bearing_deg,
        center_rc=center_rc,
        head_half_width_deg=head_half_width_deg,
        rear_half_width_deg=rear_half_width_deg,
    )
    global_mean = float(np.nanmean(slope)) if np.isfinite(slope).any() else float(
        fallback_slope_deg or 0.0
    )
    fb = (
        float(fallback_slope_deg)
        if fallback_slope_deg is not None
        else global_mean
    )
    notes: list[str] = ["wedge_mean_slope_v1", "from_dem_slope_grid"]
    n_cells: dict[str, int] = {}
    means: dict[str, float] = {}
    for sector in ("head", "flank", "rear"):
        mask = labels == sector
        vals = slope[mask]
        vals = vals[np.isfinite(vals)]
        n_cells[sector] = int(vals.size)
        if vals.size == 0:
            means[sector] = fb
            notes.append(f"{sector}_empty_used_fallback_slope")
        else:
            means[sector] = float(np.mean(vals))
    return SectorTerrainSummary(
        head_slope_deg=round(means["head"], 4),
        flank_slope_deg=round(means["flank"], 4),
        rear_slope_deg=round(means["rear"], 4),
        head_bearing_deg=float(head_bearing_deg) % 360.0,
        n_cells=n_cells,
        global_mean_slope_deg=round(global_mean, 4),
        notes=notes,
    )


def classify_sector_mask(
    bearings_deg: np.ndarray,
    head_bearing_deg: float,
    *,
    head_half_width_deg: float = 45.0,
    rear_half_width_deg: float = 45.0,
) -> np.ndarray:
    """Return object array of sector labels: head | flank | rear."""
    hb = float(head_bearing_deg) % 360.0
    d_head = np.abs(
        ((bearings_deg - hb + 180.0) % 360.0) - 180.0
    )
    d_rear = np.abs(
        ((bearings_deg - (hb + 180.0) + 180.0) % 360.0) - 180.0
    )
    labels = np.full(bearings_deg.shape, "flank", dtype=object)
    labels[d_head <= float(head_half_width_deg)] = "head"
    # rear wins only when closer to rear and outside head wedge
    rear_mask = (d_rear <= float(rear_half_width_deg)) & (
        d_head > float(head_half_width_deg)
    )
    labels[rear_mask] = "rear"
    return labels


def sector_fuel_summary_from_grid(
    fuel_id_grid: np.ndarray,
    *,
    head_bearing_deg: float,
    center_rc: tuple[float, float] | None = None,
    head_half_width_deg: float = 45.0,
    rear_half_width_deg: float = 45.0,
    ignore_unknown_if_minority: bool = True,
    dominant_fallback: str | None = None,
) -> SectorFuelSummary:
    """Compute majority fuel per head/flank/rear wedge from a fuel id grid."""
    grid = np.asarray(fuel_id_grid)
    if grid.ndim != 2:
        raise ValueError("fuel_id_grid must be 2D")
    n_rows, n_cols = grid.shape
    if n_rows < 1 or n_cols < 1:
        raise ValueError("fuel_id_grid is empty")

    labels, cr, cc = sector_labels_for_grid(
        n_rows,
        n_cols,
        head_bearing_deg=head_bearing_deg,
        center_rc=center_rc,
        head_half_width_deg=head_half_width_deg,
        rear_half_width_deg=rear_half_width_deg,
    )

    buckets: dict[str, list[str]] = {"head": [], "flank": [], "rear": []}
    flat_ids = grid.ravel()
    flat_lab = labels.ravel()
    for fid, lab in zip(flat_ids.tolist(), flat_lab.tolist()):
        buckets[str(lab)].append(str(fid))

    notes: list[str] = [
        "wedge_majority_v1",
        "UNKNOWN ignored unless strict majority (ties drop UNKNOWN)",
        "engineering landcover→fuel crosswalk — not field plot",
    ]
    fb = dominant_fallback
    if fb is None:
        all_ids = [str(x) for x in flat_ids.tolist()]
        fb = majority_fuel_id(
            all_ids, ignore_unknown_if_minority=ignore_unknown_if_minority
        )
    fb = canonicalize_fuel_id(fb) if fb is not None else "UNKNOWN"
    # if fallback itself was garbage → UNKNOWN
    if dominant_fallback is not None and not is_catalog_fuel_id(str(dominant_fallback)):
        notes.append(f"dominant_fallback_invalid_{dominant_fallback}")

    def _pick(sector: str) -> str:
        ids = buckets[sector]
        if not ids:
            notes.append(f"{sector}_empty_used_fallback")
            return str(fb)
        return majority_fuel_id(
            ids,
            ignore_unknown_if_minority=ignore_unknown_if_minority,
            fallback=str(fb),
        )

    head_f = _pick("head")
    flank_f = _pick("flank")
    rear_f = _pick("rear")

    # Validate catalog membership (get_fuel never raises — check FUEL_CATALOG)
    remapped: dict[str, str] = {}
    for name, fid in (("head", head_f), ("flank", flank_f), ("rear", rear_f)):
        if is_catalog_fuel_id(fid):
            remapped[name] = canonicalize_fuel_id(fid)
            continue
        # garbage id string → fallback if catalog-valid, else UNKNOWN
        notes.append(f"{name}_unknown_id_{fid}_to_fallback")
        if is_catalog_fuel_id(str(fb)) and canonicalize_fuel_id(fb) != "UNKNOWN":
            remapped[name] = canonicalize_fuel_id(fb)
        else:
            remapped[name] = "UNKNOWN"
    head_f, flank_f, rear_f = remapped["head"], remapped["flank"], remapped["rear"]

    return SectorFuelSummary(
        head_fuel_id=head_f,
        flank_fuel_id=flank_f,
        rear_fuel_id=rear_f,
        head_mix=fuel_mix_fractions(buckets["head"]),
        flank_mix=fuel_mix_fractions(buckets["flank"]),
        rear_mix=fuel_mix_fractions(buckets["rear"]),
        head_bearing_deg=float(head_bearing_deg) % 360.0,
        n_cells={
            "head": len(buckets["head"]),
            "flank": len(buckets["flank"]),
            "rear": len(buckets["rear"]),
        },
        method="wedge_majority_v1",
        center_rc=[cr, cc],
        head_half_width_deg=float(head_half_width_deg),
        rear_half_width_deg=float(rear_half_width_deg),
        notes=notes,
        dominant_fallback=str(fb) if fb is not None else None,
    )


def sector_fuel_summary_from_product(
    product: FuelMapProduct | Mapping[str, Any],
    *,
    head_bearing_deg: float,
    center_rc: tuple[float, float] | None = None,
    head_half_width_deg: float = 45.0,
    rear_half_width_deg: float = 45.0,
) -> SectorFuelSummary:
    """Convenience wrapper over FuelMapProduct (or dict with fuel_id_grid)."""
    if isinstance(product, FuelMapProduct):
        grid = product.fuel_id_grid
        dom = product.fuel_id_dominant
    else:
        grid = product.get("fuel_id_grid")
        if grid is None:
            raise ValueError("product missing fuel_id_grid")
        dom = product.get("fuel_id_dominant")
    return sector_fuel_summary_from_grid(
        np.asarray(grid),
        head_bearing_deg=head_bearing_deg,
        center_rc=center_rc,
        head_half_width_deg=head_half_width_deg,
        rear_half_width_deg=rear_half_width_deg,
        dominant_fallback=str(dom) if dom else None,
    )
