"""WFIGS Interagency Perimeters adapter."""

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
    epoch_ms_to_iso,
    make_observation_feature,
    query_accepts,
)
from .wfigs_rights import WFIGS_RIGHTS_POLICY_ID

WFIGS_LAYER_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/ArcGIS/rest/services/"
    "WFIGS_Interagency_Perimeters/FeatureServer/0"
)
WFIGS_FIELDS = (
    "OBJECTID,GlobalID,poly_IncidentName,poly_FeatureCategory,poly_MapMethod,"
    "poly_GISAcres,poly_Acres_AutoCalc,poly_DeleteThis,poly_FeatureAccess,"
    "poly_FeatureStatus,poly_IsVisible,poly_CreateDate,poly_DateCurrent,"
    "poly_PolygonDateTime,poly_IRWINID,poly_FORID,poly_Source,"
    "attr_IncidentName,attr_IncidentTypeCategory,attr_FireDiscoveryDateTime,"
    "attr_IrwinID,attr_UniqueFireIdentifier,attr_POOState,attr_GACC,attr_IsValid,"
    "attr_FinalAcres,BurnPeriod,AcreageChange,"
    "attr_CreatedOnDateTime_dt,attr_ModifiedOnDateTime_dt,attr_Source"
)


class WFIGSAdapter(BaseRegionalFireAdapter):
    """Fetch and normalize public WFIGS best-available fire perimeters."""

    source_id = "us_wfigs_perimeters"
    provider = "National Interagency Fire Center / WFIGS"
    licence_id = WFIGS_RIGHTS_POLICY_ID
    raw_extension = ".geojson"

    @property
    def honesty(self) -> dict[str, Any]:
        return {
            "working_data_may_change": True,
            "best_available_perimeter_is_not_automatically_a_progression_series": True,
            "candidate_requires_same_event_temporal_pair_and_leakage_audit": True,
            "not_validated_tactical_dispatch": True,
        }

    @staticmethod
    def query_url(query: RegionalQuery, *, offset: int, count: int) -> str:
        where = [
            "(poly_DeleteThis IS NULL OR poly_DeleteThis <> 'Yes')",
            "(poly_FeatureAccess IS NULL OR poly_FeatureAccess = 'Public')",
            "(poly_IsVisible IS NULL OR poly_IsVisible = 'Yes')",
        ]
        start = query.start
        end = query.end
        if start:
            where.append(f"poly_PolygonDateTime >= TIMESTAMP '{start[:10]} 00:00:00'")
        if end:
            where.append(f"poly_PolygonDateTime <= TIMESTAMP '{end[:10]} 23:59:59'")
        params: dict[str, str | int] = {
            "where": " AND ".join(where),
            "outFields": WFIGS_FIELDS,
            "returnGeometry": "true",
            "outSR": "4326",
            "orderByFields": "OBJECTID ASC",
            "resultOffset": offset,
            "resultRecordCount": count,
            "f": "geojson",
        }
        if query.bbox is not None:
            west, south, east, north = query.bbox
            params.update(
                {
                    "geometry": json.dumps(
                        {
                            "xmin": west,
                            "ymin": south,
                            "xmax": east,
                            "ymax": north,
                            "spatialReference": {"wkid": 4326},
                        },
                        separators=(",", ":"),
                    ),
                    "geometryType": "esriGeometryEnvelope",
                    "spatialRel": "esriSpatialRelIntersects",
                    "inSR": "4326",
                }
            )
        return f"{WFIGS_LAYER_URL}/query?{urlencode(params)}"

    def fetch(self, query: RegionalQuery) -> list[FetchPayload]:
        query.validate()
        payloads: list[FetchPayload] = []
        offset = 0
        remaining = query.limit
        while remaining > 0:
            count = min(2000, remaining)
            url = self.query_url(query, offset=offset, count=count)
            payload = self.request(
                url,
                name=f"page_{offset:08d}.geojson",
                accept="application/geo+json,application/json",
            )
            try:
                document = json.loads(payload.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise AdapterError("WFIGS returned invalid JSON") from exc
            if document.get("error"):
                raise AdapterError(f"WFIGS query error: {document['error']}")
            features = document.get("features") or []
            payloads.append(payload)
            received = len(features)
            if received == 0:
                break
            offset += received
            remaining -= received
            if received < count and not document.get("exceededTransferLimit"):
                break
        return payloads

    def normalize(
        self,
        payloads: list[FetchPayload],
        query: RegionalQuery,
        *,
        retrieved_at: str,
    ) -> NormalizationResult:
        result = NormalizationResult()
        for payload in payloads:
            try:
                document = json.loads(payload.body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                result.rejected.append({"payload": payload.name, "reason": type(exc).__name__})
                continue
            for raw in document.get("features") or []:
                props = raw.get("properties") or {}
                object_id = props.get("GlobalID") or props.get("OBJECTID")
                event_id = (
                    props.get("attr_UniqueFireIdentifier")
                    or props.get("attr_IrwinID")
                    or props.get("poly_IRWINID")
                    or props.get("poly_FORID")
                    or object_id
                )
                if object_id in (None, "") or event_id in (None, ""):
                    result.rejected.append(
                        {"payload": payload.name, "reason": "missing_upstream_or_event_id"}
                    )
                    continue
                category = str(props.get("poly_FeatureCategory") or "")
                observed_at = epoch_ms_to_iso(props.get("poly_PolygonDateTime"))
                source_updated_at = epoch_ms_to_iso(
                    props.get("attr_ModifiedOnDateTime_dt") or props.get("poly_DateCurrent")
                )
                geometry = raw.get("geometry")
                geometry_type = str((geometry or {}).get("type") or "")
                daily = "daily fire perimeter" in category.lower()
                public_approved = (
                    str(props.get("poly_FeatureAccess") or "Public").lower() == "public"
                    and str(props.get("poly_FeatureStatus") or "Approved").lower()
                    == "approved"
                    and str(props.get("poly_DeleteThis") or "No").lower() != "yes"
                )
                candidate = (
                    daily
                    and public_approved
                    and observed_at is not None
                    and geometry_type in {"Polygon", "MultiPolygon"}
                )
                flags = [
                    "wfigs_working_or_best_available_data",
                    "requires_event_disjoint_split",
                ]
                if not daily:
                    flags.append("not_daily_fire_perimeter_category")
                if not candidate:
                    flags.append("not_progression_candidate")
                try:
                    feature = make_observation_feature(
                        source_id=self.source_id,
                        upstream_item_id=str(object_id),
                        event_id=str(event_id).strip("{}"),
                        geometry=geometry,
                        observation_kind="perimeter",
                        geometry_semantics=(
                            "wildfire_daily_perimeter" if daily else "best_available_fire_perimeter"
                        ),
                        role="progression_label",
                        observed_at=observed_at,
                        published_at=None,
                        source_updated_at=source_updated_at,
                        retrieved_at=retrieved_at,
                        source_url=payload.url,
                        licence_id=self.licence_id,
                        provisional=True,
                        candidate_progression_label=candidate,
                        quality_flags=flags,
                        upstream_properties=props,
                    )
                except ValueError as exc:
                    result.rejected.append(
                        {
                            "payload": payload.name,
                            "upstream_item_id": str(object_id),
                            "reason": str(exc),
                        }
                    )
                    continue
                if query_accepts(feature, query):
                    result.features.append(feature)
                if len(result.features) >= query.limit:
                    return result
        return result
