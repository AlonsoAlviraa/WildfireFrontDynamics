from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from scripts.audit_caldor_clean17 import audit


def test_clean17_audit_rejects_fewer_than_15_pairs(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    path = pack / "covariates/channel.tif"
    path.parent.mkdir(parents=True)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=2,
        width=3,
        count=1,
        dtype="float32",
        crs="EPSG:32610",
        transform=from_origin(0, 60, 30, 30),
        nodata=np.nan,
    ) as dataset:
        dataset.write(np.ones((2, 3), dtype=np.float32), 1)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    names = [f"channel_{index}" for index in range(16)] + ["erc_g"]
    channel = {
        "path": "covariates/channel.tif",
        "sha256": digest,
        "finite_fraction": 1.0,
        "min": 1.0,
        "max": 1.0,
        "gridmet_day": "2021-08-18",
        "day_definition": "calendar day ending 07:00 UTC next day",
    }
    payload = {
        "status": "complete",
        "n_real_channels": 17,
        "channel_order": names,
        "target_grid": {
            "crs": "EPSG:32610",
            "width": 3,
            "height": 2,
            "gsd_m": 30,
        },
        "dynamic": [
            {
                "t0_utc": "2021-08-18T03:20:00Z",
                "t1_utc": "2021-08-19T03:30:00Z",
                "hrrr_cycle_utc": "2021-08-18T00:00:00Z",
                "hrrr_availability_lag_hours": 1,
                "hrrr_leads_hours": [0, 24],
                "channels": dict.fromkeys(names, channel),
            }
        ],
        "leakage_audit": {
            "post_fire_outcomes_used": False,
            "t1_labels_used_as_inputs": False,
            "neutral_placeholder_channels_used": False,
        },
        "compatibility": {"legacy17_checkpoint_compatible": False},
    }
    acquisition = tmp_path / "acquisition.json"
    acquisition.write_text(json.dumps(payload), encoding="utf-8")
    report = audit(acquisition, pack)
    assert report["n_pairs"] == 1
    assert report["channel_sets_exact"] is True
    assert report["hrrr_cycles_respect_availability_lag"] is True
    assert report["hrrr_target_windows_exact"] is False
    assert report["gridmet_erc_values_available_at_t0"] is False
    assert report["temporal_ok"] is False
    assert report["ok"] is False
