from __future__ import annotations

from pathlib import Path

from scripts.run_rcda_kaggle_alt_continuation import kaggle_env, single_run_source


def test_alt_kaggle_env_overrides_global_account(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("KAGGLE_API_TOKEN", "main-token")
    monkeypatch.setenv("KAGGLE_USERNAME", "main-user")
    env = kaggle_env(tmp_path)
    assert "KAGGLE_API_TOKEN" not in env
    assert "KAGGLE_USERNAME" not in env
    assert env["KAGGLE_CONFIG_DIR"] == str(tmp_path)


def test_single_run_source_is_val_only_and_numerically_guarded() -> None:
    source = single_run_source("resunet_hybrid_precision_v3")
    assert '"RCDA_STAGE2_RUNS", "resunet_hybrid_precision_v3"' in source
    assert "max_grad_norm: float = 5.0" in source
    assert "clip_grad_norm_" in source
    assert "evaluate_test=False" in source
    assert "test_evaluated\": False" in source
