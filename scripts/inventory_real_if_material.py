"""Inventory raw real-wildfire material before scientific use.

The script does not interpret the fire behaviour. It creates a traceable file
inventory so the team can decide which events have enough temporal, spatial and
meteorological evidence for WildfireFrontDynamics.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".heic"}
GIS_EXTENSIONS = {".shp", ".kml", ".kmz", ".gpx", ".geojson", ".gpkg", ".prj", ".dbf", ".shx"}
TABLE_EXTENSIONS = {".csv", ".xlsx", ".xls", ".ods"}
DOC_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz"}


@dataclass(frozen=True)
class FileInventoryRecord:
    source_root: str
    relative_path: str
    file_name: str
    suffix: str
    size_bytes: int
    sha256: str
    inferred_event_id: str
    inferred_observed_at: str
    time_quality: str
    variable_family: str
    usable_for: str
    notes: str


def sha256_of_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def slugify_event_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return cleaned or "unknown_event"


def infer_event_id(path: Path, root: Path) -> str:
    try:
        first_part = path.relative_to(root).parts[0]
    except ValueError:
        first_part = path.stem
    candidate = first_part if first_part != path.name else path.stem
    candidate = re.sub(r"\.(zip|rar|7z|tar|gz)$", "", candidate, flags=re.IGNORECASE)
    return slugify_event_id(candidate)


def infer_timestamp(path: Path) -> tuple[str, str]:
    text = " ".join([path.stem, *path.parts])
    patterns = [
        (r"(20\d{2})[-_](\d{2})[-_](\d{2})[T _-](\d{2})[-_:](\d{2})[-_:](\d{2})[-_.](\d{3,6})", "exact"),
        (r"(20\d{2})(\d{2})(\d{2})[_-]?(\d{2})(\d{2})(\d{2})", "exact"),
        (r"(20\d{2})[-_](\d{2})[-_](\d{2})[T _-](\d{2})[-_:](\d{2})[-_:](\d{2})", "exact"),
        (r"(20\d{2})(\d{2})(\d{2})", "date_only"),
        (r"(20\d{2})[-_](\d{2})[-_](\d{2})", "date_only"),
    ]
    for pattern, quality in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        values = match.groups()
        try:
            if len(values) >= 6:
                microsecond = 0
                if len(values) == 7:
                    fraction = values[6].ljust(6, "0")[:6]
                    microsecond = int(fraction)
                dt = datetime(
                    int(values[0]),
                    int(values[1]),
                    int(values[2]),
                    int(values[3]),
                    int(values[4]),
                    int(values[5]),
                    microsecond,
                    tzinfo=timezone.utc,
                )
            else:
                dt = datetime(int(values[0]), int(values[1]), int(values[2]), tzinfo=timezone.utc)
        except ValueError:
            continue
        return dt.isoformat().replace("+00:00", "Z"), quality
    return "", "missing"


def classify_file(path: Path) -> tuple[str, str, str]:
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image", "observation", "check EXIF or surrounding folder for timestamp/location"
    if suffix in GIS_EXTENSIONS:
        return "geospatial", "validation", "inspect CRS and whether it is perimeter, track or reference layer"
    if suffix in TABLE_EXTENSIONS:
        if any(token in name for token in ("meteo", "weather", "viento", "humedad", "temperatura")):
            return "meteo", "weather", "synchronize station/time resolution with event"
        return "table", "context", "inspect columns for timestamps, coordinates or operational records"
    if suffix in DOC_EXTENSIONS:
        if any(token in name for token in ("plan", "parte", "informe", "operativo", "acta")):
            return "planning", "context", "extract event timeline and operational notes"
        return "document", "context", "manual review required"
    if suffix in ARCHIVE_EXTENSIONS:
        return "archive", "context", "extract into raw_dropbox preserving original file"
    return "unknown", "context", "manual classification required"


def inventory_files(root: Path) -> list[FileInventoryRecord]:
    if not root.is_dir():
        raise ValueError(f"source root does not exist or is not a directory: {root}")
    records: list[FileInventoryRecord] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        observed_at, time_quality = infer_timestamp(path)
        variable_family, usable_for, notes = classify_file(path)
        records.append(
            FileInventoryRecord(
                source_root=str(root),
                relative_path=str(path.relative_to(root)),
                file_name=path.name,
                suffix=path.suffix.lower(),
                size_bytes=path.stat().st_size,
                sha256=sha256_of_file(path),
                inferred_event_id=infer_event_id(path, root),
                inferred_observed_at=observed_at,
                time_quality=time_quality,
                variable_family=variable_family,
                usable_for=usable_for,
                notes=notes,
            )
        )
    return records


def write_inventory(records: list[FileInventoryRecord], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = list(FileInventoryRecord.__dataclass_fields__.keys())
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a traceable inventory of real wildfire source material.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    records = inventory_files(args.source)
    write_inventory(records, args.output)
    print(f"wrote {len(records)} records to {args.output}")


if __name__ == "__main__":
    main()
