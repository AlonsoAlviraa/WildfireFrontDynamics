"""Operational fire-perimeter KMZ/KML helpers (INFOCAM / GEACAM style).

Parses multi-hour **perímetro activo** products with:
- ``Sup_ha`` attribute (often Spanish decimal comma inside HTML CDATA)
- outer-ring polygon coordinates (WGS84 lon/lat)
- observation time inferred from filename patterns
  ``..._YYYYMMDD_HHMM.kmz`` / ``.kml``

Honesty rails
-------------
- These are **operational** perimeters (ops cartography), not national cadastre.
- ``Sup_ha`` and polygon area growth are **not** Vp (m/min) or front ROS.
- Use for O2 **proxy** / multi-hour geometry only; do not promote to
  ``confirmed`` anchors without parte text Vp/ha.

Metric CRS
----------
WGS84 → EPSG:32630 transforms **require pyproj**. There is no silent
equirectangular fallback: mixing local-tangent coords with UTM main_front
would poison Hausdorff. Callers that need meters must handle
``MetricCrsError``.
"""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

# Filename: ..._20240802_1830.kmz  or  ..._20240802_1830.kml
_TIME_FROM_NAME = re.compile(
    r"(?P<date>20\d{2}[01]\d[0-3]\d)_(?P<hhmm>[0-2]\d[0-5]\d)(?:\.(?:kmz|kml))?$",
    re.IGNORECASE,
)

# HTML table cells: <td>Sup_ha</td> ... <td>21,489832</td>
_SUP_HA_HTML = re.compile(
    r"Sup[_ ]?ha\s*</td>\s*<td[^>]*>\s*([^<]+)\s*</td>",
    re.IGNORECASE | re.DOTALL,
)
_SUP_HA_PLAIN = re.compile(r"Sup[_ ]?ha\s*[=:]\s*([0-9]+[.,][0-9]+|[0-9]+)", re.IGNORECASE)

METRIC_CRS = "EPSG:32630"
GEOGRAPHIC_CRS = "EPSG:4326"


class MetricCrsError(RuntimeError):
    """Raised when a metric (UTM) transform cannot be performed honestly."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def repo_relative_path(path: Path | str, *, root: Path | None = None) -> str:
    """Return path relative to repo root when possible (portable provenance)."""
    p = Path(path).resolve()
    base = (root or _repo_root()).resolve()
    try:
        return str(p.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


@dataclass(frozen=True)
class OpsPerimeter:
    """One operational active-perimeter snapshot."""

    source_path: str
    name: str
    time_local_inferred: str | None
    time_source: str
    sup_ha: float | None
    sup_ha_source: str
    n_vertices: int
    coords_wgs84: tuple[tuple[float, float], ...]  # closed ring lon/lat
    crs: str = GEOGRAPHIC_CRS
    notes: str = "operational_active_perimeter_not_national_cadastre"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["coords_wgs84"] = [list(p) for p in self.coords_wgs84]
        return d


def _strip_ns(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def parse_spanish_float(text: str) -> float | None:
    """Parse ES decimal (comma) or EN decimal (dot); strip thousands dots carefully."""
    if text is None:
        return None
    s = str(text).strip()
    if not s or s in {"<Nulo>", "&lt;Nulo&gt;", "Nulo", "null", "None", "-"}:
        return None
    s = s.replace("\xa0", "").replace(" ", "")
    # Spanish: 21,489832  or  1.234,56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def time_from_filename(path: Path | str) -> tuple[str | None, str]:
    """Infer local wall-clock from ``..._YYYYMMDD_HHMM`` suffix.

    Returns (ISO local naive string, source label). Local = Spanish ops clock
    as encoded by INFOCAM export — not converted to UTC here.
    """
    name = Path(path).name
    m = _TIME_FROM_NAME.search(name)
    if not m:
        return None, "unparsed"
    date_s, hhmm = m.group("date"), m.group("hhmm")
    try:
        dt = datetime(
            int(date_s[0:4]),
            int(date_s[4:6]),
            int(date_s[6:8]),
            int(hhmm[0:2]),
            int(hhmm[2:4]),
        )
    except ValueError:
        return None, "unparsed"
    return dt.strftime("%Y-%m-%dT%H:%M:%S"), "filename_YYYYMMDD_HHMM_local"


def extract_kml_bytes(path: Path) -> bytes:
    """Return raw KML bytes from a ``.kml`` or ``.kmz`` path."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".kml":
        return path.read_bytes()
    if suffix == ".kmz":
        with zipfile.ZipFile(path) as zf:
            # Prefer doc.kml; else first .kml member
            names = zf.namelist()
            kml_name = next((n for n in names if n.lower().endswith("doc.kml")), None)
            if kml_name is None:
                kml_name = next((n for n in names if n.lower().endswith(".kml")), None)
            if kml_name is None:
                raise ValueError(f"no .kml member inside KMZ: {path}")
            return zf.read(kml_name)
    raise ValueError(f"expected .kml or .kmz, got {suffix}: {path}")


