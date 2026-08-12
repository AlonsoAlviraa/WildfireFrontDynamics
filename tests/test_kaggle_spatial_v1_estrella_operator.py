"""Unit tests for Kaggle spatial_v1 estrella one-shot operator helpers + CLI exits."""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_kaggle_spatial_v1_estrella import (  # noqa: E402
    BOARD_NAME,
    CORE3,
    EXIT_ERROR,
    EXIT_KAGGLE,
    EXIT_MISSING_DATA,
    EXIT_OK,
    apply_score_to_op,
    dataset_metadata_dict,
    kernel_metadata_dict,
    load_last_pack_fingerprint,
    looks_like_lofo_pack,
    main,
    pack_fingerprint,
    parse_dataset_status,
    parse_kernel_status,
    save_last_pack_fingerprint,
    score_spatial_board,
    stage_dataset_dir,
    stage_kernel_dir,
    write_bom_free_json,
    zip_lofo_pack,
)


def _make_fake_pack(root: Path, *, with_npz: bool = True) -> Path:
    """Minimal core-3 LOFO pack layout for packaging tests."""
    for fold in CORE3:
        for split in ("train", "val", "test"):
            d = root / fold / split
            d.mkdir(parents=True, exist_ok=True)
            if with_npz:
                # tiny fake npz (zip container not required for packaging)
                (d / f"clm_{fold}_000000.npz").write_bytes(b"PK\x03\x04fake")
    (root / "manifest.json").write_text(
        json.dumps({"folds": list(CORE3), "policy": "estrella_floor_v1"}),
        encoding="utf-8",
    )
    return root


def test_looks_like_lofo_pack_true_and_false(tmp_path: Path):
    pack = _make_fake_pack(tmp_path / "pack")
    assert looks_like_lofo_pack(pack) is True
    empty = tmp_path / "empty"
    empty.mkdir()
    assert looks_like_lofo_pack(empty) is False
    assert looks_like_lofo_pack(tmp_path / "missing") is False
    # Missing one fold
    bad = tmp_path / "bad"
    (bad / "CARDOSO" / "train").mkdir(parents=True)
    (bad / "LA_ESTRELLA_ACOM1" / "train").mkdir(parents=True)
    assert looks_like_lofo_pack(bad) is False


def test_write_bom_free_json_no_bom(tmp_path: Path):
    path = tmp_path / "meta.json"
    write_bom_free_json(path, {"id": "a/b", "n": 1})
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert not raw.startswith(b"\xff\xfe")
    assert not raw.startswith(b"\xfe\xff")
    data = json.loads(raw.decode("utf-8"))
    assert data["id"] == "a/b"


def test_dataset_and_kernel_metadata_shape():
    ds = dataset_metadata_dict()
    assert ds["id"] == "alonsoalviraaaa/wfd-lofo-spatial-estrella-v1"
    assert isinstance(ds["licenses"], list)
    kn = kernel_metadata_dict()
    assert kn["code_file"] == "run_spatial_v1_lofo_estrella.py"
    assert kn["enable_gpu"] is True
    assert "alonsoalviraaaa/wfd-lofo-spatial-estrella-v1" in kn["dataset_sources"]
    assert kn["machine_shape"] == "NvidiaTeslaT4"


def test_zip_and_stage_dataset(tmp_path: Path):
    pack = _make_fake_pack(tmp_path / "lofo_mix_spatial_estrella_v1")
    zpath = tmp_path / "out.zip"
    zip_lofo_pack(pack, zpath)
    assert zpath.is_file() and zpath.stat().st_size > 0
    with zipfile.ZipFile(zpath) as zf:
        names = zf.namelist()
    assert any("CARDOSO/train/" in n for n in names)

    stage = tmp_path / "stage_ds"
    stamp = stage_dataset_dir(pack, stage, force_rebuild_zip=True)
    assert (stage / "dataset-metadata.json").is_file()
    meta_raw = (stage / "dataset-metadata.json").read_bytes()
    assert not meta_raw.startswith(b"\xef\xbb\xbf")
    assert stamp["rebuilt_zip"] is True
    assert stamp["pack_fingerprint"]
    assert stamp["zip_bytes"] > 0


def test_stage_dataset_missing_pack_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        stage_dataset_dir(tmp_path / "nope", tmp_path / "stage")


