#!/usr/bin/env python3
"""C1: ERA5 BLOCKED stamp + clean W0 vs W1 weather ablation board.

W0 = DEM-lapse spatial bridge-init board (existing Kaggle result)
W1 = Open-Meteo gridded (strongest available when CDS blocked)

Does not invent ERA5 rasters. Fusion remains OFF.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
NOW = datetime.now(UTC).isoformat()


def _fold_ious(board: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for f in board.get("folds") or []:
        h = f.get("held")
        iou = f.get("model_iou")
        if h and iou is not None:
            out[str(h)] = float(iou)
    return out


def main() -> int:
    cdsapi_ok = False
    try:
        import cdsapi  # noqa: F401

        cdsapi_ok = True
    except ImportError:
        cdsapi_ok = False

    rc = Path.home() / ".cdsapirc"
    era5 = {
        "schema": "wfd_weather_era5_status_v1",
        "created_utc": NOW,
        "updated_utc": NOW,
        "work_class": "weather_gridded_v1",
        "source": "ERA5-Land",
        "status": "BLOCKED",
        "blocked_reason": "no ~/.cdsapirc (CDS API credentials missing)",
        "cdsapi_installed": cdsapi_ok,
        "cdsapi_rc_path": str(rc.as_posix()),
        "cdsapi_rc_present": rc.is_file(),
        "install_path": {
            "pip": "pip install cdsapi",
            "rc_template": ("url: https://cds.climate.copernicus.eu/api\nkey: <UID>:<API_KEY>"),
            "rc_location": "~/.cdsapirc",
            "script": "python scripts/stage_era5_land_weather.py --fire CARDOSO --download",
            "licences": "Accept ERA5-Land licences on CDS website before download",
            "docs": "docs/WEATHER_GRIDDED_SOURCE.md",
        },
        "n_variance_gate_pass": 0,
        "fires": {},
        "fallback_w1": {
            "source": "open_meteo_archive_interp_v1",
            "status_json": "outputs/ml_eval/weather_open_meteo_status.json",
            "n_variance_gate_pass": 6,
            "not_era5": True,
            "stronger_than_dem_lapse": True,
        },
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "dem_lapse_is_not_reanalysis": True,
        "press_weather_forbidden": True,
    }
    try:
        from wildfire_front.fuel.spatial_v1_sources import list_core_source_ids

        for sid in list_core_source_ids():
            era5["fires"][sid] = {
                "source_id": sid,
                "era5_dir": f"data/weather_era5/{sid.lower()}",
                "staged": False,
                "variance_gate_pass": False,
                "reason": "CDS credentials missing — not downloaded",
            }
    except Exception as exc:  # noqa: BLE001
        era5["inventory_error"] = str(exc)

    out_era5 = ROOT / "outputs" / "ml_eval" / "weather_era5_status.json"
    out_era5.parent.mkdir(parents=True, exist_ok=True)
    out_era5.write_text(json.dumps(era5, indent=2), encoding="utf-8")
    print("C1 era5 BLOCKED ->", out_era5)

    w0_path = (
        ROOT / "outputs" / "kaggle_spatial_v1_bridge_init" / "spatial_v1_bridge_init_board.json"
    )
    w1_path = (
        ROOT
        / "outputs"
        / "kaggle_spatial_v1_openmeteo_bridge"
        / "spatial_v1_openmeteo_bridge_board.json"
    )
    if not w0_path.is_file() or not w1_path.is_file():
        print("BLOCKED: missing W0 or W1 board JSON", file=sys.stderr)
        return 2

    w0_board = json.loads(w0_path.read_text(encoding="utf-8"))
    w1_board = json.loads(w1_path.read_text(encoding="utf-8"))
    m0 = _fold_ious(w0_board)
    m1 = _fold_ious(w1_board)
    folds = [h for h in CORE3 if h in m0 and h in m1]
    if len(folds) < 3:
        print("BLOCKED: incomplete identical folds for ablation", file=sys.stderr)
        return 2

    mean0 = sum(m0[h] for h in folds) / len(folds)
    mean1 = sum(m1[h] for h in folds) / len(folds)
    min0 = min(m0[h] for h in folds)
    min1 = min(m1[h] for h in folds)
    delta = mean1 - mean0
    weather_lift = delta >= 0.01

    ablation = {
        "schema": "wfd_weather_w0_w1_ablation_v1",
        "created_utc": NOW,
        "work_class": "weather_gridded_v1_ablation",
        "era5_status": "BLOCKED",
        "era5_status_path": "outputs/ml_eval/weather_era5_status.json",
        "protocol": {
            "W0": "DEM-lapse / prior spatial weather via spatial_v1 bridge-init",
            "W1": "open_meteo_archive_interp_v1 (strongest gridded available; NOT ERA5)",
            "identical_folds": list(folds),
            "recipe": "residual_small + multi_if→15ch bridge adapted init",
            "architecture": "residual_small",
            "comparability": "same CORE3 held folds, same bridge-init recipe class",
        },
        "W0": {
            "label": "DEM-lapse spatial bridge",
            "board": str(w0_path.as_posix()),
            "kernel": "alonsoalviraaaa/wfd-spatial-v1-bridge-init",
            "weather_provenance": "dem_lapse_v1",
            "folds": m0,
            "mean": mean0,
            "min": min0,
        },
        "W1": {
            "label": "Open-Meteo Archive IDW gridded",
            "board": str(w1_path.as_posix()),
            "kernel": "alonsoalviraaaa/wfd-spatial-v1-openmeteo-bridge",
            "weather_provenance": "open_meteo_archive_interp_v1",
            "not_era5": True,
            "status_json": "outputs/ml_eval/weather_open_meteo_status.json",
            "folds": m1,
            "mean": mean1,
            "min": min1,
        },
        "delta_mean_W1_minus_W0": delta,
        "delta_min_W1_minus_W0": min1 - min0,
        "weather_lift_threshold": 0.01,
        "WEATHER_LIFT": weather_lift,
        "WEATHER_NULL": not weather_lift,
        "verdict": "WEATHER_LIFT" if weather_lift else "WEATHER_NULL",
        "note": (
            "ERA5 CDS blocked (no ~/.cdsapirc). Ablation uses Open-Meteo as W1 vs DEM-lapse "
            "spatial as W0. Δmean must be ≥0.01 for WEATHER_LIFT; else WEATHER_NULL (honest)."
        ),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
    }

    abl_lab = ROOT / "outputs" / "ml_eval" / "lab_loop" / "weather_w0_w1_ablation_board.json"
    abl_lab.parent.mkdir(parents=True, exist_ok=True)
    abl_lab.write_text(json.dumps(ablation, indent=2), encoding="utf-8")
    (ROOT / "outputs" / "ml_eval" / "weather_w0_w1_ablation_board.json").write_text(
        json.dumps(ablation, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "verdict": ablation["verdict"],
                "delta_mean": delta,
                "mean_W0": mean0,
                "mean_W1": mean1,
                "board": str(abl_lab.as_posix()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
