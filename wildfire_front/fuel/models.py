"""Mediterranean + Scott–Burgan fuel model catalog for Rothermel-lite.

Parameters are **engineering priors** from literature crosswalks
(Scott & Burgan 2005; Dimitrakopoulos Med models; Vega 2024 shrub/bracken
structure; Elia Apulia WUI; Prometheus height classes). They are NOT
calibrated field inventories for a specific CLM plot until local fuel maps
are ingested.

Relative ROS scale is tuned so that under moderate wind (midflame ~2–3 m/s),
slope 5–10°, dry dead FMC ~6–8%, shrub/maquis models land in the
**5–25 m/min** order of magnitude reported for Iberian/Med shrub experimental
work (Anderson 2015; Fernandes 2001; Cruz synthesis 2025).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class FuelModel:
    """Surface fuel model for Rothermel-lite.

    Units follow simplified Rothermel inputs used in ``rothermel_lite``:
    load kg/m², depth m, sav 1/m, heat kJ/kg, density kg/m³, mx dead %.
    """

    id: str
    name: str
    family: str  # GR | GS | SH | TU | TL | SB | MED | PROM
    fuel_load: float  # kg/m² oven-dry fine+1h proxy
    fuel_depth: float  # m fuelbed depth
    fuel_sav: float  # 1/m surface-area-to-volume
    fuel_heat: float = 18600.0  # kJ/kg
    fuel_density: float = 512.0  # kg/m³
    moisture_extinction_pct: float = 25.0  # dead fuel extinction moisture %
    wind_reduction: float = 0.4  # 10 m → midflame default (open)
    height_m: float = 0.5  # typical vegetation / bed height (m)
    provenance: str = "engineering_prior"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --- Scott–Burgan style subset (engineering parameters) ---
# Depth / load / SAV chosen so relative ordering matches SB groups:
# GR high ROS, SH high, TL lower surface ROS, TU intermediate.

_SB: dict[str, FuelModel] = {
    "GR2": FuelModel(
        id="GR2",
        name="Low load, dry climate grass",
        family="GR",
        fuel_load=0.11,
        fuel_depth=0.30,
        fuel_sav=6500.0,
        moisture_extinction_pct=15.0,
        wind_reduction=0.45,
        height_m=0.3,
        provenance="scott_burgan_2005_proxy",
        notes="Fast grass; high SA/V.",
    ),
    "GR4": FuelModel(
        id="GR4",
        name="Moderate load, dry climate grass",
        family="GR",
        fuel_load=0.20,
        fuel_depth=0.60,
        fuel_sav=6200.0,
        moisture_extinction_pct=15.0,
        wind_reduction=0.45,
        height_m=0.6,
        provenance="scott_burgan_2005_proxy",
    ),
    "GS2": FuelModel(
        id="GS2",
        name="Moderate load, dry climate grass-shrub",
        family="GS",
        fuel_load=0.18,
        fuel_depth=0.50,
        fuel_sav=5200.0,
        moisture_extinction_pct=20.0,
        wind_reduction=0.40,
        height_m=0.8,
        provenance="scott_burgan_2005_proxy",
        notes="Typical Iberian dry grass–matorral mosaic.",
    ),
    "SH2": FuelModel(
        id="SH2",
        name="Moderate load dry climate shrub",
        family="SH",
        fuel_load=0.25,
        fuel_depth=0.80,
        fuel_sav=4500.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.35,
        height_m=1.2,
        provenance="scott_burgan_2005_proxy",
    ),
    "SH5": FuelModel(
        id="SH5",
        name="High load dry climate shrub",
        family="SH",
        fuel_load=0.40,
        fuel_depth=1.50,
        fuel_sav=4200.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.30,
        height_m=2.0,
        provenance="scott_burgan_2005_proxy",
        notes="Tall shrub; high intensity + ROS potential.",
    ),
    "SH7": FuelModel(
        id="SH7",
        name="Very high load dry climate shrub",
        family="SH",
        fuel_load=0.55,
        fuel_depth=2.00,
        fuel_sav=4000.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.28,
        height_m=2.5,
        provenance="scott_burgan_2005_proxy",
    ),
    "TU1": FuelModel(
        id="TU1",
        name="Low load dry climate timber-grass-shrub",
        family="TU",
        fuel_load=0.16,
        fuel_depth=0.30,
        fuel_sav=4800.0,
        moisture_extinction_pct=20.0,
        wind_reduction=0.25,
        height_m=0.5,
        provenance="scott_burgan_2005_proxy",
    ),
    "TU5": FuelModel(
        id="TU5",
        name="Very high load dry climate timber-shrub",
        family="TU",
        fuel_load=0.35,
        fuel_depth=0.90,
        fuel_sav=4000.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.20,
        height_m=1.5,
        provenance="scott_burgan_2005_proxy",
    ),
    "TL3": FuelModel(
        id="TL3",
        name="Moderate load conifer litter",
        family="TL",
        fuel_load=0.14,
        fuel_depth=0.10,
        fuel_sav=5500.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.18,
        height_m=0.1,
        provenance="scott_burgan_2005_proxy",
        notes="Surface litter; lower midflame wind under canopy.",
    ),
    "TL6": FuelModel(
        id="TL6",
        name="Moderate load broadleaf litter",
        family="TL",
        fuel_load=0.18,
        fuel_depth=0.12,
        fuel_sav=5000.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.18,
        height_m=0.12,
        provenance="scott_burgan_2005_proxy",
    ),
}

# --- Mediterranean custom engineering priors ---
# Inspired by Dimitrakopoulos (phrygana/maquis), Elia Apulia, Prometheus FT,
# Vega 2024 structure (shrub depth/load emphasis) — not published parameter dumps.

_MED: dict[str, FuelModel] = {
    "MED_GRASS": FuelModel(
        id="MED_GRASS",
        name="Mediterranean dry grassland / phrygana grass",
        family="MED",
        fuel_load=0.12,
        fuel_depth=0.35,
        fuel_sav=6400.0,
        moisture_extinction_pct=15.0,
        wind_reduction=0.45,
        height_m=0.4,
        provenance="dimitrakopoulos_prometheus_proxy",
        notes="Fast surface fires, medium–low intensity (Dimitrakopoulos 2002).",
    ),
    "MED_PHRYGANA": FuelModel(
        id="MED_PHRYGANA",
        name="Phrygana / low sclerophyll shrub <1 m",
        family="MED",
        fuel_load=0.20,
        fuel_depth=0.70,
        fuel_sav=5000.0,
        moisture_extinction_pct=20.0,
        wind_reduction=0.38,
        height_m=0.8,
        provenance="dimitrakopoulos_prometheus_proxy",
    ),
    "MED_MAQUIS_LOW": FuelModel(
        id="MED_MAQUIS_LOW",
        name="Maquis / matorral 1–1.5 m",
        family="MED",
        fuel_load=0.30,
        fuel_depth=1.20,
        fuel_sav=4300.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.32,
        height_m=1.3,
        provenance="dimitrakopoulos_elia_proxy",
        notes="Default CLM Tobarra-class scrub prior.",
    ),
    "MED_MAQUIS_TALL": FuelModel(
        id="MED_MAQUIS_TALL",
        name="Tall maquis / high load shrub 1.5–3 m",
        family="MED",
        fuel_load=0.45,
        fuel_depth=2.00,
        fuel_sav=4000.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.28,
        height_m=2.2,
        provenance="dimitrakopoulos_elia_proxy",
        notes="Highest Med surface ROS/FLI in Elia-style WUI scenarios.",
    ),
    "MED_PINE_LITTER": FuelModel(
        id="MED_PINE_LITTER",
        name="Aleppo / Mediterranean pine litter + light understorey",
        family="MED",
        fuel_load=0.16,
        fuel_depth=0.15,
        fuel_sav=5200.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.18,
        height_m=0.2,
        provenance="mitsopoulos_halepensis_proxy",
        notes="Surface only; crown fire needs CBH/CBD module (not in lite).",
    ),
    "MED_SHRUB_BRACKEN": FuelModel(
        id="MED_SHRUB_BRACKEN",
        name="Atlantic/NW shrub–bracken custom structure (Vega-style)",
        family="MED",
        fuel_load=0.38,
        fuel_depth=1.40,
        fuel_sav=4100.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.30,
        height_m=1.6,
        provenance="vega_2024_structure_proxy",
        notes="Standard SB models mis-assign Galician shrub; custom needed.",
    ),
    "PROM_FT3": FuelModel(
        id="PROM_FT3",
        name="Prometheus FT3 medium shrub",
        family="PROM",
        fuel_load=0.28,
        fuel_depth=1.00,
        fuel_sav=4500.0,
        moisture_extinction_pct=22.0,
        wind_reduction=0.33,
        height_m=1.5,
        provenance="prometheus_1999_proxy",
    ),
    "UNKNOWN": FuelModel(
        id="UNKNOWN",
        name="Unknown / missing fuel class",
        family="SB",
        fuel_load=0.0,
        fuel_depth=0.0,
        fuel_sav=1.0,
        moisture_extinction_pct=25.0,
        wind_reduction=0.4,
        height_m=0.0,
        provenance="sentinel",
        notes="Forces ABSTAIN in physics prior.",
    ),
}

FUEL_CATALOG: dict[str, FuelModel] = {**_SB, **_MED}

# CLC level-2-ish → fuel model (coarse ops crosswalk)
CLC_TO_FUEL: dict[str, str] = {
    "321": "MED_GRASS",  # natural grasslands
    "322": "MED_PHRYGANA",  # moors and heathland
    "323": "MED_MAQUIS_LOW",  # sclerophyllous vegetation
    "324": "MED_MAQUIS_TALL",  # transitional woodland-shrub
    "311": "TL6",  # broad-leaved forest
    "312": "MED_PINE_LITTER",  # coniferous
    "313": "TU1",  # mixed forest
    "231": "GR2",  # pastures
    "211": "GR2",  # non-irrigated arable
    "212": "GR2",
    "221": "GR2",  # vineyards → grass/crop proxy
    "222": "GR2",
    "223": "MED_MAQUIS_LOW",  # olive groves → light scrub proxy
    "241": "GR2",
    "242": "GR2",
    "243": "GS2",
    "244": "GS2",
    "333": "UNKNOWN",  # sparsely vegetated
    "331": "UNKNOWN",  # beaches
    "332": "UNKNOWN",  # bare rock
    "334": "UNKNOWN",  # burnt
    "411": "UNKNOWN",  # inland marshes
    "412": "UNKNOWN",
    "511": "UNKNOWN",  # water
    "512": "UNKNOWN",
    "112": "UNKNOWN",  # discontinuous urban
    "111": "UNKNOWN",
    "121": "UNKNOWN",
    "122": "UNKNOWN",
    "123": "UNKNOWN",
    "124": "UNKNOWN",
    "131": "UNKNOWN",
    "132": "UNKNOWN",
    "133": "UNKNOWN",
    "141": "GR2",  # green urban
    "142": "GR2",
    "default": "MED_MAQUIS_LOW",
}

# ESA WorldCover 10 m legend → Med/SB fuel (engineering crosswalk)
# https://esa-worldcover.org/en/data-access
WORLDCOVER_TO_FUEL: dict[int, str] = {
    10: "MED_PINE_LITTER",  # Tree cover (Med proxy; not species-specific)
    20: "MED_MAQUIS_LOW",  # Shrubland
    30: "MED_GRASS",  # Grassland
    40: "GR2",  # Cropland
    50: "UNKNOWN",  # Built-up
    60: "UNKNOWN",  # Bare / sparse vegetation
    70: "UNKNOWN",  # Snow and ice
    80: "UNKNOWN",  # Permanent water bodies
    90: "MED_GRASS",  # Herbaceous wetland
    95: "UNKNOWN",  # Mangroves
    100: "MED_PHRYGANA",  # Moss and lichen
}

# Prometheus-style height classes (optional local maps)
PROMETHEUS_TO_FUEL: dict[str, str] = {
    "1": "MED_GRASS",
    "2": "MED_PHRYGANA",
    "3": "MED_MAQUIS_LOW",
    "4": "MED_MAQUIS_TALL",
    "5": "MED_PINE_LITTER",
    "6": "TU1",
    "7": "TL3",
}


def get_fuel(fuel_id: str) -> FuelModel:
    key = (fuel_id or "UNKNOWN").strip().upper()
    # allow lowercase med ids
    if key not in FUEL_CATALOG:
        # try original case
        if fuel_id in FUEL_CATALOG:
            return FUEL_CATALOG[fuel_id]
        return FUEL_CATALOG["UNKNOWN"]
    return FUEL_CATALOG[key]


def list_fuel_ids() -> list[str]:
    return sorted(k for k in FUEL_CATALOG if k != "UNKNOWN")


def fuel_from_clc(clc_code: str | int | None) -> FuelModel:
    if clc_code is None:
        return get_fuel(CLC_TO_FUEL["default"])
    code = str(clc_code).strip()
    # tolerate float codes from rasters (323.0)
    if code.endswith(".0"):
        code = code[:-2]
    fid = CLC_TO_FUEL.get(code, CLC_TO_FUEL["default"])
    return get_fuel(fid)


def fuel_from_worldcover(code: int | float | None) -> FuelModel:
    if code is None or (isinstance(code, float) and not np_isfinite(code)):
        return get_fuel("UNKNOWN")
    c = int(code)
    fid = WORLDCOVER_TO_FUEL.get(c, "UNKNOWN")
    return get_fuel(fid)


def fuel_from_landcover(
    code: str | int | float | None,
    *,
    scheme: str = "clc",
) -> FuelModel:
    """Dispatch land-cover code → FuelModel by scheme."""
    sch = (scheme or "clc").lower()
    if sch in {"clc", "corine"}:
        return fuel_from_clc(code)
    if sch in {"worldcover", "esa_worldcover", "wc"}:
        try:
            return fuel_from_worldcover(int(float(code)) if code is not None else None)
        except (TypeError, ValueError):
            return get_fuel("UNKNOWN")
    if sch in {"prometheus", "prom"}:
        if code is None:
            return get_fuel("UNKNOWN")
        key = str(int(float(code))) if str(code).replace(".", "", 1).isdigit() else str(code)
        return get_fuel(PROMETHEUS_TO_FUEL.get(key, "UNKNOWN"))
    if sch in {"fuel_id", "wfd"}:
        return get_fuel(str(code) if code is not None else "UNKNOWN")
    return fuel_from_clc(code)


def np_isfinite(x: float) -> bool:
    import math

    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def catalog_as_list() -> list[dict[str, Any]]:
    return [m.to_dict() for m in FUEL_CATALOG.values() if m.id != "UNKNOWN"]


def crosswalk_tables() -> dict[str, Any]:
    return {
        "clc": dict(CLC_TO_FUEL),
        "worldcover": {str(k): v for k, v in WORLDCOVER_TO_FUEL.items()},
        "prometheus": dict(PROMETHEUS_TO_FUEL),
    }
