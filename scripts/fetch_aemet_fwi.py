#!/usr/bin/env python3
"""Fetch daily weather data from AEMET API and compute FWI/FFMC.

Usage:
    python scripts/fetch_aemet_fwi.py --api-key YOUR_KEY --station 4624E \\
        --start 2024-08-01 --end 2024-08-03 --output data/aemet/tobarra_fwi.csv

AEMET API docs: https://opendata.aemet.es/
Stations: https://opendata.aemet.es/opendata/api/valores/climatologicos/inventarioestaciones/all
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wildfire_front.ml.physics import compute_ffmc

AEMET_BASE = "https://opendata.aemet.es/opendata/api"


def fetch_aemet_daily(
    api_key: str,
    station: str,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Fetch daily climatology data from AEMET for a station.

    Args:
        api_key: AEMET OpenData API key.
        station: Station indicator (e.g., '4624E' for Albacete Los Llanos).
        start_date: Start date YYYY-MM-DD.
        end_date: End date YYYY-MM-DD.

    Returns:
        List of daily observation dicts with parsed numeric fields.
    """
    # AEMET API requires dates in format YYYY-MM-DDTHH:MM:SSUTC
    ini = f"{start_date}T00:00:00UTC"
    fin = f"{end_date}T23:59:59UTC"
    url = (
        f"{AEMET_BASE}/valores/climatologicos/diarios/datos/"
        f"fechaini/{ini}/fechafin/{fin}/estacion/{station}"
    )

    print(f"[AEMET] Requesting: {url}")

    # Step 1: Get the data URL from the API response
    req = urllib.request.Request(url)
    req.add_header("api_key", api_key)
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] API request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if meta.get("estado") != 200:
        print(
            f"[ERROR] AEMET returned status {meta.get('estado')}: "
            f"{meta.get('descripcion', 'unknown')}",
            file=sys.stderr,
        )
        sys.exit(1)

    data_url = meta.get("datos")
    if not data_url:
        print("[ERROR] No 'datos' URL in AEMET response", file=sys.stderr)
        sys.exit(1)

    # Step 2: Fetch the actual data
    print(f"[AEMET] Fetching data from: {data_url}")
    req2 = urllib.request.Request(data_url)
    req2.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req2, timeout=60) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[ERROR] Data fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    return raw_data


def parse_aemet_obs(raw: list[dict]) -> list[dict]:
    """Parse AEMET raw JSON observations into clean numeric dicts.

    AEMET fields:
        fecha: date (YYYY-MM-DD)
        tmed: mean temperature (deg C)
        hrmedia: mean humidity (%)
        velmedia: mean wind speed (m/s)
        prec: precipitation (mm)
        dir: wind direction (deg)
    """
    parsed = []
    for obs in raw:

        def _safe_float(val) -> float:
            """Parse AEMET values like '25,3' or 'Ip' (inappreciable)."""
            if val is None or val == "" or val == "Ip":
                return 0.0
            if isinstance(val, (int, float)):
                return float(val)
            return float(str(val).replace(",", "."))

        try:
            record = {
                "date": obs.get("fecha", ""),
                "temp_c": _safe_float(obs.get("tmed")),
                "rh_percent": _safe_float(obs.get("hrmedia")),
                "wind_ms": _safe_float(obs.get("velmedia")),
                "precip_mm": _safe_float(obs.get("prec")),
                "wind_dir": _safe_float(obs.get("dir")),
            }
            parsed.append(record)
        except (ValueError, KeyError) as e:
            print(f"[WARN] Skipping malformed record: {e}", file=sys.stderr)
            continue

    return parsed


def compute_fwi_series(records: list[dict]) -> list[dict]:
    """Compute FFMC for each day using a running FFMC memory.

    FFMC is a wetting/drying memory variable: each day's FFMC depends on
    the previous day's value and today's weather.

    Args:
        records: List of parsed weather dicts sorted by date.

    Returns:
        Records with an added 'ffmc' field.
    """
    prev_ffmc = 85.0  # Default initial FFMC (moderate dryness)
    for rec in records:
        # wind for FFMC is in km/h; AEMET gives m/s
        wind_kmh = rec["wind_ms"] * 3.6
        ffmc = float(
            compute_ffmc(
                temp_c=rec["temp_c"],
                rh_percent=rec["rh_percent"],
                wind_kmh=wind_kmh,
                precip_mm=rec["precip_mm"],
                prev_ffmc=prev_ffmc,
            )
        )
        rec["ffmc"] = ffmc
        prev_ffmc = ffmc  # Update for next day

    return records


def save_csv(records: list[dict], output_path: Path) -> None:
    """Save FWI records to a CSV file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "temp_c", "rh_percent", "wind_ms", "precip_mm", "wind_dir", "ffmc"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"[OK] Saved {len(records)} records to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch AEMET weather data and compute FWI/FFMC.")
    parser.add_argument("--api-key", required=True, help="AEMET OpenData API key")
    parser.add_argument("--station", required=True, help="AEMET station indicator (e.g., 4624E)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--output", default="data/aemet/fwi.csv", help="Output CSV path")
    args = parser.parse_args()

    # 1. Fetch raw data
    raw = fetch_aemet_daily(
        api_key=args.api_key,
        station=args.station,
        start_date=args.start,
        end_date=args.end,
    )
    print(f"[AEMET] Received {len(raw)} raw records")

    # 2. Parse
    records = parse_aemet_obs(raw)
    print(f"[AEMET] Parsed {len(records)} valid records")

    # 3. Compute FWI
    records = compute_fwi_series(records)
    print(f"[FWI] Computed FFMC for {len(records)} days")

    # 4. Save
    save_csv(records, Path(args.output))

    # 5. Summary
    ffmc_values = [r["ffmc"] for r in records]
    print("\n--- FFMC Summary ---")
    print(f"  Range: {min(ffmc_values):.1f} - {max(ffmc_values):.1f}")
    print(f"  Mean:  {np.mean(ffmc_values):.1f}")
    print(f"  Max danger days (FFMC > 90): {sum(1 for v in ffmc_values if v > 90)}")


if __name__ == "__main__":
    main()
