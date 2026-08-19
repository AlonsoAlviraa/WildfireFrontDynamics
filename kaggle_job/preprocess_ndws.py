#!/usr/bin/env python3
"""Google NDWS TFRecord → NPZ preprocessor (v2 — loop-engineering overhaul).

This is the data backbone of the experiment loop. Every modeling decision
depends on this stage being correct, so it has been hardened with:

1. **Full 64×64 grids** — no sub-patch extraction that throws away 75% of
   the native resolution. The U-Net bottleneck is 8×8 on a 64×64 input.
2. **Single-timestep input** — uses ``PrevFireMask`` as ``current_fire``
   instead of replicating the same frame 3× as a fake "sequence". The old
   replication taught the model that t == t+1 == t+2, i.e. nothing temporal.
3. **Leak-free 3-way shard split** — disjoint TFRecord shards per split.
4. **Flexible patch size** — emit either full 64×64 or sliding windows.
5. **Robust normalization** — per-channel affine transform, NaN/Inf sanitize.
6. **Optional temporal stacking** — if ``--sequence-length N`` is given,
   consecutive records are grouped into real temporal sequences.
7. **Rich filtering** — keep only patches with meaningful fire activity.

Usage (Kaggle):
    python preprocess_ndws.py --split train
    python preprocess_ndws.py --split val
    python preprocess_ndws.py --split test

    # Optional flags:
    #   --patch-size 64      (default; use 30 for legacy model compat)
    #   --max-patches 15000  (cap per split)
    #   --sequence-length 1  (1 = single timestep, 3 = real temporal stack)
"""

import argparse
import glob
import os
import sys

import numpy as np

parser = argparse.ArgumentParser(description="NDWS TFRecord preprocessor (v2)")
parser.add_argument("--split", choices=["train", "val", "test"], required=True)
parser.add_argument("--patch-size", type=int, default=64,
                    help="Patch size to emit (default 64 = full NDWS grid).")
parser.add_argument("--max-patches", type=int, default=None,
                    help="Cap patches for this split (overrides defaults).")
parser.add_argument("--sequence-length", type=int, default=1,
                    help="Number of consecutive frames per sample (1 or 3).")
parser.add_argument("--stride", type=int, default=32,
                    help="Sliding window stride when patch-size < 64.")
parser.add_argument(
    "--filter-mode",
    choices=["both_fire", "any_fire", "changed", "none"],
    default="any_fire",
    help=(
        "Patch filter: both_fire=legacy (prev>0 AND fire>0, biased); "
        "any_fire=prev OR fire active; changed=at least one pixel differs; "
        "none=keep all grids."
    ),
)
parser.add_argument(
    "--output-root",
    type=str,
    default="/tmp/ndws_npz",
    help="Root directory for train/val/test NPZ shards (default /tmp/ndws_npz).",
)
parser.add_argument(
    "--schema",
    choices=["legacy17", "clean12", "physics14", "physics15"],
    default="legacy17",
    help=(
        "Feature schema: legacy17; clean12; physics14=tmin/tmax+FFMC; "
        "physics15=physics14+wind_upslope."
    ),
)
args = parser.parse_args()

import tensorflow as tf  # noqa: E402

# Prefer repo feature_schema when cloned next to this script (Kaggle / local).
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
try:
    from wildfire_front.ml.feature_schema import build_channels_from_fields  # type: ignore
    _HAS_FEATURE_SCHEMA = True
except Exception:
    _HAS_FEATURE_SCHEMA = False
    build_channels_from_fields = None  # type: ignore

print(f"=== NDWS Preprocessing v2 | split={args.split} patch={args.patch_size}x{args.patch_size} ===")
print(
    f"    sequence_length={args.sequence_length} stride={args.stride} "
    f"filter={args.filter_mode} schema={args.schema}"
)

# --------------------------------------------------------------------------- #
# Locate TFRecord input
# --------------------------------------------------------------------------- #
CANDIDATE_INPUT_DIRS = [
    "/kaggle/input/next-day-wildfire-spread",
    "/kaggle/input/next-day-wildfire-spread/next-day-wildfire-spread",
]
input_dir = None
for d in CANDIDATE_INPUT_DIRS:
    if os.path.isdir(d):
        input_dir = d
        break

