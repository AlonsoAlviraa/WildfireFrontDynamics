"""Audit real LWIR data for coherent observed front speeds (no ground truth required).

This script closes the gap between ingestion and ML validation by verifying that
a real GeoTIFF sequence produces *observable, physically plausible* front-speed
estimates using ``estimate_observed_speeds``.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path>

from wildfire_front.models import ScenarioConfig


def audit_observed_speeds(
    images: Path,
    *,
    masks: Path | None,
    output: Path,
    event_id: str,
    sensor_id: str,
    estimated_error_m: float,
    band: int = 1,
    threshold: float | None = None,
    mad_z: float | None = None,
) -> dict[str, object]:
    """Ingest a real sequence and verify observed speeds are coherent."""

    from wildfire_front.ingestion.geotiff import ingest_geotiff_sequence, write_ingest_manifest
    from wildfire_front.reconstruction import estimate_observed_speeds

    result = ingest_geotiff_sequence(
        images,
        masks_dir=masks,
        event_id=event_id,
        sensor_id=sensor_id,
        estimated_error_m=estimated_error_m,
        band=band,
        threshold=threshold,
        mad_z=mad_z,
    )
    output.mkdir(parents=True, exist_ok=True)
    write_ingest_manifest(result.records, output / "ingest_manifest.csv")

    observations = list(result.observations)
    if len(observations) < 2:
        summary = {
            "event_id": event_id,
            "sensor_id": sensor_id,
            "observation_count": len(observations),
            "verdict": "insufficient_observations",
            "reason": "need at least 2 accepted observations to estimate speeds",
        }
        (output / "speed_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    config = ScenarioConfig(
        event_id=event_id,
        sensor_id=sensor_id,
        position_error_m=estimated_error_m,
    )
    estimates = estimate_observed_speeds(observations, config)

    # Persist per-angle speed estimates
    with (output / "observed_speeds.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "time_start_s", "time_end_s", "angle_deg", "displacement_m",
            "speed_m_min", "uncertainty_m_min", "observable", "abstention_reason",
        ])
        for est in estimates:
            writer.writerow([
                est.time_start_s, est.time_end_s, round(est.angle_deg, 1),
                round(est.displacement_m, 3),
                None if est.speed_m_min is None else round(est.speed_m_min, 4),
                round(est.uncertainty_m_min, 4),
                est.observable,
                est.abstention_reason,
            ])

    observable = [e for e in estimates if e.observable and e.speed_m_min is not None]
    speeds = [float(e.speed_m_min) for e in observable]  # type: ignore[arg-type]

    # Physical plausibility gates for wildfire spread
    MAX_PLAUSIBLE_SPEED_M_MIN = 120.0  # ~7.2 km/h, extreme spotting excluded
    MIN_PLAUSIBLE_SPEED_M_MIN = 0.1

    plausible = [s for s in speeds if MIN_PLAUSIBLE_SPEED_M_MIN <= abs(s) <= MAX_PLAUSIBLE_SPEED_M_MIN]
    implausible = [s for s in speeds if not (MIN_PLAUSIBLE_SPEED_M_MIN <= abs(s) <= MAX_PLAUSIBLE_SPEED_M_MIN)]

    median_speed = statistics.median(speeds) if speeds else None
    mean_speed = statistics.fmean(speeds) if speeds else None

    if speeds:
        observable_ratio = len(observable) / len(estimates)
        plausibility_ratio = len(plausible) / len(speeds)
    else:
        observable_ratio = 0.0
        plausibility_ratio = 0.0

    # Verdict logic
    if observable_ratio < 0.25:
        verdict = "low_observability"
        reason = "less than 25% of angles produced observable movement; increase temporal coverage or resolution"
    elif plausibility_ratio < 0.8:
        verdict = "implausible_speeds"
        reason = f"{len(implausible)} of {len(speeds)} speeds outside plausible range"
    elif median_speed is not None and abs(median_speed) < MIN_PLAUSIBLE_SPEED_M_MIN:
        verdict = "near_zero_speed"
        reason = "median observed speed below detection threshold"
    else:
        verdict = "coherent"
        reason = "observed speeds are observable and physically plausible"

    summary = {
        "event_id": event_id,
        "sensor_id": sensor_id,
        "observation_count": len(observations),
        "accepted_inputs": sum(1 for r in result.records if r.status == "accepted"),
        "total_inputs": len(result.records),
        "num_speed_estimates": len(estimates),
        "num_observable": len(observable),
        "observable_ratio": round(observable_ratio, 4),
        "median_speed_m_min": round(median_speed, 4) if median_speed is not None else None,
        "mean_speed_m_min": round(mean_speed, 4) if mean_speed is not None else None,
        "min_speed_m_min": round(min(speeds), 4) if speeds else None,
        "max_speed_m_min": round(max(speeds), 4) if speeds else None,
        "plausible_count": len(plausible),
        "implausible_count": len(implausible),
        "plausibility_ratio": round(plausibility_ratio, 4),
        "verdict": verdict,
        "reason": reason,
    }
    (output / "speed_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit real LWIR data for coherent observed front speeds."
    )
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--masks", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-id", default="real_event")
    parser.add_argument("--sensor-id", required=True)
    parser.add_argument("--estimated-error-m", type=float, required=True)
    parser.add_argument("--band", type=int, default=1)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--mad-z", type=float)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = audit_observed_speeds(
        args.images,
        masks=args.masks,
        output=args.output,
        event_id=args.event_id,
        sensor_id=args.sensor_id,
        estimated_error_m=args.estimated_error_m,
        band=args.band,
        threshold=args.threshold,
        mad_z=args.mad_z,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()