"""Weather scenario objects for fuel-stack physics / hybrid envelopes.

Honesty rails:
- Never present map-note or CLI defaults as official AEMET observations.
- ``source`` must be one of: observed | scenario_assumed | aemet | unknown.
- ``weather_scenario_assumed`` / envelope status ``inputs_assumed`` only when
  source is assumed/unknown (or caller forces assumed).
- Do not invent wind when no scenario and no explicit args.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

# Cardinal / intercardinal → meteorological *from* degrees
_CARDINAL_FROM_DEG: dict[str, float] = {
    "N": 0.0,
    "NNE": 22.5,
    "NE": 45.0,
    "ENE": 67.5,
    "E": 90.0,
    "ESE": 112.5,
    "SE": 135.0,
    "SSE": 157.5,
    "S": 180.0,
    "SSW": 202.5,
    "SW": 225.0,
    "WSW": 247.5,
    "W": 270.0,
    "WNW": 292.5,
    "NW": 315.0,
    "NNW": 337.5,
}

VALID_SOURCES = frozenset({"observed", "scenario_assumed", "aemet", "unknown"})


def load_dotenv(path: Path | str | None = None) -> Path | None:
    """Load KEY=VALUE pairs from a local ``.env`` into ``os.environ`` (no overwrite).

    Looks for ``.env`` at *path* or walks up from cwd / this file's repo root.
    Does not require python-dotenv. Returns the path loaded, or None.
    """
    import os

    candidates: list[Path] = []
    if path is not None:
        candidates.append(Path(path))
    else:
        here = Path(__file__).resolve()
        # wildfire_front/fuel/weather.py → repo root is parents[2]
        candidates.append(here.parents[2] / ".env")
        candidates.append(Path.cwd() / ".env")
    for p in candidates:
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, val = s.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
        return p
    return None


def load_aemet_api_key(*, explicit: str | None = None) -> str | None:
    """Resolve AEMET API key: explicit arg → env → .env file."""
    import os

    if explicit:
        return explicit.strip() or None
    key = os.environ.get("AEMET_API_KEY")
    if key:
        return key.strip() or None
    load_dotenv()
    key = os.environ.get("AEMET_API_KEY")
    return (key.strip() or None) if key else None


@dataclass
class WeatherScenario:
    """Explicit weather drivers with provenance for ROS physics."""

    wind_10m_ms: float | None
    wind_from_deg: float | None
    dead_fmc_pct: float | None = None
    temp_c: float | None = None
    rh_pct: float | None = None
    gust_ms: float | None = None
    source: str = "unknown"
    as_of: str | None = None
    notes: list[str] = field(default_factory=list)
    fire_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        src = str(self.source or "unknown").lower()
        if src not in VALID_SOURCES:
            self.notes = list(self.notes) + [f"source_coerced_from:{self.source}"]
            src = "unknown"
        self.source = src

    @property
    def is_assumed(self) -> bool:
        """True when weather must not be treated as station-observed truth."""
        return self.source in {"scenario_assumed", "unknown"}

    @property
    def weather_scenario_assumed(self) -> bool:
        return self.is_assumed

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["is_assumed"] = self.is_assumed
        d["weather_scenario_assumed"] = self.is_assumed
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WeatherScenario":
        notes = data.get("notes") or []
        if isinstance(notes, str):
            notes = [notes]
        return cls(
            wind_10m_ms=_opt_float(data.get("wind_10m_ms")),
            wind_from_deg=_opt_float(data.get("wind_from_deg")),
            dead_fmc_pct=_opt_float(data.get("dead_fmc_pct")),
            temp_c=_opt_float(data.get("temp_c", data.get("temperature_c"))),
            rh_pct=_opt_float(data.get("rh_pct", data.get("rh", data.get("humidity_pct")))),
            gust_ms=_opt_float(data.get("gust_ms")),
            source=str(data.get("source") or "unknown"),
            as_of=data.get("as_of"),
            notes=list(notes),
            fire_id=data.get("fire_id"),
            raw=dict(data.get("raw") or {}),
        )


def _opt_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def cardinal_to_from_deg(token: str) -> float | None:
    t = str(token).strip().upper()
    return _CARDINAL_FROM_DEG.get(t)


def kmh_to_ms(kmh: float) -> float:
    """Convert km/h → m/s (SI)."""
    return float(kmh) / 3.6


def load_weather_scenario(path: Path | str) -> WeatherScenario:
    """Load WeatherScenario JSON from disk."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(str(p))
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"weather scenario must be a JSON object: {p}")
    # allow nested {"weather_scenario": {...}}
    if "wind_10m_ms" not in data and isinstance(data.get("weather_scenario"), dict):
        data = data["weather_scenario"]
    ws = WeatherScenario.from_dict(data)
    if not ws.raw:
        ws.raw = {"path": str(p.resolve())}
    else:
        ws.raw = {**ws.raw, "path": str(p.resolve())}
    return ws


