"""Architecture sweep: configs, list-only, refuse official overwrite."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "run_same_fire_arch_sweep.py"
    spec = importlib.util.spec_from_file_location("run_same_fire_arch_sweep", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*args: str) -> subprocess.CompletedProcess:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_same_fire_arch_sweep.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_sweep_includes_residual_and_standard() -> None:
    mod = _load()
    ids = [c["id"] for c in mod.SWEEP_CONFIGS]
    arches = {c["architecture"] for c in mod.SWEEP_CONFIGS}
    assert "residual_scratch_ref" in ids
    assert any(i.startswith("standard_") for i in ids)
    assert "residual" in arches
    assert "standard" in arches
    assert any(c.get("se_attention") for c in mod.SWEEP_CONFIGS)
    assert mod.DECODE_ABLATIONS
    assert any("not official LATAM" in claim for claim in mod.NOT_CLAIMS)
    assert any("decode-ablation" in claim for claim in mod.NOT_CLAIMS)


def test_list_only_exit0() -> None:
    p = _run("--list-only")
    assert p.returncode == 0, p.stdout + p.stderr
    text = p.stdout
    assert "residual_scratch_ref" in text
    assert "standard_abs_lr1e4" in text
    assert "standard_se_abs_lr1e4" in text
    assert "residual_eval_keep_t0_norings_g50" in text


def test_unknown_config_exit3() -> None:
    p = _run("--only", "not_a_config", "--out-root", str(ROOT / "outputs" / "ml_eval" / "mega_goal_model" / "same_fire_arch_sweep"))
    assert p.returncode == 3, p.stdout + p.stderr
    assert "unknown" in (p.stderr + p.stdout).lower()


def test_refuses_official_out() -> None:
    official_parent = ROOT / "outputs" / "ml_eval" / "mega_goal_model"
    p = _run("--out-root", str(official_parent))
    assert p.returncode == 3, p.stdout + p.stderr
    assert "official" in (p.stderr + p.stdout).lower()
