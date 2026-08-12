from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine, from_origin

from wildfire_front.cli import main, run_geotiff_ingest
from wildfire_front.ingestion.geotiff import (
    extract_mask_components,
    infer_timestamp,
    ingest_geotiff_sequence,
    segment_band_mad,
    segment_band_threshold,
)


def write_tiff(
    path: Path, data: np.ndarray, *, crs: str | None = "EPSG:32630", transform: Affine | None = None
) -> None:
    array = data if data.ndim == 3 else data[np.newaxis, ...]
    transform = transform or from_origin(500000.0, 4100000.0, 10.0, 10.0)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[2],
        height=array.shape[1],
        count=array.shape[0],
        dtype=array.dtype,
        crs=crs,
        transform=transform,
    ) as dataset:
        dataset.write(array)


def make_valid_sequence(root: Path) -> tuple[Path, Path]:
    images = root / "images"
    masks = root / "masks"
    images.mkdir()
    masks.mkdir()
    for timestamp, size in (("20260610_120000", 3), ("20260610_120100", 4)):
        image = np.zeros((2, 12, 12), dtype=np.uint16)
        image[0, 2 : 2 + size, 3 : 3 + size] = 1200
        mask = np.zeros((12, 12), dtype=np.uint8)
        mask[2 : 2 + size, 3 : 3 + size] = 1
        write_tiff(images / f"burn_{timestamp}.tif", image)
        write_tiff(masks / f"burn_{timestamp}.tif", mask)
    return (images, masks)