def save_weather_scenario(scenario: WeatherScenario, path: Path | str) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(scenario.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return p


def tobarra_20240802_default_scenario() -> WeatherScenario:
    """Scenario from Pablo/INFOCAM map notes (pre_analisis_1711) — **assumed**.

    Inventory string (``data/real_if/pablo_geacam_20260730_tobarra/inventory.json``)::

        pre_analisis_1711: \"02/08/2024 17:11; meteo T35 HR10 wind W21 gust40; detection 16:42\"

    Conversion honesty:
    - **W** → wind_from_deg = 270 (meteorological from).
    - **21 / 40** interpreted as **km/h** (typical INFOCAM/ARGOS map annotation),
      not Beaufort force and not m/s (21 m/s would be storm-force; force 21 invalid).
      wind_10m_ms = 21/3.6 ≈ 5.833; gust_ms = 40/3.6 ≈ 11.111.
    - **T35** → temp_c = 35; **HR10** → rh_pct = 10.
    - **dead_fmc_pct** is **not** on the map → engineering default 7.0 with note
      (not claimed as measured FMC).
    - source = ``scenario_assumed`` (map note transcription, not AEMET station API).

    Previous stack CLI hard-defaults (4.4 m/s, 270°) remain a separate
    engineering preset when no weather file is supplied.
    """
    notes = [
        "from_pablo_inventory.map_notes.pre_analisis_1711",
        "wind_speed_unit_assumed_kmh_not_ms_not_beaufort",
        "not_aemet_station_observation",
        "dead_fmc_pct=7.0 is engineering default — not measured on map",
        "gust_ms stored for audit; Rothermel-lite uses sustained wind_10m_ms",
    ]
    wind_kmh = 21.0
    gust_kmh = 40.0
    return WeatherScenario(
        wind_10m_ms=round(kmh_to_ms(wind_kmh), 4),
        wind_from_deg=270.0,
        dead_fmc_pct=7.0,
        temp_c=35.0,
        rh_pct=10.0,
        gust_ms=round(kmh_to_ms(gust_kmh), 4),
        source="scenario_assumed",
        as_of="2024-08-02T17:11:00",
        notes=notes,
        fire_id="tobarra_20240802",
        raw={
            "pre_analisis_1711": (
                "02/08/2024 17:11; meteo T35 HR10 wind W21 gust40; detection 16:42"
            ),
            "inventory_path": (
                "data/real_if/pablo_geacam_20260730_tobarra/inventory.json"
            ),
            "wind_kmh_assumed": wind_kmh,
            "gust_kmh_assumed": gust_kmh,
            "wind_cardinal": "W",
        },
    )


def scenario_from_cli_args(
    *,
    wind_10m_ms: float | None,
    wind_from_deg: float | None,
    dead_fmc_pct: float | None = None,
    source: str = "scenario_assumed",
    notes: list[str] | None = None,
    fire_id: str | None = None,
) -> WeatherScenario:
    """Build scenario from explicit CLI numbers (always assumed unless source set)."""
    return WeatherScenario(
        wind_10m_ms=wind_10m_ms,
        wind_from_deg=wind_from_deg,
        dead_fmc_pct=dead_fmc_pct,
        source=source,
        as_of=datetime.now(timezone.utc).isoformat(),
        notes=list(notes or ["from_cli_args"]),
        fire_id=fire_id,
    )


# Library / CLI engineering defaults (not station observations)
LIBRARY_DEFAULT_WIND_MS = 4.4
LIBRARY_DEFAULT_WIND_FROM_DEG = 270.0
LIBRARY_DEFAULT_FMC_PCT = 7.0

_STATION_SOURCES = frozenset({"observed", "aemet"})


@dataclass
class MergedWeatherDrivers:
    """Resolved wind/FMC after honesty merge with a WeatherScenario."""

    wind_10m_ms: float | None
    wind_from_deg: float | None
    dead_fmc_pct: float | None
    source: str
    weather_scenario_assumed: bool
    fields_filled_from_defaults: list[str] = field(default_factory=list)
    fields_missing_cleared: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def weather_partially_filled_from_defaults(self) -> bool:
        return bool(self.fields_filled_from_defaults)

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "wind_10m_ms": self.wind_10m_ms,
            "wind_from_deg": self.wind_from_deg,
            "dead_fmc_pct": self.dead_fmc_pct,
            "source": self.source,
            "weather_scenario_assumed": self.weather_scenario_assumed,
            "weather_partially_filled_from_defaults": self.weather_partially_filled_from_defaults,
            "fields_filled_from_defaults": list(self.fields_filled_from_defaults),
            "fields_missing_cleared": list(self.fields_missing_cleared),
            "notes": list(self.notes),
        }


