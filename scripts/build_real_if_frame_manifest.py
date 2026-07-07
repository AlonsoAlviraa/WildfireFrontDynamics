"""Build a frame manifest from a raw real-if extracted folder.

Scans a folder for GeoTIFF, KML/KMZ, JPG and PNG files, groups them by
(timestamp, sensor), applies quality gates, and writes:

  1. A CSV frame manifest with one row per (timestamp, sensor).
  2. A human-readable summary with QA breakdown, gaps and duplicates.

Usage:
    python scripts/build_real_if_frame_manifest.py \
        --source data/raw/tobarra_20240802 \
        --output-dir artifacts/real_if_manifests \
        --event-id tobarra_2024_08_02
"""

from __future__ import annotations

import argparse
from pathlib import Path

from wildfire_front.real_if import (
    build_frame_manifest,
    write_frame_manifest,
    write_manifest_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a frame manifest from a raw real-if folder."
    )
    parser.add_argument(
        "--source", type=Path, required=True, help="Root of the extracted real-if folder"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="Directory to write manifest files"
    )
    parser.add_argument("--event-id", required=True, help="Event identifier for all rows")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = build_frame_manifest(args.source, args.event_id)

    csv_path = args.output_dir / "frame_manifest.csv"
    summary_path = args.output_dir / "frame_manifest_summary.txt"

    write_frame_manifest(result.rows, csv_path)
    write_manifest_summary(result, summary_path)

    print(f"Wrote {len(result.rows)} rows to {csv_path}")
    print(f"Wrote summary to {summary_path}")
    print(
        f"QA: ok={result.summary['qa_ok']} review={result.summary['qa_review']} rejected={result.summary['qa_rejected']}"
    )


if __name__ == "__main__":
    main()
