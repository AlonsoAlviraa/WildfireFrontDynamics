from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.inventory_real_if_material import (
    classify_file,
    infer_timestamp,
    inventory_files,
    write_inventory,
)


class RealIfInventoryTests(unittest.TestCase):
    def test_infers_exact_timestamp_from_filename(self) -> None:
        observed_at, quality = infer_timestamp(Path("TOBARRA-AB-20240802/IMG_20240802_153000.jpg"))
        self.assertEqual("2024-08-02T15:30:00Z", observed_at)
        self.assertEqual("exact", quality)

    def test_infers_exact_timestamp_with_milliseconds_from_real_sensor_name(self) -> None:
        observed_at, quality = infer_timestamp(Path("fotos/2024-08-02_16-08-21-553_LWIR.tif"))
        self.assertEqual("2024-08-02T16:08:21.553000Z", observed_at)
        self.assertEqual("exact", quality)

    def test_classifies_meteo_table(self) -> None:
        family, usable_for, _ = classify_file(Path("meteo_viento_humedad.csv"))
        self.assertEqual("meteo", family)
        self.assertEqual("weather", usable_for)

    def test_inventory_writes_traceable_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "raw"
            source.mkdir()
            (source / "TOBARRA-AB-20240802").mkdir()
            image = source / "TOBARRA-AB-20240802" / "IMG_20240802_153000.jpg"
            image.write_bytes(b"fake-image")
            output = root / "inventory.csv"
            records = inventory_files(source)
            write_inventory(records, output)
            with output.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(1, len(records))
        self.assertEqual(1, len(rows))
        self.assertEqual("tobarra_ab_20240802", rows[0]["inferred_event_id"])
        self.assertEqual("image", rows[0]["variable_family"])


if __name__ == "__main__":
    unittest.main()