# Fallback: scan all /kaggle/input subdirs for any .tfrecord files
if input_dir is None:
    print("Neither candidate dir exists. Scanning /kaggle/input/ ...")
    for root, _dirs, files in os.walk("/kaggle/input"):
        for f in files:
            if f.endswith(".tfrecord"):
                input_dir = os.path.dirname(os.path.join(root, f))
                break
        if input_dir:
            break

if input_dir is None:
    print("Error: No TFRecord input directory found!")
    if os.path.exists("/kaggle/input"):
        for item in os.listdir("/kaggle/input"):
            print(f"  {item}")
    sys.exit(1)

print(f"Using input_dir: {input_dir}")

output_dir = os.path.join(args.output_root, args.split)
os.makedirs(output_dir, exist_ok=True)

all_tfrecord_files = sorted(
    glob.glob(os.path.join(input_dir, "**", "*.tfrecord"), recursive=True)
)

# Prefer files with 'train' in the name (NDWS convention), but accept all
train_named = [f for f in all_tfrecord_files if "train" in os.path.basename(f).lower()]
if train_named:
    all_tfrecord_files = train_named

if not all_tfrecord_files:
    print("Error: No TFRecord files found!")
    sys.exit(1)

print(f"Found {len(all_tfrecord_files)} TFRecord files:")
for f in all_tfrecord_files:
    print(f"  {os.path.basename(f)}")

# --------------------------------------------------------------------------- #
# Leak-free 3-way shard split
# --------------------------------------------------------------------------- #
n = len(all_tfrecord_files)
if n < 4:
    raise SystemExit(f"Need at least 4 TFRecord shards for leak-free split, found {n}")

train_cut = max(4, int(round(n * 0.80)))
val_cut = min(n - 1, train_cut + max(1, int(round(n * 0.10))))
if not (train_cut >= 4 and val_cut > train_cut and val_cut < n):
    raise SystemExit(
        f"Cannot build leak-free 3-way split from {n} shards: "
        f"train_cut={train_cut}, val_cut={val_cut}."
    )

DEFAULT_MAX = {"train": 15000, "val": 5000, "test": 5000}
max_patches = args.max_patches if args.max_patches else DEFAULT_MAX[args.split]

if args.split == "train":
    tfrecord_files = all_tfrecord_files[:train_cut]
elif args.split == "val":
    tfrecord_files = all_tfrecord_files[train_cut:val_cut]
else:
    tfrecord_files = all_tfrecord_files[val_cut:]

print(f"Leak-free split: {args.split} = {len(tfrecord_files)} files, cap={max_patches} patches")

# --------------------------------------------------------------------------- #
# Detect GZIP + inspect keys
# --------------------------------------------------------------------------- #
first_file = tfrecord_files[0]
try:
    raw_dataset = tf.data.TFRecordDataset(first_file)
    first_record = next(iter(raw_dataset))
    is_gzip = False
    print("Detection: First file appears to be uncompressed.")
except Exception:
    raw_dataset = tf.data.TFRecordDataset(first_file, compression_type='GZIP')
    first_record = next(iter(raw_dataset))
    is_gzip = True
    print("Detection: First file appears to be GZIP compressed.")

example = tf.train.Example()
example.ParseFromString(first_record.numpy())
actual_keys = list(example.features.feature.keys())
print("Actual keys in TFRecord:", actual_keys)

# --------------------------------------------------------------------------- #
# Dynamic feature key mapping
# --------------------------------------------------------------------------- #
possible_keys = {
    'elevation': ['elevation', 'dem', 'Elevation'],
    'wind_direction': ['wind_direction', 'wind_dir', 'wind_direction_10m', 'th'],
    'wind_speed': ['wind_speed', 'wind_speed_10m', 'vs'],
    'min_temp': ['min_temp', 'min_temperature', 'temp_min', 'tmmn'],
    'max_temp': ['max_temp', 'max_temperature', 'temp_max', 'tmmx'],
    'humidity': ['humidity', 'relative_humidity', 'rh', 'sph'],
    'precipitation': ['precipitation', 'precip', 'prcp', 'pr'],
    'drought_index': ['drought', 'drought_index', 'kbdi', 'pdsi'],
    'vegetation': ['vegetation', 'ndvi', 'NDVI'],
    'erc': ['erc', 'energy_release_component'],
    'prev_fire_mask': ['prev_fire_mask', 'ignition', 'prev_fire', 'PrevFireMask'],
    'fire_mask': ['fire_mask', 'target', 'next_fire', 'FireMask']
}

