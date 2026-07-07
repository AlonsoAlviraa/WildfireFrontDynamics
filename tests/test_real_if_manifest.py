from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from scripts.prepare_real_if_geotiffs import prepare_sequence
from wildfire_front.real_if import (
    FrameManifestRow,
    assess_frame_quality,
    build_frame_manifest,
    compute_temporal_gaps,
    find_duplicate_timestamps,
    write_frame_manifest,
    write_manifest_summary,
)
from wildfire_front.visual_qa import render_contact_sheet, render_frame_thumbnail


def _write_projected_tiff(
    path: Path,
    data: np.ndarray,
    *,
    crs: str = "EPSG:32630",
    transform=None,
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


def _write_lonlat_tiff(path: Path) -> None:
    data = np.zeros((4, 10, 10), dtype=np.uint8)
    data[0, 2:6, 2:6] = 255
    data[3, 2:6, 2:6] = 255
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=4,
        dtype=data.dtype,
        crs="EPSG:4326",
        transform=from_origin(-1.71, 38.64, 0.00001, 0.00001),
    ) as dataset:
        dataset.write(data)


def _make_row(
    timestamp: str = "2024-08-02T16:08:21Z",
    sensor: str = "LWIR",
    qa_status: str = "ok",
) -> FrameManifestRow:
    return FrameManifestRow(
        event_id="evt",
        timestamp_utc=timestamp,
        sensor=sensor,
        geotiff_path="",
        jpg_path="",
        raw_jpg_path="",
        kml_path="",
        kmz_path="",
        window_path="",
        width=0,
        height=0,
        band_count=0,
        dtype="",
        crs="EPSG:32630",
        coordinate_system="projected_metric",
        bbox_west=0.0,
        bbox_south=0.0,
        bbox_east=0.0,
        bbox_north=0.0,
        latlon_quad="",
        resolution_estimate_m=1.0,
        alpha_valid_fraction=1.0,
        source_sha256="abc",
        qa_status=qa_status,
        qa_reasons="",
    )


class AssessFrameQualityTests(unittest.TestCase):
    def test_ok_when_all_fields_valid(self) -> None:
        status, reasons = assess_frame_quality(
            timestamp_utc="2024-01-01T00:00:00Z",
            crs="EPSG:32630",
            coordinate_system="projected_metric",
            alpha_valid_fraction=0.5,
            bbox=(0.0, 0.0, 1.0, 1.0),
            resolution_estimate_m=1.0,
        )
        self.assertEqual("ok", status)
        self.assertEqual([], reasons)

    def test_rejected_when_crs_missing(self) -> None:
        status, reasons = assess_frame_quality(
            timestamp_utc="2024-01-01T00:00:00Z",
            crs="",
            coordinate_system="unknown",
            alpha_valid_fraction=0.5,
            bbox=None,
            resolution_estimate_m=None,
        )
        self.assertEqual("rejected", status)
        self.assertIn("missing_crs", reasons)

    def test_review_when_crs_not_projected(self) -> None:
        status, reasons = assess_frame_quality(
            timestamp_utc="2024-01-01T00:00:00Z",
            crs="EPSG:4326",
            coordinate_system="geographic",
            alpha_valid_fraction=0.5,
            bbox=(0.0, 0.0, 1.0, 1.0),
            resolution_estimate_m=1.0,
        )
        self.assertEqual("review", status)
        self.assertIn("crs_not_projected_metric", reasons)

    def test_review_when_alpha_almost_empty(self) -> None:
        status, reasons = assess_frame_quality(
            timestamp_utc="2024-01-01T00:00:00Z",
            crs="EPSG:32630",
            coordinate_system="projected_metric",
            alpha_valid_fraction=0.01,
            bbox=(0.0, 0.0, 1.0, 1.0),
            resolution_estimate_m=1.0,
        )
        self.assertEqual("review", status)
        self.assertIn("alpha_almost_empty", reasons)

    def test_review_when_bbox_invalid(self) -> None:
        status, reasons = assess_frame_quality(
            timestamp_utc="2024-01-01T00:00:00Z",
            crs="EPSG:32630",
            coordinate_system="projected_metric",
            alpha_valid_fraction=0.5,
            bbox=(10.0, 0.0, 1.0, 1.0),  # west > east
            resolution_estimate_m=1.0,
        )
        self.assertEqual("review", status)
        self.assertIn("invalid_bbox", reasons)


