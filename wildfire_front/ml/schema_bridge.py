"""Schema bridge: legacy17 (17ch) ↔ spatial_v1 / physics14 (14ch).

Honesty rails
-------------
* Projected tensors are **not** geotiff spatial_v1 — stamp ``schema_bridge_projected``.
* Elevation is **not** stored in sealed legacy17 NPZ (only slope/aspect derived at build).
  Projected elevation channel is GAP (zeros + missing_mask) unless provided.
* tmin/tmax are split from a single legacy temperature slot → stamp ``temp_split_proxy``.
* Constant legacy pads (pressure/cloud/vis/dew) are **dropped**, never sold as signal.
* Partial multi_if init copies only mapped first-conv input channels; rest stay random.
* lab only · ml_product_go stays false · fusion OFF · not comparable to sealed T1 17ch board.

Usage
-----
    from wildfire_front.ml.schema_bridge import (
        project_legacy17_to_physics14,
        map_first_conv_multi_if_to_spatial,
        BRIDGE_SPEC,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from wildfire_front.ml.feature_schema import (
    LEGACY17_CHANNEL_STATS,
    PHYSICS14_CHANNEL_STATS,
    PHYSICS14_NAMES,
    SPATIAL_V1_NAMES,
    normalize_with_stats,
)

# ---------------------------------------------------------------------------
# Immutable channel map (legacy17 build order — see build_legacy17_channels)
# ---------------------------------------------------------------------------

LEGACY17_SEMANTIC: tuple[str, ...] = (
    "slope",  # 0
    "aspect_plus_pi",  # 1  (aspect + pi, pre-norm)
    "temperature",  # 2  (0.5*(tmin+tmax))
    "humidity",  # 3
    "wind_speed",  # 4
    "wind_dir",  # 5
    "precipitation",  # 6
    "pressure_const",  # 7  DROP
    "cloud_const",  # 8  DROP
    "visibility_const",  # 9  DROP
    "dewpoint_const",  # 10 DROP
    "vegetation",  # 11
    "erc",  # 12
    "one_minus_erc",  # 13 DROP (redundant)
    "pad14",  # 14 DROP
    "pad15",  # 15 DROP
    "ffmc",  # 16 → drought_or_ffmc
)

# physics14 / spatial_v1 index → how it is filled from legacy17
# kind: copy | derive | gap | temp_split
BRIDGE_SPEC: list[dict[str, Any]] = [
    {
        "physics14_idx": 0,
        "name": "elevation",
        "kind": "gap",
        "legacy_idx": None,
        "note": "legacy17 NPZ has no elevation channel; GAP unless elev_override",
    },
    {
        "physics14_idx": 1,
        "name": "slope",
        "kind": "copy",
        "legacy_idx": 0,
        "note": "direct denorm→renorm",
    },
    {
        "physics14_idx": 2,
        "name": "aspect_sin",
        "kind": "derive",
        "legacy_idx": 1,
        "note": "sin(aspect) from denorm(aspect_plus_pi - pi)",
    },
    {
        "physics14_idx": 3,
        "name": "aspect_cos",
        "kind": "derive",
        "legacy_idx": 1,
        "note": "cos(aspect) from denorm(aspect_plus_pi - pi)",
    },
    {
        "physics14_idx": 4,
        "name": "tmin",
        "kind": "temp_split",
        "legacy_idx": 2,
        "note": "proxy: same denorm temp → both tmin/tmax; stamp temp_split_proxy",
    },
    {
        "physics14_idx": 5,
        "name": "tmax",
        "kind": "temp_split",
        "legacy_idx": 2,
        "note": "proxy: same denorm temp → both tmin/tmax; stamp temp_split_proxy",
    },
    {
        "physics14_idx": 6,
        "name": "humidity",
        "kind": "copy",
        "legacy_idx": 3,
        "note": "direct",
    },
    {
        "physics14_idx": 7,
        "name": "wind_speed",
        "kind": "copy",
        "legacy_idx": 4,
        "note": "direct",
    },
    {
        "physics14_idx": 8,
        "name": "wind_sin",
        "kind": "derive",
        "legacy_idx": (4, 5),
        "note": "sin(dir)* from denorm wind_dir (speed unused for unit sin)",
    },
    {
        "physics14_idx": 9,
        "name": "wind_cos",
        "kind": "derive",
        "legacy_idx": (4, 5),
        "note": "cos(dir)* from denorm wind_dir",
    },
    {
        "physics14_idx": 10,
        "name": "precipitation",
        "kind": "copy",
        "legacy_idx": 6,
        "note": "direct",
    },
    {
        "physics14_idx": 11,
        "name": "vegetation",
        "kind": "copy",
        "legacy_idx": 11,
        "note": "direct",
    },
    {
        "physics14_idx": 12,
        "name": "erc",
        "kind": "copy",
        "legacy_idx": 12,
        "note": "direct",
    },
    {
        "physics14_idx": 13,
        "name": "drought_or_ffmc",
        "kind": "copy",
        "legacy_idx": 16,
        "note": "legacy FFMC slot",
    },
]

# First-conv input channel map for T=1 tensors:
# legacy in_channels = 17 + 1 prev_fire = 18
# spatial in_channels = 14 + 1 prev_fire = 15
# maps spatial_input_idx → legacy_input_idx (or None = no copy)
FIRST_CONV_SPATIAL_TO_LEGACY: list[int | None] = [
    None,  # 0 elevation GAP — no legacy elev
    0,  # 1 slope ← legacy 0
    None,  # 2 aspect_sin — derived; no 1:1 weight
    None,  # 3 aspect_cos
    2,  # 4 tmin ← legacy temp (proxy)
    2,  # 5 tmax ← legacy temp (proxy)
    3,  # 6 humidity
    4,  # 7 wind_speed
    None,  # 8 wind_sin derived
    None,  # 9 wind_cos derived
    6,  # 10 precip
    11,  # 11 vegetation
    12,  # 12 erc
    16,  # 13 ffmc
    17,  # 14 prev_fire ← legacy prev_fire (index 17)
]


def _denorm_channel(norm: np.ndarray, idx: int) -> np.ndarray:
    sub, div = LEGACY17_CHANNEL_STATS[idx]
    return (np.asarray(norm, dtype=np.float32) * float(div)) + float(sub)


def project_legacy17_to_physics14(
    legacy17: np.ndarray,
    *,
    elev_override: np.ndarray | None = None,
    already_normalized: bool = True,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Project (17,H,W) legacy tensor → (14,H,W) physics14/spatial layout.

    Returns
    -------
    physics14 : float32 (14,H,W) normalized with PHYSICS14_CHANNEL_STATS
    missing_mask : float32 (14,H,W) 1 where GAP / proxy
    stamp : honesty metadata
    """
    x = np.asarray(legacy17, dtype=np.float32)
    if x.ndim != 3 or x.shape[0] != 17:
        raise ValueError(f"expected legacy17 (17,H,W), got {x.shape}")
    h, w = x.shape[1], x.shape[2]

    if already_normalized:
        slope = _denorm_channel(x[0], 0)
        aspect = _denorm_channel(x[1], 1) - np.pi  # stored as aspect+pi
        temp = _denorm_channel(x[2], 2)
        humidity = _denorm_channel(x[3], 3)
        wind_speed = _denorm_channel(x[4], 4)
        wind_dir = _denorm_channel(x[5], 5)
        precip = _denorm_channel(x[6], 6)
        veg = _denorm_channel(x[11], 11)
        erc = _denorm_channel(x[12], 12)
        ffmc = _denorm_channel(x[16], 16)
    else:
        slope, aspect = x[0], x[1] - np.pi
        temp, humidity = x[2], x[3]
        wind_speed, wind_dir, precip = x[4], x[5], x[6]
        veg, erc, ffmc = x[11], x[12], x[16]

    aspect_sin = np.sin(aspect).astype(np.float32)
    aspect_cos = np.cos(aspect).astype(np.float32)
    # wind unit direction (not scaled by speed — matches feature_schema _wind_components intent)
    wd_rad = np.deg2rad(np.asarray(wind_dir, dtype=np.float32))
    wind_sin = np.sin(wd_rad).astype(np.float32)
    wind_cos = np.cos(wd_rad).astype(np.float32)

    if elev_override is not None:
        elev = np.asarray(elev_override, dtype=np.float32)
        if elev.shape != (h, w):
            raise ValueError(f"elev_override shape {elev.shape} != {(h, w)}")
        elev_gap = False
    else:
        elev = np.zeros((h, w), dtype=np.float32)
        elev_gap = True

    raw = np.zeros((14, h, w), dtype=np.float32)
    raw[0] = elev
    raw[1] = slope
    raw[2] = aspect_sin
    raw[3] = aspect_cos
    raw[4] = temp  # tmin proxy
    raw[5] = temp  # tmax proxy
    raw[6] = humidity
    raw[7] = wind_speed
    raw[8] = wind_sin
    raw[9] = wind_cos
    raw[10] = precip
    raw[11] = veg
    raw[12] = erc
    raw[13] = ffmc

    out = normalize_with_stats(raw, PHYSICS14_CHANNEL_STATS)
    missing = np.zeros((14, h, w), dtype=np.float32)
    if elev_gap:
        missing[0] = 1.0
    # temp split proxy flags both tmin/tmax
    missing[4] = 0.5
    missing[5] = 0.5

    stamp = {
        "work_class": "schema_bridge_projected",
        "feature_schema": "physics14",
        "source_schema": "legacy17",
        "schema_path_id": "E2-P2-bridge",
        "elev_gap": elev_gap,
        "temp_split_proxy": True,
        "dropped_legacy_const_channels": [7, 8, 9, 10, 13, 14, 15],
        "channel_names": list(PHYSICS14_NAMES),
        "comparability": "not_same_as_sealed_legacy17_t1",
        "ml_product_go": False,
        "field_ops_allow_ml_live_in_fusion": False,
        "honesty": (
            "Projected from sealed legacy17; elevation GAP unless override; "
            "tmin/tmax are temp_split_proxy; not geotiff spatial_v1."
        ),
    }
    return out.astype(np.float32), missing, stamp


