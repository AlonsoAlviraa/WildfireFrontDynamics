#!/usr/bin/env bash
set -euo pipefail

echo "$$" > /home/Mariano/final.pid
sudo shutdown -h +3600 >/dev/null 2>&1 || true

export OMP_NUM_THREADS="${OMP_NUM_THREADS:-32}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-32}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-32}"
export NUMEXPR_NUM_THREADS="${NUMEXPR_NUM_THREADS:-32}"
export PYTHONUNBUFFERED=1

dataset=/kaggle/input/wfd-rcda-archive/dataset
protocol=/kaggle/input/wfd-rcda-sealed/protocol
runner=/home/Mariano/run_rcda_paper_final.py

if [[ ! -d "$dataset" ]] || [[ ! -d "$protocol" ]]; then
  echo "RCDA dataset or sealed protocol is missing" >&2
  exit 2
fi
if [[ ! -f "$runner" ]]; then
  echo "Frozen final runner is missing: $runner" >&2
  exit 2
fi

mkdir -p /kaggle/working/rcda_paper_final
python3 "$runner"
