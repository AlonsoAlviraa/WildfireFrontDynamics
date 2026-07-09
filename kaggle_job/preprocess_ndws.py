import os
import sys
import glob
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--split", choices=["train", "val", "test"], required=True)
args = parser.parse_args()

import tensorflow as tf

print(f"=== Starting Google NDWS TFRecord Preprocessing for split: {args.split} ===")

# Paths on Kaggle — search multiple possible locations
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
    print(f"Neither candidate dir exists. Scanning /kaggle/input/ ...")
    for root, dirs, files in os.walk("/kaggle/input"):
        for f in files:
            if f.endswith(".tfrecord"):
                input_dir = os.path.dirname(os.path.join(root, f))
                break
        if input_dir:
            break

if input_dir is None:
    print("Error: No input directory with TFRecord files found!")
    print("Contents of /kaggle/input/:")
    if os.path.exists("/kaggle/input"):
        for item in os.listdir("/kaggle/input"):
            print(f"  {item}")
    sys.exit(1)

print(f"Using input_dir: {input_dir}")

# List contents for debugging
print(f"Contents of {input_dir}:")
for item in sorted(os.listdir(input_dir)):
    print(f"  {item}")

output_dir = os.path.join("/tmp/ndws_npz", args.split)
os.makedirs(output_dir, exist_ok=True)

# Find all tfrecord files (recursive — NDWS may nest them in subdirs)
all_tfrecord_files = sorted(glob.glob(os.path.join(input_dir, "**", "*.tfrecord"), recursive=True))

# Prefer files with 'train' in the name (NDWS convention), but accept all
train_named = [f for f in all_tfrecord_files if "train" in os.path.basename(f).lower()]
if train_named:
    all_tfrecord_files = train_named

if not all_tfrecord_files:
    print("Error: No TFRecord files found!")
    print(f"Searched: {input_dir}/**/*.tfrecord")
    sys.exit(1)

print(f"Found {len(all_tfrecord_files)} TFRecord files:")
for f in all_tfrecord_files:
    print(f"  {os.path.basename(f)}")

# --- LEAK-FREE 3-WAY SPLIT -----------------------------------------------
# NDWS ships ~15 tfrecord shards. We partition them into disjoint groups so
# that NO shard (and therefore NO fire event) appears in more than one split.
# This is the strongest guarantee against temporal/geographic leakage.
#
#   train : shards  0..11  (12 files)  -> up to 80k patches
#   val   : shards 12..13  ( 2 files)  -> up to 15k patches  (model selection)
#   test  : shards 14..    ( 1+ files) -> up to 15k patches  (unseen evaluation)
n = len(all_tfrecord_files)
if n < 4:
    raise SystemExit(f"Need at least 4 TFRecord shards for a leak-free 3-way split, found {n}")

# Robust leak-free 3-way split: guarantee train>=4, val>=1, test>=1 even when
# the shard count is small (n<15). The old `max(12, ...)` forced train_cut=12
# for any n<15, which silently collapsed val to EMPTY (a data-leak / no-val bug).
train_cut = max(4, int(round(n * 0.80)))                       # ~80% train, min 4
val_cut = min(n - 1, train_cut + max(1, int(round(n * 0.10))))  # ~10% val, keep >=1 for test
if not (train_cut >= 4 and val_cut > train_cut and val_cut < n):
    raise SystemExit(
        f"Cannot build leak-free 3-way split from {n} shards: "
        f"train_cut={train_cut}, val_cut={val_cut}. Need more shards."
    )

if args.split == "train":
    tfrecord_files = all_tfrecord_files[:train_cut]
    max_patches = 12000  # Reduced from 80k — 80k took 9910s/epoch (2.75h!), infeasible in 9h Kaggle
elif args.split == "val":
    tfrecord_files = all_tfrecord_files[train_cut:val_cut]
    max_patches = 5000
else:  # test
    tfrecord_files = all_tfrecord_files[val_cut:]
    max_patches = 5000

print(f"Leak-free split: {args.split} = shards [{0 if args.split=='train' else train_cut if args.split=='val' else val_cut}"
      f"..{train_cut if args.split=='train' else val_cut if args.split=='val' else n}] "
      f"({len(tfrecord_files)} files, cap={max_patches} patches)")

# Inspect keys of the first file in this split
first_file = tfrecord_files[0]
raw_dataset = tf.data.TFRecordDataset(first_file)
# Try uncompressed, fallback to GZIP
try:
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

# Define candidates for mapping
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

# Build feature description dynamically
feature_description = {}
for req_key, actual_key in mapped_keys.items():
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
        + 0.0694 * np.sqrt(np.maximum(wind_kmh, 0.0))
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


patch_count = 0
sequence_count = 0

