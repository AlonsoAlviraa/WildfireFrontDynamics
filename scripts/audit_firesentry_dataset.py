"""Audit the public FireSentry tree and a quarantined Region A sample."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SAMPLE = ROOT / "data/external/firesentry_public_sample"
DEFAULT_OUTPUT = ROOT / "docs/FIRESENTRY_DATASET_AUDIT.json"

SOURCE_REPOSITORY = "https://github.com/Munan222/FireSentry-Benchmark-Dataset"
SOURCE_COMMIT = "f8693204071a871562a3b4b4e24797a6a0d3ae3f"
SOURCE_TREE = "08461dd263986e99addbc1736e37436d2b371ea4"

REPOSITORY_INVENTORY: dict[str, Any] = {
    "entries": 709,
    "blobs": 684,
    "bytes": 225_109_065,
    "tree_truncated": False,
    "extensions": {".csv": 5, ".jpg": 230, ".md": 1, ".mp4": 448},
    "regions": {
        "A": {"environmental": 1, "masks": 70, "infrared": 70, "visible": 71},
        "B": {"environmental": 1, "masks": 21, "infrared": 21, "visible": 22},
        "C": {"environmental": 1, "masks": 11, "infrared": 11, "visible": 12},
        "D": {"environmental": 1, "masks": 38, "infrared": 38, "visible": 40},
        "E": {"environmental": 1, "masks": 84, "infrared": 84, "visible": 85},
    },
}

VideoProbe = Callable[[Path], dict[str, Any]]
FrameSampler = Callable[[Path], list[dict[str, Any]]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _probe_video(path: Path) -> dict[str, Any]:
    executable = shutil.which("ffprobe")
    if executable is None:
        raise RuntimeError("ffprobe is required to audit FireSentry video metadata")
    command = [
        executable,
        "-v",
        "error",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,nb_frames,duration,pix_fmt",
        "-show_entries",
        "format=duration,size",
        "-of",
        "json",
        str(path),
    ]
    payload = json.loads(subprocess.check_output(command, text=True))
    stream = payload["streams"][0]
    return {
        "codec": stream.get("codec_name"),
        "width": int(stream["width"]),
        "height": int(stream["height"]),
        "pixel_format": stream.get("pix_fmt"),
        "frame_rate": stream.get("avg_frame_rate") or stream.get("r_frame_rate"),
        "frames": int(stream["nb_frames"]),
        "duration_seconds": float(stream["duration"]),
        "bytes": int(payload["format"]["size"]),
    }


def _sample_video_frames(path: Path) -> list[dict[str, Any]]:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("ffmpeg is required to audit FireSentry mask pixels")
    with tempfile.TemporaryDirectory(prefix="wfd_firesentry_") as temp_dir:
        pattern = str(Path(temp_dir) / "frame_%04d.png")
        subprocess.run(
            [
                executable,
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-vsync",
                "0",
                pattern,
            ],
            check=True,
        )
        frames = sorted(Path(temp_dir).glob("frame_*.png"))
        indices = sorted({0, len(frames) // 2, len(frames) - 1}) if frames else []
        rows: list[dict[str, Any]] = []
        for index in indices:
            array = np.asarray(Image.open(frames[index]).convert("RGB"))
            channel_spread = np.ptp(array.astype(np.int16), axis=2)
            intensity = array.max(axis=2)
            rows.append(
                {
                    "frame_index": index,
                    "height": int(array.shape[0]),
                    "width": int(array.shape[1]),
                    "max_channel_spread": int(channel_spread.max()),
                    "positive_fraction_gt_127": float((intensity > 127).mean()),
                }
            )
        return rows


def _read_environment(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    encoding = next(
        candidate
        for candidate in ("utf-8-sig", "gb18030", "gbk")
        if _can_decode(raw, candidate)
    )
    rows = list(csv.reader(raw.decode(encoding).splitlines()))
    header, body = rows[0], rows[1:]
    timestamp_counts = Counter(row[0] for row in body)
    missing = {
        (name or "timestamp"): sum(not row[index].strip() for row in body)
        for index, name in enumerate(header)
    }
    numeric_ranges: dict[str, dict[str, float | int]] = {}
    for index, name in enumerate(header[1:10], start=1):
        values = [float(row[index]) for row in body if row[index].strip()]
        numeric_ranges[name] = {
            "min": min(values),
            "max": max(values),
            "negative_count": sum(value < 0 for value in values),
        }
    return {
        "encoding": encoding,
        "rows": len(body),
        "columns": len(header),
        "header": header,
        "timestamp_start": body[0][0],
        "timestamp_end": body[-1][0],
        "timezone": "unspecified_in_source",
        "unique_minute_timestamps": len(timestamp_counts),
        "samples_per_minute_min": min(timestamp_counts.values()),
        "samples_per_minute_max": max(timestamp_counts.values()),
        "missing_by_column": missing,
        "numeric_ranges": numeric_ranges,
    }


def _can_decode(raw: bytes, encoding: str) -> bool:
    try:
        raw.decode(encoding)
    except UnicodeDecodeError:
        return False
    return True


def audit_sample(
    sample_root: Path,
    *,
    video_probe: VideoProbe = _probe_video,
    frame_sampler: FrameSampler = _sample_video_frames,
) -> dict[str, Any]:
    sample_root = Path(sample_root)
    meta_path = sample_root / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    expected_hashes = meta["files"]
    observed_hashes = {
        relative: _sha256(sample_root / relative) for relative in expected_hashes
    }
    hashes_match = observed_hashes == expected_hashes

    mask_path = sample_root / "fire_mask/video_001.mp4"
    infrared_path = sample_root / "infrared/video_001.mp4"
    visible_path = sample_root / "visible/00000.jpg"
    environment_path = sample_root / "environmental/P171-1020.csv"
    mask_probe = video_probe(mask_path)
    infrared_probe = video_probe(infrared_path)
    aligned_fields = ("width", "height", "frame_rate", "frames", "duration_seconds")
    videos_aligned = all(
        mask_probe[field] == infrared_probe[field] for field in aligned_fields
    )
    mask_frames = frame_sampler(mask_path)
    mask_is_near_grayscale = bool(mask_frames) and all(
        row["max_channel_spread"] <= 4 for row in mask_frames
    )
    with Image.open(visible_path) as image:
        visible = {
            "format": image.format,
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "bytes": visible_path.stat().st_size,
        }
    environment = _read_environment(environment_path)
    wind_missing = all(
        environment["missing_by_column"].get(name) == environment["rows"]
        for name in ("风向", "风速(10m/s)")
    )
    negative_air_quality = any(
        details["negative_count"] > 0
        for details in environment["numeric_ranges"].values()
    )

    return {
        "schema": "wfd_firesentry_dataset_audit_v1",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "ok": hashes_match and videos_aligned,
        "source_snapshot": {
            "repository": SOURCE_REPOSITORY,
            "commit": SOURCE_COMMIT,
            "tree": SOURCE_TREE,
            "inventory": REPOSITORY_INVENTORY,
            "all_regions_a_to_e_public_at_snapshot": True,
            "readme_still_says_b_to_e_post_acceptance": True,
            "license_file_present": False,
        },
        "sample": {
            "scope": meta["scope"],
            "hashes_match_manifest": hashes_match,
            "observed_sha256": observed_hashes,
            "fire_mask_video": mask_probe,
            "infrared_video": infrared_probe,
            "mask_and_infrared_container_aligned": videos_aligned,
            "mask_sampled_frames": mask_frames,
            "mask_near_grayscale": mask_is_near_grayscale,
            "visible_asset": visible,
            "environmental_csv": environment,
        },
        "data_quality_findings": {
            "visible_assets_are_jpeg_not_video": True,
            "visible_to_ir_clip_mapping_documented": False,
            "environment_to_clip_mapping_documented": False,
            "environment_timezone_documented": False,
            "wind_columns_entirely_missing_in_region_a_sample": wind_missing,
            "negative_air_quality_values_present": negative_air_quality,
            "mask_labels_generated_by_sam2": True,
            "human_mask_quality_assurance_documented": False,
            "regions_geographically_identified": False,
            "forestry_modality_public": False,
        },
        "rights": {
            "explicit_license_found": False,
            "training_allowed": False,
            "redistribution_allowed": False,
            "commercial_use_allowed": False,
            "allowed_current_use": "public_artifact_format_and_metadata_audit_only",
            "required_action": "obtain an explicit dataset license from the authors",
        },
        "wfd_compatibility": {
            "same_temporal_scale_as_ndws_daily": False,
            "same_input_schema_as_legacy17": False,
            "direct_numeric_comparison_allowed": False,
            "thermal_encoder_pretraining_candidate": True,
            "segmentation_pretraining_candidate": True,
            "training_currently_blocked_by_rights": True,
        },
        "required_protocol": [
            "obtain an explicit license before training or redistribution",
            "publish the RGB/IR/mask/environment timestamp mapping",
            "human-audit SAM2 masks with stratified precision/recall and boundary error",
            "split by region, never by adjacent frame or clip",
            "use leave-one-region-out evaluation across all five regions",
            "keep FireSentry transfer results separate from daily perimeter IoU",
            "report performance with and without environmental covariates",
        ],
        "sources": {
            "repository": SOURCE_REPOSITORY,
            "readme": f"{SOURCE_REPOSITORY}/blob/{SOURCE_COMMIT}/README.md",
            "tree_api": (
                "https://api.github.com/repos/Munan222/"
                f"FireSentry-Benchmark-Dataset/git/trees/{SOURCE_TREE}?recursive=1"
            ),
            "paper": "https://arxiv.org/abs/2512.03369",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-root", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = audit_sample(args.sample_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "videos_aligned": report["sample"][
                    "mask_and_infrared_container_aligned"
                ],
                "training_allowed": report["rights"]["training_allowed"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
