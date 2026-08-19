"""Briefing KML 2.2 with TimeSpan for Earth Pro's slider.

Filename instants ``HHMM`` on the Pablo/GEACAM Tobarra drop are Spanish
mainland **CEST (UTC+2)** in August 2024 — they carry no offset in the file.
This module converts them to XML Schema dateTime in UTC (``...Z``) and
assigns **contiguous, non-overlapping** TimeSpans:

- perímetro *i* is visible from its instant until the next instant
- the last perímetro holds for the same duration as the previous gap

Envelope GeoJSON polygons are extra Features, labeled extrapolated / not
official / not tactical. They are never tagged as INFOCAM perímetros.

Does not write official MET JSON. Does not rewrite source KMZ/KML.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from xml.etree import ElementTree as ET

KML_NS = "http://www.opengis.net/kml/2.2"
KML_NSMAP = {"k": KML_NS}

# August 2024 Spain mainland. Filename HHMM has no offset; document this in KML.
CEST = timezone(timedelta(hours=2), name="CEST")
TIMEZONE_CONVENTION = "filename_HHMM_is_CEST_UTC+2_2024-08"
ROLE_PERIMETER = "infocam_perimeter"
ROLE_ENVELOPE = "wfd_envelope"

NOT_CLAIMS = (
    "briefing only — not official LATAM MET",
    "not a new model IoU",
    "not ROS operativo / not Decision Card",
    "envelopes are extrapolated guidance, not INFOCAM perímetros",
    "not tactical dispatch",
)


@dataclass(frozen=True)
class TimedRing:
    """One polygon ring with a local (naive or aware) observation instant."""

    name: str
    instant_local: datetime
    ring_lonlat: tuple[tuple[float, float], ...]
    role: str = ROLE_PERIMETER
    properties: dict[str, Any] = field(default_factory=dict)


def local_cest_to_utc(instant: datetime) -> datetime:
    """Treat naive datetimes as CEST; convert to UTC."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=CEST)
    return instant.astimezone(UTC)


def kml_z(dt: datetime) -> str:
    """XML Schema dateTime in UTC with Z suffix."""
    utc = dt.astimezone(UTC) if dt.tzinfo else dt.replace(tzinfo=UTC)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_local_iso(text: str) -> datetime:
    """Parse ``YYYY-MM-DDTHH:MM:SS`` (naive local) or an aware ISO string."""
    raw = str(text).strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CEST)
    return dt


def contiguous_timespans(instants_utc: list[datetime]) -> list[tuple[datetime, datetime]]:
    """Return ``(begin, end)`` pairs that abut and do not overlap interiors.

    Sorted by instant. Span *i* is ``[t_i, t_{i+1})`` encoded as
    ``begin=t_i``, ``end=t_{i+1}`` (end of *i* equals begin of *i+1*).
    The last span holds for ``t_n - t_{n-1}`` (or 1 hour if only one instant).
    """
    if not instants_utc:
        return []
    ordered = sorted(instants_utc)
    if len(ordered) == 1:
        hold = timedelta(hours=1)
        return [(ordered[0], ordered[0] + hold)]
    spans: list[tuple[datetime, datetime]] = []
    for i, t0 in enumerate(ordered):
        t1 = (
            ordered[i + 1]
            if i + 1 < len(ordered)
            else ordered[i] + (ordered[i] - ordered[i - 1])
        )
        if t1 <= t0:
            t1 = t0 + timedelta(seconds=1)
        spans.append((t0, t1))
    return spans


