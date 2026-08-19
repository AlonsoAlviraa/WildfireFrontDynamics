from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

from wildfire_front.ml.rcda_sealed import SealedTrainConfig, train_sealed


def _load_job_module():
    path = Path("kaggle_job/run_rcda_sealed_train.py")
    spec = importlib.util.spec_from_file_location("rcda_kaggle_job", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_kaggle_job_vendors_the_shipped_trainer() -> None:
    path = Path("kaggle_job/run_rcda_sealed_train.py")
    spec = importlib.util.spec_from_file_location("rcda_kaggle_job", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.PUBLISHED_MD5 == "d7856d77dcb823d0bdb5e10c6bac4f87"
    assert "dataset.rar" in module.ZENODO_URL
    repo = module._ensure_repo()
    assert repo.is_dir()


def test_generated_kaggle_kernel_compiles_and_contains_shipped_trainer() -> None:
    from scripts.push_rcda_sealed_kaggle import _self_contained_kernel

    source = _self_contained_kernel()
    compile(source, "run_rcda_sealed_train.py", "exec")
    assert "def train_sealed" in source
    assert "def encode_features" in source
    assert "test_used_for_selection" in source
    assert "locate_dataset" in source
    assert "dump_input_tree" in source
    assert "PROTOCOL_BLOBS" in source
    assert "RCDA_ALLOW_ZENODO" in source
    assert "wfd_rcda_sealed_boot_v1" in source
    assert "train.json" in source


def test_locate_protocol_finds_zip_mount_and_nested_json(tmp_path: Path) -> None:
    module = _load_job_module()
    sealed = tmp_path / "wfd-rcda-sealed"
    sealed.mkdir()
    payload = tmp_path / "payload"
    payload.mkdir()
    for name in module.PROTOCOL_FILES:
        (payload / name).write_text("{}", encoding="utf-8")
    with zipfile.ZipFile(sealed / "bundle.zip", "w") as handle:
        for name in module.PROTOCOL_FILES:
            handle.write(payload / name, arcname=name)
    found = module.find_protocol_dir([sealed])
    assert found is not None
    assert module.protocol_complete(found)


def test_locate_dataset_refuses_zenodo_when_archive_mount_is_empty(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_job_module()
    archive = tmp_path / "wfd-rcda-archive"
    archive.mkdir()
    (archive / "README.md").write_text("empty mount", encoding="utf-8")
    monkeypatch.setattr(module, "_archive_input_present", lambda: True)
    monkeypatch.setattr(module, "find_dataset_root", lambda roots: None)
    monkeypatch.setattr(module, "dump_input_tree", lambda root, max_depth=2: [str(archive)])
    monkeypatch.setenv("RCDA_ALLOW_ZENODO", "0")
    monkeypatch.delenv("RCDA_DATASET", raising=False)
    try:
        module.locate_dataset()
    except FileNotFoundError as exc:
        assert "Refusing Zenodo" in str(exc)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_find_dataset_root_supports_versioned_kaggle_mount(tmp_path: Path) -> None:
    module = _load_job_module()
    versioned = (
        tmp_path
        / "datasets"
        / "alonsoalvira"
        / "wfd-rcda-archive"
        / "versions"
        / "1"
        / "dataset"
    )
    (versioned / "train" / "inputs").mkdir(parents=True)
    found = module.find_dataset_root([tmp_path])
    assert found == versioned


def test_embedded_protocol_roundtrip(tmp_path: Path) -> None:
    import base64
    import gzip

    module = _load_job_module()
    dest = tmp_path / "embedded"
    blobs = {}
    for name in module.PROTOCOL_FILES:
        blobs[name] = base64.b64encode(gzip.compress(b'{"ok": true}', 9)).decode("ascii")
    module.PROTOCOL_BLOBS = blobs
    out = module.materialize_embedded_protocol(dest)
    assert module.protocol_complete(out)
    assert json.loads((out / "train.json").read_text(encoding="utf-8"))["ok"] is True


def test_kaggle_job_calls_same_train_sealed_entry() -> None:
    source = Path("kaggle_job/run_rcda_sealed_train.py").read_text(encoding="utf-8")
    assert "train_sealed(config)" in source
    assert "test_used_for_selection" not in source.split("def train_sealed")[0]
    assert SealedTrainConfig.model_name
    assert callable(train_sealed)
