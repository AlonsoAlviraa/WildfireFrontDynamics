"""Optional Earth Engine backend — same chip contract as satellites.py.

Enable on GCP after registering Earth Engine. Not required for the local
GIBS demo.

Collections that make the video look like a Google Cloud entry:

- ``FIRMS`` / VIIRS FIRMS
- ``NOAA/GOES/19/FDCF`` fire / hot-spot characterization (Atlantic disk)
- ``COPERNICUS/S2_SR_HARMONIZED`` 10 m true color + SWIR
- ``projects/gcp-public-data-weathernext/assets/weathernext_2_0_0``
  (form: https://developers.google.com/weathernext/guides/earth-engine)

WeatherNext wind/RH become a *cited* weather cell. They are not ROS.
"""

from __future__ import annotations

from typing import Any

EE_COLLECTIONS = {
    "firms": "FIRMS",
    "goes19_fdc": "NOAA/GOES/19/FDCF",
    "sentinel2": "COPERNICUS/S2_SR_HARMONIZED",
    "weathernext2": "projects/gcp-public-data-weathernext/assets/weathernext_2_0_0",
}


def available() -> bool:
    try:
        import ee  # type: ignore

        return hasattr(ee, "ImageCollection")
    except ImportError:
        return False


def init_project() -> dict[str, Any]:
    """Bind Earth Engine to the Relator GCP project. No generative models."""
    from .gcp import PROJECT_ID

    if not PROJECT_ID:
        return {
            "ok": False,
            "error": "GOOGLE_CLOUD_PROJECT is not configured",
            "project_id": None,
            "llm": False,
        }
    if not available():
        return {"ok": False, "error": "earthengine-api not installed", "project_id": PROJECT_ID, "llm": False}
    import ee  # type: ignore

    ee.Initialize(project=PROJECT_ID)
    return {"ok": True, "project_id": PROJECT_ID, "engine": "earthengine", "llm": False}