class TemporalGapsTests(unittest.TestCase):
    def test_detects_gap_above_threshold(self) -> None:
        rows = [
            _make_row(timestamp="2024-08-02T16:00:00Z"),
            _make_row(timestamp="2024-08-02T16:01:00Z"),  # 60s gap, below threshold
            _make_row(timestamp="2024-08-02T16:10:00Z"),  # 540s gap, above threshold
        ]
        gaps = compute_temporal_gaps(rows, threshold_s=300.0)
        self.assertEqual(1, len(gaps))
        self.assertAlmostEqual(540.0, gaps[0].gap_seconds)

    def test_no_gaps_when_dense(self) -> None:
        rows = [
            _make_row(timestamp="2024-08-02T16:00:00Z"),
            _make_row(timestamp="2024-08-02T16:01:00Z"),
        ]
        gaps = compute_temporal_gaps(rows, threshold_s=300.0)
        self.assertEqual(0, len(gaps))

    def test_gap_detection_per_sensor(self) -> None:
        rows = [
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="LWIR"),
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="HD-EO"),
            _make_row(timestamp="2024-08-02T16:10:00Z", sensor="LWIR"),
        ]
        gaps = compute_temporal_gaps(rows, threshold_s=300.0)
        self.assertEqual(1, len(gaps))


class DuplicateTimestampsTests(unittest.TestCase):
    def test_finds_duplicates(self) -> None:
        rows = [
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="LWIR"),
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="LWIR"),
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="HD-EO"),
        ]
        dups = find_duplicate_timestamps(rows)
        self.assertEqual(1, len(dups))
        self.assertEqual(("2024-08-02T16:00:00Z", "LWIR"), dups[0])

    def test_no_duplicates_when_unique(self) -> None:
        rows = [
            _make_row(timestamp="2024-08-02T16:00:00Z", sensor="LWIR"),
            _make_row(timestamp="2024-08-02T16:01:00Z", sensor="LWIR"),
        ]
        self.assertEqual(0, len(find_duplicate_timestamps(rows)))


class BuildFrameManifestTests(unittest.TestCase):
    def _make_source(self, root: Path) -> Path:
        source = root / "source"
        source.mkdir()
        lwir1 = np.zeros((4, 10, 10), dtype=np.uint8)
        lwir1[0, 2:6, 2:6] = 200
        lwir1[3, :, :] = 255
        _write_projected_tiff(source / "2024-08-02_16-00-00_LWIR.tif", lwir1)

        lwir2 = np.zeros((4, 10, 10), dtype=np.uint8)
        lwir2[0, 3:7, 3:7] = 200
        lwir2[3, :, :] = 255
        _write_projected_tiff(source / "2024-08-02_16-10-00_LWIR.tif", lwir2)
        return source

    def test_build_manifest_groups_by_timestamp_and_sensor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_source(Path(temp))
            result = build_frame_manifest(source, event_id="tobarra_2024")
            self.assertEqual(2, len(result.rows))
            sensors = {r.sensor for r in result.rows}
            self.assertIn("LWIR", sensors)
            timestamps = sorted(r.timestamp_utc for r in result.rows)
            self.assertEqual("2024-08-02T16:00:00Z", timestamps[0])
            self.assertEqual("2024-08-02T16:10:00Z", timestamps[1])

    def test_build_manifest_detects_temporal_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_source(Path(temp))
            result = build_frame_manifest(source, event_id="evt")
            self.assertEqual(1, len(result.gaps))
            self.assertAlmostEqual(600.0, result.gaps[0].gap_seconds)
            self.assertEqual(1, result.summary["gaps_above_threshold"])

    def test_build_manifest_assigns_qa_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_source(Path(temp))
            result = build_frame_manifest(source, event_id="evt")
            self.assertTrue(all(r.qa_status == "ok" for r in result.rows))
            self.assertEqual(2, result.summary["qa_ok"])

    def test_build_manifest_records_crs_and_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = self._make_source(Path(temp))
            result = build_frame_manifest(source, event_id="evt")
            row = result.rows[0]
            self.assertEqual("EPSG:32630", row.crs)
            self.assertEqual("projected_metric", row.coordinate_system)
            self.assertAlmostEqual(10.0, row.resolution_estimate_m)

    def test_build_manifest_rejects_non_projected_crs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            _write_lonlat_tiff(source / "2024-08-02_16-00-00_LWIR.tif")
            result = build_frame_manifest(source, event_id="evt")
            self.assertEqual(1, len(result.rows))
            self.assertEqual("review", result.rows[0].qa_status)
            self.assertIn("crs_not_projected_metric", result.rows[0].qa_reasons)

    def test_empty_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "empty"
            source.mkdir()
            with self.assertRaises(ValueError):
                build_frame_manifest(source, event_id="evt")

    def test_nonexistent_directory_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_frame_manifest(Path("does_not_exist_xyz"), event_id="evt")


class WriteManifestTests(unittest.TestCase):
    def test_write_frame_manifest_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "manifest.csv"
            rows = (_make_row(),)
            write_frame_manifest(rows, output)
            with output.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                data = list(reader)
            self.assertEqual(1, len(data))
            self.assertEqual("evt", data[0]["event_id"])

    def test_write_manifest_summary_includes_counts(self) -> None:
        from wildfire_front.real_if import FrameManifestResult

        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "summary.txt"
            rows = [_make_row(qa_status="ok"), _make_row(qa_status="review")]
            result = FrameManifestResult(
                rows=tuple(rows),
                gaps=(),
                duplicate_timestamps=(),
                summary={
                    "total_rows": 2,
                    "qa_ok": 1,
                    "qa_review": 1,
                    "qa_rejected": 0,
                    "sensors": "LWIR",
                    "unique_timestamps": 2,
                    "gaps_above_threshold": 0,
                    "duplicate_timestamp_sensor_pairs": 0,
                    "duration_s": 0.0,
                },
            )
            write_manifest_summary(result, output)
            text = output.read_text(encoding="utf-8")
            self.assertIn("Total rows:", text)
            self.assertIn("QA ok:", text)