def _close_lonlat(ring: tuple[tuple[float, float], ...] | list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if not pts:
        return []
    if pts[0] != pts[-1]:
        pts.append(pts[0])
    return pts


def ring_to_kml_coordinates(ring: tuple[tuple[float, float], ...] | list[tuple[float, float]]) -> str:
    """KML ``lon,lat,0`` tuples, space-separated. Input must already be WGS84."""
    pts = _close_lonlat(ring)
    return " ".join(f"{lon:.8f},{lat:.8f},0" for lon, lat in pts)


def _looks_lonlat_ring(ring: list[tuple[float, float]]) -> bool:
    if not ring:
        return False
    return all(abs(lon) <= 180.0 and abs(lat) <= 90.0 for lon, lat in ring)


def ensure_wgs84_ring(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Convert a UTM-meter ring to lon/lat; leave geographic rings alone."""
    if not ring:
        return []
    if _looks_lonlat_ring(ring):
        return ring
    from wildfire_front.geo_crs import utm_to_wgs84

    return [utm_to_wgs84(x, y, zone=30, northern=True) for x, y in ring]


def extract_polygon_rings(geom: dict[str, Any] | None) -> list[list[tuple[float, float]]]:
    """Outer rings from a GeoJSON Polygon or MultiPolygon."""
    if not geom:
        return []
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    rings: list[list[tuple[float, float]]] = []
    if gtype == "Polygon" and coords:
        outer = coords[0]
        rings.append([(float(p[0]), float(p[1])) for p in outer])
    elif gtype == "MultiPolygon" and coords:
        for poly in coords:
            if poly:
                rings.append([(float(p[0]), float(p[1])) for p in poly[0]])
    out: list[list[tuple[float, float]]] = []
    for ring in rings:
        wgs = ensure_wgs84_ring(ring)
        if len(wgs) >= 3:
            out.append(wgs)
    return out


def _qn(tag: str) -> str:
    return f"{{{KML_NS}}}{tag}"


def _text_el(tag: str, text: str) -> ET.Element:
    el = ET.Element(_qn(tag))
    el.text = text
    return el


def timespan_element(begin: datetime | str, end: datetime | str) -> ET.Element:
    ts = ET.Element(_qn("TimeSpan"))
    ts.append(_text_el("begin", begin if isinstance(begin, str) else kml_z(begin)))
    ts.append(_text_el("end", end if isinstance(end, str) else kml_z(end)))
    return ts


def _extended_data(pairs: dict[str, Any]) -> ET.Element:
    ext = ET.Element(_qn("ExtendedData"))
    for key, val in pairs.items():
        if val is None:
            continue
        data = ET.Element(_qn("Data"), {"name": str(key)})
        value = ET.Element(_qn("value"))
        if isinstance(val, bool):
            value.text = "true" if val else "false"
        else:
            value.text = str(val)
        data.append(value)
        ext.append(data)
    return ext


def _polygon_el(ring_lonlat: list[tuple[float, float]]) -> ET.Element:
    poly = ET.Element(_qn("Polygon"))
    poly.append(_text_el("tessellate", "1"))
    poly.append(_text_el("altitudeMode", "clampToGround"))
    outer = ET.Element(_qn("outerBoundaryIs"))
    lr = ET.Element(_qn("LinearRing"))
    lr.append(_text_el("coordinates", ring_to_kml_coordinates(tuple(ring_lonlat))))
    outer.append(lr)
    poly.append(outer)
    return poly


def placemark_element(
    *,
    name: str,
    begin: datetime | str,
    end: datetime | str,
    ring_lonlat: list[tuple[float, float]],
    description: str,
    extended: dict[str, Any],
    style_url: str | None = None,
) -> ET.Element:
    pm = ET.Element(_qn("Placemark"))
    pm.append(_text_el("name", name))
    pm.append(_text_el("description", description))
    if style_url:
        pm.append(_text_el("styleUrl", style_url))
    pm.append(timespan_element(begin, end))
    pm.append(_extended_data(extended))
    pm.append(_polygon_el(ring_lonlat))
    return pm


def _style(style_id: str, line_abgr: str, poly_abgr: str) -> ET.Element:
    style = ET.Element(_qn("Style"), {"id": style_id})
    line = ET.Element(_qn("LineStyle"))
    line.append(_text_el("color", line_abgr))
    line.append(_text_el("width", "2"))
    poly = ET.Element(_qn("PolyStyle"))
    poly.append(_text_el("color", poly_abgr))
    poly.append(_text_el("fill", "1"))
    poly.append(_text_el("outline", "1"))
    style.append(line)
    style.append(poly)
    return style


def perimeter_features_from_rings(rings: list[TimedRing]) -> list[ET.Element]:
    """Exactly one Placemark per TimedRing, TimeSpans contiguous on sorted instants."""
    if not rings:
        return []
    indexed = list(enumerate(rings))
    indexed.sort(key=lambda item: local_cest_to_utc(item[1].instant_local))
    instants = [local_cest_to_utc(r.instant_local) for _, r in indexed]
    spans = contiguous_timespans(instants)
    out: list[ET.Element] = []
    for (orig_i, ring), (begin, end), instant in zip(indexed, spans, instants, strict=True):
        props = dict(ring.properties)
        desc = (
            f"{ring.name}\n"
            f"instant_local_cest={ring.instant_local.strftime('%Y-%m-%dT%H:%M:%S')}\n"
            f"instant_utc={kml_z(instant)}\n"
            f"timezone={TIMEZONE_CONVENTION}\n"
            f"role={ROLE_PERIMETER}\n"
            f"sup_ha={props.get('sup_ha')}\n"
            "INFOCAM/GEACAM operational perímetro activo — not national cadastre."
        )
        ext = {
            "role": ROLE_PERIMETER,
            "timezone_convention": TIMEZONE_CONVENTION,
            "instant_local_cest": ring.instant_local.strftime("%Y-%m-%dT%H:%M:%S"),
            "instant_utc": kml_z(instant),
            "sup_ha": props.get("sup_ha"),
            "source_path": props.get("source_path"),
            "n_vertices": props.get("n_vertices"),
        }
        style = "#stylePerim0" if orig_i == 0 else "#stylePerim1"
        out.append(
            placemark_element(
                name=ring.name,
                begin=begin,
                end=end,
                ring_lonlat=_close_lonlat(ring.ring_lonlat),
                description=desc,
                extended=ext,
                style_url=style,
            )
        )
    return out


def envelope_features_from_geojson(
    fc: dict[str, Any],
    *,
    valid_from_utc: datetime | None = None,
) -> list[ET.Element]:
    """KML Placemarks from an envelope FeatureCollection (WGS84 or UTM meters)."""
    from wildfire_front.geo_crs import geojson_to_wgs84, looks_projected_meters

    doc = fc
    feats = list(doc.get("features") or [])
    if feats:
        geom0 = feats[0].get("geometry") or {}
        coords = geom0.get("coordinates")
        sample = None
        if geom0.get("type") == "Polygon" and coords:
            sample = coords[0][0]
        elif geom0.get("type") == "MultiPolygon" and coords:
            sample = coords[0][0][0]
        if sample is not None and looks_projected_meters(float(sample[0]), float(sample[1])):
            doc = geojson_to_wgs84(doc, zone=30, northern=True)
            feats = list(doc.get("features") or [])

    out: list[ET.Element] = []
    for i, feat in enumerate(feats):
        props = dict(feat.get("properties") or {})
        props.setdefault("not_official_perimeter", True)
        props.setdefault("not_tactical_dispatch", True)
        props.setdefault("guidance", props.get("guidance") or "extrapolated_from_observed_ros")
        rings = extract_polygon_rings(feat.get("geometry"))
        if not rings:
            continue
        horizon = props.get("horizon_min")
        begin: datetime | str
        end: datetime | str
        if valid_from_utc is not None and horizon is not None:
            begin = valid_from_utc
            end = valid_from_utc + timedelta(minutes=int(horizon))
            if end <= begin:
                end = begin + timedelta(minutes=1)
        elif valid_from_utc is not None:
            begin = valid_from_utc
            end = valid_from_utc + timedelta(hours=1)
        else:
            # No valid-time → still a Feature, but TimeSpan is required for slider
            # grouping: 1-hour dummy only if we have nothing else. Skip TimeSpan
            # assignment unless we have a clock — caller should pass valid_from.
            continue
        sector = props.get("sector") or "envelope"
        name = f"ENVELOPE {sector} +{horizon}min (extrapolated, not INFOCAM)"
        desc = (
            "WFD envelope — extrapolated guidance.\n"
            "not_official_perimeter=true\n"
            "not_tactical_dispatch=true\n"
            "not INFOCAM perímetro\n"
            f"horizon_min={horizon}\n"
            f"sector={sector}\n"
            f"{props.get('label_en') or ''}"
        )
        ext = {
            "role": ROLE_ENVELOPE,
            "not_official_perimeter": True,
            "not_tactical_dispatch": True,
            "guidance": props.get("guidance"),
            "horizon_min": horizon,
            "sector": sector,
            "fire_id": props.get("fire_id"),
        }
        out.append(
            placemark_element(
                name=name,
                begin=begin,
                end=end,
                ring_lonlat=_close_lonlat(rings[0]),
                description=desc,
                extended=ext,
                style_url="#styleEnvelope",
            )
        )
        _ = i
    return out


def build_briefing_kml(
    perimeter_rings: list[TimedRing],
    envelope_fc: dict[str, Any] | None = None,
    *,
    document_name: str = "Tobarra briefing TimeSpan (Earth Pro)",
) -> str:
    """Serialize a KML 2.2 Document. Perímetros first, then envelopes."""
    ET.register_namespace("", KML_NS)
    root = ET.Element(_qn("kml"))
    doc = ET.Element(_qn("Document"))
    root.append(doc)
    doc.append(_text_el("name", document_name))
    desc = (
        "Earth Pro time-slider briefing.\n"
        f"timezone_convention={TIMEZONE_CONVENTION}\n"
        "Filename 1830/2143 = 2024-08-02 18:30/21:43 CEST = 16:30/19:43 UTC.\n"
        + "\n".join(f"- {c}" for c in NOT_CLAIMS)
    )
    doc.append(_text_el("description", desc))
    doc.append(_style("stylePerim0", "ff0055ff", "440055ff"))
    doc.append(_style("stylePerim1", "ff00a5ff", "4400a5ff"))
    doc.append(_style("styleEnvelope", "ffffff00", "3300ffff"))

    folder_p = ET.Element(_qn("Folder"))
    folder_p.append(_text_el("name", "INFOCAM perímetros activos"))
    folder_p.append(
        _text_el(
            "description",
            "Operational active perimeters (Pablo/GEACAM drop). Not national cadastre.",
        )
    )
    peri_el = perimeter_features_from_rings(perimeter_rings)
    for el in peri_el:
        folder_p.append(el)
    doc.append(folder_p)

    last_utc = None
    if perimeter_rings:
        last_utc = max(local_cest_to_utc(r.instant_local) for r in perimeter_rings)

    folder_e = ET.Element(_qn("Folder"))
    folder_e.append(_text_el("name", "WFD envelopes (extrapolated, not official)"))
    folder_e.append(
        _text_el(
            "description",
            "not_official_perimeter; not_tactical_dispatch; not INFOCAM perímetros.",
        )
    )
    if envelope_fc is not None:
        for el in envelope_features_from_geojson(envelope_fc, valid_from_utc=last_utc):
            folder_e.append(el)
    doc.append(folder_e)

    ET.indent(root, space="  ")
    xml = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n"


def iter_placemarks(kml: str, *, role: str | None = None) -> list[ET.Element]:
    root = ET.fromstring(kml)
    found: list[ET.Element] = []
    for pm in root.iter(_qn("Placemark")):
        if role is None:
            found.append(pm)
            continue
        got = None
        for data in pm.iter(_qn("Data")):
            if data.get("name") == "role":
                val = data.find(_qn("value"))
                got = val.text if val is not None else None
        if got == role:
            found.append(pm)
    return found


def placemark_timespan(pm: ET.Element) -> tuple[str | None, str | None]:
    ts = pm.find(_qn("TimeSpan"))
    if ts is None:
        return None, None
    b = ts.find(_qn("begin"))
    e = ts.find(_qn("end"))
    return (b.text if b is not None else None, e.text if e is not None else None)


def timed_rings_from_ops(perims: list[Any]) -> list[TimedRing]:
    """Build TimedRing list from ``OpsPerimeter`` objects (sorted by time)."""
    out: list[TimedRing] = []
    for p in perims:
        raw = getattr(p, "time_local_inferred", None)
        if not raw:
            continue
        instant = parse_local_iso(str(raw))
        name = f"{getattr(p, 'name', 'Perímetro activo')} {instant.strftime('%H:%M')} CEST"
        out.append(
            TimedRing(
                name=name,
                instant_local=instant,
                ring_lonlat=tuple(p.coords_wgs84),
                role=ROLE_PERIMETER,
                properties={
                    "sup_ha": getattr(p, "sup_ha", None),
                    "source_path": getattr(p, "source_path", None),
                    "n_vertices": getattr(p, "n_vertices", None),
                },
            )
        )
    out.sort(key=lambda r: local_cest_to_utc(r.instant_local))
    return out


def load_envelope_geojson(path: Any) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        raise ValueError(f"not a FeatureCollection: {path}")
    return data
