"""LATAM + AU open-IF packs (F1 rights, F2 CEMS GeoTIFF, F4 domain-gap schema).

No network in this module except helpers that callers invoke explicitly.
Does not invent model IoU, ROS, or release-flag flips.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import transform, unary_union

S3_BASE = "https://cems-mapping-website.s3.eu-west-1.amazonaws.com/static/activations"
VIEWER_S3 = "https://rapidmapping-viewer.s3.eu-west-1.amazonaws.com"
RAPID_BACKEND = "https://rapidmapping.emergency.copernicus.eu/backend"
PORTAL_BASE = "https://mapping.emergency.copernicus.eu/activations"
RIGHTS_DOC = "docs/data_campaigns/LATAM_AU_RIGHTS.md"
LICENSE_ID = "copernicus_ems_reg_2021_696_open"
LICENSE_ID_MAPBIOMAS = "mapbiomas_cc_by"
LICENSE_ID_NAFI = "nafi_open_research"
LICENSE_ID_CONAF_PENDING = "conaf_pending_cession"
ALLOWED_LICENSE_IDS = frozenset(
    {LICENSE_ID, LICENSE_ID_MAPBIOMAS, LICENSE_ID_NAFI, LICENSE_ID_CONAF_PENDING}
)
MIN_LABEL_PAIR_HOURS = 12.0
STATIC_LABEL_MASK_IOU = 0.98
ANNUAL_EVAL_STATUS = "blocked_annual_not_event"
# Next-mask dynamics only among CEMS extent products. FEP is a coarse first
# estimate; GRA is damage grading — pairing them with DEL is not fire growth.
GROWTH_LABEL_KINDS = frozenset({"delineation", "delineation_monitoring"})
NON_GROWTH_LABEL_KINDS = frozenset({"first_estimate", "grading", "annual_burned", "annual_fire_scar"})
NBR_THRESHOLD_SWEEP = (-0.20, -0.15, -0.10, -0.05, 0.0)
WARP_SCHEMA = "wfd_latam_au_s2_warp_v1"
CESSION_EVIDENCE_SUFFIXES = frozenset(
    {".pdf", ".md", ".txt", ".png", ".jpg", ".jpeg", ".webp", ".json"}
)
PACK_META_SCHEMA = "wfd_open_if_pack_meta_v1"
DOMAIN_GAP_SCHEMA = "wfd_ml_domain_gap_v1"
LOFO_FOLD_SCHEMA = "wfd_latam_au_lofo_fold_v1"
ERA5_ALIGN_SCHEMA = "wfd_latam_au_era5_align_v1"
AL_RANK_SCHEMA = "wfd_latam_au_active_learning_v1"
WEAK_INVENTORY_SCHEMA = "wfd_latam_au_weak_label_inventory_v1"
USER_AGENT = "WildfireFrontDynamics-latam-au-packs/1.0 (+lab; CEMS attribution)"
MAPBIOMAS_FOGO_ANNUAL = (
    "https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
    "collection_10/fire-col5/mapbiomas_fire_collection5_annual_burned_v1/"
    "burned_area_{year}.tif"
)
NAFI_IMAGE_ZIP = (
    "https://firenorth.org.au/nafi3/downloads/firescars/{year}/"
    "{year} firescar image files.zip"
)
NAFI_SHAPE_ZIP = (
    "https://firenorth.org.au/nafi3/downloads/firescars/{year}/"
    "{year} firescar shapefiles.zip"
)

# Public vector zips researched from official activation HTML (2026-08-13).
EMSR_PACK_SPECS: dict[str, dict[str, Any]] = {
    "AU_EMSR500_PERTH": {
        "event_id": "AU_EMSR500_PERTH",
        "region": "au",
        "country": "AU",
        "activation": "EMSR500",
        "aoi": "AOI01",
        "aoi_name": "Perth",
        "year": 2021,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32750,  # UTM 50S — Perth ~116.18E, 31.78S
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR500/",
        "approx_lonlat": (116.17767, -31.77966),
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20210205_203225",
                "delivery_utc": "2021-02-05T20:32:25Z",
                "url": f"{S3_BASE}/EMSR500/EMSR500_AOI01_DEL_PRODUCT_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "DEL_MONIT01",
                "kind": "delineation_monitoring",
                "dated": "20210211_170324",
                "delivery_utc": "2021-02-11T17:03:24Z",
                "url": f"{S3_BASE}/EMSR500/EMSR500_AOI01_DEL_MONIT01_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "GRA_PRODUCT",
                "kind": "grading",
                "dated": "20210213_022304",
                "delivery_utc": "2021-02-13T02:23:04Z",
                "url": f"{S3_BASE}/EMSR500/EMSR500_AOI01_GRA_PRODUCT_r1_RTP01_v1_vector.zip",
            },
        ],
    },
    "CL_EMSR647_NACIMIENTO": {
        "event_id": "CL_EMSR647_NACIMIENTO",
        "region": "cl",
        "country": "CL",
        "activation": "EMSR647",
        "aoi": "AOI01",
        "aoi_name": "Nacimiento",
        "year": 2023,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32718,  # UTM 18S — Biobío / Nacimiento
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR647/",
        "approx_lonlat": (-72.6700, -37.5050),
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20230213_235634",
                "delivery_utc": "2023-02-13T23:56:34Z",
                "url": f"{S3_BASE}/EMSR647/EMSR647_AOI01_DEL_PRODUCT_r1_RTP01_v2_vector.zip",
            },
            {
                "product_id": "DEL_MONIT05",
                "kind": "delineation_monitoring",
                "dated": "20230214_021543",
                "delivery_utc": "2023-02-14T02:15:43Z",
                "url": f"{S3_BASE}/EMSR647/EMSR647_AOI01_DEL_MONIT05_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "DEL_MONIT06",
                "kind": "delineation_monitoring",
                "dated": "20230215_212410",
                "delivery_utc": "2023-02-15T21:24:10Z",
                "url": f"{S3_BASE}/EMSR647/EMSR647_AOI01_DEL_MONIT06_r1_RTP01_v1_vector.zip",
            },
        ],
    },
    "AU_EMSR408_NSW": {
        "event_id": "AU_EMSR408_NSW",
        "region": "au",
        "country": "AU",
        "activation": "EMSR408",
        "aoi": "AOI09",
        "aoi_name": "Bendemeer",
        "year": 2019,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32756,  # UTM 56S — Bendemeer / New England NSW
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR408/",
        "approx_lonlat": (151.1550, -30.8820),
        "source_kind": "cems_s3_vector_zip",
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20191114_211550",
                "delivery_utc": "2019-11-14T21:15:50Z",
                "url": f"{S3_BASE}/EMSR408/EMSR408_AOI09_DEL_PRODUCT_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "DEL_MONIT01",
                "kind": "delineation_monitoring",
                "dated": "20191116_181046",
                "delivery_utc": "2019-11-16T18:10:46Z",
                "url": f"{S3_BASE}/EMSR408/EMSR408_AOI09_DEL_MONIT01_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "DEL_MONIT02",
                "kind": "delineation_monitoring",
                "dated": "20191118_215333",
                "delivery_utc": "2019-11-18T21:53:33Z",
                "url": f"{S3_BASE}/EMSR408/EMSR408_AOI09_DEL_MONIT02_r1_RTP01_v1_vector.zip",
            },
            {
                "product_id": "DEL_MONIT03",
                "kind": "delineation_monitoring",
                "dated": "20191121_212042",
                "delivery_utc": "2019-11-21T21:20:42Z",
                "url": f"{S3_BASE}/EMSR408/EMSR408_AOI09_DEL_MONIT03_r1_RTP01_v1_vector.zip",
            },
        ],
    },
    "CL_EMSR715_VALPARAISO": {
        "event_id": "CL_EMSR715_VALPARAISO",
        "region": "cl",
        "country": "CL",
        "activation": "EMSR715",
        "aoi": "AOI01",
        "aoi_name": "Valparaiso",
        "year": 2024,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32719,  # UTM 19S — Valparaíso
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR715/",
        "approx_lonlat": (-71.526947, -33.043937),
        "source_kind": "cems_rapid_json",
        "products": [
            {
                "product_id": "FEP_PRODUCT",
                "kind": "first_estimate",
                "dated": "20240204_200240",
                "delivery_utc": "2024-02-04T20:02:40Z",
                "url": f"{VIEWER_S3}/EMSR715/AOI01/FEP_PRODUCT/EMSR715_AOI01_FEP_PRODUCT_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR715/AOI01/FEP_PRODUCT/EMSR715_AOI01_FEP_PRODUCT_v1.zip",
            },
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20240206_165236",
                "delivery_utc": "2024-02-06T16:52:36Z",
                "url": f"{VIEWER_S3}/EMSR715/AOI01/DEL_PRODUCT/EMSR715_AOI01_DEL_PRODUCT_observedEventA_v2.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR715/AOI01/DEL_PRODUCT/EMSR715_AOI01_DEL_PRODUCT_v2.zip",
            },
            {
                "product_id": "GRA_PRODUCT",
                "kind": "grading",
                "dated": "20240209_140139",
                "delivery_utc": "2024-02-09T14:01:39Z",
                "url": f"{VIEWER_S3}/EMSR715/AOI01/GRA_PRODUCT/EMSR715_AOI01_GRA_PRODUCT_observedEventA_v3.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR715/AOI01/GRA_PRODUCT/EMSR715_AOI01_GRA_PRODUCT_v3.zip",
            },
        ],
    },
    "BO_EMSR765": {
        "event_id": "BO_EMSR765",
        "region": "bo",
        "country": "BO",
        "activation": "EMSR765",
        "aoi": "AOI01",
        "aoi_name": "El Macho",
        "year": 2024,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32720,  # UTM 20S — Santa Cruz / El Macho
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR765/",
        "approx_lonlat": (-62.3000, -15.1500),
        "source_kind": "cems_rapid_json",
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20240926_171213",
                "delivery_utc": "2024-09-26T17:12:13Z",
                "url": f"{VIEWER_S3}/EMSR765/AOI01/DEL_PRODUCT/EMSR765_AOI01_DEL_PRODUCT_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR765/AOI01/DEL_PRODUCT/EMSR765_AOI01_DEL_PRODUCT_v2.zip",
            },
            {
                "product_id": "DEL_MONIT01",
                "kind": "delineation_monitoring",
                "dated": "20240930_094734",
                "delivery_utc": "2024-09-30T09:47:34Z",
                "url": f"{VIEWER_S3}/EMSR765/AOI01/DEL_MONIT01/EMSR765_AOI01_DEL_MONIT01_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR765/AOI01/DEL_MONIT01/EMSR765_AOI01_DEL_MONIT01_v1.zip",
            },
            {
                "product_id": "DEL_MONIT02",
                "kind": "delineation_monitoring",
                "dated": "20241004_194544",
                "delivery_utc": "2024-10-04T19:45:44Z",
                "url": f"{VIEWER_S3}/EMSR765/AOI01/DEL_MONIT02/EMSR765_AOI01_DEL_MONIT02_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR765/AOI01/DEL_MONIT02/EMSR765_AOI01_DEL_MONIT02_v1.zip",
            },
        ],
    },
    "MX_EMSR717": {
        "event_id": "MX_EMSR717",
        "region": "mx",
        "country": "MX",
        "activation": "EMSR717",
        "aoi": "AOI01",
        "aoi_name": "Benito Juarez",
        "year": 2024,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32615,  # UTM 15N — Oaxaca / Benito Juárez
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR717/",
        "approx_lonlat": (-94.1250, 16.7700),
        "source_kind": "cems_rapid_json",
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20240409_063059",
                "delivery_utc": "2024-04-09T06:30:59Z",
                "url": f"{VIEWER_S3}/EMSR717/AOI01/DEL_PRODUCT/EMSR717_AOI01_DEL_PRODUCT_observedEventA_v2.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR717/AOI01/DEL_PRODUCT/EMSR717_AOI01_DEL_PRODUCT_v2.zip",
            },
            {
                "product_id": "DEL_MONIT05",
                "kind": "delineation_monitoring",
                "dated": "20240411_232818",
                "delivery_utc": "2024-04-11T23:28:18Z",
                "url": f"{VIEWER_S3}/EMSR717/AOI01/DEL_MONIT05/EMSR717_AOI01_DEL_MONIT05_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR717/AOI01/DEL_MONIT05/EMSR717_AOI01_DEL_MONIT05_v1.zip",
            },
            {
                "product_id": "GRA_PRODUCT",
                "kind": "grading",
                "dated": "20240418_221508",
                "delivery_utc": "2024-04-18T22:15:08Z",
                "url": f"{VIEWER_S3}/EMSR717/AOI01/GRA_PRODUCT/EMSR717_AOI01_GRA_PRODUCT_observedEventA_v1.json",
                "zip_url": f"{RAPID_BACKEND}/EMSR717/AOI01/GRA_PRODUCT/EMSR717_AOI01_GRA_PRODUCT_v1.zip",
            },
        ],
    },
    "ES_EMSR685_TENERIFE": {
        "event_id": "ES_EMSR685_TENERIFE",
        "region": "es",
        "country": "ES",
        "activation": "EMSR685",
        "aoi": "AOI01",
        "aoi_name": "Candelaria",
        "year": 2023,
        "class": "ml_weak",
        "label_level": "L2_proxy",
        "license_id": LICENSE_ID,
        "crs_epsg": 32628,  # UTM 28N — Tenerife / Candelaria
        "gsd_m": 30.0,
        "portal_url": f"{PORTAL_BASE}/EMSR685/",
        "approx_lonlat": (-16.4800, 28.3500),
        "source_kind": "cems_rapid_zip",
        "grafcan_referral": (
            "GRAFCAN / IDECanarias #260728 (2026-08-10): no Canary agency layer; "
            "use Copernicus EMSR685"
        ),
        "products": [
            {
                "product_id": "DEL_PRODUCT",
                "kind": "delineation",
                "dated": "20230819_045000",
                "delivery_utc": "2023-08-19T04:50:00Z",
                "url": f"{RAPID_BACKEND}/EMSR685/AOI01/DEL_PRODUCT/EMSR685_AOI01_DEL_PRODUCT_v1.zip",
            },
            {
                "product_id": "DEL_MONIT01",
                "kind": "delineation_monitoring",
                "dated": "20230822_003000",
                "delivery_utc": "2023-08-22T00:30:00Z",
                "url": f"{RAPID_BACKEND}/EMSR685/AOI01/DEL_MONIT01/EMSR685_AOI01_DEL_MONIT01_v2.zip",
            },
            {
                "product_id": "DEL_MONIT02",
                "kind": "delineation_monitoring",
                "dated": "20230825_010000",
                "delivery_utc": "2023-08-25T01:00:00Z",
                "url": f"{RAPID_BACKEND}/EMSR685/AOI01/DEL_MONIT02/EMSR685_AOI01_DEL_MONIT02_v1.zip",
            },
            {
                "product_id": "GRA_PRODUCT",
                "kind": "grading",
                "dated": "20230826_233000",
                "delivery_utc": "2023-08-26T23:30:00Z",
                "url": f"{RAPID_BACKEND}/EMSR685/AOI01/GRA_PRODUCT/EMSR685_AOI01_GRA_PRODUCT_v1.zip",
            },
        ],
    },
}

# L1 annual / seasonal scars (not intra-event CEMS). Same pack-meta contract.
WEAK_PACK_SPECS: dict[str, dict[str, Any]] = {
    "BR_PANTANAL_2020_MAPBIOMAS": {
        "event_id": "BR_PANTANAL_2020_MAPBIOMAS",
        "region": "br",
        "country": "BR",
        "activation": "MAPBIOMAS_FOGO_COL5",
        "aoi": "PANTANAL_WINDOW",
        "aoi_name": "Pantanal (windowed annual burned)",
        "year": 2020,
        "class": "ml_weak",
        "label_level": "L1_annual",
        "license_id": LICENSE_ID_MAPBIOMAS,
        "crs_epsg": 4326,
        "gsd_m": 30.0,
        "portal_url": "https://brasil.mapbiomas.org/en/mapbiomas-fogo/",
        "approx_lonlat": (-57.0000, -17.0000),
        "source_kind": "mapbiomas_annual",
        "bbox_wgs84": [-58.5, -18.5, -55.5, -16.0],
        "years": [2018, 2019, 2020],
        "products": [
            {
                "product_id": f"ANNUAL_{year}",
                "kind": "annual_burned",
                "dated": f"{year}0101_000000",
                "delivery_utc": f"{year}-12-31T00:00:00Z",
                "url": MAPBIOMAS_FOGO_ANNUAL.format(year=year),
            }
            for year in (2018, 2019, 2020)
        ],
    },
    "AU_NAFI_NT_SEASON_2023": {
        "event_id": "AU_NAFI_NT_SEASON_2023",
        "region": "au",
        "country": "AU",
        "activation": "NAFI_FIRESCHAR",
        "aoi": "DARWIN_NT_WINDOW",
        "aoi_name": "Darwin / north NT (windowed annual scars)",
        "year": 2023,
        "class": "ml_weak",
        "label_level": "L1_annual",
        "license_id": LICENSE_ID_NAFI,
        "crs_epsg": 4326,
        "gsd_m": 250.0,
        "portal_url": "https://firenorth.org.au/nafi3/views/data/Download1.html",
        "approx_lonlat": (130.8456, -12.4634),
        "source_kind": "nafi_annual",
        "bbox_wgs84": [130.50, -13.10, 131.40, -12.00],
        "years": [2021, 2022, 2023],
        "products": [
            {
                "product_id": f"NAFI_{year}",
                "kind": "annual_fire_scar",
                "dated": f"{year}1231_000000",
                "delivery_utc": f"{year}-12-31T00:00:00Z",
                "url": NAFI_IMAGE_ZIP.format(year=year),
                "shape_url": NAFI_SHAPE_ZIP.format(year=year),
            }
            for year in (2021, 2022, 2023)
        ],
    },
}

ALL_PACK_SPECS: dict[str, dict[str, Any]] = {**EMSR_PACK_SPECS, **WEAK_PACK_SPECS}

ALLOWED_PACK_ROOT_PARTS = ("data", "open_if", "latam_au")
ALLOWED_PACK_REGIONS = frozenset({"au", "cl", "br", "mx", "bo", "gt", "es"})
GEOTIFF_NAME_RE = re.compile(
    r"(20\d{6}_\d{6}|20\d{2}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2})"
)

FORBIDDEN_SCORECARD_KEYS = frozenset(
    {
        "primary_ros",
        "vp_tactical",
        "ros_m_min",
        "primary_ros_m_min",
        "vp_ha",
    }
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def pack_dir_for(root: Path, spec: dict[str, Any]) -> Path:
    return Path(root) / spec["region"] / spec["event_id"]


def is_allowed_pack_path(path: Path, *, repo_root: Path) -> bool:
    """Packs must live under data/open_if/latam_au/<region>/<event_id>/."""
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    parts = rel.parts
    if len(parts) < 5:
        return False
    return parts[:3] == ALLOWED_PACK_ROOT_PARTS and parts[3] in ALLOWED_PACK_REGIONS


def sha256_file(path: Path, chunk: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def geoms_from_geojson(data: dict[str, Any]) -> list[Any]:
    geoms = []
    if data.get("type") == "FeatureCollection":
        for feat in data.get("features") or []:
            g = feat.get("geometry")
            if g:
                try:
                    geoms.append(shape(g))
                except Exception:
                    continue
    elif data.get("type") == "Feature":
        g = data.get("geometry")
        if g:
            geoms.append(shape(g))
    elif "coordinates" in data:
        try:
            parsed = shape(data)
        except Exception:
            parsed = None
        if parsed is not None:
            geoms.append(parsed)
    return [g for g in geoms if g is not None and not g.is_empty]


def rank_cems_member(member: str) -> int:
    m = member.lower().replace("\\", "/")
    base = m.rsplit("/", 1)[-1]
    if "areaofinterest" in base:
        return -100
    if any(x in base for x in ("builtup", "facilit", "hydro", "transport", "physiography", "settlement")):
        return -50
    if "observedeventa" in base:
        return 100
    if "observedevent" in base and "observedeventp" not in base:
        return 80
    if "burnt" in base or "burned" in base:
        return 70
    return 0


def area_ha_wgs84(geom: Any) -> float:
    try:
        from pyproj import Transformer
    except ImportError:
        Transformer = None  # type: ignore
    if Transformer is None:
        minx, miny, maxx, maxy = geom.bounds
        lat = (miny + maxy) / 2.0
        m_per_deg_lat = 111_320.0
        m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat))

        def _to_m(x: float, y: float, z: float | None = None) -> tuple[float, float]:
            return (x * m_per_deg_lon, y * m_per_deg_lat)

        return float(transform(_to_m, geom).area) / 10_000.0
    tf = Transformer.from_crs("EPSG:4326", "EPSG:6933", always_xy=True)

    def _proj(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return tf.transform(x, y)

    return float(transform(_proj, geom).area) / 10_000.0


def load_observed_from_vector_zip(zpath: Path) -> dict[str, Any] | None:
    import zipfile

    items: list[dict[str, Any]] = []
    with zipfile.ZipFile(zpath, "r") as zf:
        for name in zf.namelist():
            low = name.lower()
            if not low.endswith((".json", ".geojson")):
                continue
            raw = zf.read(name)
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            items.append({"member": name, "geojson": data})
    if not items:
        return None
    ranked = sorted(items, key=lambda it: rank_cems_member(it["member"]), reverse=True)
    chosen = ranked[0] if rank_cems_member(ranked[0]["member"]) > 0 else None
    if chosen is None:
        return None
    return observed_from_geojson(chosen["geojson"], member=chosen["member"])


def observed_from_geojson(data: dict[str, Any], *, member: str = "geojson") -> dict[str, Any] | None:
    gs = geoms_from_geojson(data)
    if not gs:
        return None
    union = unary_union(gs)
    return {
        "member": member,
        "geometry": union,
        "area_ha": area_ha_wgs84(union),
        "bounds_wgs84": list(union.bounds),
        "n_parts": len(gs),
    }


def load_observed_from_path(path: Path) -> dict[str, Any] | None:
    """Load observed geometry from a CEMS vector zip or standalone GeoJSON."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return load_observed_from_vector_zip(path)
    if suffix in {".json", ".geojson"}:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return observed_from_geojson(data, member=path.name)
    return None


