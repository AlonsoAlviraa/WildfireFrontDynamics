"""Metric CRS helpers, area, validity, nesting checks for PSB."""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from shapely import affinity
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union
from shapely.validation import make_valid

try:
    from pyproj import Transformer
except ImportError:  # pragma: no cover
    Transformer = None

from .schemas import MIN_COMPONENT_AREA_HA_DEFAULT


@lru_cache(maxsize=32)
def _transformer(src: str, dst: str):
    if Transformer is None:
        raise ImportError("pyproj is required for progressive_burn CRS transforms")
    return Transformer.from_crs(src, dst, always_xy=True)


def reproject(geom: BaseGeometry, src_crs: str, dst_crs: str) -> BaseGeometry:
    if src_crs == dst_crs:
        return geom
    tf = _transformer(src_crs, dst_crs)
    return transform(lambda x, y, z=None: tf.transform(x, y), geom)


def ensure_valid(geom: BaseGeometry, *, allow_empty: bool = False) -> BaseGeometry:
    if geom is None or geom.is_empty:
        if allow_empty:
            return Polygon() if geom is None or not isinstance(geom, BaseGeometry) else geom
        raise ValueError("geometry is empty")
    g = make_valid(geom) if not geom.is_valid else geom
    if g.is_empty:
        if allow_empty:
            return g
        raise ValueError("geometry empty after make_valid")
    # Collapse GeometryCollection to polygonal
    if isinstance(g, GeometryCollection):
        polys = [p for p in g.geoms if isinstance(p, (Polygon, MultiPolygon)) and not p.is_empty]
        if not polys:
            raise ValueError("no polygonal parts after make_valid")
        g = unary_union(polys)
    if isinstance(g, Polygon):
        return g
    if isinstance(g, MultiPolygon):
        return g
    # buffer(0) last resort
    g2 = g.buffer(0)
    if isinstance(g2, (Polygon, MultiPolygon)) and not g2.is_empty:
        return g2
    raise ValueError(f"unsupported geometry type after fix: {g.geom_type}")


def as_multipolygon(geom: BaseGeometry) -> MultiPolygon:
    g = ensure_valid(geom)
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    if isinstance(g, MultiPolygon):
        return g
    raise ValueError(f"expected Polygon/MultiPolygon, got {g.geom_type}")


def area_m2(geom: BaseGeometry) -> float:
    return float(geom.area)


def area_ha(geom: BaseGeometry) -> float:
    return area_m2(geom) / 10_000.0


def perimeter_m(geom: BaseGeometry) -> float:
    return float(geom.length)


def component_polygons(geom: BaseGeometry) -> list[Polygon]:
    mp = as_multipolygon(geom)
    return [p for p in mp.geoms if isinstance(p, Polygon) and not p.is_empty and p.area > 0]


def drop_micro_components(
    geom: BaseGeometry,
    min_area_ha: float = MIN_COMPONENT_AREA_HA_DEFAULT,
) -> tuple[BaseGeometry, int]:
    """Drop components below min area (metric CRS, ha = m²/1e4). Returns (geom, n_dropped)."""
    min_m2 = min_area_ha * 10_000.0
    all_parts = component_polygons(geom)
    parts = [p for p in all_parts if p.area >= min_m2]
    dropped = len(all_parts) - len(parts)
    if not parts:
        return Polygon(), dropped
    if len(parts) == 1:
        return parts[0], dropped
    return MultiPolygon(parts), dropped


def safe_homothety_center(geom: BaseGeometry) -> tuple[float, float]:
    """KD13 M1: representative_point inside geom — never multipolygon centroid."""
    pt = geom.representative_point()
    return float(pt.x), float(pt.y)


def scale_about(geom: BaseGeometry, factor: float, origin: tuple[float, float]) -> BaseGeometry:
    return affinity.scale(geom, xfact=factor, yfact=factor, origin=origin)


def erode(geom: BaseGeometry, distance_m: float) -> BaseGeometry:
    if distance_m <= 0:
        return ensure_valid(geom)
    g = geom.buffer(-float(distance_m))
    if g is None or g.is_empty:
        return Polygon()  # empty is a valid erosion result
    return ensure_valid(g)


def nested_within(
    inner: BaseGeometry,
    outer: BaseGeometry,
    *,
    snap_m: float = 1.0,
) -> bool:
    """True if inner ⊆ outer within snap buffer (metric)."""
    if inner is None or inner.is_empty:
        return True
    if outer is None or outer.is_empty:
        return False
    # Allow tiny exterior leak within snap_m
    return bool(inner.difference(outer.buffer(snap_m)).area <= 1e-3)


def iou(a: BaseGeometry, b: BaseGeometry) -> float:
    if a.is_empty and b.is_empty:
        return 1.0
    u = a.union(b).area
    if u <= 0:
        return 0.0
    return float(a.intersection(b).area / u)


def hausdorff_m(a: BaseGeometry, b: BaseGeometry) -> float:
    try:
        return float(a.hausdorff_distance(b))
    except Exception:
        return float("inf")


def geometry_identity_wkt(a: BaseGeometry, b: BaseGeometry) -> bool:
    """Exact WKT match after normalize (pack CRS terminal identity)."""
    return a.wkt == b.wkt


def geom_to_geojson(geom: BaseGeometry) -> dict[str, Any]:
    return mapping(geom)


def geojson_to_geom(obj: dict[str, Any]) -> BaseGeometry:
    if obj.get("type") == "FeatureCollection":
        feats = obj.get("features") or []
        if not feats:
            raise ValueError("empty FeatureCollection")
        return shape(feats[0]["geometry"])
    if obj.get("type") == "Feature":
        return shape(obj["geometry"])
    return shape(obj)


def densify_ring(
    coords: list[tuple[float, float]], min_points: int = 8
) -> list[tuple[float, float]]:
    """Ensure closed ring has enough distinct vertices for FrontObservation."""
    if not coords:
        return coords
    ring = list(coords)
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    # Distinct count excluding closing point
    distinct: list[tuple[float, float]] = []
    for p in ring[:-1]:
        if not distinct or p != distinct[-1]:
            distinct.append(p)
    while len(distinct) < min_points and len(distinct) >= 2:
        # Insert midpoints
        new_pts: list[tuple[float, float]] = []
        for i in range(len(distinct)):
            a = distinct[i]
            b = distinct[(i + 1) % len(distinct)]
            new_pts.append(a)
            mid = (0.5 * (a[0] + b[0]), 0.5 * (a[1] + b[1]))
            new_pts.append(mid)
        distinct = new_pts
    out = distinct + [distinct[0]]
    return out


def exterior_rings(geom: BaseGeometry, *, min_points: int = 8) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []
    for poly in component_polygons(geom):
        coords = [(float(x), float(y)) for x, y in poly.exterior.coords]
        rings.append(densify_ring(coords, min_points=min_points))
    return rings


def finite_coords(geom: BaseGeometry) -> bool:
    if geom.is_empty:
        return True
    for x, y in geom.coords if hasattr(geom, "coords") else []:
        if not (math.isfinite(x) and math.isfinite(y)):
            return False
    for poly in component_polygons(geom):
        for x, y in poly.exterior.coords:
            if not (math.isfinite(x) and math.isfinite(y)):
                return False
    return True
