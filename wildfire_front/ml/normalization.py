"""Channel normalization for the 17-channel wildfire input tensor.

This module provides a **single source of truth** for normalizing the
multimodal input channels of ``A3C_PerCellModel_LSTM``.

Problem (root cause of NaN loss)
---------------------------------
The raw NDWS TFRecords and the local GeoTIFF pipeline feed values with
wildly different magnitudes into the same tensor:

    | Channel        | Raw range          | Example      |
    |----------------|--------------------|--------------|
    | slope (rad)    | 0 – π/2            | 0.3          |
    | temperature    | 250-330 K (!)      | 300          |
    | humidity       | 0 – 100 %          | 45           |
    | pressure       | 900 – 1050 hPa     | 1013         |
    | wind direction | 0 – 360 deg        | 180          |
    | FFMC           | 0 – 101            | 88           |
    | NDVI           | -1 – 1             | 0.6          |

A 3-order-of-magnitude spread causes the first Conv2d to explode activations,
which under fp16 (AMP on T4) overflows to ``inf`` → ``NaN`` in one step.

Solution
--------
Every channel is mapped to approximately ``[0, 1]`` (or ``[-1, 1]`` for
z-scored signals) **before** entering the model.  The constants below are
derived from the physical ranges of each variable.
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------------- #
# Per-channel normalization constants
# --------------------------------------------------------------------------- #
# Each entry: (subtract, divide_by)
# normalized = (raw - subtract) / divide_by
#
# Values chosen so the normalized output lands in ~[0, 1] or ~[-3, 3].
_CHANNEL_STATS: list[tuple[float, float]] = [
    # 0: slope (radians, 0 to π/2)
    (0.0, 1.5708),  # divide by π/2
    # 1: aspect (radians, -π to π) → shift to [0, 2π] then scale
    (3.14159, 6.28318),  # (aspect + π) / 2π
    # 2: temperature (Celsius, -10 to 50)
    (15.0, 20.0),  # (temp - 15) / 20
    # 3: humidity (%, 0-100)
    (0.0, 100.0),
    # 4: wind speed (m/s, 0-30+)
    (0.0, 20.0),
    # 5: wind direction (degrees, 0-360)
    (0.0, 360.0),
    # 6: precipitation (mm, 0-50+)
    (0.0, 10.0),
    # 7: pressure (hPa, 900-1050)
    (1000.0, 50.0),  # (p - 1000) / 50
    # 8: cloud cover (%, 0-100)
    (0.0, 100.0),
    # 9: visibility (km, 0-50+)
    (0.0, 20.0),
    # 10: dew point (°C, -20 to 30)
    (5.0, 15.0),
    # 11: thermal/NDVI (already z-scored or [-1, 1])
    (0.0, 1.0),
    # 12-15: FSM one-hot (already 0 or 1)
    (0.0, 1.0),
    (0.0, 1.0),
    (0.0, 1.0),
    (0.0, 1.0),
    # 16: FFMC (0-101)
    (50.0, 51.0),  # (ffmc - 50) / 51 → ~[0, 1]
]


def normalize_channels(channels: np.ndarray) -> np.ndarray:
    """Normalize a (17, H, W) array channel-by-channel to ~[0, 1].

    Args:
        channels: Raw float32 array of shape (17, H, W).

    Returns:
        Normalized array of same shape. NaN/Inf values are replaced with 0
        before normalization to prevent cascade corruption.
    """
    # Sanitize NaN/Inf FIRST — replace with 0 to prevent propagation
    channels = np.where(np.isfinite(channels), channels, 0.0)

    normalized = channels.copy()
    for ch_idx, (sub, div) in enumerate(_CHANNEL_STATS):
        normalized[ch_idx] = (channels[ch_idx] - sub) / div

    # Final safety clamp: no value should exceed ±10 after normalization
    normalized = np.clip(normalized, -10.0, 10.0)

    return normalized.astype(np.float32)


def normalize_channels_inplace(channels: np.ndarray) -> np.ndarray:
    """In-place variant for memory-constrained environments (Kaggle).

    Modifies ``channels`` directly and returns it.
    """
    # Sanitize NaN/Inf
    np.copyto(channels, 0.0, where=~np.isfinite(channels))
    for ch_idx, (sub, div) in enumerate(_CHANNEL_STATS):
        channels[ch_idx] = (channels[ch_idx] - sub) / div
    np.clip(channels, -10.0, 10.0, out=channels)
    return channels