def _scenario_source(scenario: WeatherScenario | Mapping[str, Any] | None) -> str:
    if scenario is None:
        return "unknown"
    if isinstance(scenario, WeatherScenario):
        return str(scenario.source or "unknown")
    return str(scenario.get("source") or "unknown")


def _scenario_field(
    scenario: WeatherScenario | Mapping[str, Any] | None, name: str
) -> float | None:
    if scenario is None:
        return None
    if isinstance(scenario, WeatherScenario):
        return _opt_float(getattr(scenario, name, None))
    return _opt_float(scenario.get(name))


def merge_weather_drivers(
    scenario: WeatherScenario | Mapping[str, Any] | None,
    *,
    wind_10m_ms: float | None = None,
    wind_from_deg: float | None = None,
    dead_fmc_pct: float | None = None,
    library_wind_ms: float = LIBRARY_DEFAULT_WIND_MS,
    library_from_deg: float = LIBRARY_DEFAULT_WIND_FROM_DEG,
    library_fmc: float = LIBRARY_DEFAULT_FMC_PCT,
    fill_library_when_missing: bool = True,
) -> MergedWeatherDrivers:
    """Merge scenario + library/CLI fallbacks with honesty for incomplete observed.

    Rules:
    - ``source in {observed, aemet}`` and missing ``wind_10m_ms`` → **do not** fill
      library 4.4; leave ``None`` so physics can ABSTAIN (missing_wind). Cleared
      fields listed in ``fields_missing_cleared``.
    - Station-like source missing ``wind_from_deg`` / ``dead_fmc_pct`` may be
      filled from library defaults, but then ``weather_scenario_assumed=True``
      and ``fields_filled_from_defaults`` records which keys were filled.
    - ``scenario_assumed`` / ``unknown`` may use library/CLI fallbacks freely
      (assumed remains True) when ``fill_library_when_missing`` is True.
    - When ``fill_library_when_missing`` is False and no scenario value / caller
      value exists, leave field as ``None`` (obs-only CLI paths).
    - Never leave ``weather_scenario_assumed=False`` while using library wind.
    """
    source = _scenario_source(scenario)
    station_like = source in _STATION_SOURCES
    filled: list[str] = []
    cleared: list[str] = []
    notes: list[str] = []

    ws_wind = _scenario_field(scenario, "wind_10m_ms")
    ws_from = _scenario_field(scenario, "wind_from_deg")
    ws_fmc = _scenario_field(scenario, "dead_fmc_pct")

    # --- wind_10m_ms ---
    if ws_wind is not None:
        out_wind: float | None = float(ws_wind)
    elif station_like:
        # Incomplete station payload: never present library wind as observed
        out_wind = None
        cleared.append("wind_10m_ms")
        notes.append(
            "observed_or_aemet_missing_wind_10m_ms_not_filled_from_library"
        )
    elif wind_10m_ms is not None:
        out_wind = float(wind_10m_ms)
        # caller/CLI value under assumed scenario
        if scenario is not None:
            filled.append("wind_10m_ms")
    elif fill_library_when_missing:
        out_wind = float(library_wind_ms)
        filled.append("wind_10m_ms")
    else:
        out_wind = None

    # --- wind_from_deg ---
    if ws_from is not None:
        out_from: float | None = float(ws_from)
    elif station_like:
        if out_wind is not None:
            # have sustained wind but no direction → fill with stamp (assumed)
            out_from = float(library_from_deg)
            filled.append("wind_from_deg")
            notes.append("observed_or_aemet_missing_wind_from_filled_library")
        else:
            out_from = None
            cleared.append("wind_from_deg")
    elif wind_from_deg is not None:
        out_from = float(wind_from_deg)
        if scenario is not None:
            filled.append("wind_from_deg")
    elif fill_library_when_missing:
        out_from = float(library_from_deg)
        filled.append("wind_from_deg")
    else:
        out_from = None

    # --- dead_fmc_pct ---
    if ws_fmc is not None:
        out_fmc: float | None = float(ws_fmc)
    elif station_like:
        if fill_library_when_missing or out_wind is not None:
            out_fmc = float(library_fmc)
            filled.append("dead_fmc_pct")
            notes.append("observed_or_aemet_missing_fmc_filled_library_engineering")
        else:
            out_fmc = None
            cleared.append("dead_fmc_pct")
    elif dead_fmc_pct is not None:
        out_fmc = float(dead_fmc_pct)
        if scenario is not None:
            filled.append("dead_fmc_pct")
    elif fill_library_when_missing:
        out_fmc = float(library_fmc)
        filled.append("dead_fmc_pct")
    else:
        out_fmc = None

    # Assumed flag honesty
    if scenario is None:
        assumed = True
        notes.append("no_weather_scenario_library_or_caller")
    elif station_like:
        # Station source stays non-assumed only if we did not fill any defaults
        # and did not invent wind. Missing wind (cleared) keeps assumed=False
        # (physics abstains) — incomplete but not falsely filled.
        if filled:
            assumed = True
            notes.append(
                "station_source_but_defaults_filled_weather_scenario_assumed"
            )
        else:
            assumed = False
    else:
        assumed = source in {"scenario_assumed", "unknown"} or bool(filled)

    return MergedWeatherDrivers(
        wind_10m_ms=out_wind,
        wind_from_deg=out_from,
        dead_fmc_pct=out_fmc,
        source=source,
        weather_scenario_assumed=assumed,
        fields_filled_from_defaults=filled,
        fields_missing_cleared=cleared,
        notes=notes,
    )