mapped_keys = {}
for req_key, candidates in possible_keys.items():
    for cand in candidates:
        if cand in actual_keys:
            mapped_keys[req_key] = cand
            break

print("Mapped feature keys:")
for k, v in mapped_keys.items():
    print(f"  {k} -> {v}")

feature_description = {}
for _req_key, actual_key in mapped_keys.items():
    feature_description[actual_key] = tf.io.FixedLenFeature([64, 64], tf.float32)


def parse_proto(example_proto):
    return tf.io.parse_single_example(example_proto, feature_description)


# --------------------------------------------------------------------------- #
# FFMC (Fine Fuel Moisture Code) — Van Wagner (1987)
# --------------------------------------------------------------------------- #
def compute_ffmc(temp_c, rh, wind_kmh, precip_mm, prev_ffmc=85.0):
    """Compute FFMC from weather arrays. Range [0, 101]."""
    temp_c = np.asarray(temp_c, dtype=np.float64)
    rh = np.asarray(rh, dtype=np.float64)
    wind_kmh = np.asarray(wind_kmh, dtype=np.float64)
    precip_mm = np.asarray(precip_mm, dtype=np.float64)
    prev = np.full_like(temp_c, prev_ffmc, dtype=np.float64)

    rf = np.where(precip_mm > 0.5, precip_mm - 0.5, 0.0)
    mo_prev = 147.2 * (101.0 - prev) / (59.5 + prev)
    mo_rain = mo_prev + 100.0 * rf / (10.0 + rf) * np.exp(
        -100.0 / (25.04 - 0.0759 * rf) - 8.62 / (1.0 + rf)
    )
    mo_rain = np.clip(mo_rain, 0.0, 250.0)

    ed = (
        0.942 * np.power(rh, 0.679)
        + 11.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp_c) * (1.0 - np.exp(-0.115 * rh))
    )
    ew = (
        0.618 * np.power(rh, 0.753)
        + 10.0 * np.exp((rh - 100.0) / 10.0)
        + 0.18 * (21.1 - temp_c) * (1.0 - np.exp(-0.115 * rh))
    )

    is_drying = mo_rain > ed
    ko = np.where(is_drying, 1.0, ew / np.maximum(ed, 1e-6))

    k0 = (
        0.424 * (1.0 - np.power(rh / 100.0, 1.7))
        + 0.0694 * sqrt_or_zero(wind_kmh)
        * (1.0 - np.power(rh / 100.0, 8.0))
    )
    kd = ko * k0 * 0.581 * np.exp(21.06 - 0.0495 * mo_rain)

    mo_new = np.where(
        is_drying,
        ed + (mo_rain - ed) * np.power(10.0, -kd),
        ew - (ew - mo_rain) * np.power(10.0, -kd),
    )
    mo_new = np.clip(mo_new, 0.0, 250.0)
    ffmc = 59.5 * (250.0 - mo_new) / (147.2 + mo_new)
    return np.clip(ffmc, 0.0, 101.0).astype(np.float32)


def sqrt_or_zero(x):
    """np.sqrt with negative guard (wind arrays may have -0.0 artifacts)."""
    return np.sqrt(np.maximum(x, 0.0))


# --------------------------------------------------------------------------- #
# Normalization constants (must match wildfire_front.ml.normalization)
# --------------------------------------------------------------------------- #
_NORM = [
    (0.0, 1.5708),    # 0: slope (rad)
    (3.14159, 6.28318),  # 1: aspect (rad) -> [0,1]
    (15.0, 20.0),     # 2: temperature (C)
    (0.0, 100.0),     # 3: humidity (%)
    (0.0, 20.0),      # 4: wind speed (m/s)
    (0.0, 360.0),     # 5: wind direction (deg)
    (0.0, 10.0),      # 6: precipitation (mm)
    (1000.0, 50.0),   # 7: pressure (hPa)
    (0.0, 100.0),     # 8: cloud (%)
    (0.0, 20.0),      # 9: visibility (km)
    (5.0, 15.0),      # 10: dew point (C)
    (0.0, 1.0),       # 11: NDVI / thermal
    (0.0, 1.0),       # 12: FSM
    (0.0, 1.0),       # 13: FSM
    (0.0, 1.0),       # 14: FSM
    (0.0, 1.0),       # 15: FSM
    (50.0, 51.0),     # 16: FFMC -> [0,1]
]