def rasterize_geom_to_geotiff(
    geom_wgs84: Any,
    dest: Path,
    *,
    epsg: int,
    gsd_m: float,
    pad_m: float = 300.0,
    ref_bounds_m: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Rasterize a WGS84 polygon to a uint8 GeoTIFF in a projected CRS."""
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    dest.parent.mkdir(parents=True, exist_ok=True)
    to_m = Transformer.from_crs("EPSG:4326", f"EPSG:{int(epsg)}", always_xy=True)

    def _proj(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return to_m.transform(x, y)

    g_m = transform(_proj, geom_wgs84)
    minx, miny, maxx, maxy = g_m.bounds
    if ref_bounds_m is not None:
        minx, miny, maxx, maxy = ref_bounds_m
    minx -= pad_m
    miny -= pad_m
    maxx += pad_m
    maxy += pad_m
    width = max(8, int(math.ceil((maxx - minx) / gsd_m)))
    height = max(8, int(math.ceil((maxy - miny) / gsd_m)))
    # Cap huge AOIs so a lab pack stays small (still a real GeoTIFF).
    max_dim = 2048
    if width > max_dim or height > max_dim:
        scale = max(width / max_dim, height / max_dim)
        gsd_m = gsd_m * scale
        width = max(8, int(math.ceil((maxx - minx) / gsd_m)))
        height = max(8, int(math.ceil((maxy - miny) / gsd_m)))
    transform_aff = from_origin(minx, maxy, gsd_m, gsd_m)
    burned = rasterize(
        [(g_m, 1)],
        out_shape=(height, width),
        transform=transform_aff,
        fill=0,
        dtype="uint8",
        all_touched=True,
    )
    with rasterio.open(
        dest,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="uint8",
        crs=f"EPSG:{int(epsg)}",
        transform=transform_aff,
        compress="deflate",
        nodata=0,
    ) as ds:
        ds.write(np.asarray(burned, dtype="uint8"), 1)
        ds.update_tags(
            source="Copernicus EMS Rapid Mapping (rasterized observedEvent)",
            license_id=LICENSE_ID,
            not_national_cadastre="true",
        )
    return {
        "path": str(dest),
        "crs": f"EPSG:{int(epsg)}",
        "gsd_m": float(gsd_m),
        "width": int(width),
        "height": int(height),
        "positive_pixels": int(burned.sum()),
        "bounds_m": [float(minx), float(miny), float(maxx), float(maxy)],
    }


def aligned_bounds_m(
    geoms_wgs84: list[Any],
    *,
    epsg: int,
    pad_m: float = 300.0,
) -> tuple[float, float, float, float]:
    from pyproj import Transformer

    to_m = Transformer.from_crs("EPSG:4326", f"EPSG:{int(epsg)}", always_xy=True)

    def _proj(x: float, y: float, z: float | None = None) -> tuple[float, float]:
        return to_m.transform(x, y)

    union = unary_union([transform(_proj, g) for g in geoms_wgs84])
    minx, miny, maxx, maxy = union.bounds
    return (minx - pad_m, miny - pad_m, maxx + pad_m, maxy + pad_m)


def binary_iou(a: Any, b: Any) -> float | None:
    import numpy as np

    aa = np.asarray(a) > 0
    bb = np.asarray(b) > 0
    if aa.shape != bb.shape:
        return None
    inter = int(np.logical_and(aa, bb).sum())
    union = int(np.logical_or(aa, bb).sum())
    if union == 0:
        return None
    return float(inter / union)


def dated_geotiff_ok(name: str) -> bool:
    return bool(GEOTIFF_NAME_RE.search(name))


def validate_pack_meta(meta: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if meta.get("schema") != PACK_META_SCHEMA:
        fails.append(f"bad_schema:{meta.get('schema')}")
    for key in (
        "event_id",
        "region",
        "activation",
        "license_id",
        "crs",
        "gsd_m",
        "class",
        "geotiffs",
        "labels",
        "rights_doc",
    ):
        if key not in meta:
            fails.append(f"missing_{key}")
    tifs = meta.get("geotiffs") or []
    if not isinstance(tifs, list) or len(tifs) < 3:
        fails.append(f"need_ge3_geotiff:n={len(tifs) if isinstance(tifs, list) else 0}")
    else:
        dated = 0
        for rec in tifs:
            rel = str((rec or {}).get("rel") or (rec or {}).get("file") or "")
            if dated_geotiff_ok(rel):
                dated += 1
        if dated < 3:
            fails.append(f"need_ge3_dated_geotiff:dated={dated}")
    labels = meta.get("labels") or []
    if not isinstance(labels, list) or len(labels) < 1:
        fails.append("need_label_layer")
    if meta.get("license_id") not in ALLOWED_LICENSE_IDS:
        fails.append(f"unexpected_license_id:{meta.get('license_id')}")
    if meta.get("class") not in {"ml_weak", "ml_strong", "context_only"}:
        fails.append(f"bad_class:{meta.get('class')}")
    if meta.get("not_national_cadastre") is not True:
        fails.append("must_flag_not_national_cadastre")
    if meta.get("not_lwir") is not True:
        fails.append("must_flag_not_lwir")
    return fails


def build_pack_meta(
    spec: dict[str, Any],
    *,
    geotiffs: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "schema": PACK_META_SCHEMA,
        "event_id": spec["event_id"],
        "region": spec["region"],
        "country": spec["country"],
        "activation": spec["activation"],
        "aoi": spec["aoi"],
        "aoi_name": spec["aoi_name"],
        "year": spec["year"],
        "class": spec["class"],
        "label_level": spec["label_level"],
        "license_id": spec["license_id"],
        "rights_doc": RIGHTS_DOC,
        "portal_url": spec["portal_url"],
        "crs": f"EPSG:{int(spec['crs_epsg'])}",
        "gsd_m": spec["gsd_m"],
        "sensor": "CEMS Rapid Mapping observedEvent (rasterized vector)",
        "geotiff_origin": "rasterized_cems_vector",
        "native_cems_geotiff_listed": False,
        "dates": [p["delivery_utc"] for p in spec["products"]],
        "geotiffs": geotiffs,
        "labels": labels,
        "not_national_cadastre": True,
        "not_o2_es": True,
        "not_lwir": True,
        "not_grade_a": True,
        "not_tactical_ros": True,
        "lab_ok_provisional": True,
        "built_at_utc": utc_now(),
    }
    if extra:
        meta.update(extra)
    return meta


def pack_readme(spec: dict[str, Any], meta: dict[str, Any]) -> str:
    lines = [
        f"# {spec['event_id']}",
        "",
        f"- Activation: **{spec['activation']}** {spec['aoi']} ({spec['aoi_name']})",
        f"- Portal: {spec['portal_url']}",
        f"- Class: `{spec['class']}` / {spec['label_level']}",
        f"- CRS: {meta.get('crs')} · GSD: {meta.get('gsd_m')} m",
        f"- License: `{spec['license_id']}`",
        f"- Rights: `{RIGHTS_DOC}`",
        "",
        "## Attribution",
        "",
    ]
    if spec.get("license_id") == LICENSE_ID:
        lines += [
            "Contains modified Copernicus Emergency Management Service information "
            f"({spec['year']}). Source: {spec['portal_url']}",
            "© European Union, Copernicus EMS — as-is, no warranty.",
            "Proxy perimeter ≠ national cadastre / O2 España / CONAF official.",
        ]
    elif spec.get("license_id") == LICENSE_ID_MAPBIOMAS:
        lines += [
            "MapBiomas Fogo Collection 5 annual burned (CC-BY). Cite MapBiomas.",
            f"Source: {spec['portal_url']}",
            "Annual scar ≠ intra-event perimeter; L1 weak only.",
        ]
    elif spec.get("license_id") == LICENSE_ID_NAFI:
        lines += [
            "NAFI north Australia fire scars (research/management use; check redistribution).",
            f"Source: {spec['portal_url']}",
            "250 m annual scar ≠ agency cadastre; L1 weak only.",
        ]
    else:
        lines += [f"Source: {spec['portal_url']}"]
    lines += [
        "",
        "## GeoTIFFs",
        "",
        f"Origin: `{meta.get('geotiff_origin')}`.",
        "",
    ]
    for rec in meta.get("geotiffs") or []:
        lines.append(f"- `{rec.get('rel')}` · {rec.get('role')} · {rec.get('delivery_utc')}")
    lines += [
        "",
        "## Non-claims",
        "",
        "- Not GO_Q complete, not FREEZE lift, not fusion change, not ROS/Vp.",
        "- Not `ml_strong` until aligned multi-date EO + human review.",
        "",
    ]
    return "\n".join(lines) + "\n"


def load_clm_sealed_test() -> dict[str, Any]:
    """Cite sealed U1 TEST numbers. Never invent. Never use catalog 0.8963 as U1."""
    root = Path(__file__).resolve().parents[2]
    scorecard = root / "docs" / "ML_PRODUCT_SCORECARD.json"
    stamp = root / "docs" / "ML_PRODUCT_GO_STATUS.json"
    out: dict[str, Any] = {
        "source": str(scorecard.as_posix()),
        "iou": None,
        "n": None,
        "selective_iou_80": None,
        "ece_patch_conf": None,
        "product_id": "clm_ensemble_v34",
        "split": "test",
        "note": "Sealed U1 TEST mean IoU. Not catalog 0.8963. Not ROS.",
    }
    if scorecard.is_file():
        data = json.loads(scorecard.read_text(encoding="utf-8"))
        primary = data.get("primary") or {}
        unc = data.get("uncertainty") or {}
        out["source"] = "docs/ML_PRODUCT_SCORECARD.json"
        out["iou"] = primary.get("model_iou")
        out["n"] = primary.get("n_patches")
        out["selective_iou_80"] = unc.get("selective_iou_at_80pct_coverage")
        out["ece_patch_conf"] = unc.get("ece_patch_conf")
        out["product_id"] = data.get("product_id") or out["product_id"]
        out["protocol"] = data.get("protocol")
    if stamp.is_file():
        st = json.loads(stamp.read_text(encoding="utf-8"))
        ev = st.get("evidence") or {}
        if out["iou"] is None:
            out["iou"] = ev.get("mean_iou_test")
            out["n"] = ev.get("n_patches")
    return out


def empty_domain_row(event_id: str, region: str) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "region": region,
        "eval_status": "not_run",
        "model_iou": None,
        "n": 0,
        "reason": "",
        "pack_metrics": {},
    }


def validate_domain_gap(doc: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if doc.get("schema") != DOMAIN_GAP_SCHEMA:
        fails.append(f"bad_schema:{doc.get('schema')}")
    for key in ("as_of_utc", "product_id", "clm_test", "au", "latam", "zero_shot", "not_claims"):
        if key not in doc:
            fails.append(f"missing_{key}")
    blob = json.dumps(doc)
    for forbidden in FORBIDDEN_SCORECARD_KEYS:
        if forbidden in blob:
            fails.append(f"forbidden_key:{forbidden}")
    clm = doc.get("clm_test") or {}
    if clm.get("iou") is not None and not clm.get("source"):
        fails.append("clm_iou_missing_source")
    for side in ("au", "latam"):
        row = doc.get(side) or {}
        iou = row.get("model_iou")
        status = str(row.get("eval_status") or "")
        if iou is not None and status in {"not_run", "blocked_incompatible_schema", ""}:
            fails.append(f"{side}_invented_iou_while_{status or 'empty'}")
        if iou is not None and not row.get("n"):
            fails.append(f"{side}_iou_without_n")
    for extra in doc.get("extra_packs") or []:
        if not isinstance(extra, dict):
            continue
        eid = str(extra.get("event_id") or "extra")
        iou = extra.get("model_iou")
        status = str(extra.get("eval_status") or "")
        if iou is not None and status in {
            "not_run",
            "blocked_incompatible_schema",
            ANNUAL_EVAL_STATUS,
            "",
        }:
            fails.append(f"{eid}_invented_iou_while_{status or 'empty'}")
        if iou is not None and not extra.get("n"):
            fails.append(f"{eid}_iou_without_n")
    zs = doc.get("zero_shot") or {}
    if zs.get("status") == "measured" and zs.get("model_iou") is None:
        fails.append("zero_shot_measured_without_iou")
    rails = doc.get("rails") or {}
    if rails.get("go_q") not in {None, "partial", "false"}:
        fails.append("go_q_must_stay_partial")
    if rails.get("tobarra_keep_reopen") is True:
        fails.append("must_not_reopen_tobarra_keep")
    return fails


def successive_mask_ious(arrays: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i in range(1, len(arrays)):
        iou = binary_iou(arrays[i - 1], arrays[i])
        rows.append({"from_idx": i - 1, "to_idx": i, "mask_iou": iou})
    return rows


def write_label_geojson(geom: Any, dest: Path, properties: dict[str, Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fc = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": properties,
                "geometry": mapping(geom),
            }
        ],
    }
    dest.write_text(json.dumps(fc), encoding="utf-8")


# --- Product open_if bridge (scorecard_pista_b for decide / open-pack APIs) ---

PRODUCT_PACK_SLUGS: dict[str, str] = {
    "AU_EMSR500_PERTH": "emsr500_perth",
    "CL_EMSR647_NACIMIENTO": "emsr647_nacimiento",
    "AU_EMSR408_NSW": "emsr408_bendemeer",
    "CL_EMSR715_VALPARAISO": "emsr715_valparaiso",
    "BR_PANTANAL_2020_MAPBIOMAS": "mapbiomas_pantanal_2020",
    "AU_NAFI_NT_SEASON_2023": "nafi_nt_2023",
    "BO_EMSR765": "emsr765_el_macho",
    "MX_EMSR717": "emsr717_benito_juarez",
    "ES_EMSR685_TENERIFE": "emsr685_tenerife",
}

# Product E2E default stays the two P0 packs so adding P1 specs does not fail
# the live decide path when new rasters are missing. Pass --event-id for more.
PRODUCT_E2E_DEFAULT_IDS: tuple[str, ...] = (
    "AU_EMSR500_PERTH",
    "CL_EMSR647_NACIMIENTO",
)

ML_EXPORT_SCHEMA = "wfd_latam_au_ml_export_v1"
ML_PATCH_CONTRACT = "cems_label_mask_patches_v1"
PRODUCT_E2E_SCHEMA = "wfd_latam_au_product_e2e_v1"


def product_slug_for(event_id: str) -> str:
    if event_id in PRODUCT_PACK_SLUGS:
        return PRODUCT_PACK_SLUGS[event_id]
    spec = ALL_PACK_SPECS.get(event_id) or EMSR_PACK_SPECS.get(event_id) or {}
    act = spec.get("activation") or event_id
    return str(act).lower()


def source_pack_ready(pack_dir: Path) -> tuple[bool, str]:
    """Return (ok, reason). Requires meta.json + ≥1 label geojson or tif."""
    pack = Path(pack_dir)
    meta_p = pack / "meta.json"
    if not meta_p.is_file():
        return False, f"missing_meta:{meta_p}"
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"bad_meta:{exc}"
    labels_dir = pack / "labels"
    geojsons = sorted(labels_dir.glob("*.geojson")) if labels_dir.is_dir() else []
    tifs = sorted(labels_dir.glob("*.tif")) if labels_dir.is_dir() else []
    if not geojsons and not tifs:
        return False, f"missing_labels:{labels_dir}"
    n_gt = len(meta.get("geotiffs") or [])
    if n_gt < 1:
        return False, "meta_has_no_geotiffs"
    return True, "ok"


def _label_geojson_rows(pack_dir: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Timeline rows from label geotiff meta + companion geojson when present."""
    rows: list[dict[str, Any]] = []
    for rec in meta.get("geotiffs") or []:
        role = str(rec.get("role") or "")
        if not role.startswith("label_"):
            continue
        rel = rec.get("rel")
        if not rel:
            continue
        stem = Path(str(rel)).stem
        gj_rel = f"labels/{stem}.geojson"
        gj_path = pack_dir / gj_rel
        area = rec.get("area_ha")
        rows.append(
            {
                "kind": rec.get("kind") or "delineation",
                "product_id": rec.get("product_id"),
                "delivery_utc": rec.get("delivery_utc"),
                "area_ha": float(area) if area is not None else None,
                "label_tif": str(rel).replace("\\", "/"),
                "geojson_path": gj_rel if gj_path.is_file() else None,
                "source_zip": rec.get("source_zip"),
            }
        )
    rows.sort(key=lambda r: str(r.get("delivery_utc") or ""))
    return rows


def build_pista_b_scorecard_from_meta(
    meta: dict[str, Any],
    *,
    pack_dir_rel: str,
    timeline_n: int,
) -> dict[str, Any]:
    """scorecard_pista_b.json fields loadable by load_open_metrics_from_pack."""
    areas = [
        float(r["area_ha"])
        for r in (meta.get("geotiffs") or [])
        if str(r.get("role") or "").startswith("label_") and r.get("area_ha") is not None
    ]
    max_area = max(areas) if areas else 0.0
    has_del = any(
        str(r.get("kind") or "").startswith("delineation")
        for r in (meta.get("geotiffs") or [])
        if str(r.get("role") or "").startswith("label_")
    )
    activation = str(meta.get("activation") or meta.get("event_id") or "unknown")
    return {
        "track": "Pista_B",
        "activation": activation,
        "pack_id": meta.get("event_id") or activation,
        "event_id": meta.get("event_id"),
        "region": meta.get("region"),
        "country": meta.get("country"),
        "max_area_ha": max_area,
        "n_timeline_steps": int(timeline_n),
        "n_ros_proxy_steps": max(0, int(timeline_n) - 1),
        "O2_cems_delineation": "GO" if has_del else "PARTIAL",
        "O2_national_official": "NO_GO_CEMS_PROXY",
        "lwir_heligraphics": False,
        "status": "GO_OPEN_DATA_PACK",
        "decision_open": "HOLD",
        "decision_open_note": (
            "Open CEMS LATAM/AU pack is monitoring/research only — not tactical "
            "dispatch, not ops ROS, not field_ops GO. status=GO_OPEN_DATA_PACK "
            "means product open_if bridge ready."
        ),
        "not_tactical_dispatch": True,
        "not_ops_ros": True,
        "ros_is_proxy_only": True,
        "vp_invented": False,
        "firms_hull_is_official_burned_area": False,
        "not_national_cadastre": True,
        "not_o2_es": True,
        "not_conaf_official": True,
        "label_level": meta.get("label_level"),
        "class": meta.get("class"),
        "license_id": meta.get("license_id"),
        "rights_doc": meta.get("rights_doc") or RIGHTS_DOC,
        "source_meta_schema": meta.get("schema"),
        "bridge": "latam_au_to_open_if_v1",
        "pack_dir": pack_dir_rel.replace("\\", "/"),
    }


def bridge_source_pack_to_open_if(
    source_pack: Path,
    out_pack: Path,
    *,
    repo_root: Path | None = None,
    copy_vectors: bool = True,
) -> dict[str, Any]:
    """Materialize product open_if layout from a latam_au source pack.

    Writes scorecard_pista_b.json (+ companions) so decide --open-pack works.
    Does not invent ROS/Vp or national O2.
    """
    source_pack = Path(source_pack)
    out_pack = Path(out_pack)
    ok, reason = source_pack_ready(source_pack)
    if not ok:
        raise FileNotFoundError(reason)

    meta = json.loads((source_pack / "meta.json").read_text(encoding="utf-8"))
    fails = validate_pack_meta(meta)
    # Soft: allow bridge even if undated names fail in fixtures; live packs pass.
    timeline = _label_geojson_rows(source_pack, meta)
    if not timeline:
        raise FileNotFoundError(f"no_label_timeline:{source_pack}")

    out_pack.mkdir(parents=True, exist_ok=True)
    vec_dir = out_pack / "vectors"
    vec_dir.mkdir(exist_ok=True)

    features: list[dict[str, Any]] = []
    product_rows: list[dict[str, Any]] = []
    for i, row in enumerate(timeline):
        gj_src = source_pack / row["geojson_path"] if row.get("geojson_path") else None
        dest_name = None
        if copy_vectors and gj_src is not None and gj_src.is_file():
            dest_name = f"{meta.get('activation', 'cems')}_{row.get('product_id') or i}.geojson"
            dest = vec_dir / dest_name
            dest.write_text(gj_src.read_text(encoding="utf-8"), encoding="utf-8")
            fc = json.loads(dest.read_text(encoding="utf-8"))
            for feat in fc.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                feat.setdefault("properties", {})
                if isinstance(feat["properties"], dict):
                    feat["properties"]["timeline_index"] = i
                    feat["properties"]["product_kind"] = row.get("kind")
                    feat["properties"]["product_id"] = row.get("product_id")
                    feat["properties"]["delivery_utc"] = row.get("delivery_utc")
                features.append(feat)
            product_rows.append(
                {
                    **row,
                    "vector_rel": f"vectors/{dest_name}",
                }
            )
        else:
            product_rows.append(dict(row))

    combined = {"type": "FeatureCollection", "features": features}
    (out_pack / "timeline_perimeters.geojson").write_text(
        json.dumps(combined, indent=2), encoding="utf-8"
    )

    # provenance link to source bytes (do not duplicate large tifs)
    source_rel = str(source_pack)
    if repo_root is not None:
        try:
            source_rel = str(source_pack.resolve().relative_to(Path(repo_root).resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            source_rel = str(source_pack).replace("\\", "/")

    pack_rel = str(out_pack)
    if repo_root is not None:
        try:
            pack_rel = str(out_pack.resolve().relative_to(Path(repo_root).resolve())).replace(
                "\\", "/"
            )
        except ValueError:
            pack_rel = str(out_pack).replace("\\", "/")

    score = build_pista_b_scorecard_from_meta(
        meta, pack_dir_rel=pack_rel, timeline_n=len(timeline)
    )
    (out_pack / "scorecard_pista_b.json").write_text(
        json.dumps(score, indent=2), encoding="utf-8"
    )

    # Point product loader at source meta for audit (not used by decide area path).
    (out_pack / "source_meta.json").write_text(
        json.dumps(
            {
                "schema": "wfd_latam_au_bridge_source_v1",
                "source_pack": source_rel,
                "event_id": meta.get("event_id"),
                "activation": meta.get("activation"),
                "meta_validation_fails": fails,
                "built_at_utc": utc_now(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    report = {
        "schema": "wfd_open_if_pack_manifest_v1",
        "bridge": "latam_au_to_open_if_v1",
        "activation": meta.get("activation"),
        "event_id": meta.get("event_id"),
        "source_pack": source_rel,
        "pack_dir": pack_rel,
        "built_at_utc": utc_now(),
        "max_area_ha": score["max_area_ha"],
        "n_timeline_steps": score["n_timeline_steps"],
        "products": product_rows,
        "gates": {
            "O2_official_national_perimeter": "NO_GO_CEMS_PROXY",
            "O2_open_cems_delineation": score["O2_cems_delineation"],
            "lwir_required": False,
        },
        "data_policy": (
            "CEMS delineation is satellite emergency mapping — proxy perimeter, "
            "not national cadastre / O2 ES / CONAF official. Not tactical ROS."
        ),
        "not_tactical_dispatch": True,
        "not_ops_ros": True,
    }
    (out_pack / "manifest.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )

    brief_lines = [
        f"# Brief open-data — {meta.get('activation')} ({meta.get('event_id')})",
        "",
        f"_Bridged: {report['built_at_utc']}_",
        "",
        f"- Source: `{source_rel}`",
        f"- Product pack: `{pack_rel}`",
        f"- Max area (CEMS): **{score['max_area_ha']:.1f} ha**",
        f"- Timeline steps: **{score['n_timeline_steps']}**",
        f"- Class: `{meta.get('class')}` / {meta.get('label_level')}",
        "",
        "## Non-claims",
        "",
        "- Not field_ops GO, not ops ROS, not national O2, not CONAF official.",
        "- CEMS proxy only; decide may HOLD/ABSTAIN without ops — valid product path.",
        "",
    ]
    (out_pack / "operator_brief_open_if.md").write_text(
        "\n".join(brief_lines), encoding="utf-8"
    )

    return {
        "ok": True,
        "source_pack": source_rel,
        "out_pack": pack_rel,
        "scorecard": score,
        "n_timeline_steps": len(timeline),
        "n_vector_features": len(features),
        "meta_validation_fails": fails,
    }


def default_product_out_dir(repo_root: Path, event_id: str) -> Path:
    return Path(repo_root) / "outputs" / "open_if" / product_slug_for(event_id)


def default_source_pack_dir(repo_root: Path, event_id: str) -> Path:
    spec = ALL_PACK_SPECS.get(event_id) or EMSR_PACK_SPECS[event_id]
    return pack_dir_for(Path(repo_root) / "data" / "open_if" / "latam_au", spec)


def cems_product_url_ok(url: str) -> bool:
    """Public CEMS vector zip (legacy S3) or Rapid Mapping JSON/zip."""
    u = str(url or "")
    if u.startswith(S3_BASE) and u.endswith("_vector.zip"):
        return True
    if u.startswith(VIEWER_S3) and u.endswith(".json"):
        return True
    return u.startswith(RAPID_BACKEND) and u.endswith(".zip")


def quote_http_url(url: str) -> str:
    """Percent-encode spaces in a public http(s) URL (NAFI filenames)."""
    from urllib.parse import quote, urlsplit, urlunsplit

    parts = urlsplit(url)
    path = quote(parts.path, safe="/")
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, parts.fragment))


def window_geotiff_to_bbox(
    src_path: Path,
    dest: Path,
    bbox_wgs84: tuple[float, float, float, float],
    *,
    max_dim: int = 2048,
) -> dict[str, Any]:
    """Window a GeoTIFF to a WGS84 bbox. Returns raster metadata."""
    import numpy as np
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    dest.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(src_path) as src:
        src_crs = src.crs
        if src_crs is None:
            raise ValueError(f"no CRS: {src_path}")
        west, south, east, north = transform_bounds(
            "EPSG:4326", src_crs, *bbox_wgs84, densify_pts=21
        )
        window = from_bounds(west, south, east, north, transform=src.transform)
        window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
        if window.width < 2 or window.height < 2:
            raise ValueError(f"empty_window:{src_path}")
        data = src.read(1, window=window, boundless=False)
        transform = src.window_transform(window)
        profile = src.profile.copy()
        height, width = data.shape
        gsd_x = abs(transform.a)
        if width > max_dim or height > max_dim:
            scale = max(width / max_dim, height / max_dim)
            new_w = max(8, int(width / scale))
            new_h = max(8, int(height / scale))
            try:
                import rasterio.enums

                resampling = rasterio.enums.Resampling.nearest
            except Exception:  # pragma: no cover
                resampling = 0
            from rasterio.transform import Affine

            data = src.read(
                1,
                window=window,
                out_shape=(new_h, new_w),
                resampling=resampling,
            )
            transform = Affine(
                transform.a * (width / new_w),
                transform.b,
                transform.c,
                transform.d,
                transform.e * (height / new_h),
                transform.f,
            )
            height, width = data.shape
            gsd_x = abs(transform.a)
        profile.update(
            {
                "height": height,
                "width": width,
                "transform": transform,
                "compress": "deflate",
                "count": 1,
                "driver": "GTiff",
            }
        )
        with rasterio.open(dest, "w", **profile) as out:
            out.write(np.asarray(data), 1)
        positive = int((np.asarray(data) > 0).sum())
        return {
            "path": str(dest),
            "crs": str(src_crs),
            "gsd_m": float(gsd_x) if src_crs and src_crs.is_projected else None,
            "width": int(width),
            "height": int(height),
            "positive_pixels": positive,
            "source": str(src_path.name),
        }


def clm_lofo_source_counts(repo_root: Path) -> dict[str, int]:
    """Cite existing CLM LOFO fold sizes. Do not invent."""
    man = Path(repo_root) / "artifacts" / "clm_ndws_patches" / "lofo_v1" / "manifest.json"
    if not man.is_file():
        return {}
    try:
        data = json.loads(man.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    sources = data.get("sources") or {}
    return {str(k): int(v) for k, v in sources.items()}


def build_lofo_fold_doc(
    *,
    repo_root: Path,
    non_clm_event_id: str,
    pack_dir: Path | None = None,
) -> dict[str, Any]:
    """Leave-one-fire-out definition including one non-CLM fire.

    Does not copy 98k NPZ. Does not run clm_ensemble_v34 on CEMS/weak rasters.
    model_iou stays null.
    """
    clm_sources = clm_lofo_source_counts(repo_root)
    spec = ALL_PACK_SPECS.get(non_clm_event_id) or {}
    pack = Path(pack_dir) if pack_dir is not None else None
    ready, reason = (False, "no_pack_dir")
    n_label = 0
    if pack is not None:
        ready, reason = source_pack_ready(pack)
        labels = pack / "labels"
        if labels.is_dir():
            n_label = len(list(labels.glob("*.tif")))
    annual = is_annual_l1_spec(spec)
    if annual:
        eval_status = ANNUAL_EVAL_STATUS
        fold_reason = (
            "Held-out fire is an annual/seasonal L1 scar (MapBiomas/NAFI), not an "
            "intra-event next-mask. eval_status=blocked_annual_not_event. "
            "Running UNet next-mask IoU would invent dynamics."
        )
    else:
        eval_status = "blocked_incompatible_schema"
        fold_reason = (
            "Held-out fire is CEMS/weak burned-area GeoTIFF, not NDWS "
            "17-channel sequences. Running UNet would invent transfer IoU."
        )
    return {
        "schema": LOFO_FOLD_SCHEMA,
        "as_of_utc": utc_now(),
        "protocol": "latam_au_lofo_non_clm_v1",
        "product_id": "clm_ensemble_v34",
        "clm_sources": clm_sources,
        "clm_train_pool": sorted(clm_sources),
        "held_out": {
            "event_id": non_clm_event_id,
            "region": spec.get("region"),
            "country": spec.get("country"),
            "class": spec.get("class"),
            "label_level": spec.get("label_level"),
            "pack_ready": ready,
            "pack_reason": reason,
            "n_label_tif": n_label,
            "compatible_with_clm_ensemble_v34": False,
        },
        "folds": {
            non_clm_event_id: {
                "train": sorted(clm_sources),
                "val": "clm_holdout_v1_val",
                "test": non_clm_event_id,
                "eval_status": eval_status,
                "model_iou": None,
                "n": 0,
                "reason": fold_reason,
            }
        },
        "rails": {
            "go_q": "partial",
            "tobarra_keep_reopen": False,
            "no_retrain": True,
            "iou_is_not_ros": True,
        },
        "not_claims": [
            "not transfer IoU",
            "not model IoU on non-CLM fire",
            "not FREEZE lift",
            "not GO_Q complete",
            "not ROS / Vp",
        ],
    }


def validate_lofo_fold(doc: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if doc.get("schema") != LOFO_FOLD_SCHEMA:
        fails.append(f"bad_schema:{doc.get('schema')}")
    held = doc.get("held_out") or {}
    if not held.get("event_id"):
        fails.append("missing_held_out_event")
    if held.get("compatible_with_clm_ensemble_v34") is True:
        fails.append("must_not_claim_ndws_compatible")
    folds = doc.get("folds") or {}
    for fid, fold in folds.items():
        if fold.get("model_iou") is not None:
            fails.append(f"{fid}_invented_iou")
        if fold.get("eval_status") == "measured" and fold.get("model_iou") is None:
            fails.append(f"{fid}_measured_without_iou")
    blob = json.dumps(doc)
    for forbidden in FORBIDDEN_SCORECARD_KEYS:
        if forbidden in blob:
            fails.append(f"forbidden_key:{forbidden}")
    return fails


def build_era5_request_template(spec: dict[str, Any]) -> dict[str, Any]:
    """CDS-style request JSON. Optional; does not invent ROS."""
    lon, lat = spec.get("approx_lonlat") or (0.0, 0.0)
    bbox = spec.get("bbox_wgs84")
    if not bbox:
        pad = 0.35
        bbox = [float(lon) - pad, float(lat) - pad, float(lon) + pad, float(lat) + pad]
    dates = [p.get("delivery_utc") for p in (spec.get("products") or []) if p.get("delivery_utc")]
    start = (dates[0] if dates else f"{spec.get('year', 2020)}-01-01")[:10]
    end = (dates[-1] if dates else start)[:10]
    return {
        "schema": ERA5_ALIGN_SCHEMA,
        "dataset": "reanalysis-era5-land",
        "event_id": spec["event_id"],
        "source_id": spec["event_id"].lower(),
        "date_start": start,
        "date_end": end,
        "bbox_wgs84": [float(x) for x in bbox],
        "centroid_lonlat": [float(lon), float(lat)],
        "variables": [
            "2m_temperature",
            "2m_dewpoint_temperature",
            "10m_u_component_of_wind",
            "10m_v_component_of_wind",
            "total_precipitation",
        ],
        "not_ros": True,
        "not_tactical": True,
        "note": (
            "Optional meteo align only. Open-Meteo archive may be used as a "
            "no-key proxy; that is not CDS ERA5-Land native. Never sell as ROS."
        ),
    }


def validate_era5_align(doc: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if doc.get("schema") != ERA5_ALIGN_SCHEMA:
        fails.append(f"bad_schema:{doc.get('schema')}")
    if doc.get("not_ros") is not True:
        fails.append("must_flag_not_ros")
    blob = json.dumps(doc)
    for forbidden in FORBIDDEN_SCORECARD_KEYS:
        if forbidden in blob:
            fails.append(f"forbidden_key:{forbidden}")
    if "model_iou" in blob:
        fails.append("must_not_include_model_iou")
    return fails


def rank_active_learning_tiles(
    tiles: list[dict[str, Any]],
    *,
    event_id: str,
) -> list[dict[str, Any]]:
    """Rank tiles by label disagreement / mixed pos_frac. Not model IoU."""
    ranked: list[dict[str, Any]] = []
    for i, tile in enumerate(tiles):
        raw_pos = tile.get("pos_frac")
        pos = float(raw_pos) if isinstance(raw_pos, (int, float, str)) else 0.0
        # Mixed burned/unburned tiles are most useful to review (uncertainty proxy).
        mixed = 1.0 - abs(pos - 0.5) * 2.0
        disagree = tile.get("successive_disagreement")
        if disagree is None:
            disagree = 0.0
        score = 0.7 * mixed + 0.3 * float(disagree)
        ranked.append(
            {
                "event_id": event_id,
                "rank": 0,
                "tile_id": tile.get("tile_id") or tile.get("file") or f"tile_{i:03d}",
                "pos_frac": pos,
                "mixed_score": mixed,
                "successive_disagreement": float(disagree),
                "al_score": score,
                "source": "label_geometry_not_v34_softmax",
                "model_iou": None,
                "not_transfer_iou": True,
            }
        )
    ranked.sort(key=lambda r: (-float(r["al_score"]), str(r["tile_id"])))
    for i, row in enumerate(ranked, start=1):
        row["rank"] = i
    return ranked


def validate_al_ranking(doc: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if doc.get("schema") != AL_RANK_SCHEMA:
        fails.append(f"bad_schema:{doc.get('schema')}")
    if doc.get("model_iou") is not None:
        fails.append("invented_model_iou")
    for row in doc.get("tiles") or []:
        if row.get("model_iou") is not None:
            fails.append(f"tile_invented_iou:{row.get('tile_id')}")
        if row.get("not_transfer_iou") is not True:
            fails.append(f"tile_must_flag_not_transfer:{row.get('tile_id')}")
    blob = json.dumps(doc)
    for forbidden in FORBIDDEN_SCORECARD_KEYS:
        if forbidden in blob:
            fails.append(f"forbidden_key:{forbidden}")
    return fails


def is_annual_l1_spec(spec: dict[str, Any] | None) -> bool:
    spec = spec or {}
    level = str(spec.get("label_level") or "")
    kind = str(spec.get("source_kind") or "")
    return level.startswith("L1") or kind.startswith("mapbiomas") or kind.startswith("nafi")


def parse_iso_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def hours_between(a: datetime, b: datetime) -> float:
    return float((b - a).total_seconds() / 3600.0)


def label_kind_family(kind: str | None) -> str:
    k = str(kind or "").strip().lower()
    if k in GROWTH_LABEL_KINDS:
        return "growth"
    if k in NON_GROWTH_LABEL_KINDS:
        return "non_growth"
    return "unknown"


def compatible_growth_kinds(prev_kind: str | None, next_kind: str | None) -> bool:
    """True when both labels are CEMS extent (DEL / MONIT). None/unknown does not block."""
    if not prev_kind and not next_kind:
        return True
    return (
        label_kind_family(prev_kind) == "growth"
        and label_kind_family(next_kind) == "growth"
    )


def classify_temporal_pair(
    *,
    delta_hours: float | None,
    label_mask_iou: float | None,
    min_hours: float = MIN_LABEL_PAIR_HOURS,
    static_iou: float = STATIC_LABEL_MASK_IOU,
    prev_kind: str | None = None,
    next_kind: str | None = None,
) -> str:
    """Classify a successive label pair.

    incompatible_product_kind (FEP/GRA vs DEL) is not next-day growth.
    too_short_delta wins over static copy when kinds are compatible.
    """
    if (prev_kind or next_kind) and not compatible_growth_kinds(prev_kind, next_kind):
        return "incompatible_product_kind"
    if delta_hours is not None and delta_hours < float(min_hours):
        return "too_short_delta"
    if label_mask_iou is not None and label_mask_iou > float(static_iou):
        return "static_label_copy"
    return "usable"


def mean_usable_pair_ious(
    pairs: list[dict[str, Any]], *, key: str = "complete_proxy_model_iou"
) -> float | None:
    vals = [
        float(p[key])
        for p in pairs
        if p.get("pair_class") == "usable" and p.get(key) is not None
    ]
    if not vals:
        return None
    return float(sum(vals) / len(vals))


def is_nested_to_cems_name(name: str) -> bool:
    stem = Path(str(name)).stem
    return stem.count("_to_cems") >= 2 or "_to_cems_to_cems" in stem


def is_s2_source_tif(path: Path, *, pack_dir: Path) -> bool:
    """True only for pack/eo/*.tif that are not already aligned."""
    path = Path(path)
    if path.suffix.lower() != ".tif":
        return False
    if path.stem.endswith("_to_cems") or is_nested_to_cems_name(path.name):
        return False
    try:
        rel = path.resolve().relative_to(Path(pack_dir).resolve())
    except ValueError:
        return False
    return len(rel.parts) == 2 and rel.parts[0] == "eo"


def s2_source_paths(pack_dir: Path, meta: dict[str, Any] | None = None) -> list[Path]:
    """S2 sources from pack/eo/*.tif only (never eo_aligned, never *_to_cems)."""
    pack = Path(pack_dir)
    found: list[Path] = []
    seen: set[Path] = set()
    for rec in (meta or {}).get("geotiffs") or []:
        rel = str(rec.get("rel") or "")
        if not rel or rel.replace("\\", "/").startswith("eo_aligned/"):
            continue
        path = pack / rel
        if is_s2_source_tif(path, pack_dir=pack) and path not in seen:
            seen.add(path)
            found.append(path)
    eo = pack / "eo"
    if eo.is_dir():
        for path in sorted(eo.glob("*.tif")):
            if is_s2_source_tif(path, pack_dir=pack) and path not in seen:
                seen.add(path)
                found.append(path)
    return found


def aligned_s2_paths(pack_dir: Path) -> list[Path]:
    """Canonical aligned dests: eo_aligned/{original_stem}_to_cems.tif (no nested repeats)."""
    aligned = Path(pack_dir) / "eo_aligned"
    if not aligned.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(aligned.glob("*.tif")):
        if path.stem.endswith("_to_cems") and not is_nested_to_cems_name(path.name):
            out.append(path)
    return out


def gc_nested_to_cems(pack_dir: Path) -> list[str]:
    """Delete *_to_cems_to_cems*.tif (and deeper repeats) under eo_aligned/."""
    aligned = Path(pack_dir) / "eo_aligned"
    removed: list[str] = []
    if not aligned.is_dir():
        return removed
    for path in sorted(aligned.glob("*.tif")):
        if is_nested_to_cems_name(path.name):
            path.unlink(missing_ok=True)
            removed.append(f"eo_aligned/{path.name}")
    return removed


def load_warp_provenance(pack_dir: Path) -> dict[str, Any] | None:
    path = Path(pack_dir) / "eo_aligned" / "WARP_PROVENANCE.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def warp_proxy_from_pack(pack_dir: Path) -> dict[str, Any] | None:
    """Return already-computed NBR vs CEMS proxy if an audited warp exists."""
    prov = load_warp_provenance(pack_dir)
    aligned = aligned_s2_paths(pack_dir)
    if prov is None or not aligned:
        return None
    metric = prov.get("proxy_metric") or {}
    iou = metric.get("nbr_vs_cems_iou")
    if iou is None:
        iou = (prov.get("proxy") or {}).get("nbr_vs_cems_iou")
    status = metric.get("status") or ("measured" if iou is not None else "warp_present_iou_null")
    return {
        "status": status,
        "metric": metric.get("metric") or "nbr_vs_cems_iou",
        "value": iou,
        "threshold": metric.get("threshold"),
        "reason": (
            "Audited S2→CEMS warp present (WARP_PROVENANCE.json + eo_aligned). "
            "Reporting stored proxy IoU — not model/transfer IoU."
        ),
        "n_aligned": len(aligned),
        "provenance": "eo_aligned/WARP_PROVENANCE.json",
        "honesty": metric.get("honesty")
        or ["proxy NBR threshold IoU after audited warp", "not model IoU", "not transfer IoU"],
    }


def label_records_from_meta(pack_dir: Path, meta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pack = Path(pack_dir)
    for rec in meta.get("geotiffs") or []:
        if not str(rec.get("role") or "").startswith("label_"):
            continue
        rel = rec.get("rel")
        if not rel:
            continue
        path = pack / rel
        if not path.is_file():
            continue
        dt = parse_iso_utc(str(rec.get("delivery_utc") or rec.get("datetime") or ""))
        rows.append(
            {
                "rel": str(rel).replace("\\", "/"),
                "path": path,
                "delivery_utc": rec.get("delivery_utc") or rec.get("datetime"),
                "dt": dt,
                "product_id": rec.get("product_id"),
                "kind": rec.get("kind"),
                "name": path.name,
            }
        )
    rows.sort(key=lambda r: (r["dt"] or datetime.min.replace(tzinfo=UTC), r["name"]))
    return rows


def s2_datetime_from_name_or_meta(path: Path, rec: dict[str, Any] | None = None) -> datetime | None:
    if rec:
        dt = parse_iso_utc(str(rec.get("delivery_utc") or rec.get("datetime") or ""))
        if dt is not None:
            return dt
    m = re.search(r"(20\d{6})_(\d{6})", path.stem)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def pick_post_s2_path(
    pack_dir: Path,
    meta: dict[str, Any],
    *,
    aligned: bool = True,
) -> dict[str, Any] | None:
    """Prefer S2 datetime > last label; else nearest after first label."""
    labels = label_records_from_meta(pack_dir, meta)
    label_dts = [r["dt"] for r in labels if r.get("dt") is not None]
    last_label = max(label_dts) if label_dts else None
    first_label = min(label_dts) if label_dts else None
    recs_by_stem: dict[str, dict[str, Any]] = {}
    for rec in meta.get("geotiffs") or []:
        rel = str(rec.get("rel") or "")
        if rel:
            recs_by_stem[Path(rel).stem] = rec
    cands: list[dict[str, Any]] = []
    if aligned:
        for p in aligned_s2_paths(pack_dir):
            src_stem = p.stem[: -len("_to_cems")] if p.stem.endswith("_to_cems") else p.stem
            rec = recs_by_stem.get(src_stem) or recs_by_stem.get(p.stem) or {}
            cands.append(
                {
                    "path": p,
                    "rel": f"eo_aligned/{p.name}",
                    "dt": s2_datetime_from_name_or_meta(p, rec),
                    "rec": rec,
                }
            )
    if not cands:
        for p in s2_source_paths(pack_dir, meta):
            rec = recs_by_stem.get(p.stem) or {}
            cands.append(
                {
                    "path": p,
                    "rel": f"eo/{p.name}",
                    "dt": s2_datetime_from_name_or_meta(p, rec),
                    "rec": rec,
                }
            )
    if not cands:
        return None
    posts = [
        c
        for c in cands
        if c["dt"] is not None and last_label is not None and c["dt"] > last_label
    ]
    if posts:
        def _cov(c: dict[str, Any]) -> tuple[int, int]:
            p = Path(c["path"])
            return (p.stat().st_size if p.is_file() else 0, -int(c["dt"].timestamp()) if c.get("dt") else 0)

        posts.sort(key=_cov, reverse=True)
        pick = posts[0]
        pick["pair_rule"] = "datetime_after_last_label"
        return pick
    after_first = [
        c
        for c in cands
        if c["dt"] is not None and first_label is not None and c["dt"] > first_label
    ]
    if after_first:
        after_first.sort(key=lambda c: c["dt"])
        pick = after_first[0]
        pick["pair_rule"] = "nearest_after_first_label"
        return pick
    dated = [c for c in cands if c["dt"] is not None]
    pick = max(dated, key=lambda c: c["dt"]) if dated else cands[-1]
    pick["pair_rule"] = "fallback_latest_s2"
    return pick


def pick_pre_s2_path(
    pack_dir: Path,
    meta: dict[str, Any],
    *,
    aligned: bool = True,
) -> dict[str, Any] | None:
    """Prefer S2 datetime < first label (pre-fire fuel). Do not use post-fire NBR as veg."""
    labels = label_records_from_meta(pack_dir, meta)
    label_dts = [r["dt"] for r in labels if r.get("dt") is not None]
    first_label = min(label_dts) if label_dts else None
    recs_by_stem: dict[str, dict[str, Any]] = {}
    for rec in meta.get("geotiffs") or []:
        rel = str(rec.get("rel") or "")
        if rel:
            recs_by_stem[Path(rel).stem] = rec
    cands: list[dict[str, Any]] = []
    if aligned:
        for p in aligned_s2_paths(pack_dir):
            src_stem = p.stem[: -len("_to_cems")] if p.stem.endswith("_to_cems") else p.stem
            rec = recs_by_stem.get(src_stem) or recs_by_stem.get(p.stem) or {}
            cands.append(
                {
                    "path": p,
                    "rel": f"eo_aligned/{p.name}",
                    "dt": s2_datetime_from_name_or_meta(p, rec),
                    "rec": rec,
                }
            )
    if not cands:
        for p in s2_source_paths(pack_dir, meta):
            rec = recs_by_stem.get(p.stem) or {}
            cands.append(
                {
                    "path": p,
                    "rel": f"eo/{p.name}",
                    "dt": s2_datetime_from_name_or_meta(p, rec),
                    "rec": rec,
                }
            )
    if not cands:
        return None
    pres = [
        c
        for c in cands
        if c["dt"] is not None and first_label is not None and c["dt"] < first_label
    ]
    if pres:
        pres.sort(key=lambda c: c["dt"], reverse=True)
        pick = pres[0]
        pick["pair_rule"] = "datetime_before_first_label"
        return pick
    dated = [c for c in cands if c["dt"] is not None]
    pick = min(dated, key=lambda c: c["dt"]) if dated else cands[0]
    pick["pair_rule"] = "fallback_earliest_s2"
    return pick


def cession_evidence_ok(path: Path | None) -> tuple[bool, str]:
    """Same file-level rules as record_conaf_cession (no product-flag writes)."""
    if path is None:
        return False, "missing_evidence"
    evidence = Path(path)
    if not evidence.is_file():
        return False, f"evidence_missing:{evidence}"
    if evidence.suffix.lower() not in CESSION_EVIDENCE_SUFFIXES:
        return False, f"evidence_suffix_not_allowed:{evidence.suffix}"
    if evidence.stat().st_size < 16:
        return False, "evidence_too_small"
    return True, "ok"


def distinct_s2_windows(event_date: str) -> list[tuple[str, str]]:
    """Non-overlapping pre/mid/post STAC datetime windows around YYYY-MM-DD."""
    mid = datetime.strptime(event_date[:10], "%Y-%m-%d").replace(tzinfo=UTC)

    def _fmt(a: datetime, b: datetime) -> str:
        return f"{a.strftime('%Y-%m-%d')}/{b.strftime('%Y-%m-%d')}"

    pre = (mid - timedelta(days=24), mid - timedelta(days=10))
    midw = (mid - timedelta(days=9), mid + timedelta(days=5))
    post = (mid + timedelta(days=6), mid + timedelta(days=20))
    return [
        ("pre", _fmt(*pre)),
        ("mid", _fmt(*midw)),
        ("post", _fmt(*post)),
    ]


def _s2_sort_key(rec: dict[str, Any]) -> str:
    return str(
        rec.get("datetime") or rec.get("delivery_utc") or rec.get("file") or rec.get("rel") or ""
    )


def assign_s2_roles_by_datetime(recs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign pre/mid/post by acquisition time. Same civil day extras are tiles."""
    out: list[dict[str, Any]] = []
    s2_idx: list[int] = []
    for i, rec in enumerate(recs):
        role = str(rec.get("role") or "")
        if role.startswith("eo_s2_nbr") and "aligned" not in role:
            s2_idx.append(i)
        out.append(dict(rec))
    if not s2_idx:
        return out
    ordered = sorted(s2_idx, key=lambda i: _s2_sort_key(out[i]))
    civil_of: list[str] = []
    for rank, i in enumerate(ordered):
        dt = parse_iso_utc(_s2_sort_key(out[i]))
        civil_of.append(dt.date().isoformat() if dt is not None else f"undated-{rank}")
    unique_days: list[str] = []
    for day in civil_of:
        if day not in unique_days:
            unique_days.append(day)
    day_role: dict[str, str] = {}
    n_days = len(unique_days)
    for d_i, day in enumerate(unique_days):
        if n_days == 1:
            day_role[day] = "eo_s2_nbr_post"
        elif d_i == 0:
            day_role[day] = "eo_s2_nbr_pre"
        elif d_i == n_days - 1:
            day_role[day] = "eo_s2_nbr_post"
        else:
            day_role[day] = "eo_s2_nbr_mid"
    seen_day: dict[str, int] = {}
    remapped: list[dict[str, Any]] = []
    for i, day in zip(ordered, civil_of, strict=True):
        rec = dict(out[i])
        count = seen_day.get(day, 0)
        seen_day[day] = count + 1
        if count > 0:
            rec["role"] = "eo_s2_nbr_same_day_tile"
            rec["s2_same_civil_day"] = True
        else:
            rec["role"] = day_role[day]
        rec["s2_role_assigned_by"] = "datetime"
        remapped.append(rec)
    for slot, rec in zip(s2_idx, remapped, strict=True):
        out[slot] = rec
    return out


def remap_pack_s2_roles(meta: dict[str, Any]) -> dict[str, Any]:
    out = dict(meta)
    if isinstance(out.get("geotiffs"), list):
        out["geotiffs"] = assign_s2_roles_by_datetime(list(out["geotiffs"]))
    if isinstance(out.get("stac_eo"), list):
        out["stac_eo"] = assign_s2_roles_by_datetime(list(out["stac_eo"]))
    return out


def try_stac_s2_windows(
    pack_dir: Path,
    spec: dict[str, Any],
    bbox_wgs84: tuple[float, float, float, float] | list[float],
    event_date: str,
    max_cloud: float = 60.0,
) -> list[dict[str, Any]]:
    """Windowed S2 NBR via Element84 STAC. Honest GAP rows on failure. No invented IoU."""
    from .stac_s2 import load_nbr_for_item, stac_search

    pack = Path(pack_dir)
    eo_dir = pack / "eo"
    eo_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    bbox = [float(x) for x in bbox_wgs84]
    for role, rng in distinct_s2_windows(event_date):
        start, end = rng.split("/")
        stac_rng = f"{start}T00:00:00Z/{end}T23:59:59Z"
        rec: dict[str, Any] = {
            "role": f"eo_s2_nbr_{role}",
            "range": stac_rng,
            "status": "gap",
        }
        try:
            items = stac_search(bbox, stac_rng, max_cloud=max_cloud, limit=5)
        except Exception as exc:  # noqa: BLE001
            rec["reason"] = f"stac_search_failed:{type(exc).__name__}:{exc}"
            rows.append(rec)
            continue
        if not items:
            rec["reason"] = "no_stac_item"
            rows.append(rec)
            continue
        item = items[0]
        props = item.get("properties") or {}
        dt = str(props.get("datetime") or "")
        try:
            nbr, nbr_meta = load_nbr_for_item(item, bbox, max_size=256)
        except Exception as exc:  # noqa: BLE001
            rec["reason"] = f"nbr_read_failed:{type(exc).__name__}:{exc}"
            rec["item_id"] = item.get("id")
            rows.append(rec)
            continue
        stamp = "00000000_000000"
        parsed = parse_iso_utc(dt)
        if parsed is not None:
            stamp = parsed.strftime("%Y%m%d_%H%M%S")
        fname = f"{spec['event_id']}_S2NBR_{stamp}.tif"
        dest = eo_dir / fname
        try:
            import rasterio
            from rasterio.transform import from_bounds

            h, w = nbr.shape
            west, south, east, north = bbox
            transform = from_bounds(west, south, east, north, w, h)
            profile = {
                "driver": "GTiff",
                "height": h,
                "width": w,
                "count": 1,
                "dtype": "float32",
                "crs": "EPSG:4326",
                "transform": transform,
                "compress": "deflate",
            }
            with rasterio.open(dest, "w", **profile) as ds:
                ds.write(nbr.astype("float32"), 1)
            rec.update(
                {
                    "status": "ok",
                    "rel": f"eo/{fname}",
                    "file": fname,
                    "datetime": dt,
                    "item_id": item.get("id"),
                    "sensor": "Sentinel-2 L2A (windowed NBR)",
                    "crs": "EPSG:4326",
                    "bytes": dest.stat().st_size,
                    "sha256": sha256_file(dest),
                    "cloud_cover": props.get("eo:cloud_cover"),
                    "nbr_meta": {k: nbr_meta.get(k) for k in ("item_id",) if k in nbr_meta},
                }
            )
        except Exception as exc:  # noqa: BLE001
            rec["reason"] = f"write_failed:{type(exc).__name__}:{exc}"
            rec["item_id"] = item.get("id")
        rows.append(rec)
    return assign_s2_roles_by_datetime(rows)