def resolve_weather_for_stack(
    *,
    weather_path: Path | str | None = None,
    wind_10m_ms: float | None = None,
    wind_from_deg: float | None = None,
    dead_fmc_pct: float | None = None,
    use_tobarra_map_default: bool = False,
    fire_id: str | None = None,
) -> WeatherScenario | None:
    """Resolve weather with honesty: file > map default > explicit CLI > None.

    Returns None only when no path, no map default, and no wind provided —
    callers must not invent wind in that case.
    """
    if weather_path is not None:
        return load_weather_scenario(weather_path)
    if use_tobarra_map_default:
        return tobarra_20240802_default_scenario()
    if wind_10m_ms is not None or wind_from_deg is not None:
        return scenario_from_cli_args(
            wind_10m_ms=wind_10m_ms,
            wind_from_deg=wind_from_deg,
            dead_fmc_pct=dead_fmc_pct,
            source="scenario_assumed",
            notes=["from_cli_explicit_or_preset"],
            fire_id=fire_id,
        )
    return None


def _aemet_safe_float(val: Any, *, default: float | None = None) -> float | None:
    """Parse AEMET fields like '25,3', 'Ip' (inappreciable), empty."""
    if val is None or val == "":
        return default
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s in {"Ip", "ip", "Varias", "Calma", "calma"}:
        return 0.0 if default is None else default
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return default