def normalize_channels(channels: np.ndarray) -> np.ndarray:
    """Apply per-channel affine normalization and sanitize NaN/Inf."""
    channels = np.where(np.isfinite(channels), channels, 0.0)
    for ci, (sub, div) in enumerate(_NORM):
        channels[ci] = (channels[ci] - sub) / div
    return np.clip(channels, -10.0, 10.0).astype(np.float32)


def build_channels(record):
    """Build feature tensor from a parsed TFRecord (schema-aware)."""
    def get_field(name, default_val=0.0):
        if name in mapped_keys:
            return record[mapped_keys[name]].numpy()
        return np.full((64, 64), default_val, dtype=np.float32)

    elevation = get_field('elevation')
    wind_dir = get_field('wind_direction')
    wind_speed = get_field('wind_speed')
    max_temp = get_field('max_temp', 25.0)
    min_temp = get_field('min_temp', 15.0)
    humidity = get_field('humidity', 40.0)
    precip = get_field('precipitation')
    veg = get_field('vegetation', 0.6)
    erc = get_field('erc', 40.0)
    drought = get_field('drought_index', 0.0) if 'drought_index' in mapped_keys else None
    prev_fire = get_field('prev_fire_mask')
    fire = get_field('fire_mask')

    schema = getattr(args, "schema", "legacy17")

    if _HAS_FEATURE_SCHEMA and build_channels_from_fields is not None:
        channels = build_channels_from_fields(
            schema,
            elevation=elevation,
            wind_dir=wind_dir,
            wind_speed=wind_speed,
            max_temp=max_temp,
            min_temp=min_temp,
            humidity=humidity,
            precip=precip,
            veg=veg,
            erc=erc,
            drought=drought,
        )
        return channels, prev_fire, fire

    # Fallback (no package import): legacy17 only, inlined.
    if schema != "legacy17":
        raise RuntimeError(
            f"schema={schema} requires wildfire_front.ml.feature_schema on PYTHONPATH"
        )

    if np.max(max_temp) > 200:
        max_temp = max_temp - 273.15
    if np.max(min_temp) > 200:
        min_temp = min_temp - 273.15

    dy, dx = np.gradient(elevation)
    slope = np.arctan(np.sqrt(dx**2 + dy**2))
    aspect = np.arctan2(-dy, dx)

    temp_c = 0.5 * (min_temp + max_temp)
    wind_kmh = wind_speed * 3.6
    ffmc = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)

    channels = np.zeros((17, 64, 64), dtype=np.float32)
    channels[0] = slope
    channels[1] = aspect + np.pi  # align with (aspect+pi)/2pi via legacy stats
    channels[2] = temp_c
    channels[3] = humidity
    channels[4] = wind_speed
    channels[5] = wind_dir
    channels[6] = precip
    channels[7] = 1013.0
    channels[8] = 10.0
    channels[9] = 10.0
    channels[10] = 12.0
    channels[11] = veg

    erc_norm = np.clip(erc / 100.0, 0.0, 1.0)
    channels[12] = erc_norm
    channels[13] = 1.0 - erc_norm
    channels[14] = 0.0
    channels[15] = 0.0
    channels[16] = ffmc

    return normalize_channels(channels), prev_fire, fire