class GeoTiffIngestionTests:
    def test_valid_projected_sequence_produces_metric_observations(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            images, masks = make_valid_sequence(Path(temp))
            result = ingest_geotiff_sequence(
                images,
                masks_dir=masks,
                event_id="burn_1",
                sensor_id="thermal_1",
                estimated_error_m=2.0,
            )
            assert len(result.observations) == 2
            assert all(record.status == "accepted" for record in result.records)
            first = result.observations[0]
            assert first.crs == "EPSG:32630"
            assert first.coordinate_system == "projected_metric"
            assert first.resolution_m == 10.0
            assert first.time_s == 0.0
            assert result.observations[1].time_s == 60.0
            xs = [point[0] for point in first.components[0]]
            ys = [point[1] for point in first.components[0]]
            assert 500030.0 in xs
            assert 4099980.0 in ys

    def test_threshold_baseline_is_deterministic(self) -> None:
        image = np.array([[0, 10], [11, 10]], dtype=np.uint16)
        expected = np.array([[0, 0], [1, 0]], dtype=np.uint8)
        np.testing.assert_array_equal(expected, segment_band_threshold(image, 10))

    def test_threshold_can_respect_alpha_mask(self) -> None:
        image = np.array([[255, 255], [0, 255]], dtype=np.uint8)
        valid = np.array([[True, False], [True, True]])
        expected = np.array([[1, 0], [0, 1]], dtype=np.uint8)
        np.testing.assert_array_equal(expected, segment_band_threshold(image, 200, valid))

    def test_mad_baseline_detects_radiometric_outlier(self) -> None:
        image = np.full((10, 10), 100, dtype=np.uint16)
        image[5, 5] = 1000
        mask, threshold = segment_band_mad(image, z_score=6.0)
        assert int(mask.sum()) == 1
        assert threshold >= 100

    def test_mad_baseline_ignores_invalid_alpha_pixels(self) -> None:
        image = np.full((10, 10), 100, dtype=np.uint16)
        image[0, 0] = 1000
        valid = np.ones((10, 10), dtype=bool)
        valid[0, 0] = False
        mask, _ = segment_band_mad(image, z_score=6.0, valid_mask=valid)
        assert int(mask.sum()) == 0

    def test_infers_millisecond_timestamp_from_real_sensor_name(self) -> None:
        observed_at = infer_timestamp(Path("2024-08-02_16-08-21-553_LWIR.tif"))
        assert observed_at == "2024-08-02T16:08:21.553000Z"

    def test_sequence_can_use_threshold_without_masks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            images.mkdir()
            image = np.zeros((2, 8, 8), dtype=np.uint16)
            image[1, 2:6, 2:6] = 500
            write_tiff(images / "threshold_20260610_120000.tif", image)
            result = ingest_geotiff_sequence(
                images,
                masks_dir=None,
                event_id="threshold",
                sensor_id="thermal",
                estimated_error_m=2.0,
                band=2,
                threshold=350,
            )
            assert len(result.observations) == 1
            assert result.observations[0].method == "band_2_threshold_350"

    def test_sequence_threshold_can_ignore_transparent_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            images.mkdir()
            rgba = np.zeros((4, 8, 8), dtype=np.uint8)
            rgba[0, :, :] = 255
            rgba[3, :, :] = 0
            rgba[3, 2:6, 2:6] = 255
            write_tiff(images / "rgba_20260610_120000.tif", rgba)
            unmasked = ingest_geotiff_sequence(
                images,
                masks_dir=None,
                event_id="rgba",
                sensor_id="thermal",
                estimated_error_m=2.0,
                band=1,
                threshold=200,
            )
            masked = ingest_geotiff_sequence(
                images,
                masks_dir=None,
                event_id="rgba",
                sensor_id="thermal",
                estimated_error_m=2.0,
                band=1,
                threshold=200,
                respect_alpha=True,
            )
            assert unmasked.records[0].positive_pixel_fraction == 1.0
            assert masked.records[0].positive_pixel_fraction == 0.25

    def test_sequence_can_sieve_small_threshold_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            images.mkdir()
            image = np.zeros((8, 8), dtype=np.uint8)
            image[1, 1] = 255
            image[3:6, 3:6] = 255
            write_tiff(images / "speckled_20260610_120000.tif", image)
            result = ingest_geotiff_sequence(
                images,
                masks_dir=None,
                event_id="speckled",
                sensor_id="thermal",
                estimated_error_m=2.0,
                band=1,
                threshold=200,
                min_component_pixels=4,
            )
            assert len(result.observations) == 1
            assert result.records[0].component_count == 1
            assert pytest.approx(result.records[0].positive_pixel_fraction) == 9 / 64

    def test_extract_mask_preserves_multiple_components(self) -> None:
        mask = np.zeros((8, 8), dtype=np.uint8)
        mask[1:3, 1:3] = 1
        mask[5:7, 5:7] = 1
        components = extract_mask_components(mask, from_origin(0, 80, 10, 10))
        assert len(components) == 2

    def test_invalid_inputs_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            masks = root / "masks"
            images.mkdir()
            masks.mkdir()
            base = np.ones((8, 8), dtype=np.uint16)
            write_tiff(
                images / "no_crs_20260610_120000.tif", base, crs=None, transform=Affine.identity()
            )
            write_tiff(
                masks / "no_crs_20260610_120000.tif",
                np.ones((8, 8), dtype=np.uint8),
                crs=None,
                transform=Affine.identity(),
            )
            write_tiff(images / "mismatch_20260610_120100.tif", base * 2)
            write_tiff(masks / "mismatch_20260610_120100.tif", np.ones((7, 7), dtype=np.uint8))
            write_tiff(images / "empty_20260610_120200.tif", base * 3)
            write_tiff(masks / "empty_20260610_120200.tif", np.zeros((8, 8), dtype=np.uint8))
            result = ingest_geotiff_sequence(
                images,
                masks_dir=masks,
                event_id="invalid",
                sensor_id="thermal",
                estimated_error_m=1.0,
            )
            reasons = {record.reason for record in result.records}
            assert "missing_crs_or_transform" in reasons
            assert "mask_dimensions_mismatch" in reasons
            assert "empty_mask" in reasons
            assert len(result.observations) == 0

    def test_duplicate_sources_timestamps_and_resolution_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            images.mkdir()
            base = np.zeros((8, 8), dtype=np.uint16)
            base[2:5, 2:5] = 100
            write_tiff(images / "a_20260610_120000.tif", base)
            write_tiff(images / "duplicate_hash_20260610_120100.tif", base)
            write_tiff(images / "duplicate_time_20260610_120000.tif", base * 2)
            write_tiff(
                images / "resolution_20260610_120200.tif",
                base * 3,
                transform=from_origin(500000, 4100000, 20, 20),
            )
            result = ingest_geotiff_sequence(
                images,
                masks_dir=None,
                event_id="qa",
                sensor_id="thermal",
                estimated_error_m=1.0,
                threshold=50,
            )
            reasons = {record.reason for record in result.records}
            assert "duplicate_source_sha256" in reasons
            assert "duplicate_timestamp" in reasons
            assert "sequence_resolution_mismatch" in reasons
            assert len(result.observations) == 1

    def test_invalid_input_does_not_define_sequence_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            masks = root / "masks"
            images.mkdir()
            masks.mkdir()
            base = np.zeros((8, 8), dtype=np.uint16)
            base[2:5, 2:5] = 100
            write_tiff(
                images / "a_invalid_20260610_120000.tif",
                base,
                transform=from_origin(500000, 4100000, 20, 20),
            )
            write_tiff(
                masks / "a_invalid_20260610_120000.tif",
                np.zeros((8, 8), dtype=np.uint8),
                transform=from_origin(500000, 4100000, 20, 20),
            )
            write_tiff(images / "b_valid_20260610_120000.tif", base * 2)
            write_tiff(masks / "b_valid_20260610_120000.tif", (base > 0).astype(np.uint8))
            result = ingest_geotiff_sequence(
                images, masks_dir=masks, event_id="qa", sensor_id="thermal", estimated_error_m=1.0
            )
            assert len(result.observations) == 1
            assert result.observations[0].resolution_m == 10.0
            assert "empty_mask" in {record.reason for record in result.records}

    def test_cli_flow_generates_complete_real_artifacts_and_speed_quality(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, masks = make_valid_sequence(root)
            output = root / "output"
            metrics = run_geotiff_ingest(images, masks, output, "burn_1", "thermal_1", 2.0, 1, None)
            expected = {
                "arrival_time.csv",
                "fronts.geojson",
                "fronts.svg",
                "ingest_manifest.csv",
                "local_speeds.csv",
                "observations_manifest.csv",
                "report.html",
                "summary.json",
            }
            assert expected == {path.name for path in output.iterdir()}
            assert metrics["speed_status"] in {"estimated", "abstained"}
            assert "speed_mae_m_min" not in metrics
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            assert summary["config"] is None
            with (output / "local_speeds.csv").open(encoding="utf-8") as handle:
                assert sum(1 for _ in handle) > 1
            with (output / "ingest_manifest.csv").open(encoding="utf-8") as handle:
                assert len(list(csv.DictReader(handle))) == 2

    def test_cli_returns_nonzero_for_invalid_input(self) -> None:
        with pytest.raises(SystemExit) as raised:
            main(
                [
                    "ingest-geotiff",
                    "--images",
                    "missing",
                    "--sensor-id",
                    "thermal",
                    "--estimated-error-m",
                    "1",
                    "--threshold",
                    "100",
                ]
            )
        assert raised.value.code == 2
