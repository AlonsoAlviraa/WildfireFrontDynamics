"""Standard vs CLM all-fires runner: list, exits, official JSON rail."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "run_standard_vs_clm_all_fires.py"
    spec = importlib.util.spec_from_file_location("run_standard_vs_clm_all_fires", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(*args: str) -> subprocess.CompletedProcess:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_standard_vs_clm_all_fires.py"), *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )


def test_list_covers_latam_and_same_fire() -> None:
    p = _run("--list-only")
    assert p.returncode == 0, p.stdout + p.stderr
    text = p.stdout
    assert "AU_EMSR500_PERTH" in text
    assert "CL_EMSR647_NACIMIENTO" in text
    assert "EMSR578_AOI01" in text
    assert "US_FIREBENCH_CALDOR_2021" in text
    assert "ES_EMSR685_TENERIFE" in text
    assert "clm_in_sample" in text
    assert "standard_in_sample" in text


def test_sample_kind_splits() -> None:
    mod = _load()
    assert mod.sample_kind("AU_EMSR500_PERTH") == "clm_in_sample"
    assert mod.sample_kind("EMSR578_AOI01") == "standard_in_sample"
    assert mod.sample_kind("TOBARRA_20240802") == "both_ood"
    assert mod.sample_kind("BO_EMSR765") == "both_ood"
    assert mod.sample_kind("ES_EMSR685_TENERIFE") == "both_ood"


def test_unknown_fire_exit3(tmp_path: Path) -> None:
    p = _run("--fire", "NOT_A_FIRE", "--out-root", str(tmp_path / "out"))
    assert p.returncode == 3, p.stdout + p.stderr


def test_refuses_official_out() -> None:
    official_parent = ROOT / "outputs" / "ml_eval" / "mega_goal_model"
    p = _run("--out-root", str(official_parent))
    assert p.returncode == 3, p.stdout + p.stderr
    assert "official" in (p.stderr + p.stdout).lower()
