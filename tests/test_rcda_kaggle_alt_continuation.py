from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scripts.run_rcda_kaggle_alt_continuation import (
    kaggle_env,
    require_successful_kernel_push,
    single_run_source,
    single_seed_run_source,
    validate_single_run_val_summary,
)


def test_kaggle_push_guard_rejects_zero_exit_cli_error() -> None:
    result = subprocess.CompletedProcess(
        args=["kaggle", "kernels", "push"],
        returncode=0,
        stdout="Kernel push error: Maximum batch GPU session count of 2 reached.",
        stderr="",
    )

    with pytest.raises(RuntimeError, match="Maximum batch GPU"):
        require_successful_kernel_push(result, kernel="owner/kernel")


def test_kaggle_push_guard_accepts_successful_creation() -> None:
    result = subprocess.CompletedProcess(
        args=["kaggle", "kernels", "push"],
        returncode=0,
        stdout="Kernel version 1 successfully pushed.",
        stderr="",
    )

    require_successful_kernel_push(result, kernel="owner/kernel")


def test_alt_kaggle_env_overrides_global_account(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "main-token")
    monkeypatch.setenv("KAGGLE_USERNAME", "main-user")
    monkeypatch.setenv("KAGGLE_KEY", "main-key")
    env = kaggle_env(tmp_path)
    assert "KAGGLE_API_TOKEN" not in env
    assert "KAGGLE_USERNAME" not in env
    assert "KAGGLE_KEY" not in env
    assert env["KAGGLE_CONFIG_DIR"] == str(tmp_path)


def test_legacy_val_summary_is_normalized_only_from_embedded_evidence() -> None:
    summary = {
        "selection_split": "val",
        "test_evaluated": False,
        "ranking": [{"run_name": "low_lr"}],
        "reports": [
            {
                "config": {"run_name": "low_lr"},
                "test_evaluated": False,
                "test_used_for_selection": False,
            }
        ],
    }

    assert validate_single_run_val_summary(summary, "low_lr") is True
    assert summary["test_used_for_selection"] is False
    assert validate_single_run_val_summary(summary, "low_lr") is False


def test_single_run_source_is_val_only_and_numerically_guarded() -> None:
    source = single_run_source("resunet_hybrid_precision_v3")
    assert '"RCDA_STAGE2_RUNS", "resunet_hybrid_precision_v3"' in source
    assert "max_grad_norm: float = 5.0" in source
    assert "clip_grad_norm_" in source
    assert "evaluate_test=False" in source
    assert "test_evaluated\": False" in source


def test_single_seed_source_changes_only_the_training_seed() -> None:
    source = single_seed_run_source("resunet_multitask_front_ring_v1", 29)
    assert '"RCDA_STAGE2_RUNS", "resunet_multitask_front_ring_v1"' in source
    assert source.count("seed=29,") == 1
    assert "seed=0," not in source
    assert "evaluate_test=False" in source
    assert "test_evaluated\": False" in source
    with pytest.raises(ValueError, match="non-negative"):
        single_seed_run_source("resunet_multitask_front_ring_v1", -1)
