#!/usr/bin/env python3
"""Pista B: build open-data IF pack from Copernicus EMS Rapid Mapping vectors.

No Heligrafics LWIR required. Downloads public CEMS vector zips, extracts
observed-event polygons, computes area/timeline, approximate multi-perimeter ROS,
writes brief + scorecard + provenance.

Examples:
  python scripts/build_open_if_pack.py --activation EMSR578
  python scripts/build_open_if_pack.py --activation EMSR583
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import re
import shutil
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from shapely.geometry import mapping, shape
    from shapely.ops import transform, unary_union
except ImportError:  # pragma: no cover
    print("shapely required: pip install shapely", file=sys.stderr)
    raise

try:
    from pyproj import Transformer
except ImportError:  # pragma: no cover
    Transformer = None  # type: ignore


BASE = "https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations"
PAGE = "https://mapping.emergency.copernicus.eu/activations"
# 2026+ Rapid Mapping SPA API (vector zips no longer embedded in HTML)
RM_API = "https://rapidmapping.emergency.copernicus.eu/backend/dashboard-api/public-activations/"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def fetch_activation_vectors(code: str) -> list[str]:
    """Return product zip URLs for an activation (legacy S3 HTML scrape + 2026 API)."""
    code = code.upper().strip()
    urls: list[str] = []

    # Legacy: server-rendered activation pages embed s3 vector.zip links
    try:
        html = (
            urllib.request.urlopen(f"{PAGE}/{code}", timeout=60).read().decode("utf-8", "replace")
        )
        s3 = sorted(set(re.findall(r"https://cems-mapping-website[^\s\"'<>]+", html)))
        urls.extend(u for u in s3 if u.endswith("_vector.zip") or "vector.zip" in u)
    except Exception as e:
        print(f"  legacy HTML scrape skip: {e}", flush=True)

    if urls:
        return sorted(set(urls))

    # 2026 SPA: public-activations API → product downloadPath zips
    try:
        api = f"{RM_API}?code={code}"
        raw = urllib.request.urlopen(api, timeout=90).read().decode("utf-8", "replace")
        data = json.loads(raw)
        results = data.get("results") or []
        if not results and isinstance(data, dict) and data.get("code"):
            results = [data]
        geojson_urls: list[str] = []
        zip_urls: list[str] = []
        for act in results:
            for aoi in act.get("aois") or []:
                for prod in aoi.get("products") or []:
                    ptype = str(prod.get("type") or "").upper()
                    # Harvest observedEventA layer JSON from S3 (preferred)
                    for layer in prod.get("layers") or []:
                        if not isinstance(layer, dict):
                            continue
                        lj = layer.get("json")
                        lname = str(layer.get("name") or "")
                        nlow = lname.lower().replace("_", "")
                        if not (
                            isinstance(lj, str)
                            and lj.endswith(".json")
                            and "observedeventa" in nlow
                        ):
                            continue
                        # Skip heavy GRA grading layers when DEL monits exist
                        if "gra" in nlow and ptype == "GRA":
                            continue
                        geojson_urls.append("GEOJSON:" + lj)
                    # Fallback: vectors-only zip
                    dp = prod.get("downloadPath")
                    if isinstance(dp, str) and dp.endswith(".zip"):
                        zip_urls.append(dp if "?" in dp else dp + "?type=vectors")
        # Prefer geojson; cap count to keep pack builds tractable
        if geojson_urls:
            # Prefer DEL monits first, then DEL product; drop GRA
            def _gj_key(u: str) -> tuple[int, str]:
                s = u.lower()
                if "del_monit" in s:
                    return (0, s)
                if "del_product" in s:
                    return (1, s)
                if "gra" in s:
                    return (9, s)
                return (5, s)

            geojson_urls = sorted(set(geojson_urls), key=_gj_key)[:6]
            urls.extend(geojson_urls)
        else:
            urls.extend(zip_urls[:6])
    except Exception as e:
        print(f"  rapidmapping API skip: {e}", flush=True)

    # de-dupe preserving order, prefer plain zip before ?type=vectors if both fail later
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 100:
        return dest
    print(f"  GET {url}", flush=True)
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "WildfireFrontDynamics-open-if/1.0",
            "Accept": "application/zip, application/octet-stream, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        dest.write_bytes(resp.read())
    return dest


def _load_geojsons_from_zip(zpath: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with zipfile.ZipFile(zpath, "r") as zf:
        for name in zf.namelist():
            if not name.lower().endswith((".json", ".geojson")):
                continue
            raw = zf.read(name)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            out.append({"member": name, "geojson": data})
    return out


def _geoms_from_fc(fc: dict[str, Any]) -> list[Any]:
    geoms = []
    if fc.get("type") == "FeatureCollection":
        for f in fc.get("features") or []:
            g = f.get("geometry")
            if g:
                try:
                    geoms.append(shape(g))
                except Exception:
                    continue
    elif fc.get("type") == "Feature":
        g = fc.get("geometry")
        if g:
            geoms.append(shape(g))
    elif "coordinates" in fc:
        geoms.append(shape(fc))
    return [g for g in geoms if not g.is_empty]


def _area_ha_wgs84(geom: Any) -> float:
    """Approximate geodesic area via equal-area projection (EPSG:6933)."""
    if Transformer is None:
        # fallback: equirectangular at centroid (rough)
        minx, miny, maxx, maxy = geom.bounds
        lat = (miny + maxy) / 2.0
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))

        # use shapely transform scale
        def _to_m(x, y, z=None):
            return (x * m_per_deg_lon, y * m_per_deg_lat)

        g_m = transform(_to_m, geom)
        return float(g_m.area) / 10_000.0
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)

    def _proj(x, y, z=None):
        return tf.transform(x, y)

    g_m = transform(_proj, geom)
    return float(g_m.area) / 10_000.0


def _parse_product_kind(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    if "_DEL_MONIT" in name:
        return "delineation_monitoring"
    if "_DEL_PRODUCT" in name:
        return "delineation"
    if "_GRA_" in name:
        return "grading"
    if "_FEP_" in name:
        return "first_estimate"
    return "other"


def _centroid_lonlat(geom: Any) -> tuple[float, float]:
    c = geom.centroid
    return float(c.x), float(c.y)


def _load_union_from_rel(pack_dir: Path, rel: str | None) -> Any | None:
    if not rel:
        return None
    path = pack_dir / rel
    if not path.is_file():
        return None
    fc = json.loads(path.read_text(encoding="utf-8"))
    gs = _geoms_from_fc(fc)
    if not gs:
        return None
    return unary_union(gs)


def build_pack(activation: str, out_root: Path) -> dict[str, Any]:
    pack_dir = out_root / activation.lower()
    raw_dir = pack_dir / "raw_cems"
    vec_dir = pack_dir / "vectors"
    pack_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(exist_ok=True)
    vec_dir.mkdir(exist_ok=True)

    urls = fetch_activation_vectors(activation)
    if not urls:
        raise RuntimeError(f"No vector zips found for {activation}")

    products: list[dict[str, Any]] = []
    fire_polys: list[dict[str, Any]] = []

    for url in urls:
        kind = _parse_product_kind(url)
        geo_items: list[dict[str, Any]] = []

        # Direct observedEventA JSON from rapidmapping-viewer S3
        if url.startswith("GEOJSON:"):
            gurl = url[len("GEOJSON:") :]
            gname = gurl.rsplit("/", 1)[-1]
            fname = gname
            gpath = raw_dir / gname
            try:
                download(gurl, gpath)
                # Skip pathological large layers (multi-10MB vector tiles dumps)
                if gpath.stat().st_size > 5_000_000:
                    print(
                        f"  skip oversized geojson {gname} "
                        f"({gpath.stat().st_size // 1_000_000} MB)",
                        flush=True,
                    )
                    continue
                geo_items.append(
                    {
                        "member": gname,
                        "geojson": json.loads(gpath.read_text(encoding="utf-8")),
                    }
                )
            except Exception as e:
                print(f"  skip geojson {gurl}: {e}", flush=True)
                continue
            # synthesize minimal product record path below via same ranking
            extract_dir = raw_dir / (gname + "_dir")
            zpath = gpath
        else:
            # sanitize filename for query-string downloads
            raw_name = url.rsplit("/", 1)[-1]
            fname = raw_name.split("?", 1)[0]
            if not fname.endswith(".zip"):
                fname = fname + ".zip"
            if "type=vectors" in url:
                fname = fname.replace(".zip", "_vectors.zip")
            zpath = raw_dir / fname
            try:
                download(url, zpath)
            except Exception as e:
                print(f"  skip download {url}: {e}", flush=True)
                continue
            if not zipfile.is_zipfile(zpath):
                print(f"  skip non-zip {zpath.name}", flush=True)
                with contextlib.suppress(OSError):
                    zpath.unlink()
                continue
            extract_dir = raw_dir / fname.replace(".zip", "")
            if extract_dir.exists():
                shutil.rmtree(extract_dir)
            extract_dir.mkdir(parents=True)
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(extract_dir)

            geo_items = _load_geojsons_from_zip(zpath)
            # also load extracted
            for p in extract_dir.rglob("*"):
                if p.suffix.lower() in {".json", ".geojson"}:
                    with contextlib.suppress(OSError, json.JSONDecodeError):
                        geo_items.append(
                            {
                                "member": str(p.relative_to(extract_dir)),
                                "geojson": json.loads(p.read_text(encoding="utf-8")),
                            }
                        )

        # Prefer observedEventA (fire area polygons). Never AOI/hydro/buildings.
        def _rank(member: str) -> int:
            m = member.lower().replace("\\", "/")
            base = m.rsplit("/", 1)[-1]
            if "areaofinterest" in base:
                return -100
            if any(
                x in base
                for x in (
                    "builtup",
                    "facilit",
                    "hydro",
                    "transport",
                    "physiography",
                    "settlement",
                )
            ):
                return -50
            if "observedeventa" in base:
                return 100
            if "observedevent" in base and "observedeventp" not in base:
                return 80
            if "burnt" in base or "burned" in base:
                return 70
            return 0

        ranked = sorted(geo_items, key=lambda it: _rank(it["member"]), reverse=True)
        chosen = None
        if ranked and _rank(ranked[0]["member"]) > 0:
            chosen = ranked[0]
        if chosen is None and geo_items:
            # fallback: largest non-AOI polygon layer
            best_a = -1.0
            for item in geo_items:
                if _rank(item["member"]) < 0:
                    continue
                gs = _geoms_from_fc(item["geojson"])
                if not gs:
                    continue
                u = unary_union(gs)
                a = _area_ha_wgs84(u)
                if a > best_a:
                    best_a = a
                    chosen = item

        rec: dict[str, Any] = {
            "url": url,
            "file": fname,
            "kind": kind,
            "geojson_members": [g["member"] for g in geo_items],
            "selected_member": chosen["member"] if chosen else None,
        }
        if chosen:
            gs = _geoms_from_fc(chosen["geojson"])
            if gs:
                union = unary_union(gs)
                area_ha = _area_ha_wgs84(union)
                lon, lat = _centroid_lonlat(union)
                # write clean FC
                out_gj = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "properties": {
                                "activation": activation,
                                "kind": kind,
                                "source_file": fname,
                                "member": chosen["member"],
                                "area_ha": area_ha,
                                "not_lwir": True,
                                "source": "Copernicus EMS Rapid Mapping",
                            },
                            "geometry": mapping(union),
                        }
                    ],
                }
                out_path = vec_dir / f"{activation}_{kind}_{fname.replace('.zip', '')}.geojson"
                # simplify name
                short = f"{kind}.geojson" if kind != "other" else fname.replace(".zip", ".geojson")
                # avoid overwrite: include stem
                short = f"{fname.replace('_vector.zip', '').replace('.zip', '')}.geojson"
                out_path = vec_dir / short
                out_path.write_text(json.dumps(out_gj, indent=2), encoding="utf-8")
                rec.update(
                    {
                        "area_ha": area_ha,
                        "centroid_lon": lon,
                        "centroid_lat": lat,
                        "geojson_path": str(out_path.relative_to(pack_dir)),
                        "n_parts": len(gs),
                    }
                )
                if kind.startswith("delineation") or kind == "grading":
                    fire_polys.append(rec)
        products.append(rec)

    # Timeline: prefer delineation sequence on primary AOI (AOI01), fire areas only
    def _sort_key(p: dict[str, Any]) -> tuple[int, str]:
        f = p.get("file") or ""
        if "FEP" in f:
            return (0, f)
        if "DEL_PRODUCT" in f and "MONIT" not in f:
            return (1, f)
        m = re.search(r"MONIT(\d+)", f)
        if m:
            return (1 + int(m.group(1)), f)
        if "GRA" in f:
            return (50, f)
        return (20, f)

    def _is_fire_layer(p: dict[str, Any]) -> bool:
        mem = (p.get("selected_member") or "").lower()
        return "observedeventa" in mem.replace("\\", "/")

    primary = [
        p
        for p in products
        if p.get("area_ha") and _is_fire_layer(p) and "AOI01" in (p.get("file") or "")
    ]
    if not primary:
        primary = [p for p in products if p.get("area_ha") and _is_fire_layer(p)]
    timeline = sorted(primary, key=_sort_key)

    # multi-perimeter growth proxy: without real acquisition times do NOT invent
    # m/min ROS as primary_ros / Vp tactical. Prefer ha/day (or ha/h) + ros_is_proxy.
    # Assumed 24h spacing is flagged; m/min only under explicit proxy key if retained.
    ros_rows: list[dict[str, Any]] = []
    for i in range(1, len(timeline)):
        a0 = float(timeline[i - 1]["area_ha"])
        a1 = float(timeline[i]["area_ha"])
        r0 = math.sqrt(max(a0, 0) * 10_000 / math.pi)
        r1 = math.sqrt(max(a1, 0) * 10_000 / math.pi)
        dt_h = 24.0  # assumed only — not a measured acquisition delta
        growth_ha_day = (a1 - a0) * (24.0 / dt_h) if dt_h else (a1 - a0)
        growth_ha_h = (a1 - a0) / dt_h if dt_h else None
        # Retained only as flagged proxy (never primary_ros / vp_tactical)
        equiv_r_growth_m_min_proxy = ((r1 - r0) / (dt_h * 60.0)) if r1 > r0 else 0.0
        # perimeter-to-perimeter distances (m) if both geojson present
        haus_m = None
        mean_boundary_m = None
        try:
            g0 = _load_union_from_rel(pack_dir, timeline[i - 1].get("geojson_path"))
            g1 = _load_union_from_rel(pack_dir, timeline[i].get("geojson_path"))
            if g0 is not None and g1 is not None and Transformer is not None:
                tf = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)

                def _proj(x, y, z=None, _tf=tf):
                    return _tf.transform(x, y)

                g0m = transform(_proj, g0)
                g1m = transform(_proj, g1)
                haus_m = float(g0m.hausdorff_distance(g1m))
                # mean distance of g1 boundary points sample to g0
                b = g1m.boundary
                if b is not None and not b.is_empty:
                    # densify sample
                    pts = []
                    if b.geom_type == "LineString":
                        for t in [i / 20 for i in range(21)]:
                            pts.append(b.interpolate(t, normalized=True))
                    elif b.geom_type == "MultiLineString":
                        for line in b.geoms:
                            pts.append(line.interpolate(0.5, normalized=True))
                    if pts:
                        mean_boundary_m = float(sum(g0m.distance(pt) for pt in pts) / len(pts))
        except Exception:
            pass
        ros_rows.append(
            {
                "from": timeline[i - 1].get("file"),
                "to": timeline[i].get("file"),
                "area_ha_from": a0,
                "area_ha_to": a1,
                "delta_area_ha": a1 - a0,
                "assumed_dt_hours": dt_h,
                "dt_is_assumed": True,
                "growth_ha_per_day": growth_ha_day,
                "growth_ha_per_hour": growth_ha_h,
                # Never as primary_ros / Vp tactical — proxy only, assumed dt
                "equiv_radius_growth_m_min_proxy": equiv_r_growth_m_min_proxy,
                "ros_is_proxy": True,
                "not_primary_ros": True,
                "not_vp_tactical": True,
                "vp_tactical": None,
                "hausdorff_m": haus_m,
                "mean_boundary_to_prev_m": mean_boundary_m,
                "note": (
                    "Area growth proxy from successive CEMS products with *assumed* 24h "
                    "spacing (no parsed acquisition times). Prefer ha/day. "
                    "equiv_radius_growth_m_min_proxy is NOT primary_ros and NOT tactical Vp. "
                    "Hausdorff is perimeter-to-perimeter (CEMS vs CEMS), not national official."
                ),
            }
        )

    max_area = max((p.get("area_ha") or 0) for p in products) if products else 0
    report = {
        "product": "open_if_pack_v1",
        "track": "Pista_B_famous_open_data",
        "activation": activation,
        "activation_url": f"{PAGE}/{activation}",
        "built_at_utc": _utc(),
        "requires_lwir_heligraphics": False,
        "data_policy": (
            "Copernicus EMS Rapid Mapping public vectors. "
            "CEMS delineation/grading is satellite-based emergency mapping — "
            "not Spanish national cadastral perimeter; cite as CEMS, not invent official."
        ),
        "n_vector_products": len(products),
        "max_area_ha": max_area,
        "products": products,
        "timeline": timeline,
        "ros_proxy_rows": ros_rows,
        "papers_and_context": [
            {
                "title": "FIRE-RES D5.3 ForeFire-MesoNH EWE",
                "url": "https://fire-res.eu/wp-content/uploads/2024/11/D5.3_FIRE-RES_IA5.2_Modelling-the-EWE-and-smoke-spread-based-on-coupled-fire-atmosphere-approaches.pdf",
            },
            {
                "title": "FIRE-RES D1.1 Lessons learned EWE",
                "url": "https://fire-res.eu/wp-content/uploads/2024/01/D1.1_FIRE-RES_Transfer_of_LL_on_EWE.pdf",
            },
            {
                "title": "Copernicus EMS Rapid Mapping",
                "url": PAGE + f"/{activation}",
            },
        ],
        "gates": {
            "O2_official_national_perimeter": "NO_GO_CEMS_PROXY",
            "O2_open_cems_delineation": "GO"
            if any(p.get("kind", "").startswith("delineation") for p in products)
            else "PARTIAL",
            "O1_multi_source_open": "GO_PROXY" if max_area > 0 else "NO_GO",
            "lwir_required": False,
        },
    }

    (pack_dir / "manifest.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    # combined timeline geojson for map
    features = []
    for i, p in enumerate(timeline):
        rel = p.get("geojson_path")
        if not rel:
            continue
        path = pack_dir / rel
        if not path.is_file():
            continue
        fc = json.loads(path.read_text(encoding="utf-8"))
        for f in fc.get("features") or []:
            f.setdefault("properties", {})
            f["properties"]["timeline_index"] = i
            f["properties"]["product_kind"] = p.get("kind")
            features.append(f)
    combined = {"type": "FeatureCollection", "features": features}
    (pack_dir / "timeline_perimeters.geojson").write_text(
        json.dumps(combined, indent=2), encoding="utf-8"
    )

    # brief
    brief = _render_brief(report)
    (pack_dir / "operator_brief_open_if.md").write_text(brief, encoding="utf-8")

    # scorecard — data-pack GO is not tactical GO; decision_open is monitoring-only.
    score = {
        "track": "Pista_B",
        "activation": activation,
        "max_area_ha": max_area,
        "n_timeline_steps": len(timeline),
        "n_ros_proxy_steps": len(ros_rows),
        "O2_cems_delineation": report["gates"]["O2_open_cems_delineation"],
        "O2_national_official": report["gates"]["O2_official_national_perimeter"],
        "lwir_heligraphics": False,
        "status": "GO_OPEN_DATA_PACK",
        "decision_open": "HOLD",
        "decision_open_note": (
            "Open CEMS pack is monitoring/research only — not tactical dispatch, "
            "not ops ROS, not field_ops GO. status=GO_OPEN_DATA_PACK means data pack ready."
        ),
        "not_tactical_dispatch": True,
        "not_ops_ros": True,
        "ros_is_proxy_only": True,
        "pack_dir": str(pack_dir.relative_to(ROOT)),
    }
    (pack_dir / "scorecard_pista_b.json").write_text(json.dumps(score, indent=2), encoding="utf-8")

    # simple leaflet-ish HTML (static, no deps)
    html = _map_html(report, combined)
    (pack_dir / "map.html").write_text(html, encoding="utf-8")

    print(json.dumps(score, indent=2))
    return report


def _render_brief(report: dict[str, Any]) -> str:
    act = report["activation"]
    lines = [
        f"# Brief open-data — {act} (Pista B)",
        "",
        f"_Generado: {report['built_at_utc']}_",
        "",
        "## Qué es",
        f"- Activación **Copernicus EMS Rapid Mapping** `{act}`",
        f"- URL: {report['activation_url']}",
        "- **No** usa LWIR Heligrafics / CLM drone",
        f"- Área máxima (CEMS): **{report.get('max_area_ha', 0):.1f} ha**",
        "",
        "## Timeline de productos vectoriales",
    ]
    for p in report.get("timeline") or []:
        lines.append(f"- `{p.get('kind')}` · {p.get('area_ha', 0):.1f} ha · {p.get('file')}")
    lines.extend(["", "## ROS proxy (perímetros sucesivos)", ""])
    if not report.get("ros_proxy_rows"):
        lines.append("- (un solo producto con área — no hay secuencia multi-perímetro)")
    for r in report.get("ros_proxy_rows") or []:
        gday = r.get("growth_ha_per_day")
        gday_s = f"{gday:.2f}" if gday is not None else "—"
        gh = r.get("growth_ha_per_hour")
        gh_s = f"{gh:.2f}" if gh is not None else "—"
        lines.append(
            f"- Δarea={r['delta_area_ha']:.1f} ha · growth≈{gday_s} ha/day "
            f"({gh_s} ha/h) · ros_is_proxy=true · not primary_ros "
            f"(dt asumido {r['assumed_dt_hours']} h)"
        )
    lines.extend(
        [
            "",
            "## Papers / contexto",
        ]
    )
    for p in report.get("papers_and_context") or []:
        lines.append(f"- [{p['title']}]({p['url']})")
    lines.extend(
        [
            "",
            "## Gates (honesto)",
            f"- O2 CEMS delineation: **{report['gates']['O2_open_cems_delineation']}**",
            f"- O2 perímetro nacional oficial: **{report['gates']['O2_official_national_perimeter']}**",
            "- LWIR requerido: **no**",
            "",
            "## No usar como",
            "- ROS táctico de dron ni orden de extinción",
            "- Sustituto de ancla INFOCAM CLM (Pablo) — pista paralela",
            "",
            report["data_policy"],
            "",
        ]
    )
    return "\n".join(lines)


def _map_html(report: dict[str, Any], fc: dict[str, Any]) -> str:
    # Minimal HTML + Leaflet CDN + inline geojson
    gj = json.dumps(fc)
    act = report["activation"]
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"/>
<title>{act} open IF pack</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{{height:100%;margin:0}} .banner{{padding:8px;font-family:sans-serif;background:#111;color:#eee}}</style>
</head><body>
<div class="banner"><b>{act}</b> · Copernicus EMS vectors · no LWIR · max {report.get("max_area_ha", 0):.0f} ha</div>
<div id="map"></div>
<script>
const data = {gj};
const map = L.map('map');
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '&copy; OpenStreetMap'
}}).addTo(map);
const layer = L.geoJSON(data, {{
  style: function(f) {{
    const i = (f.properties && f.properties.timeline_index) || 0;
    const colors = ['#fecc5c','#fd8d3c','#f03b20','#bd0026','#800026'];
    return {{color: colors[i % colors.length], weight: 2, fillOpacity: 0.25}};
  }}
}}).addTo(map);
try {{ map.fitBounds(layer.getBounds(), {{padding:[20,20]}}); }} catch(e) {{ map.setView([40.4,-3.7], 6); }}
</script>
</body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Pista B open IF pack from CEMS")
    ap.add_argument("--activation", default="EMSR578", help="e.g. EMSR578, EMSR583")
    ap.add_argument(
        "--out-root",
        type=Path,
        default=ROOT / "outputs" / "open_if",
    )
    args = ap.parse_args()
    print(f"=== Pista B pack {args.activation} ===", flush=True)
    build_pack(args.activation.upper(), args.out_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