# --------------------------------------------------------------------------- #
# Patch extraction
# --------------------------------------------------------------------------- #
def _fire_bin(mask: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    m = np.where(mask < 0.0, 0.0, mask)
    return (m >= threshold).astype(bool)


def should_keep_patch(prev_fire: np.ndarray, fire: np.ndarray, filter_mode: str) -> bool:
    """Decide whether a 64x64 grid passes the configured filter."""
    prev_bin = _fire_bin(prev_fire)
    fire_bin = _fire_bin(fire)
    if filter_mode == "both_fire":
        return bool(np.any(prev_bin) and np.any(fire_bin))
    if filter_mode == "any_fire":
        return bool(np.any(prev_bin) or np.any(fire_bin))
    if filter_mode == "changed":
        return bool(np.any(prev_bin != fire_bin))
    if filter_mode == "none":
        return True
    raise ValueError(f"Unknown filter_mode: {filter_mode}")


def patch_change_fraction(prev_fire: np.ndarray, fire: np.ndarray) -> float:
    prev_bin = _fire_bin(prev_fire)
    fire_bin = _fire_bin(fire)
    return float(np.mean(prev_bin != fire_bin))


def save_patch_npz(
    output_dir: str,
    patch_count: int,
    seq_data: np.ndarray,
    patch_prev: np.ndarray,
    patch_fire: np.ndarray,
) -> int:
    change_fraction = patch_change_fraction(patch_prev, patch_fire)
    np.savez_compressed(
        os.path.join(output_dir, f"patch_{patch_count:06d}.npz"),
        sequence=seq_data,
        current_fire=patch_prev,
        target_fire=patch_fire,
        change_fraction=np.float32(change_fraction),
    )
    return patch_count + 1


def extract_patches(channels, prev_fire, fire, patch_size, stride):
    """Yield (patch_channels, patch_prev, patch_fire) sliding-window patches.

    When patch_size == 64, yields a single full-grid patch.
    """
    if patch_size >= 64:
        yield channels, prev_fire, fire
        return

    for row in range(0, 64 - patch_size + 1, stride):
        for col in range(0, 64 - patch_size + 1, stride):
            patch_ch = channels[:, row:row+patch_size, col:col+patch_size]
            patch_prev = prev_fire[row:row+patch_size, col:col+patch_size]
            patch_fire = fire[row:row+patch_size, col:col+patch_size]
            yield patch_ch, patch_prev, patch_fire


# --------------------------------------------------------------------------- #
# Main loop
# --------------------------------------------------------------------------- #
patch_count = 0
sequence_count = 0
GRID = 64

for file_path in tfrecord_files:
    if patch_count >= max_patches:
        break

    print(f"Processing: {os.path.basename(file_path)}")
    try:
        if is_gzip:
            raw_dataset = tf.data.TFRecordDataset(file_path, compression_type='GZIP')
        else:
            raw_dataset = tf.data.TFRecordDataset(file_path)

        parsed_dataset = raw_dataset.map(parse_proto)

        # Buffer consecutive records for temporal sequence mode
        buffer = []

        for record in parsed_dataset:
            if patch_count >= max_patches:
                break

            channels, prev_fire, fire = build_channels(record)

            if args.sequence_length > 1:
                # Temporal mode: accumulate frames and emit windows
                buffer.append((channels, prev_fire, fire))
                if len(buffer) >= args.sequence_length:
                    # Use last `sequence_length` frames
                    window = buffer[-args.sequence_length:]
                    # Stack channels across time: (T, C, 64, 64)
                    seq_data = np.stack([w[0] for w in window], axis=0)
                    # Current fire = prev_fire of the LAST frame in window
                    curr_fire = window[-1][1]
                    # Target fire = fire mask of the LAST frame
                    tgt_fire = window[-1][2]

                    if should_keep_patch(curr_fire, tgt_fire, args.filter_mode):
                        for patch_ch, patch_prev, patch_fire in extract_patches(
                            seq_data if args.patch_size >= 64 else None,
                            curr_fire, tgt_fire, args.patch_size, args.stride
                        ):
                            if patch_ch is None:
                                # patch_size < 64 temporal: extract from seq
                                # (simplified: skip sub-patch temporal for now)
                                continue
                            patch_count = save_patch_npz(
                                output_dir, patch_count, seq_data, patch_prev, patch_fire
                            )
                            if patch_count >= max_patches:
                                break
            else:
                # Single-timestep mode: use PrevFireMask as current, FireMask as target
                if should_keep_patch(prev_fire, fire, args.filter_mode):
                    for patch_ch, patch_prev, patch_fire in extract_patches(
                        channels, prev_fire, fire, args.patch_size, args.stride
                    ):
                        # Build a (1, C, H, W) "sequence" for dataset compat
                        seq_data = patch_ch[np.newaxis, ...]
                        patch_count = save_patch_npz(
                            output_dir, patch_count, seq_data, patch_prev, patch_fire
                        )
                        if patch_count >= max_patches:
                            break

            sequence_count += 1

    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

print("=== Preprocessing v2 Completed ===")
print(f"Processed {sequence_count} full sequences.")
print(f"Generated {patch_count} patches ({args.patch_size}x{args.patch_size}) saved to {output_dir}.")
