#!/usr/bin/env python3
"""Push parallel Kaggle LOFO grid shards (max GPU utilization)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "kaggle_job" / "run_metrics_lift_lofo_grid.py"
TMP = Path(r"C:\Users\Mariano\AppData\Local\Temp")

SHARDS = {
    "a": "v2_anchor,long_lowlr_multi_if,long_lowlr_acom2_heavy,v30_ema_mid,v28_clm_ft",
    "b": "multi_if_r8,warm_recover_v2,batch16_lr1e4,lr2e4_short_patience,growth_extreme_acom2",
    "c": "mild_growth_balanced,v21_ndws_init,force_train_multi_if,warm_v2_acom2_extreme",
}


def main() -> int:
    src = SRC.read_text(encoding="utf-8")
    lines = src.splitlines(True)
    for name, ids in SHARDS.items():
        kd = TMP / f"wfd_grid_{name}"
        if kd.exists():
            shutil.rmtree(kd)
        kd.mkdir(parents=True)
        boot = f"import os as _os_boot\n_os_boot.environ.setdefault('WF_CONFIG_IDS', '{ids}')\n"
        body = lines[0] + boot + "".join(lines[1:])
        (kd / "run_metrics_lift_lofo_grid.py").write_text(body, encoding="utf-8", newline="\n")
        meta = {
            "id": f"alonsoalviraaaa/wfd-metrics-lift-lofo-grid-{name}",
            "title": f"WFD Metrics Lift LOFO Grid {name}",
            "code_file": "run_metrics_lift_lofo_grid.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "machine_shape": "NvidiaTeslaT4",
            "dataset_sources": ["alonsoalviraaaa/wfd-lofo-grid-inits"],
            "competition_sources": [],
            "kernel_sources": [],
        }
        (kd / "kernel-metadata.json").write_bytes(
            (json.dumps(meta, indent=2) + "\n").encode("ascii")
        )
        print(f"PUSH shard={name} ids={ids}", flush=True)
        r = subprocess.run(
            ["kaggle", "kernels", "push", "-p", str(kd)],
            capture_output=True,
            text=True,
        )
        print(r.stdout or "", flush=True)
        print(r.stderr or "", flush=True)
        if r.returncode != 0:
            print(f"push failed rc={r.returncode}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