def _parse_coordinates_text(text: str) -> list[tuple[float, float]]:
    pts: list[tuple[float, float]] = []
    for token in text.replace("\n", " ").replace("\t", " ").split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            pts.append((lon, lat))
    return pts


def _extract_sup_ha_from_text(blob: str) -> tuple[float | None, str]:
    m = _SUP_HA_HTML.search(blob)
    if m:
        val = parse_spanish_float(m.group(1))
        if val is not None:
            return val, "description_html_Sup_ha"
        # Present but null/unparseable
        raw = (m.group(1) or "").strip()
        if raw in {"<Nulo>", "&lt;Nulo&gt;", "Nulo", ""} or parse_spanish_float(raw) is None:
            return None, "description_html_Sup_ha_null"
    m2 = _SUP_HA_PLAIN.search(blob)
    if m2:
        val = parse_spanish_float(m2.group(1))
        if val is not None:
            return val, "description_plain_Sup_ha"
    return None, "missing"


def _placemark_name(pm: ET.Element) -> str:
    for child in pm:
        if _strip_ns(child.tag) == "name" and child.text:
            return child.text.strip()
    return "unnamed"


def _placemark_description(pm: ET.Element) -> str:
    for child in pm:
        if _strip_ns(child.tag) == "description" and child.text:
            return child.text
    return ""


def _rings_from_placemark(pm: ET.Element) -> list[list[tuple[float, float]]]:
    """Collect outer rings from Polygon / MultiGeometry under a Placemark."""
    rings: list[list[tuple[float, float]]] = []
    for el in pm.iter():
        tag = _strip_ns(el.tag)
        if tag != "coordinates" or not el.text:
            continue
        # Accept polygon-like rings (>=3 verts); pick largest later.
        pts = _parse_coordinates_text(el.text)
        if len(pts) >= 3:
            rings.append(pts)
    # Filter out LatLonQuad-like 4-corner boxes when longer rings exist.
    if len(rings) > 1:
        long_rings = [r for r in rings if len(r) >= 5]
        if long_rings:
            rings = long_rings
    return rings