def project_sequence_legacy17_to_physics14(
    sequence: np.ndarray,
    *,
    elev_override: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Project (T,17,H,W) → (T,14,H,W)."""
    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 4 or seq.shape[1] != 17:
        raise ValueError(f"expected (T,17,H,W), got {seq.shape}")
    frames = []
    masks = []
    stamp: dict[str, Any] = {}
    for t in range(seq.shape[0]):
        p14, m, stamp = project_legacy17_to_physics14(
            seq[t], elev_override=elev_override, already_normalized=True
        )
        frames.append(p14)
        masks.append(m)
    return np.stack(frames, axis=0), np.stack(masks, axis=0), stamp


@dataclass
class PartialInitReport:
    mapped_input_channels: int
    total_spatial_input_channels: int
    skipped: list[int]
    loaded_keys: list[str]
    work_class: str = "schema_bridge_partial_multi_if_init"
    ml_product_go: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "mapped_input_channels": self.mapped_input_channels,
            "total_spatial_input_channels": self.total_spatial_input_channels,
            "frac_mapped": self.mapped_input_channels / max(self.total_spatial_input_channels, 1),
            "skipped_spatial_input_idx": self.skipped,
            "loaded_keys": self.loaded_keys,
            "work_class": self.work_class,
            "ml_product_go": self.ml_product_go,
            "field_ops_allow_ml_live_in_fusion": False,
            "first_conv_map": FIRST_CONV_SPATIAL_TO_LEGACY,
        }


def map_first_conv_multi_if_to_spatial(
    multi_if_state: dict[str, Any],
    spatial_model: Any,
    *,
    legacy_in_channels: int = 18,
    spatial_in_channels: int = 15,
) -> PartialInitReport:
    """Copy multi_if weights into spatial residual-small where shapes allow.

    Strategy
    --------
    1. First conv (in_channels mismatch): copy per-input-channel slices via
       ``FIRST_CONV_SPATIAL_TO_LEGACY``.
    2. All other parameters with **identical shape**: full copy.
    3. Mismatched shapes: skip (keep spatial init).

    Does not freeze layers; caller may freeze encoder if desired.
    """

    if not isinstance(multi_if_state, dict):
        raise TypeError("multi_if_state must be a state_dict-like dict")

    # Unwrap common checkpoint wrappers
    if "model" in multi_if_state and isinstance(multi_if_state["model"], dict):
        src = multi_if_state["model"]
    elif "state_dict" in multi_if_state and isinstance(multi_if_state["state_dict"], dict):
        src = multi_if_state["state_dict"]
    else:
        src = multi_if_state

    # strip module. prefix
    src_clean = {k.replace("module.", ""): v for k, v in src.items()}
    dst = spatial_model.state_dict()
    loaded: list[str] = []
    skipped_idx: list[int] = [i for i, m in enumerate(FIRST_CONV_SPATIAL_TO_LEGACY) if m is None]

    # Identify first conv weight key in both models
    def _first_conv_key(sd: dict[str, Any]) -> str | None:
        for k, v in sd.items():
            if not hasattr(v, "ndim"):
                continue
            if (
                v.ndim == 4
                and v.shape[1] in (legacy_in_channels, spatial_in_channels)
                and "weight" in k
            ):
                return k
        # fallback: first 4D weight
        for k, v in sd.items():
            if hasattr(v, "ndim") and v.ndim == 4 and "weight" in k:
                return k
        return None

    src_fc = _first_conv_key(src_clean)
    dst_fc = _first_conv_key(dst)

    mapped = 0
    if src_fc and dst_fc:
        sw = src_clean[src_fc]
        dw = dst[dst_fc]
        if (
            hasattr(sw, "shape")
            and hasattr(dw, "shape")
            and sw.shape[0] == dw.shape[0]
            and sw.shape[2:] == dw.shape[2:]
        ):
            new_w = dw.clone() if hasattr(dw, "clone") else dw.copy()
            for s_i, l_i in enumerate(FIRST_CONV_SPATIAL_TO_LEGACY):
                if l_i is None:
                    continue
                if s_i >= dw.shape[1] or l_i >= sw.shape[1]:
                    continue
                new_w[:, s_i, :, :] = sw[:, l_i, :, :]
                mapped += 1
            dst[dst_fc] = new_w
            loaded.append(dst_fc)

    # Copy matching non-first-conv tensors
    for k, v in src_clean.items():
        if k == src_fc:
            continue
        if k not in dst:
            continue
        if (
            hasattr(v, "shape")
            and hasattr(dst[k], "shape")
            and tuple(v.shape) == tuple(dst[k].shape)
        ):
            dst[k] = v
            loaded.append(k)

    spatial_model.load_state_dict(dst, strict=False)
    return PartialInitReport(
        mapped_input_channels=mapped,
        total_spatial_input_channels=spatial_in_channels,
        skipped=skipped_idx,
        loaded_keys=sorted(set(loaded)),
    )


def bridge_spec_table() -> list[dict[str, Any]]:
    """Public copy of BRIDGE_SPEC for docs/tests."""
    return [dict(row) for row in BRIDGE_SPEC]


def unwrap_state_dict(obj: Any) -> dict[str, Any]:
    """Normalize checkpoint wrappers → flat state_dict."""
    if not isinstance(obj, dict):
        raise TypeError(f"expected dict checkpoint, got {type(obj)}")
    if "model" in obj and isinstance(obj["model"], dict):
        obj = obj["model"]
    elif "state_dict" in obj and isinstance(obj["state_dict"], dict):
        obj = obj["state_dict"]
    # raw OrderedDict of tensors
    if all(hasattr(v, "shape") or hasattr(v, "dtype") for v in obj.values()):
        return {str(k).replace("module.", ""): v for k, v in obj.items()}
    # nested again?
    for key in ("model", "state_dict", "net"):
        if key in obj and isinstance(obj[key], dict):
            return unwrap_state_dict(obj[key])
    return {str(k).replace("module.", ""): v for k, v in obj.items()}


def export_spatial_init_from_multi_if(
    multi_if_path: str | Any,
    out_path: str | Any,
    *,
    legacy_in_channels: int = 18,
    spatial_in_channels: int = 15,
    model: str = "small",
    architecture: str = "residual",
) -> dict[str, Any]:
    """Build residual-small spatial weights from multi_if and save a full checkpoint.

    The saved file is a **flat state_dict** loadable with
    ``model.load_state_dict(..., strict=True)`` on a spatial (15ch) model.

    Returns report dict (mapped channels, paths, honesty stamps).
    """
    from pathlib import Path as _Path

    import torch

    from wildfire_front.ml.unet_train import UNetTrainConfig, build_model

    in_path = _Path(multi_if_path)
    out_p = _Path(out_path)
    if not in_path.is_file():
        raise FileNotFoundError(f"multi_if weights missing: {in_path}")

    raw = torch.load(str(in_path), map_location="cpu", weights_only=False)
    src = unwrap_state_dict(raw)

    cfg = UNetTrainConfig(model=model, architecture=architecture)
    spatial = build_model(cfg, spatial_in_channels)
    report = map_first_conv_multi_if_to_spatial(
        src,
        spatial,
        legacy_in_channels=legacy_in_channels,
        spatial_in_channels=spatial_in_channels,
    )
    out_p.parent.mkdir(parents=True, exist_ok=True)
    # Save pure state_dict for strict load
    torch.save(spatial.state_dict(), str(out_p))

    # Sanity: reload strict
    spatial2 = build_model(cfg, spatial_in_channels)
    spatial2.load_state_dict(
        torch.load(str(out_p), map_location="cpu", weights_only=True), strict=True
    )

    payload = report.as_dict()
    payload.update(
        {
            "multi_if_path": str(in_path.as_posix()),
            "out_path": str(out_p.as_posix()),
            "legacy_in_channels": legacy_in_channels,
            "spatial_in_channels": spatial_in_channels,
            "strict_reload_ok": True,
            "work_class": "schema_bridge_adapted_init_v1",
            "honesty": (
                "Adapted multi_if→spatial first-conv channel map; "
                "elevation/aspect_sin/cos/wind_sin/cos input filters not fully inherited."
            ),
        }
    )
    return payload


assert list(SPATIAL_V1_NAMES) == list(PHYSICS14_NAMES)
assert len(FIRST_CONV_SPATIAL_TO_LEGACY) == 15
assert len(BRIDGE_SPEC) == 14