# Read files and extract patches
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

        for record in parsed_dataset:
            if patch_count >= max_patches:
                break

            # Helper to get parsed field or return zeros
            def get_field(name, default_val=0.0):
                if name in mapped_keys:
                    return record[mapped_keys[name]].numpy()
                return np.full((64, 64), default_val, dtype=np.float32)

            # Extract features dynamically
            elevation = get_field('elevation')
            wind_dir = get_field('wind_direction')
            wind_speed = get_field('wind_speed')
            max_temp = get_field('max_temp', default_val=25.0)
            min_temp = get_field('min_temp', default_val=15.0)
            humidity = get_field('humidity', default_val=40.0)
            precip = get_field('precipitation')
            veg = get_field('vegetation', default_val=0.6)
            erc = get_field('erc', default_val=40.0)
            prev_fire = get_field('prev_fire_mask')
            fire = get_field('fire_mask')

            # --- CRITICAL FIX: Convert NDWS Kelvin temperatures to Celsius ---
            # NDWS ships temperatures in Kelvin (~250-330K). Using them as-is
            # caused a 10x magnitude mismatch that overflowed fp16 → NaN loss.
            # Heuristic: if values > 200, assume Kelvin and subtract 273.15.
            if np.max(max_temp) > 200:
                max_temp = max_temp - 273.15
            if np.max(min_temp) > 200:
                min_temp = min_temp - 273.15

            # Compute slope and aspect from elevation using numpy gradients
            dy, dx = np.gradient(elevation)
            slope = np.arctan(np.sqrt(dx**2 + dy**2))
            aspect = np.arctan2(-dy, dx)

            # Compute FFMC (channel 16) — #1 predictor of ignition probability
            temp_c = 0.5 * (min_temp + max_temp)
            wind_kmh = wind_speed * 3.6  # m/s -> km/h for FFMC formula
            ffmc = compute_ffmc(temp_c, humidity, wind_kmh, precip, prev_ffmc=85.0)

            # Build 17 channels (channel 16 = FFMC for physics-informed loss)
            channels = np.zeros((17, 64, 64), dtype=np.float32)
            channels[0] = slope
            channels[1] = aspect
            channels[2] = temp_c          # Average temperature
            channels[3] = humidity
            channels[4] = wind_speed
            channels[5] = wind_dir
            channels[6] = precip
            channels[7] = 1013.0          # Default pressure
            channels[8] = 10.0            # Default cloud cover
            channels[9] = 10.0            # Default visibility
            channels[10] = 12.0           # Default dew point
            channels[11] = veg            # NDVI

            # FSM (One-hot mapping or susceptibility proxy based on normalized ERC)
            erc_norm = np.clip(erc / 100.0, 0.0, 1.0)
            channels[12] = erc_norm
            channels[13] = 1.0 - erc_norm
            channels[14] = 0.0
            channels[15] = 0.0
            channels[16] = ffmc           # Fine Fuel Moisture Code (Sprint 4)

            # --- CRITICAL FIX: Normalize ALL channels to ~[0,1] before saving ---
            # Without this, pressure=1013 vs slope=0.3 causes a 3-order-of-magnitude
            # spread that overflows fp16 (AMP) → NaN loss on epoch 1.
            # Sanitize NaN/Inf first, then apply per-channel affine transform.
            channels = np.where(np.isfinite(channels), channels, 0.0)
            _NORM = [
                (0.0, 1.5708), (3.14159, 6.28318), (15.0, 20.0), (0.0, 100.0),
                (0.0, 20.0), (0.0, 360.0), (0.0, 10.0), (1000.0, 50.0),
                (0.0, 100.0), (0.0, 20.0), (5.0, 15.0), (0.0, 1.0),
                (0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (50.0, 51.0),
            ]
            for _ci, (_sub, _div) in enumerate(_NORM):
                channels[_ci] = (channels[_ci] - _sub) / _div
            channels = np.clip(channels, -10.0, 10.0).astype(np.float32)

            # Extract sliding patches of 30x30 to fit our model's input expectations
            # Strides of 10 over the 64x64 grid
            for row in [0, 10, 20, 34]:
                for col in [0, 10, 20, 34]:
                    patch_prev_fire = prev_fire[row:row+30, col:col+30]
                    patch_fire = fire[row:row+30, col:col+30]

                    # Only save patches that contain active fire spreading transitions
                    if np.sum(patch_prev_fire) > 0 and np.sum(patch_fire) > 0:
                        patch_channels = channels[:, row:row+30, col:col+30]

                        # Replicate channels 3 times to build the temporal sequence length of 3
                        sequence_data = np.stack([patch_channels] * 3, axis=0)

                        # Save the patch data
                        np.savez_compressed(
                            os.path.join(output_dir, f"patch_{patch_count:06d}.npz"),
                            sequence=sequence_data,
                            current_fire=patch_prev_fire,
                            target_fire=patch_fire
                        )
                        patch_count += 1

            sequence_count += 1

    except Exception as e:
        print(f"Error reading file {file_path}: {e}")

print(f"=== Preprocessing Completed ===")
print(f"Processed {sequence_count} full sequences.")
print(f"Generated {patch_count} active 30x30 patches saved to {output_dir}.")