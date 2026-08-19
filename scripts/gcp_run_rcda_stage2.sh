#!/usr/bin/env bash
set -euo pipefail

echo "$$" > "$HOME/stage2.pid"
sudo shutdown -h +3600 >/dev/null 2>&1 || true

sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3-pip p7zip-full unrar curl
python3 -m pip install --user --quiet torch scipy numpy
sudo mkdir -p /kaggle/working
sudo chown -R "$(id -un):$(id -gn)" /kaggle

archive="/kaggle/cache/rcda_dataset.rar"
archive_url="https://zenodo.org/records/16641619/files/dataset.rar?download=1"
expected_md5="d7856d77dcb823d0bdb5e10c6bac4f87"
extract_root="/kaggle/input/wfd-rcda-archive"
dataset_root="$extract_root/dataset"
mkdir -p "$(dirname "$archive")" "$extract_root"
if [[ ! -f "$archive" ]] || [[ "$(md5sum "$archive" | cut -d' ' -f1)" != "$expected_md5" ]]; then
  curl -L -C - "$archive_url" -o "$archive"
fi
if [[ ! -f "$archive" ]] || [[ "$(md5sum "$archive" | cut -d' ' -f1)" != "$expected_md5" ]]; then
  echo "RCDA archive MD5 mismatch after resume" >&2
  exit 1
fi
dataset_ready=true
if ! find "$dataset_root" -type f -path '*/train/inputs/*.npy' -print -quit 2>/dev/null | grep -q .; then
  dataset_ready=false
fi
if find "$dataset_root" -type f -name '*.npy' -size 0 -print -quit 2>/dev/null | grep -q .; then
  dataset_ready=false
fi
if [[ "$dataset_ready" != "true" ]]; then
  unrar x -o+ "$archive" "$extract_root/"
fi
if find "$dataset_root" -type f -name '*.npy' -size 0 -print -quit | grep -q .; then
  echo "RCDA extraction contains empty NPY files" >&2
  exit 1
fi

export RCDA_ALLOW_ZENODO=1
export RCDA_STAGE2_RUNS="${RCDA_STAGE2_RUNS:-resunet_hybrid_long_v2}"
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
python3 "$HOME/run_rcda_paper_stage2.py"
