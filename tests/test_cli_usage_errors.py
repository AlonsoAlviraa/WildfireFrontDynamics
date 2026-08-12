"""CLI usage errors: print_error + exit 2 with copy-paste hints."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wildfire_front.cli import run_geotiff_ingest

ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "wildfire_front", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={**dict(os.environ), "PYTHONPATH": str(ROOT)},
    )


def test_export_acta_missing_card_exits_2_with_hint():
    p = _run(["export-acta"])
    assert p.returncode == 2
    err = p.stderr
    assert "error:" in err
    assert "export-acta requires" in err
    assert "wildfire-front export-acta --work-dir outputs/incidents/IF1" in err
    assert "hint:" in err


def test_replay_decide_missing_args_exits_2_with_hint():
    p = _run(["replay-decide"])
    assert p.returncode == 2
    err = p.stderr
    assert "error:" in err
    assert "replay-decide requires" in err
    assert "wildfire-front replay-decide --work-dir outputs/incidents/IF1" in err


def test_no_accepted_observations_message_includes_manifest_path(tmp_path: Path):
    import numpy as np
    import rasterio
    from rasterio.transform import from_origin

    images = tmp_path / "images"
    images.mkdir()
    output = tmp_path / "out"
    # Zero band + high threshold → rejected mask → empty observations (not the
    # early "threshold required" / "no GeoTIFF" validators).
    arr = np.zeros((1, 8, 8), dtype=np.uint16)
    transform = from_origin(500000.0, 4100000.0, 10.0, 10.0)
    with rasterio.open(
        images / "burn_20260610_120000.tif",
        "w",
        driver="GTiff",
        width=8,
        height=8,
        count=1,
        dtype="uint16",
        crs="EPSG:32630",
        transform=transform,
    ) as dataset:
        dataset.write(arr)
    with pytest.raises(ValueError, match="ingest_manifest.csv") as ei:
        run_geotiff_ingest(
            images,
            None,
            output,
            event_id="empty",
            sensor_id="lwir_drone",
            estimated_error_m=2.0,
            band=1,
            threshold=10.0,
        )
    msg = str(ei.value)
    assert str(output / "ingest_manifest.csv") in msg
    assert "wildfire-front ingest-geotiff" in msg


def test_export_acta_help_has_example():
    p = _run(["export-acta", "--help"])
    assert p.returncode == 0
    assert "wildfire-front export-acta --work-dir" in p.stdout
