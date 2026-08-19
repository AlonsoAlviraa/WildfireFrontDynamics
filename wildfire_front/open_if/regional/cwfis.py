"""Canadian Wildland Fire Information System WFS adapter."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from .base import (
    AdapterError,
    BaseRegionalFireAdapter,
    FetchPayload,
    NormalizationResult,
    RegionalQuery,
    make_observation_feature,
    normalize_iso,
    query_accepts,
)

NEW_WFS = "https://geoserver.cwfif.nrcan.gc.ca/geoserver/wfs"
LEGACY_WFS = "https://cwfis.cfs.nrcan.gc.ca/geoserver/public/wfs"

CWFIS_LAYERS: dict[str, dict[str, Any]] = {
    "activefires": {
        "endpoint": NEW_WFS,
        "typename": "public:cwfif_national_activefires",
        "observation_kind": "incident_location",
        "geometry_semantics": "reported_active_fire_location",
        "role": "event_discovery",
        "event_keys": ("national_fire_id", "agency_fire_id", "id"),
        "time_keys": ("status_date", "record_start", "situation_report_date"),
        "sort_by": "id A",
    },
    "reportedfires": {
        "endpoint": NEW_WFS,
        "typename": "public:cwfif_national_reportedfires",
        "observation_kind": "incident_location",
        "geometry_semantics": "reported_fire_location",
        "role": "event_discovery",
        "event_keys": ("national_fire_id", "agency_fire_id", "id"),
        "time_keys": ("status_date", "record_start", "situation_report_date"),
        "sort_by": "id A",
    },
    "hotspots": {
        "endpoint": LEGACY_WFS,
        "typename": "public:hotspots",
        "observation_kind": "hotspot",
        "geometry_semantics": "thermal_detection_point_or_pixel",
        "role": "active_fire_observation",
        "event_keys": ("id", "sensor", "rep_date"),
        "time_keys": ("rep_date", "date", "acq_date"),
        "sort_by": None,
    },
    "fire_perimeter_estimate": {
        "endpoint": LEGACY_WFS,
        "typename": "public:m3polygons",
        "observation_kind": "perimeter_proxy",
        "geometry_semantics": "buffered_hotspot_fire_perimeter_estimate",
        "role": "active_fire_observation",
        "event_keys": ("fire_id", "id", "polyid"),
        "time_keys": ("rep_date", "date", "acq_date"),
        "sort_by": None,
    },
    "burned_area": {
        "endpoint": LEGACY_WFS,
        "typename": "public:nbac",
        "observation_kind": "burn_scar",
        "geometry_semantics": "final_or_seasonal_burned_area_composite",
        "role": "eo_input",
        "event_keys": ("fire_id", "nbac_id", "id"),
        "time_keys": ("date", "year", "rep_date"),
        "sort_by": None,
    },
}


class CWFISAdapter(BaseRegionalFireAdapter):
    """Fetch active fires and explicitly typed CWFIS vector layers."""

    source_id = "ca_cwfis_ogc"
    provider = "Natural Resources Canada / CWFIS-CWFIF"
    licence_id = "open-government-licence-canada-2.0"
    raw_extension = ".geojson"

    @property
    def honesty(self) -> dict[str, Any]:
        return {
            "active_fire_points_are_not_perimeters": True,
            "m3_polygons_are_buffered_hotspot_estimates_not_official_perimeters": True,
            "nbac_is_burned_area_not_temporal_progression": True,
            "provider_warns_data_may_not_show_most_current_situation": True,
            "candidate_progression_labels": False,
        }

    @staticmethod
    def layer_config(layer: str) -> dict[str, Any]:
        try:
            return CWFIS_LAYERS[layer]
        except KeyError as exc:
            allowed = ", ".join(sorted(CWFIS_LAYERS))
            raise ValueError(f"unknown CWFIS layer {layer!r}; choose: {allowed}") from exc

    @classmethod
    def query_url(cls, query: RegionalQuery, *, offset: int, count: int) -> str:
        config = cls.layer_config(query.cwfis_layer)
        params: dict[str, str | int] = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": config["typename"],
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": count,
        }
        if offset:
            params["startIndex"] = offset
        if config.get("sort_by"):
            params["sortBy"] = config["sort_by"]
        if query.bbox is not None:
            params["bbox"] = ",".join(str(value) for value in (*query.bbox, "EPSG:4326"))
        return f"{config['endpoint']}?{urlencode(params)}"

    def fetch(self, query: RegionalQuery) -> list[FetchPayload]:
        query.validate()
        self.layer_config(query.cwfis_layer)
        payloads: list[FetchPayload] = []
        offset = 0
        remaining = query.limit
        while remaining > 0:
            count = min(1000, remaining)
            url = self.query_url(query, offset=offset, count=count)
            payload = self.request(
                url,
                name=f"{query.cwfis_layer}_{offset:08d}.geojson",
                accept="application/geo+json,application/json",
            )
            try:
                document = json.loads(payload.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise AdapterError("CWFIS returned invalid JSON") from exc
            features = document.get("features") or []
            payloads.append(payload)
            received = len(features)
            if received == 0:
                break
            offset += received
            remaining -= received
            number_matched = document.get("numberMatched")
            if received < count or (isinstance(number_matched, int) and offset >= number_matched):
                break
        return payloads

    def normalize(
        self,
        payloads: list[FetchPayload],
        query: RegionalQuery,
        *,
        retrieved_at: str,
    ) -> NormalizationResult:
        config = self.layer_config(query.cwfis_layer)
        result = NormalizationResult()
        for payload in payloads:
            try:
                document = json.loads(payload.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                result.rejected.append({"payload": payload.name, "reason": type(exc).__name__})
                continue
            for position, raw in enumerate(document.get("features") or []):
                props = raw.get("properties") or {}
                event_id = next(
                    (
                        props.get(key)
                        for key in config["event_keys"]
                        if props.get(key) not in (None, "")
                    ),
                    None,
                )
                upstream_id = raw.get("id") or props.get("id") or event_id or position
                if event_id in (None, ""):
                    event_id = f"cwfis-unlinked-{upstream_id}"
                observed_at = next(
                    (
                        normalize_iso(props.get(key))
                        for key in config["time_keys"]
                        if props.get(key) not in (None, "")
                    ),
                    None,
                )
                source_updated_at = normalize_iso(
                    props.get("status_date") or props.get("record_start")
                )
                flags = ["cwfis_approximation_check_provincial_source"]
                if query.cwfis_layer == "activefires":
                    flags.append("incident_location_not_perimeter")
                elif query.cwfis_layer == "hotspots":
                    flags.append("hotspot_not_perimeter")
                elif query.cwfis_layer == "fire_perimeter_estimate":
                    flags.append("buffered_hotspot_proxy_not_progression_label")
                elif query.cwfis_layer == "burned_area":
                    flags.append("final_or_seasonal_scar_not_progression_label")
                try:
                    feature = make_observation_feature(
                        source_id=self.source_id,
                        upstream_item_id=str(upstream_id),
                        event_id=str(event_id),
                        geometry=raw.get("geometry"),
                        observation_kind=config["observation_kind"],
                        geometry_semantics=config["geometry_semantics"],
                        role=config["role"],
                        observed_at=observed_at,
                        published_at=None,
                        source_updated_at=source_updated_at,
                        retrieved_at=retrieved_at,
                        source_url=payload.url,
                        licence_id=self.licence_id,
                        provisional=True,
                        candidate_progression_label=False,
                        quality_flags=flags,
                        upstream_properties=props,
                    )
                except ValueError as exc:
                    result.rejected.append(
                        {
                            "payload": payload.name,
                            "upstream_item_id": str(upstream_id),
                            "reason": str(exc),
                        }
                    )
                    continue
                if query_accepts(feature, query):
                    result.features.append(feature)
                if len(result.features) >= query.limit:
                    return result
        return result
