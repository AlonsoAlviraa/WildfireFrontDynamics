"""Tests for chain-local LWIR alignment (W3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

try:
    import rasterio
    from rasterio.transform import from_origin
except ModuleNotFoundError:  # pragma: no cover
    rasterio = None  # type: ignore[assignment]
    from_origin = None  # type: ignore[assignment]

pytestmark = pytest.mark.skipif(rasterio is None, reason="rasterio not installed")


def _write(
    path: Path, h: int, w: int, *, left: float, top: float, res: float = 10.0, mask: bool = False
) -> None:
    transform = from_origin(left, top, res, res)
    if mask:
        data = np.zeros((h, w), dtype=np.uint8)
        data[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4] = 1
        dtype = "uint8"
    else:
        data = np.arange(h * w, dtype=np.float32).reshape(h, w) % 100
        dtype = "float32"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=h,
        width=w,
        count=1,
        dtype=dtype,
        crs="EPSG:32630",
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_overlap_and_chains(tmp_path: Path):
    from wildfire_front.ml.align_geotiff_stack import (
        consecutive_overlap_chains,
        load_matched_frames,
        overlap_ratio,
    )

    img = tmp_path / "img"
    msk = tmp_path / "msk"
    img.mkdir()
    msk.mkdir()
    # Three frames: 1–2 overlap well; 3 is far away
    _write(img / "2024-01-01_12-00-00_LWIR.tif", 40, 40, left=500000, top=4200000)
    _write(msk / "2024-01-01_12-00-00_LWIR_mask.tif", 40, 40, left=500000, top=4200000, mask=True)
    _write(img / "2024-01-01_12-00-10_LWIR.tif", 50, 45, left=500050, top=4200050)  # shifted
    _write(msk / "2024-01-01_12-00-10_LWIR_mask.tif", 50, 45, left=500050, top=4200050, mask=True)
    _write(img / "2024-01-01_12-00-20_LWIR.tif", 40, 40, left=520000, top=4300000)  # far
    _write(msk / "2024-01-01_12-00-20_LWIR_mask.tif", 40, 40, left=520000, top=4300000, mask=True)

    frames = load_matched_frames(img, msk)
    assert len(frames) == 3
    assert overlap_ratio(frames[0], frames[1]) > 0.3
    assert overlap_ratio(frames[1], frames[2]) < 0.1
    chains = consecutive_overlap_chains(frames, min_overlap=0.3)
    assert len(chains) == 2
    assert chains[0] == [0, 1]
    assert chains[1] == [2]


def test_align_chain_same_shape(tmp_path: Path):
    from wildfire_front.ml.align_geotiff_stack import (
        align_fire_chains,
        verify_dir_aligned,
    )
    from wildfire_front.ml.dataset import WildfireDataset

    img = tmp_path / "img"
    msk = tmp_path / "msk"
    img.mkdir()
    msk.mkdir()
    # Overlapping different shapes
    for i, (h, w, left, top) in enumerate(
        [
            (60, 50, 500000.0, 4200000.0),
            (70, 55, 500020.0, 4200020.0),
            (65, 60, 500010.0, 4200010.0),
            (80, 70, 500000.0, 4200000.0),
        ]
    ):
        name = f"2024-01-01_12-0{i}-00_LWIR.tif"
        _write(img / name, h, w, left=left, top=top, res=10.0)
        _write(
            msk / name.replace(".tif", "_mask.tif"), h, w, left=left, top=top, res=10.0, mask=True
        )

    out = tmp_path / "aligned"
    man = align_fire_chains(
        img,
        msk,
        out,
        min_overlap=0.2,
        mode="intersection",
        max_side_px=512,
    )
    assert man["ok"] is True
    assert man["n_aligned_ok"] >= 1
    chain0 = next(c for c in man["chains"] if c.get("ok"))
    ver = verify_dir_aligned(Path(chain0["images_dir"]), Path(chain0["masks_dir"]))
    assert ver["ok"] is True

    # WildfireDataset must accept without allow_unaligned_crop
    ds = WildfireDataset(
        Path(chain0["images_dir"]),
        Path(chain0["masks_dir"]),
        sequence_length=1,
        patch_size=30,
        max_patches=5,
        allow_unaligned_crop=False,
    )
    assert len(ds) >= 1
    seq, cf, tf = ds[0]
    assert seq.shape[-2:] == (30, 30)
    assert cf.shape == (30, 30)


def test_build_common_grid_auto_coarsen():
    from wildfire_front.ml.align_geotiff_stack import FrameRef, build_common_grid

    # Huge extent would exceed max_side at 1m
    frames = [
        FrameRef(
            image_path="a.tif",
            mask_path="a_mask.tif",
            left=0,
            bottom=0,
            right=20000,
            top=20000,
            width=20000,
            height=20000,
            res_m=1.0,
            crs="EPSG:32630",
        )
    ]
    g = build_common_grid(frames, mode="union", resolution_m=1.0, max_side_px=1024)
    assert g.width <= 1024
    assert g.height <= 1024
    assert g.resolution_m > 1.0
