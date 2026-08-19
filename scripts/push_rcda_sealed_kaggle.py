"""Stage protocol + trainer and push the sealed RCDA Kaggle kernel."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "kaggle_job/_push_rcda_sealed"
DATASET_STAGE = ROOT / "kaggle_job/_push_rcda_dataset"


def _run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def stage_dataset() -> Path:
    if DATASET_STAGE.exists():
        shutil.rmtree(DATASET_STAGE)
    proto = DATASET_STAGE / "protocol"
    proto.mkdir(parents=True)
    src = ROOT / "data/external/rcda_net_full/protocol"
    for name in (
        "train.json",
        "val.json",
        "test.json",
        "normalization_train_only.json",
    ):
        shutil.copy2(src / name, proto / name)
        shutil.copy2(src / name, DATASET_STAGE / name)
    (DATASET_STAGE / "dataset-metadata.json").write_text(
        json.dumps(
            {
                "title": "WFD RCDA sealed protocol",
                "id": "alonsoalvira/wfd-rcda-sealed",
                "licenses": [{"name": "other"}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (DATASET_STAGE / "README.md").write_text(
        "Event-disjoint RCDA TRAIN/VAL/TEST manifests. "
        "The image tensors are loaded from Zenodo record 16641619 inside the kernel.\n",
        encoding="utf-8",
    )
    return DATASET_STAGE


def _protocol_blobs() -> dict[str, str]:
    import base64
    import gzip

    src = ROOT / "data/external/rcda_net_full/protocol"
    blobs: dict[str, str] = {}
    for name in (
        "train.json",
        "val.json",
        "test.json",
        "normalization_train_only.json",
    ):
        raw = (src / name).read_bytes()
        blobs[name] = base64.b64encode(gzip.compress(raw, compresslevel=9)).decode("ascii")
    return blobs


def _self_contained_kernel() -> str:
    library = (ROOT / "wildfire_front/ml/rcda_sealed.py").read_text(encoding="utf-8")
    extra = (ROOT / "kaggle_job/run_rcda_sealed_train.py").read_text(encoding="utf-8")
    start = extra.index("ZENODO_URL")
    end = extra.index("def main() -> int:")
    helpers = extra[start:end]
    blobs = json.dumps(_protocol_blobs(), indent=2)
    return f'''{library.rstrip()}

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

{helpers}
PROTOCOL_BLOBS = {blobs}

def main() -> int:
    output = Path(os.environ.get("RCDA_OUTPUT", "/kaggle/working/rcda_sealed"))
    output.mkdir(parents=True, exist_ok=True)
    if Path("/kaggle/input").exists():
        tree = dump_input_tree(Path("/kaggle/input"))
        print("KAGGLE_INPUT_TREE\\n" + "\\n".join(tree), flush=True)
        (output / "input_tree.txt").write_text("\\n".join(tree) + "\\n", encoding="utf-8")
    dataset = locate_dataset()
    protocol = locate_protocol(Path("/kaggle/input/wfd-rcda-sealed"))
    boot = {{
        "schema": "wfd_rcda_sealed_boot_v1",
        "dataset": str(dataset),
        "protocol": str(protocol),
        "n_train_inputs": len(list((dataset / "train" / "inputs").glob("*.npy"))),
        "protocol_files": sorted(path.name for path in protocol.glob("*.json")),
    }}
    (output / "boot.json").write_text(json.dumps(boot, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps(boot, indent=2), flush=True)
    smoke = os.environ.get("RCDA_SMOKE", "0") == "1"
    epochs = int(os.environ.get("RCDA_EPOCHS", "2" if smoke else "16"))
    models = os.environ.get("RCDA_MODELS", "unet,rcda").split(",")
    seeds = [int(item) for item in os.environ.get("RCDA_SEEDS", "0").split(",")]
    reports = []
    for model_name in models:
        for seed in seeds:
            config = SealedTrainConfig(
                dataset_root=str(dataset),
                protocol_dir=str(protocol),
                output_dir=str(output),
                model_name=model_name.strip(),
                seed=seed,
                epochs=epochs,
                batch_size=int(os.environ.get("RCDA_BATCH", "4" if smoke else "8")),
                smoke=smoke,
                max_train_samples=8 if smoke else None,
                max_eval_samples=8 if smoke else None,
                num_workers=0 if smoke else 2,
            )
            reports.append(train_sealed(config))
    summary = {{
        "schema": "wfd_rcda_sealed_kaggle_v1",
        "dataset": str(dataset),
        "protocol": str(protocol),
        "models": reports,
        "test_used_for_selection": False,
        "not_claims": [
            "not a published RCDA reproduction of the contaminated TEST protocol",
            "Caldor is holdout-only and is not used here",
            "legacy17 weights were not loaded",
        ],
    }}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\\n", encoding="utf-8")
    print(json.dumps({{"n_reports": len(reports), "output": str(output)}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def stage_kernel() -> Path:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    (STAGE / "run_rcda_sealed_train.py").write_text(
        _self_contained_kernel(), encoding="utf-8"
    )
    shutil.copy2(
        ROOT / "kaggle_job/kernel-metadata-rcda-sealed.json",
        STAGE / "kernel-metadata.json",
    )
    proto = STAGE / "protocol"
    proto.mkdir()
    src = ROOT / "data/external/rcda_net_full/protocol"
    for name in (
        "train.json",
        "val.json",
        "test.json",
        "normalization_train_only.json",
    ):
        shutil.copy2(src / name, proto / name)
    return STAGE


def dataset_exists(slug: str) -> bool:
    result = subprocess.run(
        ["kaggle", "datasets", "list", "--mine", "-s", slug.split("/")[-1], "-v"],
        capture_output=True,
        text=True,
    )
    return slug.split("/")[-1] in (result.stdout or "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-dataset", action="store_true")
    parser.add_argument("--skip-kernel", action="store_true")
    args = parser.parse_args()
    if not args.skip_dataset:
        dataset = stage_dataset()
        slug = "alonsoalvira/wfd-rcda-sealed"
        if dataset_exists(slug):
            _run(
                [
                    "kaggle",
                    "datasets",
                    "version",
                    "-p",
                    str(dataset),
                    "--dir-mode",
                    "zip",
                    "-m",
                    "sealed protocol manifests",
                ]
            )
        else:
            _run(
                [
                    "kaggle",
                    "datasets",
                    "create",
                    "-p",
                    str(dataset),
                    "--dir-mode",
                    "zip",
                ]
            )
    if not args.skip_kernel:
        kernel = stage_kernel()
        _run(["kaggle", "kernels", "push", "-p", str(kernel)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