def _close_ring(pts: list[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    if not pts:
        return tuple()
    out = list(pts)
    if out[0] != out[-1]:
        out.append(out[0])
    return tuple(out)


def _ring_area_deg2(ring: list[tuple[float, float]]) -> float:
    """Shoelace in lon/lat degrees (relative ranking only)."""
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def parse_ops_perimeter(path: Path | str, *, root: Path | None = None) -> OpsPerimeter:
    """Parse a single operational perimeter from KMZ or KML."""
    path = Path(path)
    raw = extract_kml_bytes(path)
    root_el = ET.fromstring(raw)

    best: OpsPerimeter | None = None
    best_score = -1.0

    for pm in root_el.iter():
        if _strip_ns(pm.tag) != "Placemark":
            continue
        name = _placemark_name(pm)
        desc = _placemark_description(pm)
        sup_ha, sup_src = _extract_sup_ha_from_text(desc)
        # also scan all text under placemark for Sup_ha
        if sup_ha is None and sup_src == "missing":
            blob = " ".join((t or "") for t in pm.itertext())
            sup_ha, sup_src = _extract_sup_ha_from_text(blob)

        rings = _rings_from_placemark(pm)
        if not rings:
            continue
        ring = max(rings, key=_ring_area_deg2)
        closed = _close_ring(ring)
        # Count closed-ring coordinate positions (includes repeated first point),
        # matching INFOCAM/inventory vertex counts on these products.
        n_vert = len(closed) if closed else 0
        score = _ring_area_deg2(list(closed))
        # prefer named "Perímetro activo" and those with Sup_ha
        if "perímetro" in name.lower() or "perimetro" in name.lower():
            score += 1e6
        if sup_ha is not None:
            score += 1e5

        t_local, t_src = time_from_filename(path)
        candidate = OpsPerimeter(
            source_path=repo_relative_path(path, root=root),
            name=name,
            time_local_inferred=t_local,
            time_source=t_src,
            sup_ha=sup_ha,
            sup_ha_source=sup_src,
            n_vertices=n_vert,
            coords_wgs84=closed,
        )
        if score > best_score:
            best_score = score
            best = candidate

    if best is None:
        raise ValueError(f"no polygonal Placemark found in {path}")
    return best


def parse_ops_perimeters(paths: list[Path | str], *, root: Path | None = None) -> list[OpsPerimeter]:
    """Parse many paths; sort by inferred time when available."""
    out = [parse_ops_perimeter(p, root=root) for p in paths]
    out.sort(key=lambda p: p.time_local_inferred or "")
    return out


def pyproj_available() -> bool:
    try:
        import pyproj  # noqa: F401

        return True
    except ImportError:
        return False


def wgs84_to_utm30n(lon: float, lat: float) -> tuple[float, float]:
    """WGS84 → UTM zone 30N (EPSG:32630) for Spain CLM.

    Requires ``pyproj``. Raises ``MetricCrsError`` if unavailable or transform fails.
    No equirectangular fallback — that would not be comparable to true UTM main_front.
    """
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise MetricCrsError(
            "pyproj is required for WGS84→EPSG:32630 metric transforms; "
            "refusing silent equirectangular fallback (would poison Hausdorff vs UTM main_front)"
        ) from exc
    try:
        tr = Transformer.from_crs(GEOGRAPHIC_CRS, METRIC_CRS, always_xy=True)
        x, y = tr.transform(lon, lat)
        return float(x), float(y)
    except Exception as exc:  # transform failure only after import succeeded
        raise MetricCrsError(f"WGS84→{METRIC_CRS} transform failed: {exc}") from exc


def ring_wgs84_to_utm30n(
    ring: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
    return tuple(wgs84_to_utm30n(lon, lat) for lon, lat in ring)


def polygon_area_m2_utm(ring_utm: tuple[tuple[float, float], ...]) -> float:
    """Shoelace area for a closed ring in projected meters."""
    pts = list(ring_utm)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return 0.0
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def area_ha_from_ring_wgs84(ring: tuple[tuple[float, float], ...]) -> float:
    utm = ring_wgs84_to_utm30n(ring)
    return polygon_area_m2_utm(utm) / 10_000.0


def to_geojson_feature(perim: OpsPerimeter, *, include_utm: bool = False) -> dict[str, Any]:
    """Single GeoJSON Feature (WGS84 lon/lat polygon, RFC 7946 order)."""
    coords = [[list(p) for p in perim.coords_wgs84]]
    props: dict[str, Any] = {
        "name": perim.name,
        "sup_ha": perim.sup_ha,
        "sup_ha_source": perim.sup_ha_source,
        "time_local_inferred": perim.time_local_inferred,
        "time_source": perim.time_source,
        "n_vertices": perim.n_vertices,
        "source_path": perim.source_path,
        "crs": GEOGRAPHIC_CRS,
        "product_class": "operational_active_perimeter",
        "notes": perim.notes,
    }
    try:
        props["area_ha_geom_utm30n"] = round(area_ha_from_ring_wgs84(perim.coords_wgs84), 6)
    except MetricCrsError:
        props["area_ha_geom_utm30n"] = None
        props["area_ha_geom_note"] = "pyproj required for metric area"
    if include_utm:
        props["coords_utm30n_note"] = "see companion FeatureCollection export"
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": coords},
    }


def to_geojson_collection(
    perims: list[OpsPerimeter],
    *,
    name: str = "ops_perimeters",
) -> dict[str, Any]:
    """RFC 7946-oriented FeatureCollection (lon/lat; no top-level crs)."""
    features = [to_geojson_feature(p) for p in perims]
    # Carry collection-level metadata without nonstandard top-level "properties"
    # / deprecated "crs" members — put disclaimer on first feature if needed,
    # and expose name + disclaimer via a dedicated foreign member avoided:
    # use feature props only; collection name as optional foreign key "name"
    # is common and harmless for our GIS use.
    for f in features:
        props = f.setdefault("properties", {})
        props.setdefault(
            "collection_disclaimer",
            (
                "Operational active perimeters (INFOCAM/GEACAM style). "
                "Not national cadastre. Area growth ≠ Vp m/min. CRS=EPSG:4326 lon/lat."
            ),
        )
    return {
        "type": "FeatureCollection",
        "name": name,
        "features": features,
    }


def write_geojson(perims: list[OpsPerimeter], path: Path | str, *, name: str = "ops_perimeters") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fc = to_geojson_collection(perims, name=name)
    path.write_text(json.dumps(fc, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def area_growth_summary(perims: list[OpsPerimeter]) -> dict[str, Any]:
    """Δha / Δt between first and last perimeter with times + Sup_ha."""
    usable = [p for p in perims if p.time_local_inferred and p.sup_ha is not None]
    if len(usable) < 2:
        return {
            "status": "insufficient",
            "note": "need ≥2 perimeters with time_local_inferred and Sup_ha",
        }
    a, b = usable[0], usable[-1]
    t0 = datetime.fromisoformat(a.time_local_inferred)  # type: ignore[arg-type]
    t1 = datetime.fromisoformat(b.time_local_inferred)  # type: ignore[arg-type]
    delta_min = (t1 - t0).total_seconds() / 60.0
    delta_ha = float(b.sup_ha) - float(a.sup_ha)  # type: ignore[arg-type]
    mean_ha_h = (delta_ha / (delta_min / 60.0)) if delta_min > 0 else None
    return {
        "status": "ok",
        "t0_local": a.time_local_inferred,
        "t1_local": b.time_local_inferred,
        "sup_ha_t0": a.sup_ha,
        "sup_ha_t1": b.sup_ha,
        "delta_ha": round(delta_ha, 6),
        "delta_minutes": round(delta_min, 3),
        "mean_ha_per_hour": round(mean_ha_h, 4) if mean_ha_h is not None else None,
        "disclaimer": (
            "Polygon Sup_ha growth only — not front ROS / Vp m/min. "
            "Ops perimeter ≠ national cadastre."
        ),
    }