def aemet_dir_to_from_deg(dir_raw: Any) -> float | None:
    """Convert AEMET daily ``dir`` field to meteorological from-degrees.

    AEMET open-data daily climatology often encodes direction in **tens of
    degrees** (0–36). Values already in 0–360 are left as degrees.
    ``99`` is AEMET's conventional code for variable direction → None.
    """
    d = _aemet_safe_float(dir_raw)
    if d is None:
        return None
    if d == 99.0:
        return None  # variable / not a true azimuth
    if d <= 36.0:
        return (d * 10.0) % 360.0
    return d % 360.0


def weather_scenario_from_aemet_daily(
    record: Mapping[str, Any],
    *,
    fire_id: str | None = None,
    station_id: str | None = None,
    station_name: str | None = None,
    prev_ffmc: float = 85.0,
    compute_fmc: bool = True,
) -> WeatherScenario:
    """Build ``source=aemet`` WeatherScenario from one AEMET daily record.

    Expected keys (raw AEMET or parsed by ``fetch_aemet_fwi``):
    - fecha / date
    - tmed / temp_c
    - hrMedia / hrmedia / rh_percent / rh_pct
    - velmedia / wind_ms
    - dir / wind_dir (99 = variable)
    - racha / gust_ms
    - prec / precip_mm
    - optional ffmc

    ``dead_fmc_pct`` from FFMC via ``ffmc_to_moisture`` when T/RH/wind present.
    """
    # Support both raw AEMET (camelCase) and already-parsed dicts
    temp = _aemet_safe_float(record.get("temp_c", record.get("tmed")))
    rh = _aemet_safe_float(
        record.get(
            "rh_pct",
            record.get(
                "rh_percent",
                record.get("hrMedia", record.get("hrmedia", record.get("hr_media"))),
            ),
        )
    )
    wind = _aemet_safe_float(record.get("wind_ms", record.get("velmedia")))
    dir_raw = record.get("wind_dir", record.get("dir"))
    wind_from = aemet_dir_to_from_deg(dir_raw)
    gust = _aemet_safe_float(record.get("gust_ms", record.get("racha")))
    precip = _aemet_safe_float(record.get("precip_mm", record.get("prec")), default=0.0)
    fecha = record.get("date") or record.get("fecha")
    ffmc = _aemet_safe_float(record.get("ffmc"))
    fmc: float | None = None
    notes = [
        "source_aemet_daily_climatology",
        "wind_velmedia_is_10m_mean_ms_per_aemet_docs",
        "dir_tens_of_deg_if_le_36",
    ]
    if station_id:
        notes.append(f"station_id={station_id}")
    if station_name:
        notes.append(f"station_name={station_name}")
    if _aemet_safe_float(dir_raw) == 99.0:
        notes.append("wind_dir_variable_aemet_code_99")

    if compute_fmc and temp is not None and rh is not None and wind is not None:
        try:
            from wildfire_front.ml.physics import compute_ffmc, ffmc_to_moisture

            if ffmc is None:
                wind_kmh = float(wind) * 3.6
                ffmc = float(
                    compute_ffmc(
                        temp_c=float(temp),
                        rh_percent=float(rh),
                        wind_kmh=wind_kmh,
                        precip_mm=float(precip or 0.0),
                        prev_ffmc=float(prev_ffmc),
                    )
                )
            fmc = float(ffmc_to_moisture(ffmc))
            notes.append(f"dead_fmc_from_ffmc={ffmc:.2f}")
        except Exception as exc:  # pragma: no cover
            notes.append(f"ffmc_compute_failed:{exc}")
            fmc = LIBRARY_DEFAULT_FMC_PCT
            notes.append("dead_fmc_fallback_library_7")
    elif fmc is None:
        fmc = LIBRARY_DEFAULT_FMC_PCT
        notes.append("dead_fmc_library_default_no_t_rh_wind")

    return WeatherScenario(
        wind_10m_ms=round(wind, 4) if wind is not None else None,
        wind_from_deg=round(wind_from, 2) if wind_from is not None else None,
        dead_fmc_pct=round(fmc, 3) if fmc is not None else None,
        temp_c=temp,
        rh_pct=rh,
        gust_ms=round(gust, 4) if gust is not None else None,
        source="aemet",
        as_of=str(fecha) if fecha else None,
        notes=notes,
        fire_id=fire_id,
        raw={
            "aemet_record": dict(record),
            "station_id": station_id,
            "station_name": station_name,
            "ffmc": ffmc,
            "precip_mm": precip,
        },
    )


