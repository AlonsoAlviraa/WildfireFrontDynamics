"""Verify every materialized Caldor clean17 channel and leakage invariant."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import rasterio

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from wildfire_front.open_if.caldor_temporal import (
    erc_available_at_t0,
    hrrr_window_report,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACK = ROOT / "data/open_if/external_bridge/US_FIREBENCH_CALDOR_2021"
DEFAULT_ACQUISITION = ROOT / "docs/CALDOR_CLEAN17_ACQUISITION.json"
DEFAULT_OUTPUT = ROOT / "docs/CALDOR_CLEAN17_AUDIT.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(acquisition_path: Path, pack_root: Path) -> dict[str, Any]:
    acquisition = json.loads(acquisition_path.read_text(encoding="utf-8"))
    expected_order = acquisition["channel_order"]
    target = acquisition["target_grid"]
    unique_files: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    cycles_safe = True
    hrrr_windows_exact = True
    erc_values_available = True
    channel_sets_exact = True
    for dynamic in acquisition["dynamic"]:
        t0 = datetime.fromisoformat(dynamic["t0_utc"].replace("Z", "+00:00"))
        cycle = datetime.fromisoformat(
            dynamic["hrrr_cycle_utc"].replace("Z", "+00:00")
        )
        lag = int(dynamic["hrrr_availability_lag_hours"])
        cycles_safe &= cycle <= t0 - timedelta(hours=lag)
        leads = [int(value) for value in dynamic.get("hrrr_leads_hours", [])]
        window = hrrr_window_report(cycle, t0, dynamic["t1_utc"], leads)
        window_exact = bool(window["window_ok"])
        hrrr_windows_exact &= window_exact
        channels = dynamic["channels"]
        channel_sets_exact &= set(channels) == set(expected_order)
        erc = channels.get("erc_g", {})
        erc_day = str(erc.get("gridmet_day", ""))
        erc_available = bool(erc_day) and erc_available_at_t0(erc_day, t0)
        erc_values_available &= erc_available
        for _channel_name, channel in channels.items():
            unique_files.setdefault(channel["path"], channel)
        rows.append(
            {
                "t0_utc": dynamic["t0_utc"],
                "t1_utc": dynamic["t1_utc"],
                "hrrr_cycle_utc": dynamic["hrrr_cycle_utc"],
                "hrrr_target_window_exact": window_exact,
                "gridmet_erc_available_at_t0": erc_available,
                "n_channels": len(channels),
            }
        )
    files: list[dict[str, Any]] = []
    for relative, declared in sorted(unique_files.items()):
        path = pack_root / relative
        exists = path.is_file()
        observed_hash = _sha256(path) if exists else None
        grid_ok = False
        if exists:
            with rasterio.open(path) as dataset:
                grid_ok = (
                    dataset.crs is not None
                    and dataset.crs.to_string() == target["crs"]
                    and dataset.width == target["width"]
                    and dataset.height == target["height"]
                    and abs(dataset.transform.a - target["gsd_m"]) < 1e-9
                    and abs(dataset.transform.e + target["gsd_m"]) < 1e-9
                    and dataset.nodata is not None
                )
        files.append(
            {
                "path": relative,
                "exists": exists,
                "sha256_declared": declared["sha256"],
                "sha256_observed": observed_hash,
                "hash_matches": observed_hash == declared["sha256"],
                "grid_ok": grid_ok,
                "finite_fraction": declared["finite_fraction"],
                "min": declared["min"],
                "max": declared["max"],
            }
        )
    n_pairs = len(acquisition["dynamic"])
    spatial_ok = (
        acquisition["status"] == "complete"
        and acquisition["n_real_channels"] == 17
        and n_pairs == 15
        and channel_sets_exact
        and cycles_safe
        and bool(files)
        and all(row["exists"] and row["hash_matches"] and row["grid_ok"] for row in files)
        and acquisition["leakage_audit"]["post_fire_outcomes_used"] is False
        and acquisition["leakage_audit"]["t1_labels_used_as_inputs"] is False
        and acquisition["leakage_audit"]["neutral_placeholder_channels_used"]
        is False
    )
    temporal_ok = cycles_safe and hrrr_windows_exact and erc_values_available
    ok = spatial_ok and temporal_ok
    return {
        "schema": "wfd_caldor_clean17_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ok": ok,
        "n_pairs": n_pairs,
        "n_channels_per_pair": len(expected_order),
        "channel_order": expected_order,
        "channel_sets_exact": channel_sets_exact,
        "spatial_ok": spatial_ok,
        "temporal_ok": temporal_ok,
        "hrrr_cycles_respect_availability_lag": cycles_safe,
        "hrrr_target_windows_exact": hrrr_windows_exact,
        "gridmet_erc_values_available_at_t0": erc_values_available,
        "unique_materialized_channel_files": len(files),
        "files": files,
        "rows": rows,
        "checkpoint_gate": acquisition["compatibility"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquisition", type=Path, default=DEFAULT_ACQUISITION)
    parser.add_argument("--pack-root", type=Path, default=DEFAULT_PACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit(args.acquisition, args.pack_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "n_pairs": report["n_pairs"],
                "n_channels_per_pair": report["n_channels_per_pair"],
                "unique_files": report["unique_materialized_channel_files"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
