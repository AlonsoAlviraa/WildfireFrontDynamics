"""Priority B: multi-fire mix designer (estrella_floor_v1)."""

from __future__ import annotations

# Import pure policy from scripts/
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_lofo_mix_v1 import (  # noqa: E402
    CORE_SOURCES,
    design_train_pool,
    is_external,
    is_tobarra,
    sibling_of,
)


def _fake_by_src(counts: dict[str, int], tmp: Path) -> dict[str, list[Path]]:
    by: dict[str, list[Path]] = {}
    for src, n in counts.items():
        paths = []
        for i in range(n):
            p = tmp / f"{src}_{i:04d}.npz"
            # minimal npz with source key (optional for design which only uses lists)
            if not p.exists():
                p.write_bytes(b"")  # design_train_pool only needs Path objects
            paths.append(p)
        by[src] = paths
    return by


def test_sibling_map():
    assert sibling_of("LA_ESTRELLA_ACOM1") == "LA_ESTRELLA_ACOM2"
    assert sibling_of("LA_ESTRELLA_ACOM2") == "LA_ESTRELLA_ACOM1"
    assert sibling_of("CARDOSO") is None


def test_tobarra_and_external_classifiers():
    assert is_tobarra("tobarra_20240802")
    assert is_tobarra("tobarra")
    assert not is_tobarra("CARDOSO")
    assert is_external("hellin_2024")
    assert is_external("HELLIN20240719")
    assert not is_external("CARDOSO")
    assert not is_external("tobarra_20240802")


def test_external_cap_and_no_tobarra_in_acom2_train(tmp_path: Path):
    by = _fake_by_src(
        {
            "CARDOSO": 40,
            "LA_ESTRELLA_ACOM1": 40,
            "LA_ESTRELLA_ACOM2": 40,
            "hellin_2024": 200,  # large external — must be capped
            "tobarra_20240802": 50,
        },
        tmp_path,
    )
    design = design_train_pool(
        by,
        held="LA_ESTRELLA_ACOM2",
        external_cap=0.28,
        sibling_oversample=2.0,
        exclude_tobarra=True,
    )
    sources = set(design["path_sources"])
    assert "LA_ESTRELLA_ACOM2" not in sources  # held out
    assert "tobarra_20240802" not in sources
    assert "tobarra_20240802" in design["excluded"] or any(
        "tobarra" in e for e in design["excluded"]
    )
    # external fraction ≤ 0.28
    frac = design["fractions_by_source"].get("hellin_2024", 0.0)
    assert frac <= 0.28 + 1e-6
    # sibling oversample: ACOM1 count > base 40
    assert design["counts_by_source"]["LA_ESTRELLA_ACOM1"] >= 40
    assert design["sibling_extra_n"] >= 40  # 2× → one full extra copy


def test_sibling_oversample_counts(tmp_path: Path):
    by = _fake_by_src(
        {
            "CARDOSO": 20,
            "LA_ESTRELLA_ACOM1": 30,
            "LA_ESTRELLA_ACOM2": 30,
        },
        tmp_path,
    )
    d1 = design_train_pool(
        by, held="LA_ESTRELLA_ACOM1", sibling_oversample=1.0, exclude_tobarra=True
    )
    d2 = design_train_pool(
        by, held="LA_ESTRELLA_ACOM1", sibling_oversample=2.0, exclude_tobarra=True
    )
    # When holding ACOM1, sibling is ACOM2
    assert (
        d2["counts_by_source"]["LA_ESTRELLA_ACOM2"]
        == 2 * d1["counts_by_source"]["LA_ESTRELLA_ACOM2"]
    )
    assert d2["sibling"] == "LA_ESTRELLA_ACOM2"


def test_held_not_in_train_cardoso(tmp_path: Path):
    by = _fake_by_src(
        {
            "CARDOSO": 25,
            "LA_ESTRELLA_ACOM1": 25,
            "LA_ESTRELLA_ACOM2": 25,
            "hellin_2024": 10,
        },
        tmp_path,
    )
    design = design_train_pool(by, held="CARDOSO", external_cap=0.30)
    assert "CARDOSO" not in design["path_sources"]
    assert design["counts_by_source"].get("CARDOSO", 0) == 0


def test_reweight_stamp_positive(tmp_path: Path):
    by = _fake_by_src(
        {
            "CARDOSO": 10,
            "LA_ESTRELLA_ACOM1": 10,
            "LA_ESTRELLA_ACOM2": 10,
            "hellin_2024": 5,
        },
        tmp_path,
    )
    design = design_train_pool(by, held="CARDOSO", reweight_1_over_n=True)
    assert len(design["weights"]) == len(design["paths"])
    assert all(w > 0 for w in design["weights"])


def test_core_sources_constant():
    assert {"CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2"} == CORE_SOURCES


def test_build_clm_lofo_splits_mix_dry_run_no_crash(tmp_path: Path):
    """BUG-3: --mix-policy --dry-run must not FileNotFoundError on missing out_root."""
    import json
    import subprocess

    repo = Path(__file__).resolve().parents[1]
    out_root = tmp_path / "does_not_exist_yet" / "lofo_mix"
    # out_root intentionally absent
    assert not out_root.exists()
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts" / "build_clm_lofo_splits.py"),
            "--mix-policy",
            "estrella_floor_v1",
            "--dry-run",
            "--src-root",
            str(repo / "artifacts" / "clm_ndws_patches" / "holdout_v1"),
            "--out-root",
            str(out_root),
            "--manifest-out",
            str(tmp_path / "man.json"),
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env={
            **dict(**dict(__import__("os").environ.items())),
            "PYTHONPATH": str(repo),
        },
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert not out_root.exists() or not (out_root / "manifest.json").exists()
    man = json.loads((tmp_path / "man.json").read_text(encoding="utf-8"))
    assert man.get("mix_policy") == "estrella_floor_v1"
    assert man.get("work_class") == "data_mix_estrella_floor_v1"
    assert man.get("dry_run") is True