def _decode_aemet_body(body: bytes) -> str:
    """AEMET open-data payloads are often ISO-8859-1 (e.g. station names with accents)."""
    for encoding in ("utf-8", "iso-8859-1", "cp1252"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def fetch_aemet_daily_records(
    api_key: str,
    station: str,
    start_date: str,
    end_date: str,
    *,
    timeout_s: int = 60,
) -> list[dict[str, Any]]:
    """Fetch AEMET daily climatology JSON for a station (two-step open-data API).

    Requires a personal API key from https://opendata.aemet.es/
    """
    import urllib.request

    base = "https://opendata.aemet.es/opendata/api"
    ini = f"{start_date}T00:00:00UTC"
    fin = f"{end_date}T23:59:59UTC"
    url = (
        f"{base}/valores/climatologicos/diarios/datos/"
        f"fechaini/{ini}/fechafin/{fin}/estacion/{station}"
    )
    req = urllib.request.Request(url)
    req.add_header("api_key", api_key)
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        meta = json.loads(_decode_aemet_body(resp.read()))
    if meta.get("estado") != 200:
        raise RuntimeError(
            f"AEMET status {meta.get('estado')}: {meta.get('descripcion')}"
        )
    data_url = meta.get("datos")
    if not data_url:
        raise RuntimeError("AEMET response missing datos URL")
    req2 = urllib.request.Request(data_url)
    req2.add_header("Accept", "application/json")
    with urllib.request.urlopen(req2, timeout=timeout_s) as resp:
        raw = json.loads(_decode_aemet_body(resp.read()))
    if not isinstance(raw, list):
        raise RuntimeError("AEMET datos payload is not a list")
    return list(raw)


# Albacete / Tobarra-region default station (Los Llanos) used in fetch_aemet_fwi docs
DEFAULT_TOBARRA_AEMET_STATION = "8175"  # common Albacete base; override if needed
# Note: 4624E appears in fetch_aemet_fwi.py examples — keep both documented.
AEMET_STATION_HINTS = {
    "tobarra_20240802": {
        "station_id": "8175",
        "station_name": "Albacete / Los Llanos (verify against inventario)",
        "note": "Nearest-region climatology — not on-fire tower",
    },
}


def build_aemet_weather_for_fire_day(
    *,
    api_key: str,
    date: str,
    station: str = DEFAULT_TOBARRA_AEMET_STATION,
    fire_id: str | None = None,
    station_name: str | None = None,
    prev_ffmc: float = 85.0,
) -> WeatherScenario:
    """Fetch one calendar day from AEMET and return WeatherScenario source=aemet."""
    # AEMET needs a range; use single day
    raw = fetch_aemet_daily_records(api_key, station, date, date)
    if not raw:
        raise RuntimeError(f"No AEMET records for station={station} date={date}")
    # pick exact fecha match if multiple
    rec = raw[0]
    for r in raw:
        if str(r.get("fecha", "")).startswith(date):
            rec = r
            break
    return weather_scenario_from_aemet_daily(
        rec,
        fire_id=fire_id,
        station_id=station,
        station_name=station_name,
        prev_ffmc=prev_ffmc,
    )
