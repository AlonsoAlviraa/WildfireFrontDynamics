from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine, from_origin

from wildfire_front.cli import main, run_geotiff_ingest
from wildfire_front.ingestion.geotiff import (
    extract_mask_components,
    ingest_geotiff_sequence,
    segment_band_threshold,
)


def write_tiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: str | None = "EPSG:32630",
    transform: Affine | None = None,
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
    return images, masks


class GeoTiffIngestionTests(unittest.TestCase):
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
            self.assertEqual(2, len(result.observations))
            self.assertTrue(all(record.status == "accepted" for record in result.records))
            first = result.observations[0]
            self.assertEqual("EPSG:32630", first.crs)
            self.assertEqual("projected_metric", first.coordinate_system)
            self.assertEqual(10.0, first.resolution_m)
            self.assertEqual(0.0, first.time_s)
            self.assertEqual(60.0, result.observations[1].time_s)
            xs = [point[0] for point in first.components[0]]
            ys = [point[1] for point in first.components[0]]
            self.assertIn(500030.0, xs)
            self.assertIn(4099980.0, ys)

    def test_threshold_baseline_is_deterministic(self) -> None:
        image = np.array([[0, 10], [11, 10]], dtype=np.uint16)
        expected = np.array([[0, 0], [1, 0]], dtype=np.uint8)
        np.testing.assert_array_equal(expected, segment_band_threshold(image, 10))

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
            self.assertEqual(1, len(result.observations))
            self.assertEqual("band_2_threshold_350", result.observations[0].method)

    def test_extract_mask_preserves_multiple_components(self) -> None:
        mask = np.zeros((8, 8), dtype=np.uint8)
        mask[1:3, 1:3] = 1
        mask[5:7, 5:7] = 1
        components = extract_mask_components(mask, from_origin(0, 80, 10, 10))
        self.assertEqual(2, len(components))

    def test_invalid_inputs_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images = root / "images"
            masks = root / "masks"
            images.mkdir()
            masks.mkdir()

            base = np.ones((8, 8), dtype=np.uint16)
            write_tiff(images / "no_crs_20260610_120000.tif", base, crs=None, transform=Affine.identity())
            write_tiff(masks / "no_crs_20260610_120000.tif", np.ones((8, 8), dtype=np.uint8), crs=None, transform=Affine.identity())

            write_tiff(images / "mismatch_20260610_120100.tif", base)
            write_tiff(masks / "mismatch_20260610_120100.tif", np.ones((7, 7), dtype=np.uint8))

            write_tiff(images / "empty_20260610_120200.tif", base)
            write_tiff(masks / "empty_20260610_120200.tif", np.zeros((8, 8), dtype=np.uint8))

            result = ingest_geotiff_sequence(
                images,
                masks_dir=masks,
                event_id="invalid",
                sensor_id="thermal",
                estimated_error_m=1.0,
            )
            reasons = {record.reason for record in result.records}
            self.assertIn("missing_crs_or_transform", reasons)
            self.assertIn("mask_dimensions_mismatch", reasons)
            self.assertIn("empty_mask", reasons)
            self.assertEqual(0, len(result.observations))

    def test_cli_flow_generates_complete_real_artifacts_and_abstains(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            images, masks = make_valid_sequence(root)
            output = root / "output"
            metrics = run_geotiff_ingest(
                images,
                masks,
                output,
                "burn_1",
                "thermal_1",
                2.0,
                1,
                None,
            )
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
            self.assertEqual(expected, {path.name for path in output.iterdir()})
            self.assertEqual("abstained", metrics["speed_status"])
            self.assertNotIn("speed_mae_m_min", metrics)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertIsNone(summary["config"])
            with (output / "local_speeds.csv").open(encoding="utf-8") as handle:
                self.assertEqual(1, sum(1 for _ in handle))
            with (output / "ingest_manifest.csv").open(encoding="utf-8") as handle:
                self.assertEqual(2, len(list(csv.DictReader(handle))))

    def test_cli_returns_nonzero_for_invalid_input(self) -> None:
        with self.assertRaises(SystemExit) as raised:
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
        self.assertEqual(2, raised.exception.code)


if __name__ == "__main__":
    unittest.main()
