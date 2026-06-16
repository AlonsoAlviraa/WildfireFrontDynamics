import os
import sys
import glob
import numpy as np
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--split", choices=["train", "val"], required=True)
args = parser.parse_args()

import tensorflow as tf

print(f"=== Starting Google NDWS TFRecord Preprocessing for split: {args.split} ===")

# Paths on Kaggle
input_dir = "/kaggle/input/next-day-wildfire-spread"
output_dir = os.path.join("/tmp/ndws_npz", args.split)
os.makedirs(output_dir, exist_ok=True)

# Find all training tfrecords
all_tfrecord_files = sorted(glob.glob(os.path.join(input_dir, "*train*.tfrecord")))
if not all_tfrecord_files:
    all_tfrecord_files = sorted(glob.glob(os.path.join(input_dir, "*.tfrecord")))

if not all_tfrecord_files:
    print("Error: No TFRecord files found!")
    sys.exit(1)

# Distribute tfrecord files to avoid train-validation leakage
if args.split == "train":
    tfrecord_files = all_tfrecord_files[:13]
    max_patches = 80000
else:
    tfrecord_files = all_tfrecord_files[13:]
    max_patches = 15000

print(f"Split {args.split} contains {len(tfrecord_files)} files. Limit set to {max_patches} patches.")

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
            
            # Compute slope and aspect from elevation using numpy gradients
            dy, dx = np.gradient(elevation)
            slope = np.arctan(np.sqrt(dx**2 + dy**2))
            aspect = np.arctan2(-dy, dx)
            
            # Build 16 channels
            channels = np.zeros((16, 64, 64), dtype=np.float32)
            channels[0] = slope
            channels[1] = aspect
            channels[2] = 0.5 * (min_temp + max_temp) # Average temperature
            channels[3] = humidity
            channels[4] = wind_speed
            channels[5] = wind_dir
            channels[6] = precip
            channels[7] = 1013.0 # Default pressure
            channels[8] = 10.0   # Default cloud cover
            channels[9] = 10.0   # Default visibility
            channels[10] = 12.0  # Default dew point
            channels[11] = veg   # NDVI
            
            # FSM (One-hot mapping or susceptibility proxy based on normalized ERC)
            erc_norm = np.clip(erc / 100.0, 0.0, 1.0)
            channels[12] = erc_norm
            channels[13] = 1.0 - erc_norm
            channels[14] = 0.0
            channels[15] = 0.0
            
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
