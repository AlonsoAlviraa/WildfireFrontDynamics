"""Input adapters for observed wildfire geometry."""

from .geotiff import GeoTiffIngestRecord, GeoTiffIngestResult, ingest_geotiff_sequence

__all__ = ["GeoTiffIngestRecord", "GeoTiffIngestResult", "ingest_geotiff_sequence"]

