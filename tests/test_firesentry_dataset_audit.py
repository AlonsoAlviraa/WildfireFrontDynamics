from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from scripts.audit_firesentry_dataset import audit_sample


def _write_fixture(root: Path) -> None:
    paths = {
        "environmental/P171-1020.csv": (
            ",pm2d5(μg/m3),pm10(μg/m3),co(mg/m3),so2(μg/m3),"
            "no2(μg/m3),o3(μg/m3),voc(ppm),温度(℃),湿度(%),风向,风速(10m/s)\n"
            "2025/2/19 11:34,1,2,-1,4,5,-2,1,16,34,,\n"
        ).encode("gb18030"),
        "fire_mask/video_001.mp4": b"mask",
        "infrared/video_001.mp4": b"infrared",
    }
    for relative, content in paths.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    visible = root / "visible/00000.jpg"
    visible.parent.mkdir(parents=True)
    Image.new("RGB", (1920, 1080)).save(visible)
    hashes = {
        str(path.relative_to(root)).replace("\\", "/"): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }
    (root / "meta.json").write_text(
        json.dumps({"scope": "test", "files": hashes}),
        encoding="utf-8",
    )


def test_audit_blocks_training_and_detects_modality_gaps(tmp_path: Path) -> None:
    _write_fixture(tmp_path)

    def fake_probe(path: Path) -> dict[str, object]:
        return {
            "codec": "mpeg4",
            "width": 832,
            "height": 480,
            "pixel_format": "yuv420p",
            "frame_rate": "30/1",
            "frames": 17,
            "duration_seconds": 17 / 30,
            "bytes": path.stat().st_size,
        }

    def fake_frames(_path: Path) -> list[dict[str, object]]:
        return [
            {
                "frame_index": 0,
                "height": 480,
                "width": 832,
                "max_channel_spread": 0,
                "positive_fraction_gt_127": 0.01,
            }
        ]

    report = audit_sample(
        tmp_path,
        video_probe=fake_probe,
        frame_sampler=fake_frames,
    )

    assert report["ok"] is True
    assert report["sample"]["hashes_match_manifest"] is True
    assert report["sample"]["mask_and_infrared_container_aligned"] is True
    assert report["sample"]["environmental_csv"]["encoding"] == "gb18030"
    assert report["data_quality_findings"][
        "wind_columns_entirely_missing_in_region_a_sample"
    ] is True
    assert report["data_quality_findings"][
        "negative_air_quality_values_present"
    ] is True
    assert report["rights"]["training_allowed"] is False
    assert report["wfd_compatibility"]["direct_numeric_comparison_allowed"] is False
