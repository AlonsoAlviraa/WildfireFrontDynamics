from __future__ import annotations

from pathlib import Path

import pytest

from scripts.audit_firebench_caldor_covariates import audit_caldor_covariates

h5py = pytest.importorskip("h5py")


def test_caldor_covariate_audit_refuses_incomplete_restricted_contract(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    licenses = pack / "DATA_LICENSES"
    licenses.mkdir(parents=True)
    (licenses / "LANDFIRE.txt").write_text("public", encoding="utf-8")
    with h5py.File(pack / "Caldor.h5", "w") as h5:
        spatial = h5.create_group("spatial_2d/Caldor_CH")
        spatial.create_dataset("canopy_height", data=[[1, 2], [3, 4]])
        spatial.attrs["license"] = "/DATA_LICENSES/LANDFIRE.txt"
        station = h5.create_group("time_series/station_TEST")
        station.create_dataset("time", data=[0.0, 1.0])
        station.create_dataset("air_temperature", data=[20.0, 21.0])
        station.attrs["license"] = "/DATA_LICENSES/Synoptic.txt"
        station.attrs["data_use_restrictions"] = "No commercial use allowed"
        station.attrs["redistribution_allowed"] = False

    report = audit_caldor_covariates(pack)

    assert report["status"] == "blocked_incompatible_and_restricted"
    assert report["model_inference_allowed"] is False
    assert report["n_compatible_channels"] == 0
    assert report["rights"]["synoptic_notice_missing"] is True
    assert report["station_inventory"]["n_restricted_or_nonredistributable"] == 1


def test_caldor_covariate_audit_missing_h5(tmp_path: Path) -> None:
    report = audit_caldor_covariates(tmp_path)
    assert report["ok"] is False
    assert report["status"] == "blocked_missing_h5"
