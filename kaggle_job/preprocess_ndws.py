import os
import sys
import glob
import numpy as np
import tensorflow as tf

print("=== Starting Google NDWS TFRecord Preprocessing ===")

# Define the features present in the TFRecords
feature_description = {
    'elevation': tf.io.FixedLenFeature([64, 64], tf.float32),
    'wind_direction': tf.io.FixedLenFeature([64, 64], tf.float32),
    'wind_speed': tf.io.FixedLenFeature([64, 64], tf.float32),
    'min_temp': tf.io.FixedLenFeature([64, 64], tf.float32),
    'max_temp': tf.io.FixedLenFeature([64, 64], tf.float32),
    'humidity': tf.io.FixedLenFeature([64, 64], tf.float32),
    'precipitation': tf.io.FixedLenFeature([64, 64], tf.float32),
    'drought_index': tf.io.FixedLenFeature([64, 64], tf.float32),
    'vegetation': tf.io.FixedLenFeature([64, 64], tf.float32),
    'population_density': tf.io.FixedLenFeature([64, 64], tf.float32),
    'erc': tf.io.FixedLenFeature([64, 64], tf.float32),
    'prev_fire_mask': tf.io.FixedLenFeature([64, 64], tf.float32),
    'fire_mask': tf.io.FixedLenFeature([64, 64], tf.float32),
}

def parse_proto(example_proto):
    return tf.io.parse_single_example(example_proto, feature_description)

# Paths on Kaggle
input_dir = "/kaggle/input/next-day-wildfire-spread"
output_dir = "/tmp/ndws_npz"
os.makedirs(output_dir, exist_ok=True)

# Find all training tfrecords
tfrecord_files = sorted(glob.glob(os.path.join(input_dir, "*train*.tfrecord")))
if not tfrecord_files:
    # Fallback to check any tfrecords if naming is different
    tfrecord_files = sorted(glob.glob(os.path.join(input_dir, "*.tfrecord")))

print(f"Found {len(tfrecord_files)} TFRecord files to process.")

patch_count = 0
sequence_count = 0
max_patches = 12000  # Cap the total number of patches to prevent disk/time overflow

# Read files and extract patches
for file_path in tfrecord_files:
    if patch_count >= max_patches:
        break
    
    print(f"Processing: {os.path.basename(file_path)}")
    try:
        # Google NDWS TFRecords are GZIP compressed
        raw_dataset = tf.data.TFRecordDataset(file_path, compression_type='GZIP')
        parsed_dataset = raw_dataset.map(parse_proto)
        
        for record in parsed_dataset:
            if patch_count >= max_patches:
                break
            
            # Extract features as numpy arrays
            elevation = record['elevation'].numpy()
            wind_dir = record['wind_direction'].numpy()
            wind_speed = record['wind_speed'].numpy()
            max_temp = record['max_temp'].numpy()
            min_temp = record['min_temp'].numpy()
            humidity = record['humidity'].numpy()
            precip = record['precipitation'].numpy()
            veg = record['vegetation'].numpy()
            erc = record['erc'].numpy()
            prev_fire = record['prev_fire_mask'].numpy()
            fire = record['fire_mask'].numpy()
            
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
            # Normalize ERC to [0, 1] range to serve as fuel susceptibility channel 0
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