class PrepareRealIfManifestTests(unittest.TestCase):
    def test_prepare_sequence_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            manifest = root / "manifest.csv"
            source.mkdir()
            _write_lonlat_tiff(source / "2024-08-02_16-08-21-553_LWIR.tif")
            _write_lonlat_tiff(source / "2024-08-02_16-08-21-553_HD-EO.tif")

            written = prepare_sequence(
                source,
                output,
                pattern="*_LWIR.tif",
                dst_crs="EPSG:32630",
                resolution_m=1.0,
                resampling=Resampling.nearest,
                manifest_path=manifest,
            )

            self.assertEqual(1, len(written))
            self.assertTrue(manifest.exists())
            with manifest.open(encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(1, len(rows))
            self.assertEqual("LWIR", rows[0]["sensor"])
            self.assertEqual("EPSG:4326", rows[0]["source_crs"])
            self.assertEqual("EPSG:32630", rows[0]["destination_crs"])
            self.assertEqual("2024-08-02T16:08:21.553000Z", rows[0]["timestamp_utc"])
            self.assertTrue(rows[0]["source_sha256"])

    def test_prepare_sequence_without_manifest_works(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            output = root / "output"
            source.mkdir()
            _write_lonlat_tiff(source / "2024-08-02_16-08-21-553_LWIR.tif")

            written = prepare_sequence(
                source,
                output,
                pattern="*_LWIR.tif",
                dst_crs="EPSG:32630",
                resolution_m=1.0,
                resampling=Resampling.nearest,
            )
            self.assertEqual(1, len(written))


class VisualQaTests(unittest.TestCase):
    def _make_manifest_row(self, geotiff_path: str, qa_status: str = "ok") -> FrameManifestRow:
        return FrameManifestRow(
            event_id="evt",
            timestamp_utc="2024-08-02T16:00:00Z",
            sensor="LWIR",
            geotiff_path=geotiff_path,
            jpg_path="",
            raw_jpg_path="",
            kml_path="",
            kmz_path="",
            window_path="",
            width=10,
            height=10,
            band_count=4,
            dtype="uint8",
            crs="EPSG:32630",
            coordinate_system="projected_metric",
            bbox_west=0.0,
            bbox_south=0.0,
            bbox_east=1.0,
            bbox_north=1.0,
            latlon_quad="",
            resolution_estimate_m=1.0,
            alpha_valid_fraction=1.0,
            source_sha256="abc",
            qa_status=qa_status,
            qa_reasons="",
        )

    def test_render_frame_thumbnail_writes_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tiff_path = root / "frame_LWIR.tif"
            data = np.zeros((4, 20, 20), dtype=np.uint8)
            data[0, 5:15, 5:15] = 200
            data[3, :, :] = 255
            _write_projected_tiff(tiff_path, data)

            output_dir = root / "thumbs"
            row = self._make_manifest_row(str(tiff_path))
            result = render_frame_thumbnail(row, output_dir)

            self.assertIsNotNone(result)
            assert result is not None  # for type checker
            self.assertTrue(result.thumbnail_path.exists())
            with Image.open(result.thumbnail_path) as img:
                self.assertGreater(img.width, 0)
                self.assertGreater(img.height, 0)

    def test_render_frame_thumbnail_returns_none_for_missing(self) -> None:
        row = self._make_manifest_row("")
        result = render_frame_thumbnail(row, Path("irrelevant"))
        self.assertIsNone(result)

    def test_render_contact_sheet_produces_single_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = []
            for i in range(4):
                path = root / f"frame_{i}_LWIR.tif"
                data = np.zeros((4, 20, 20), dtype=np.uint8)
                data[0, 5:15, 5:15] = 100 + i * 50
                data[3, :, :] = 255
                _write_projected_tiff(path, data)
                qa = "ok" if i % 2 == 0 else "review"
                rows.append(self._make_manifest_row(str(path), qa_status=qa))

            sheet_path = root / "contact_sheet.png"
            results = render_contact_sheet(rows, sheet_path, columns=3)
            self.assertTrue(sheet_path.exists())
            self.assertEqual(4, len(results))
            with Image.open(sheet_path) as img:
                self.assertGreater(img.width, 0)

    def test_render_contact_sheet_raises_on_empty(self) -> None:
        with self.assertRaises(ValueError):
            render_contact_sheet([], Path("irrelevant.png"))


if __name__ == "__main__":
    unittest.main()
