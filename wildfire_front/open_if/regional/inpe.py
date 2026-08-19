"""INPE Programa Queimadas Fire Events KML adapter."""

from __future__ import annotations

import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any

from .base import (
    BaseRegionalFireAdapter,
    FetchPayload,
    NormalizationResult,
    RegionalQuery,
    make_observation_feature,
    query_accepts,
)

INPE_URLS = {
    "active": (
        "https://dataserver-coids.inpe.br/queimadas/queimadas/eventos/ativos/"
        "eventos_ativos.kml"
    ),
    "observation": (
        "https://dataserver-coids.inpe.br/queimadas/queimadas/eventos/observacao/"
        "eventos_observacao.kml"
    ),
}
EVENT_RE = re.compile(r"Evento\s+(\d+)", re.IGNORECASE)
TR_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
TD_RE = re.compile(r"<td\b[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _direct_child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _local_name(child.tag) == name:
            return str(child.text or "").strip()
    return ""


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")


def _plain_cell(value: str) -> str:
    unescaped = html.unescape(value)
    without_tags = TAG_RE.sub(" ", unescaped)
    return re.sub(r"\s+", " ", without_tags).strip()


def parse_description(description: str) -> dict[str, str]:
    """Extract KML HTML-table fields without depending on an HTML package."""
    fields: dict[str, str] = {}
    for row in TR_RE.findall(description or ""):
        cells = [_plain_cell(cell) for cell in TD_RE.findall(row)]
        if len(cells) >= 2 and cells[0]:
            fields[_slug(cells[0])] = cells[1]
    return fields


def _coordinates(text: str) -> list[list[float]]:
    output: list[list[float]] = []
    for token in re.split(r"\s+", (text or "").strip()):
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            output.append([float(parts[0]), float(parts[1])])
        except ValueError:
            continue
    return output


def _first_descendant_text(element: ET.Element, local_name: str) -> str:
    for descendant in element.iter():
        if _local_name(descendant.tag) == local_name:
            return str(descendant.text or "").strip()
    return ""


def _polygon(element: ET.Element) -> dict[str, Any] | None:
    rings: list[list[list[float]]] = []
    for boundary_name in ("outerBoundaryIs", "innerBoundaryIs"):
        for boundary in element.iter():
            if _local_name(boundary.tag) != boundary_name:
                continue
            coords = _coordinates(_first_descendant_text(boundary, "coordinates"))
            if len(coords) >= 4:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                rings.append(coords)
    return {"type": "Polygon", "coordinates": rings} if rings else None


def _geometry_from_element(element: ET.Element) -> dict[str, Any] | None:
    name = _local_name(element.tag)
    if name == "Point":
        coords = _coordinates(_first_descendant_text(element, "coordinates"))
        return {"type": "Point", "coordinates": coords[0]} if coords else None
    if name == "LineString":
        coords = _coordinates(_first_descendant_text(element, "coordinates"))
        return {"type": "LineString", "coordinates": coords} if len(coords) >= 2 else None
    if name == "Polygon":
        return _polygon(element)
    if name == "MultiGeometry":
        members = [
            geometry
            for child in element
            if (geometry := _geometry_from_element(child)) is not None
        ]
        if not members:
            return None
        types = {member["type"] for member in members}
        if len(types) == 1:
            only = next(iter(types))
            if only == "Point":
                return {"type": "MultiPoint", "coordinates": [m["coordinates"] for m in members]}
            if only == "LineString":
                return {
                    "type": "MultiLineString",
                    "coordinates": [m["coordinates"] for m in members],
                }
            if only == "Polygon":
                return {
                    "type": "MultiPolygon",
                    "coordinates": [m["coordinates"] for m in members],
                }
        return {"type": "GeometryCollection", "geometries": members}
    return None


def _placemark_geometry(placemark: ET.Element) -> dict[str, Any] | None:
    for child in placemark:
        if _local_name(child.tag) in {"Point", "LineString", "Polygon", "MultiGeometry"}:
            return _geometry_from_element(child)
    return None


def _inpe_observed_at(fields: dict[str, str]) -> tuple[str | None, list[str]]:
    last_focus = fields.get("ultimo_foco")
    if last_focus:
        return last_focus.replace(" ", "T"), ["timestamp_local_timezone_unspecified"]
    end_date = fields.get("data_fim")
    if end_date:
        return end_date, ["date_only_observation_time"]
    return None, ["missing_observation_time"]


class INPEFireEventsAdapter(BaseRegionalFireAdapter):
    """Fetch and normalize provisional INPE active/observation fire events."""

    source_id = "br_inpe_queimadas"
    provider = "INPE Programa Queimadas"
    licence_id = "inpe-open-data-attribution-verify-redistribution"
    raw_extension = ".kml"

    @property
    def honesty(self) -> dict[str, Any]:
        return {
            "provider_maturity": "provisional_validation",
            "event_extent_is_not_automatically_an_active_front": True,
            "focus_points_are_not_perimeters": True,
            "local_timestamp_timezone_is_not_declared_in_kml": True,
            "front_geometries_require_same_event_temporal_pair_audit": True,
        }

    def fetch(self, query: RegionalQuery) -> list[FetchPayload]:
        query.validate()
        statuses = (
            ["active", "observation"] if query.inpe_status == "both" else [query.inpe_status]
        )
        return [
            self.request(
                INPE_URLS[status],
                name=f"eventos_{status}.kml",
                accept="application/vnd.google-earth.kml+xml,application/xml,text/xml",
            )
            for status in statuses
        ]

    @staticmethod
    def _status_for_payload(payload: FetchPayload, query: RegionalQuery) -> str:
        lowered = f"{payload.name} {payload.url}".lower()
        if "observ" in lowered:
            return "observation"
        if "ativ" in lowered or "active" in lowered:
            return "active"
        return query.inpe_status if query.inpe_status != "both" else "unknown"

    def normalize(
        self,
        payloads: list[FetchPayload],
        query: RegionalQuery,
        *,
        retrieved_at: str,
    ) -> NormalizationResult:
        result = NormalizationResult()
        for payload in payloads:
            status = self._status_for_payload(payload, query)
            try:
                root = ET.fromstring(payload.body)
            except ET.ParseError as exc:
                result.rejected.append({"payload": payload.name, "reason": f"ParseError:{exc}"})
                continue
            self._walk(
                root,
                payload=payload,
                query=query,
                retrieved_at=retrieved_at,
                result=result,
                status=status,
                event_id=None,
                event_name=None,
                section=None,
            )
            if len(result.features) >= query.limit:
                break
        return result

    def _walk(
        self,
        element: ET.Element,
        *,
        payload: FetchPayload,
        query: RegionalQuery,
        retrieved_at: str,
        result: NormalizationResult,
        status: str,
        event_id: str | None,
        event_name: str | None,
        section: str | None,
    ) -> None:
        if len(result.features) >= query.limit:
            return
        name = _direct_child_text(element, "name")
        match = EVENT_RE.search(name)
        if match:
            event_id = match.group(1)
            event_name = name
        name_slug = _slug(name)
        if name_slug == "frentes":
            section = "fronts"
        elif name_slug == "focos":
            section = "focuses"

        for child in element:
            local = _local_name(child.tag)
            if local in {"Document", "Folder"}:
                self._walk(
                    child,
                    payload=payload,
                    query=query,
                    retrieved_at=retrieved_at,
                    result=result,
                    status=status,
                    event_id=event_id,
                    event_name=event_name,
                    section=section,
                )
            elif local == "Placemark":
                self._normalize_placemark(
                    child,
                    payload=payload,
                    query=query,
                    retrieved_at=retrieved_at,
                    result=result,
                    status=status,
                    event_id=event_id,
                    event_name=event_name,
                    section=section,
                )
            if len(result.features) >= query.limit:
                return

    def _normalize_placemark(
        self,
        placemark: ET.Element,
        *,
        payload: FetchPayload,
        query: RegionalQuery,
        retrieved_at: str,
        result: NormalizationResult,
        status: str,
        event_id: str | None,
        event_name: str | None,
        section: str | None,
    ) -> None:
        placemark_name = _direct_child_text(placemark, "name")
        match = EVENT_RE.search(placemark_name)
        if match:
            event_id = match.group(1)
        if event_id is None:
            result.rejected.append({"payload": payload.name, "reason": "placemark_without_event_id"})
            return
        geometry = _placemark_geometry(placemark)
        if geometry is None:
            result.rejected.append(
                {"payload": payload.name, "event_id": event_id, "reason": "missing_geometry"}
            )
            return
        description = _direct_child_text(placemark, "description")
        fields = parse_description(description)
        observed_at, time_flags = _inpe_observed_at(fields)
        geometry_type = geometry.get("type")
        candidate = section == "fronts" and geometry_type in {
            "LineString",
            "MultiLineString",
            "Polygon",
            "MultiPolygon",
        }
        if section == "fronts":
            semantics = "provisional_active_fire_front"
            kind = "fire_front"
            role = "progression_label"
            semantic_flags = ["provisional_front_requires_temporal_pair_audit"]
        elif section == "focuses" or geometry_type in {"Point", "MultiPoint"}:
            semantics = "active_fire_focus_point"
            kind = "hotspot"
            role = "active_fire_observation"
            candidate = False
            semantic_flags = ["focus_point_not_perimeter"]
        else:
            semantics = "provisional_event_extent_estimate"
            kind = "event_extent"
            role = "event_discovery"
            candidate = False
            semantic_flags = ["event_extent_not_active_front"]
        placemark_id = placemark.attrib.get("id") or placemark_name or semantics
        upstream_properties: dict[str, Any] = {
            "event_name": event_name,
            "placemark_name": placemark_name,
            "event_status": status,
            "section": section,
            **fields,
        }
        try:
            feature = make_observation_feature(
                source_id=self.source_id,
                upstream_item_id=f"{status}:{event_id}:{placemark_id}",
                event_id=f"INPE-{event_id}",
                geometry=geometry,
                observation_kind=kind,
                geometry_semantics=semantics,
                role=role,
                observed_at=observed_at,
                published_at=None,
                source_updated_at=None,
                retrieved_at=retrieved_at,
                source_url=payload.url,
                licence_id=self.licence_id,
                provisional=True,
                candidate_progression_label=bool(candidate and observed_at),
                quality_flags=[
                    "inpe_fire_events_product_provisional",
                    *time_flags,
                    *semantic_flags,
                ],
                upstream_properties=upstream_properties,
            )
        except ValueError as exc:
            result.rejected.append(
                {
                    "payload": payload.name,
                    "event_id": event_id,
                    "upstream_item_id": str(placemark_id),
                    "reason": str(exc),
                }
            )
            return
        if query_accepts(feature, query):
            result.features.append(feature)