def test_stage_kernel_dir(tmp_path: Path):
    script = tmp_path / "run_spatial_v1_lofo_estrella.py"
    script.write_text("# fake kernel\nprint('ok')\n", encoding="utf-8")
    stage = tmp_path / "kn"
    info = stage_kernel_dir(script, stage)
    assert (stage / "run_spatial_v1_lofo_estrella.py").is_file()
    meta = json.loads((stage / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert meta["code_file"] == "run_spatial_v1_lofo_estrella.py"
    assert meta["id"] == info["kernel_slug"]
    assert (stage / "kernel-metadata.json").read_bytes()[:3] != b"\xef\xbb\xbf"


def test_stage_kernel_missing_script_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        stage_kernel_dir(tmp_path / "missing.py", tmp_path / "kn")


def test_pack_fingerprint_stable(tmp_path: Path):
    pack = _make_fake_pack(tmp_path / "pack")
    a = pack_fingerprint(pack)
    b = pack_fingerprint(pack)
    assert a == b
    assert len(a) == 16


def test_parse_status_helpers():
    assert parse_dataset_status("ready") == "ready"
    assert parse_dataset_status("Dataset is ready") == "ready"
    # Negatives must not false-positive as ready
    assert parse_dataset_status("not ready") == "pending"
    assert parse_dataset_status("Dataset status is not ready") == "pending"
    assert parse_dataset_status("error: upload failed before ready") == "error"
    assert parse_dataset_status("failed") == "error"
    assert parse_dataset_status("pending") == "pending"
    assert parse_dataset_status("") == "unknown"
    assert parse_kernel_status('has status "KernelWorkerStatus.COMPLETE"') == "COMPLETE"
    assert parse_kernel_status("KernelWorkerStatus.ERROR") == "ERROR"
    assert parse_kernel_status("KernelWorkerStatus.RUNNING") == "RUNNING"
    assert parse_kernel_status("") == "UNKNOWN"


def test_pack_fingerprint_store_roundtrip(tmp_path: Path):
    store = tmp_path / "fp.json"
    assert load_last_pack_fingerprint(store) is None
    save_last_pack_fingerprint(store, "abc123def4567890", action="version")
    assert load_last_pack_fingerprint(store) == "abc123def4567890"


def test_cli_missing_pack_root_exit_2(tmp_path: Path):
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--pack-root",
            str(tmp_path / "does_not_exist_pack"),
            "--dry-run",
            "--status-out",
            str(tmp_path / "status.json"),
        ]
    )
    assert rc == EXIT_MISSING_DATA
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["steps"]["pack"]["ok"] is False


def test_cli_score_only_missing_board_exit_2(tmp_path: Path):
    empty_out = tmp_path / "kaggle_out"
    empty_out.mkdir()
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out",
            str(empty_out),
            "--score-only",
            "--status-out",
            str(tmp_path / "st.json"),
        ]
    )
    assert rc == EXIT_MISSING_DATA


def test_cli_dry_run_stages_ok(tmp_path: Path):
    pack = _make_fake_pack(tmp_path / "lofo_mix_spatial_estrella_v1")
    script = tmp_path / "run_spatial_v1_lofo_estrella.py"
    script.write_text("print(0)\n", encoding="utf-8")
    short = tmp_path / "short"
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--pack-root",
            str(pack),
            "--kernel-script",
            str(script),
            "--short-root",
            str(short),
            "--dry-run",
            "--status-out",
            str(tmp_path / "op.json"),
        ]
    )
    assert rc == EXIT_OK
    assert (short / "dataset" / "dataset-metadata.json").is_file()
    assert (short / "kernel" / "kernel-metadata.json").is_file()
    op = json.loads((tmp_path / "op.json").read_text(encoding="utf-8"))
    assert op["steps"]["stage"]["ok"] is True
    assert op["rails"]["field_ops_allow_ml_live_in_fusion"] is False
    assert op["rails"]["never_invent_keep"] is True


def test_score_spatial_board_writes_kill_not_fake_keep(tmp_path: Path):
    """Low IoU board must score KILL — never invent KEEP."""
    board = {
        "schema": "wfd_kaggle_spatial_v1_estrella_lofo_v1",
        "core3_mean_iou": 0.482,
        "core3_min_iou": 0.301,
        "folds": [
            {
                "held": "CARDOSO",
                "model_iou": 0.589,
                "copy_baseline_iou": 0.347,
                "improvement_vs_copy_iou": 0.242,
            },
            {
                "held": "LA_ESTRELLA_ACOM1",
                "model_iou": 0.301,
                "copy_baseline_iou": 0.275,
                "improvement_vs_copy_iou": 0.026,
            },
            {
                "held": "LA_ESTRELLA_ACOM2",
                "model_iou": 0.556,
                "copy_baseline_iou": 0.296,
                "improvement_vs_copy_iou": 0.260,
            },
        ],
        "feature_schema": "spatial_v1",
        "work_class": "feature_spatial_v1+data_mix_estrella_floor_v1",
    }
    bp = tmp_path / BOARD_NAME
    bp.write_text(json.dumps(board), encoding="utf-8")
    kill_out = tmp_path / "kill.json"
    kill = score_spatial_board(
        bp,
        repo=ROOT,
        experiment_id="E2_P2_spatial_v1_estrella_test",
        out_kill=kill_out,
    )
    assert kill_out.is_file()
    assert kill["verdict"] == "KILL"
    assert kill["verdict"] != "KEEP"
    assert kill["feature_schema"] == "spatial_v1"
    assert kill["rails_operator"]["field_ops_allow_ml_live_in_fusion"] is False
    assert kill["checks"]["L1_lofo_mean_lift"]["pass"] is False
    assert kill["checks"]["L2_weak_floor"]["pass"] is False


