"""Event-disjoint geometry baselines for approved WFIGS temporal pairs."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from pyproj import CRS, Transformer
from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform
from shapely.validation import make_valid

from .base import _atomic_write_json, utc_now
from .temporal_pairs import _iter_geojson_features

BASELINE_SCHEMA = "wfd_wfigs_geometry_baseline_v1"
DEFAULT_RADII_M = (0, 30, 60, 120, 250, 500, 1000, 2000, 4000)


def _safe_geometry(value: dict[str, Any]) -> BaseGeometry:
    geometry = shape(value)
    if not geometry.is_valid:
        geometry = make_valid(geometry)
    if geometry.is_empty:
        raise ValueError("empty geometry")
    return geometry


def _project_pair(
    first: BaseGeometry, second: BaseGeometry
) -> tuple[BaseGeometry, BaseGeometry]:
    centroid = first.centroid
    local = CRS.from_proj4(
        f"+proj=aeqd +lat_0={centroid.y:.10f} +lon_0={centroid.x:.10f} "
        "+datum=WGS84 +units=m +no_defs"
    )
    transformer = Transformer.from_crs("EPSG:4326", local, always_xy=True)
    return transform(transformer.transform, first), transform(transformer.transform, second)


def _iou(first: BaseGeometry, second: BaseGeometry) -> float:
    union = first.union(second)
    if union.is_empty or union.area <= 0:
        return 0.0
    return float(first.intersection(second).area / union.area)


def _metrics(
    first: BaseGeometry,
    second: BaseGeometry,
    radius_m: float,
    *,
    true_growth: BaseGeometry | None = None,
) -> dict[str, float]:
    prediction = first if radius_m <= 0 else first.buffer(radius_m)
    if true_growth is None:
        true_growth = second.difference(first)
    predicted_growth = prediction.difference(first)
    return {
        "full_iou": _iou(prediction, second),
        "growth_transition_iou": _iou(predicted_growth, true_growth),
    }


def _aggregate(
    rows: list[dict[str, Any]], radii: tuple[int, ...]
) -> dict[str, dict[str, float | int]]:
    output: dict[str, dict[str, float | int]] = {}
    for radius in radii:
        key = str(radius)
        usable = [row for row in rows if key in row.get("radii", {})]
        by_event: dict[str, list[dict[str, float]]] = defaultdict(list)
        for row in usable:
            by_event[str(row["event_id"])].append(row["radii"][key])
        event_full = [mean(item["full_iou"] for item in values) for values in by_event.values()]
        event_growth = [
            mean(item["growth_transition_iou"] for item in values)
            for values in by_event.values()
        ]
        output[key] = {
            "radius_m": radius,
            "pairs": len(usable),
            "events": len(by_event),
            "pair_macro_full_iou": (
                mean(row["radii"][key]["full_iou"] for row in usable) if usable else 0.0
            ),
            "event_macro_full_iou": mean(event_full) if event_full else 0.0,
            "pair_macro_growth_transition_iou": (
                mean(row["radii"][key]["growth_transition_iou"] for row in usable)
                if usable
                else 0.0
            ),
            "event_macro_growth_transition_iou": mean(event_growth) if event_growth else 0.0,
        }
    return output


class WFIGSGeometryBaseline:
    """Evaluate copy/dilation baselines with VAL-only selection and frozen TEST."""

    def __init__(
        self,
        *,
        pairs_path: Path,
        observations_path: Path,
        output_path: Path,
        radii_m: tuple[int, ...] = DEFAULT_RADII_M,
    ) -> None:
        if not radii_m or radii_m[0] != 0 or any(radius < 0 for radius in radii_m):
            raise ValueError("radii_m must start at zero and contain no negative values")
        self.pairs_path = Path(pairs_path)
        self.observations_path = Path(observations_path)
        self.output_path = Path(output_path)
        self.radii_m = tuple(sorted(set(radii_m)))

    def build(self) -> dict[str, Any]:
        document = json.loads(self.pairs_path.read_text(encoding="utf-8"))
        pairs = list(document.get("pairs") or [])
        wanted = {
            str(pair[key])
            for pair in pairs
            for key in ("t0_observation_id", "t1_observation_id")
        }
        geometries: dict[str, BaseGeometry] = {}
        for feature in _iter_geojson_features(self.observations_path):
            properties = feature.get("properties") or {}
            observation_id = str(properties.get("observation_id") or "")
            if observation_id not in wanted:
                continue
            try:
                geometries[observation_id] = _safe_geometry(feature["geometry"])
            except (KeyError, TypeError, ValueError, GEOSException):
                continue
            if len(geometries) == len(wanted):
                break

        rows: list[dict[str, Any]] = []
        failure_counts: dict[str, int] = defaultdict(int)
        for pair in pairs:
            first = geometries.get(str(pair["t0_observation_id"]))
            second = geometries.get(str(pair["t1_observation_id"]))
            row: dict[str, Any] = {
                "pair_id": pair["pair_id"],
                "event_id": pair["event_id"],
                "split": pair["split"],
                "status": "usable",
                "radii": {},
            }
            if first is None or second is None:
                row["status"] = "reject"
                row["reason"] = "geometry_missing"
                failure_counts["geometry_missing"] += 1
                rows.append(row)
                continue
            try:
                projected_first, projected_second = _project_pair(first, second)
                true_growth = projected_second.difference(projected_first)
                for radius in self.radii_m:
                    row["radii"][str(radius)] = {
                        metric: round(value, 8)
                        for metric, value in _metrics(
                            projected_first,
                            projected_second,
                            float(radius),
                            true_growth=true_growth,
                        ).items()
                    }
            except (GEOSException, TypeError, ValueError, OverflowError):
                row["status"] = "reject"
                row["reason"] = "projection_or_geometry_operation_failed"
                row["radii"] = {}
                failure_counts["projection_or_geometry_operation_failed"] += 1
            rows.append(row)

        by_split = {
            split: _aggregate(
                [row for row in rows if row["split"] == split and row["status"] == "usable"],
                self.radii_m,
            )
            for split in ("train", "validation", "test")
        }
        validation = by_split["validation"]
        selected_full = min(
            self.radii_m,
            key=lambda radius: (
                -float(validation[str(radius)]["event_macro_full_iou"]),
                radius,
            ),
        )
        selected_growth = min(
            self.radii_m,
            key=lambda radius: (
                -float(validation[str(radius)]["event_macro_growth_transition_iou"]),
                radius,
            ),
        )
        test = by_split["test"]
        copy_test = test["0"]
        full_test = test[str(selected_full)]
        growth_test = test[str(selected_growth)]
        report = {
            "schema": BASELINE_SCHEMA,
            "generated_at": utc_now(),
            "counts": {
                "pairs_input": len(pairs),
                "pairs_usable": sum(row["status"] == "usable" for row in rows),
                "pairs_rejected": sum(row["status"] != "usable" for row in rows),
                "rejection_reasons": dict(sorted(failure_counts.items())),
            },
            "radii_m": list(self.radii_m),
            "selection": {
                "full_iou": {
                    "metric": "validation_event_macro_full_iou",
                    "selected_radius_m": selected_full,
                },
                "growth_transition_iou": {
                    "metric": "validation_event_macro_growth_transition_iou",
                    "selected_radius_m": selected_growth,
                },
                "test_not_used_for_selection": True,
            },
            "aggregate": by_split,
            "sealed_test": {
                "copy_radius_0m": copy_test,
                "selected_full_iou_baseline": full_test,
                "selected_growth_baseline": growth_test,
                "delta_event_macro_full_iou_vs_copy": round(
                    float(full_test["event_macro_full_iou"])
                    - float(copy_test["event_macro_full_iou"]),
                    8,
                ),
                "delta_event_macro_growth_iou_vs_copy": round(
                    float(growth_test["event_macro_growth_transition_iou"])
                    - float(copy_test["event_macro_growth_transition_iou"]),
                    8,
                ),
            },
            "per_pair": rows,
            "claims": {
                "event_disjoint_split_used": True,
                "learned_model_training_executed": False,
                "diagnostic_geometry_baseline_only": True,
                "wfigs_internal_noncommercial_training_allowed": True,
                "wfigs_raw_or_derived_data_publication_blocked": True,
                "cross_protocol_comparison_to_clm_v34_forbidden": True,
            },
        }
        _atomic_write_json(self.output_path, report)
        return report


__all__ = ["BASELINE_SCHEMA", "DEFAULT_RADII_M", "WFIGSGeometryBaseline"]
