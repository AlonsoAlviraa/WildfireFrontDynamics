"""Kaggle entry: sealed RCDA/U-Net train + dilated-copy on the same TEST."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_CANDIDATES = [
    Path(__file__).resolve().parent,
    Path("/tmp/WildfireFrontDynamics"),
    Path("/kaggle/working/WildfireFrontDynamics"),
    Path(__file__).resolve().parents[1] if len(Path(__file__).resolve().parents) > 1 else Path("."),
]
ZENODO_URL = "https://zenodo.org/records/16641619/files/dataset.rar?download=1"
PUBLISHED_MD5 = "d7856d77dcb823d0bdb5e10c6bac4f87"
PROTOCOL_FILES = (
    "train.json",
    "val.json",
    "test.json",
    "normalization_train_only.json",
)
SMALL_ZIP_BYTES = 50 * 1024 * 1024
PROTOCOL_BLOBS: dict[str, str] = {}


def _ensure_repo() -> Path:
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    for candidate in ROOT_CANDIDATES:
        sealed = candidate / "wildfire_front" / "ml" / "rcda_sealed.py"
        if sealed.is_file():
            sys.path.insert(0, str(candidate))
            return candidate
        if (candidate / "rcda_sealed.py").is_file():
            sys.path.insert(0, str(candidate))
            return candidate
    return here


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _install_unrar() -> None:
    if shutil.which("unrar") or shutil.which("7z"):
        return
    subprocess.run(["apt-get", "update", "-qq"], check=False)
    subprocess.run(["apt-get", "install", "-y", "-qq", "unrar", "p7zip-full"], check=False)


def _extract_archive(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    _install_unrar()
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(dest)
    else:
        for command in (
            ["unrar", "x", "-o+", str(archive), str(dest)],
            ["7z", "x", f"-o{dest}", str(archive)],
        ):
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode == 0:
                break
        else:
            raise RuntimeError(
                f"could not extract {archive}; install unrar/7z. "
                f"last={(result.stderr or result.stdout or '')[-400:]}"
            )
    for child in dest.rglob("train"):
        if (child / "inputs").is_dir():
            return child.parent
    raise FileNotFoundError("extracted archive has no train/inputs")


def dump_input_tree(root: Path, max_depth: int = 2) -> list[str]:
    """Summarize a mount without listing every npy."""
    lines: list[str] = []
    if not root.exists():
        return [f"{root} MISSING"]
    if root.is_file():
        return [f"{root} file bytes={root.stat().st_size}"]

    def walk(path: Path, depth: int) -> None:
        try:
            children = sorted(path.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            lines.append(f"{path} ERROR {exc}")
            return
        dirs = [child for child in children if child.is_dir()]
        files = [child for child in children if child.is_file()]
        lines.append(f"{path} dirs={len(dirs)} files={len(files)}")
        if depth >= max_depth:
            return
        for child in dirs[:40]:
            walk(child, depth + 1)
        for child in files[:12]:
            lines.append(f"{child} bytes={child.stat().st_size}")

    walk(root, 0)
    return lines


def protocol_complete(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in PROTOCOL_FILES)


def _unzip_small(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as handle:
        handle.extractall(dest)
    return dest


def find_protocol_dir(roots: list[Path]) -> Path | None:
    seen: set[Path] = set()
    queue = list(roots)
    while queue:
        root = queue.pop(0)
        try:
            resolved = root.resolve() if root.exists() else root
        except OSError:
            resolved = root
        if resolved in seen:
            continue
        seen.add(resolved)
        if protocol_complete(root):
            return root
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".zip" and root.stat().st_size <= SMALL_ZIP_BYTES:
            extracted = _unzip_small(root, Path("/tmp/rcda_protocol_unzip") / root.stem)
            queue.append(extracted)
            continue
        if not root.is_dir():
            continue
        for zip_path in root.glob("*.zip"):
            if zip_path.stat().st_size <= SMALL_ZIP_BYTES:
                queue.append(zip_path)
        for name in PROTOCOL_FILES:
            if (root / name).is_file() and protocol_complete(root):
                return root
        nested = root / "protocol"
        if protocol_complete(nested):
            return nested
        try:
            for train_json in root.rglob("train.json"):
                if protocol_complete(train_json.parent):
                    return train_json.parent
        except OSError:
            continue
    return None


def find_dataset_root(roots: list[Path]) -> Path | None:
    for root in roots:
        if not root.exists():
            continue
        direct = (
            root
            if (root / "train" / "inputs").is_dir()
            else root / "dataset" if (root / "dataset" / "train" / "inputs").is_dir() else None
        )
        if direct is not None:
            return direct
        if root.is_file():
            continue
        try:
            for child in root.rglob("train"):
                if (child / "inputs").is_dir():
                    return child.parent
        except OSError:
            continue
    return None


def materialize_embedded_protocol(dest: Path) -> Path:
    import base64
    import gzip

    if not PROTOCOL_BLOBS:
        raise FileNotFoundError("no embedded protocol blobs")
    dest.mkdir(parents=True, exist_ok=True)
    for name, blob in PROTOCOL_BLOBS.items():
        (dest / name).write_bytes(gzip.decompress(base64.b64decode(blob)))
    if not protocol_complete(dest):
        raise FileNotFoundError(f"embedded protocol incomplete at {dest}")
    return dest


def _archive_input_present() -> bool:
    archive = Path("/kaggle/input/wfd-rcda-archive")
    return archive.exists()


def locate_dataset() -> Path:
    env = os.environ.get("RCDA_DATASET")
    if env:
        found = find_dataset_root([Path(env)])
        if found is not None:
            return found
    search = [
        Path("/kaggle/input/wfd-rcda-archive/dataset"),
        Path("/kaggle/input/wfd-rcda-archive"),
        # Kaggle's 2026 mount layout nests datasets under
        # /kaggle/input/datasets/<owner>/<slug>/versions/<n>/.
        Path("/kaggle/input"),
        Path("/kaggle/input/wfd-rcda-sealed/dataset"),
        Path("/kaggle/input/wfd-rcda-net-full/dataset"),
        Path("/tmp/rcda_extracted/dataset"),
        Path("/tmp/rcda_extracted"),
        Path(__file__).resolve().parents[1] / "data/external/rcda_net_full/dataset",
    ]
    found = find_dataset_root(search)
    if found is not None:
        return found
    if _archive_input_present() and os.environ.get("RCDA_ALLOW_ZENODO", "0") != "1":
        tree = dump_input_tree(Path("/kaggle/input"))
        raise FileNotFoundError(
            "wfd-rcda-archive is mounted but train/inputs was not found. "
            "Refusing Zenodo download. input_tree=\n" + "\n".join(tree)
        )
    archives: list[Path] = []
    for root in (Path("/kaggle/input"), Path("/tmp"), Path("/kaggle/working")):
        if not root.is_dir():
            continue
        for archive in root.rglob("*"):
            if archive.suffix.lower() in {".rar", ".zip"} and archive.stat().st_size > 1_000_000_000:
                archives.append(archive)
    archive = archives[0] if archives else Path("/tmp/rcda_dataset.rar")
    if not archive.is_file():
        if os.environ.get("RCDA_ALLOW_ZENODO", "0") != "1":
            tree = dump_input_tree(Path("/kaggle/input")) if Path("/kaggle/input").exists() else ["no /kaggle/input"]
            raise FileNotFoundError(
                "RCDA dataset not mounted and RCDA_ALLOW_ZENODO!=1. "
                "Attach alonsoalvira/wfd-rcda-archive. input_tree=\n" + "\n".join(tree)
            )
        print("Downloading RCDA archive from Zenodo to /tmp ...", flush=True)
        subprocess.run(["curl", "-L", ZENODO_URL, "-o", str(archive)], check=True)
    print(f"Using archive {archive} ({archive.stat().st_size} bytes)", flush=True)
    if archive.name == "dataset.rar" and _md5(archive) != PUBLISHED_MD5:
        raise RuntimeError("Zenodo archive MD5 mismatch")
    extracted = Path("/tmp/rcda_extracted")
    result = _extract_archive(archive, extracted)
    if archive.parent == Path("/tmp") and archive.is_file():
        archive.unlink()
    return result


def locate_protocol(repo: Path) -> Path:
    found = find_protocol_dir(
        [
            Path(__file__).resolve().parent / "protocol",
            Path("/kaggle/input/wfd-rcda-sealed/protocol"),
            Path("/kaggle/input/wfd-rcda-sealed"),
            Path("/kaggle/input/wfd-rcda-protocol/protocol"),
            Path("/kaggle/working/rcda_protocol"),
            Path("/tmp/rcda_protocol"),
            repo / "data/external/rcda_net_full/protocol",
            repo / "protocol",
        ]
    )
    if found is not None:
        return found
    if PROTOCOL_BLOBS:
        dest = Path(os.environ.get("RCDA_PROTOCOL_OUT", "/kaggle/working/rcda_protocol"))
        if not str(dest).startswith("/kaggle") and not dest.is_dir():
            dest = Path("/tmp/rcda_protocol")
        return materialize_embedded_protocol(dest)
    tree = dump_input_tree(Path("/kaggle/input")) if Path("/kaggle/input").exists() else ["no /kaggle/input"]
    raise FileNotFoundError(
        "sealed protocol manifests not found. input_tree=\n" + "\n".join(tree)
    )


def main() -> int:
    repo = _ensure_repo()
    try:
        from wildfire_front.ml.rcda_sealed import SealedTrainConfig, train_sealed
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from rcda_sealed import SealedTrainConfig, train_sealed  # type: ignore

    output = Path(os.environ.get("RCDA_OUTPUT", "/kaggle/working/rcda_sealed"))
    if not output.is_dir() and not str(output).startswith("/kaggle"):
        output = repo / "outputs/ml_eval/rcda_sealed"
    output.mkdir(parents=True, exist_ok=True)
    if Path("/kaggle/input").exists():
        tree = dump_input_tree(Path("/kaggle/input"))
        print("KAGGLE_INPUT_TREE\n" + "\n".join(tree), flush=True)
    dataset = locate_dataset()
    protocol = locate_protocol(repo)
    boot = {
        "schema": "wfd_rcda_sealed_boot_v1",
        "dataset": str(dataset),
        "protocol": str(protocol),
        "n_train_inputs": len(list((dataset / "train" / "inputs").glob("*.npy"))),
        "protocol_files": sorted(path.name for path in protocol.glob("*.json")),
    }
    (output / "boot.json").write_text(json.dumps(boot, indent=2) + "\n", encoding="utf-8")
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
    dilated = json.loads(
        (repo / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json").read_text(
            encoding="utf-8"
        )
    ) if (repo / "outputs/ml_eval/rcda_sealed_baselines/dilated_copy.json").is_file() else None
    summary = {
        "schema": "wfd_rcda_sealed_kaggle_v1",
        "dataset": str(dataset),
        "protocol": str(protocol),
        "models": reports,
        "dilated_copy_reference": dilated["test"] if dilated and "test" in dilated else dilated,
        "not_claims": [
            "not a published RCDA reproduction of the contaminated TEST protocol",
            "Caldor is holdout-only and is not used here",
            "legacy17 weights were not loaded",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"n_reports": len(reports), "output": str(output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
