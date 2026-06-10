"""Scientific data-quality summaries for observed geometry sequences."""

from __future__ import annotations

from collections import Counter

import numpy as np

from .geometry_speed import signed_area
from .ingestion.geotiff import GeoTiffIngestRecord
from .models import FrontObservation


def summarize_ingest_quality(records: tuple[GeoTiffIngestRecord, ...]) -> dict[str, object]:
    reasons = Counter(record.reason for record in records if record.reason)
    total = len(records)
    accepted = sum(record.status == "accepted" for record in records)
    fractions = [
        record.positive_pixel_fraction
        for record in records
        if record.positive_pixel_fraction is not None
    ]
    return {
        "input_count": total,
        "accepted_inputs": accepted,
        "review_inputs": sum(record.status == "review" for record in records),
        "rejected_inputs": sum(record.status == "rejected" for record in records),
        "accepted_input_ratio": accepted / total if total else 0.0,
        "qa_reason_counts": dict(sorted(reasons.items())),
        "positive_pixel_fraction_median": float(np.median(fractions)) if fractions else None,
        "positive_pixel_fraction_max": float(np.max(fractions)) if fractions else None,
    }


def summarize_observation_quality(observations: list[FrontObservation]) -> dict[str, object]:
    ordered = sorted(observations, key=lambda item: item.time_s)
    intervals = np.diff([item.time_s for item in ordered])
    areas = [
        sum(abs(signed_area(component)) for component in observation.components)
        for observation in ordered
    ]
    area_differences = np.diff(areas)
    return {
        "observation_count": len(ordered),
        "component_count_max": max((len(item.components) for item in ordered), default=0),
        "interval_s_median": float(np.median(intervals)) if len(intervals) else None,
        "interval_s_min": float(np.min(intervals)) if len(intervals) else None,
        "interval_s_max": float(np.max(intervals)) if len(intervals) else None,
        "non_increasing_timestamp_count": int(np.sum(intervals <= 0)) if len(intervals) else 0,
        "observed_area_m2_first": float(areas[0]) if areas else None,
        "observed_area_m2_last": float(areas[-1]) if areas else None,
        "observed_area_decrease_count": int(np.sum(area_differences < 0)) if len(area_differences) else 0,
    }
