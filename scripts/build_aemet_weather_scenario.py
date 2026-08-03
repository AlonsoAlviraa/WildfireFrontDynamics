#!/usr/bin/env python3
"""Build WeatherScenario JSON from AEMET open-data (source=aemet).

Usage:
  set AEMET_API_KEY=...
  python scripts/build_aemet_weather_scenario.py --date 2024-08-02 --station 8175 \\
      --fire-id tobarra_20240802 --out data/fuel_stack/tobarra/weather_aemet_20240802.json

Or from a pre-downloaded AEMET JSON list:
  python scripts/build_aemet_weather_scenario.py --from-json path/to/aemet_raw.json --date 2024-08-02
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.fuel.weather import (  # noqa: E402
    DEFAULT_TOBARRA_AEMET_STATION,
    build_aemet_weather_for_fire_day,
    load_aemet_api_key,
    load_dotenv,
    save_weather_scenario,
    weather_scenario_from_aemet_daily,
)


def main() -> int:
    load_dotenv(ROOT / ".env")
    ap = argparse.ArgumentParser(description="AEMET → WeatherScenario (source=aemet)")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--station", default=DEFAULT_TOBARRA_AEMET_STATION)
    ap.add_argument("--station-name", default=None)
    ap.add_argument("--fire-id", default="tobarra_20240802")
    ap.add_argument("--api-key", default=None, help="or env AEMET_API_KEY / .env")
    ap.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="Pre-fetched AEMET daily list JSON (skip network)",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--prev-ffmc", type=float, default=85.0)
    args = ap.parse_args()

    if args.from_json is not None:
        raw = json.loads(args.from_json.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and isinstance(raw.get("datos"), list):
            raw = raw["datos"]
        if not isinstance(raw, list):
            print("from-json must be a list of daily records", file=sys.stderr)
            return 2
        rec = raw[0]
        for r in raw:
            if str(r.get("fecha", "")).startswith(args.date):
                rec = r
                break
        ws = weather_scenario_from_aemet_daily(
            rec,
            fire_id=args.fire_id,
            station_id=args.station,
            station_name=args.station_name,
            prev_ffmc=args.prev_ffmc,
        )
    else:
        key = load_aemet_api_key(explicit=args.api_key)
        if not key:
            print(
                "Need --api-key or AEMET_API_KEY (env/.env), or --from-json offline file",
                file=sys.stderr,
            )
            return 2
        try:
            ws = build_aemet_weather_for_fire_day(
                api_key=key,
                date=args.date,
                station=args.station,
                fire_id=args.fire_id,
                station_name=args.station_name,
                prev_ffmc=args.prev_ffmc,
            )
        except Exception as exc:
            print(f"AEMET fetch failed: {exc}", file=sys.stderr)
            return 1

    out = args.out or (
        ROOT
        / "data"
        / "fuel_stack"
        / "tobarra"
        / f"weather_aemet_{args.date.replace('-', '')}.json"
    )
    save_weather_scenario(ws, out)
    print(json.dumps(ws.to_dict(), indent=2, ensure_ascii=False))
    print(f"\nWrote {out}", file=sys.stderr)
    print(
        f"Use: python scripts/build_fuel_terrain_stack.py --fire tobarra "
        f"--with-physics --with-envelope --with-ensemble --weather {out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