def test_cli_score_only_on_existing_board(tmp_path: Path):
    """score-only path: exit 0 with honest KILL when board present."""
    out = tmp_path / "kout"
    out.mkdir()
    board = {
        "core3_mean_iou": 0.48,
        "core3_min_iou": 0.30,
        "folds": [
            {
                "held": f,
                "model_iou": iou,
                "copy_baseline_iou": 0.2,
                "improvement_vs_copy_iou": iou - 0.2,
            }
            for f, iou in zip(CORE3, (0.59, 0.30, 0.55), strict=True)
        ],
    }
    (out / BOARD_NAME).write_text(json.dumps(board), encoding="utf-8")
    kill_out = tmp_path / "k.json"
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out",
            str(out),
            "--score-only",
            "--experiment-id",
            "E2_P2_spatial_v1_estrella_cli_test",
            "--kill-out",
            str(kill_out),
            "--status-out",
            str(tmp_path / "st.json"),
        ]
    )
    assert rc == EXIT_OK
    kill = json.loads(kill_out.read_text(encoding="utf-8"))
    assert kill["verdict"] == "KILL"
    st = json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))
    assert st["verdict"] == "KILL"


def test_cli_auth_failure_download_only_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Auth/CLI failure on --download-only must return EXIT_KAGGLE (3)."""
    import run_kaggle_spatial_v1_estrella as mod

    monkeypatch.setattr(
        mod,
        "kaggle_available",
        lambda: (False, "kaggle auth failure: unauthorized"),
    )
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out",
            str(tmp_path / "out"),
            "--download-only",
            "--status-out",
            str(tmp_path / "st.json"),
        ]
    )
    assert rc == EXIT_KAGGLE
    st = json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))
    assert st["steps"]["auth"]["ok"] is False
    assert "auth" in (st["steps"]["auth"].get("error") or "").lower() or (
        "failure" in (st["steps"]["auth"].get("error") or "").lower()
    )


def test_cli_auth_failure_watch_only_exit_3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import run_kaggle_spatial_v1_estrella as mod

    monkeypatch.setattr(
        mod,
        "kaggle_available",
        lambda: (False, "kaggle CLI not found on PATH"),
    )
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--watch-only",
            "--status-out",
            str(tmp_path / "st.json"),
        ]
    )
    assert rc == EXIT_KAGGLE
    st = json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))
    assert st["steps"]["auth"]["ok"] is False


def test_apply_score_to_op_maps_raise_to_exit_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Scorer exceptions map to EXIT_ERROR consistently."""
    import run_kaggle_spatial_v1_estrella as mod

    def _boom(*_a, **_k):
        raise RuntimeError("bad board")

    monkeypatch.setattr(mod, "score_spatial_board", _boom)
    op: dict = {"steps": {}}
    board = tmp_path / "board.json"
    board.write_text("{}", encoding="utf-8")
    rc, kill = apply_score_to_op(
        op,
        board,
        repo=ROOT,
        experiment_id="x",
        out_kill=tmp_path / "k.json",
    )
    assert rc == EXIT_ERROR
    assert kill is None
    assert op["steps"]["score"]["ok"] is False
    assert "bad board" in op["steps"]["score"]["error"]


def test_cli_score_only_score_error_exit_4(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import run_kaggle_spatial_v1_estrella as mod

    out = tmp_path / "kout"
    out.mkdir()
    (out / BOARD_NAME).write_text("{}", encoding="utf-8")

    def _boom(*_a, **_k):
        raise ValueError("scorer exploded")

    monkeypatch.setattr(mod, "score_spatial_board", _boom)
    rc = main(
        [
            "--repo",
            str(ROOT),
            "--out",
            str(out),
            "--score-only",
            "--status-out",
            str(tmp_path / "st.json"),
        ]
    )
    assert rc == EXIT_ERROR
    st = json.loads((tmp_path / "st.json").read_text(encoding="utf-8"))
    assert st["steps"]["score"]["ok"] is False
