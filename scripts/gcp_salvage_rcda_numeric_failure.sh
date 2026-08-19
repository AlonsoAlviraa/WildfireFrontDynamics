#!/usr/bin/env bash
set -euo pipefail

FAILED_PID="${1:?failed training pid is required}"
echo "$$" > "$HOME/stage2.pid"
kill "${FAILED_PID}" 2>/dev/null || true
for _attempt in $(seq 1 30); do
  if ! kill -0 "${FAILED_PID}" 2>/dev/null; then
    break
  fi
  sleep 1
done
if kill -0 "${FAILED_PID}" 2>/dev/null; then
  echo "failed process ${FAILED_PID} did not terminate" >&2
  exit 1
fi

python3 "$HOME/salvage_rcda_numeric_failure.py" \
  --runner "$HOME/run_rcda_paper_stage2.py" \
  --dataset-root /kaggle/input/wfd-rcda-archive/dataset \
  --protocol-dir /kaggle/working/rcda_protocol \
  --output-dir /kaggle/working/rcda_paper_stage2 \
  --run-name resunet_hybrid_long_v2 \
  --failed-epoch 16 \
  --observed-loss nan
