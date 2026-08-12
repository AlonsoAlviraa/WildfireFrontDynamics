#!/usr/bin/env python3
"""V1: Promote Hellín into LOFO redesign (legacy17) with leak audit.

Builds ``artifacts/clm_ndws_patches/lofo_v2_hellin`` from existing sealed patches:

* Core held folds: CARDOSO, LA_ESTRELLA_ACOM1, LA_ESTRELLA_ACOM2, hellin_2024
* Train never contains held source (leak-free by construction)
* Tobarra stays train fill (not held) unless --include-tobarra-held
* Retuerta excluded (QA flag); press_only never ingested
* Brazatortas included as capped external if present in pool

Honesty: work_class=data_lofo_v2_hellin_promote · lab only · not product.

Usage
-----
    $env:PYTHONPATH = "."
    python scripts/build_lofo_v2_hellin_promote.py
    python scripts/build_lofo_v2_hellin_promote.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CORE_HELD = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2", "hellin_2024")
EXCLUDE_TRAIN_ALWAYS = frozenset({"retuerta_2025"})  # QA flag
SCAN_ROOTS = (
    ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1",
    ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1",
    ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1_plus_w3",
    ROOT / "artifacts" / "clm_ndws_patches" / "train",
    ROOT / "artifacts" / "clm_ndws_patches" / "extra_fires_legacy17",
    ROOT / "artifacts" / "clm_ndws_patches" / "brazatortas_2025_legacy17",
)
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v2_hellin"
EXTERNAL_CAP = 0.28


def _source_of(path: Path) -> str | None:
    try:
        with np.load(path, allow_pickle=True) as z:
            if "sequence" not in z.files:
                return None
            seq = z["sequence"]
            c = int(seq.shape[-3]) if seq.ndim == 4 else int(seq.shape[0])
            if c != 17:
                return None
            if "source" not in z.files:
                return None
            src = z["source"]
            return str(src.item() if hasattr(src, "item") else src)
    except Exception:  # noqa: BLE001
        return None


def _content_key(path: Path) -> str:
    st = path.stat()
    return f"{path.name}:{st.st_size}"


def load_pool() -> dict[str, list[Path]]:
    by: dict[str, list[Path]] = defaultdict(list)
    seen: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.is_dir():
            continue
        for p in root.rglob("*.npz"):
            src = _source_of(p)
            if not src:
                continue
            key = f"{src}:{_content_key(p)}"
            if key in seen:
                continue
            seen.add(key)
            by[src].append(p)
    return dict(by)


def design_fold(
    by_src: dict[str, list[Path]],
    held: str,
    *,
    external_cap: float = EXTERNAL_CAP,
    val_fraction: float = 0.1,
) -> dict:
    excluded = [held]
    pool: list[tuple[str, Path]] = []
    for src, paths in sorted(by_src.items()):
        if src == held:
            continue
        if src in EXCLUDE_TRAIN_ALWAYS:
            excluded.append(src)
            continue
        # cap externals (not in core held set and not tobarra)
        is_core = src in CORE_HELD or src.startswith("tobarra")
        if not is_core:
            # will cap later
            for p in paths:
                pool.append((src, p))
        else:
            for p in paths:
                pool.append((src, p))

    # Cap each non-core, non-tobarra source
    core_like = []
    external = defaultdict(list)
    for src, p in pool:
        if src in CORE_HELD or src.startswith("tobarra"):
            core_like.append((src, p))
        else:
            external[src].append(p)

    n_core = len(core_like)
    max_per_ext = (
        10**9
        if external_cap >= 1.0
        else int(math.floor((external_cap / (1.0 - external_cap)) * max(n_core, 1)))
    )
    train_pairs = list(core_like)
    for src, paths in sorted(external.items()):
        take = paths[: max(0, max_per_ext)]
        train_pairs.extend((src, p) for p in take)

    # stratified val
    by_tr: dict[str, list[Path]] = defaultdict(list)
    for src, p in train_pairs:
        by_tr[src].append(p)
    tr_paths, tr_src, val_paths, val_src = [], [], [], []
    for src, paths in sorted(by_tr.items()):
        n_val = max(1, int(round(len(paths) * val_fraction))) if len(paths) > 5 else 0
        n_val = min(n_val, max(0, len(paths) // 5))
        val_paths.extend(paths[-n_val:]) if n_val else None
        val_src.extend([src] * n_val) if n_val else None
        keep = paths[:-n_val] if n_val else paths
        tr_paths.extend(keep)
        tr_src.extend([src] * len(keep))

    test_paths = list(by_src.get(held, []))
    return {
        "held": held,
        "train": list(zip(tr_src, tr_paths, strict=True)),
        "val": list(zip(val_src, val_paths, strict=True)),
        "test": test_paths,
        "excluded": sorted(set(excluded)),
        "train_counts": {s: tr_src.count(s) for s in sorted(set(tr_src))},
        "n_train": len(tr_paths),
        "n_val": len(val_paths),
        "n_test": len(test_paths),
        "held_in_train": held in tr_src,
    }


def _link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        dst.hardlink_to(src)
    except Exception:  # noqa: BLE001
        shutil.copy2(src, dst)


def materialize(out_root: Path, designs: list[dict], *, dry_run: bool) -> dict:
    if not dry_run:
        if out_root.exists():
            shutil.rmtree(out_root)
        out_root.mkdir(parents=True)
    leak = []
    for d in designs:
        held = d["held"]
        if d["held_in_train"]:
            leak.append(held)
        if dry_run:
            continue
        for split, key in (("train", "train"), ("val", "val")):
            pairs = d[key]
            for _i, (src, p) in enumerate(pairs):
                name = f"{src}__{p.name}"
                _link_or_copy(p, out_root / held / split / name)
        for _i, p in enumerate(d["test"]):
            _link_or_copy(p, out_root / held / "test" / f"{held}__{p.name}")
    return {"leak_held_in_train": leak, "leak_free": len(leak) == 0}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--manifest-out",
        type=Path,
        default=ROOT / "outputs" / "ml_eval" / "lofo_v2_hellin_manifest.json",
    )
    args = ap.parse_args(argv)

    pool = load_pool()
    print("pool", {k: len(v) for k, v in sorted(pool.items())})
    if "hellin_2024" not in pool or len(pool["hellin_2024"]) < 20:
        print("BLOCKED: hellin_2024 patches insufficient in pool", file=sys.stderr)
        return 2

    designs = []
    for held in CORE_HELD:
        if held not in pool:
            print(f"skip missing held {held}")
            continue
        d = design_fold(pool, held)
        designs.append(d)
        print(
            f"held={held} train={d['n_train']} val={d['n_val']} test={d['n_test']} "
            f"leak={d['held_in_train']} counts={d['train_counts']}"
        )

    mat = materialize(args.out_root, designs, dry_run=args.dry_run)
    manifest = {
        "schema": "wfd_lofo_v2_hellin_promote_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "work_class": "data_lofo_v2_hellin_promote",
        "feature_schema": "legacy17",
        "out_root": str(args.out_root.as_posix()),
        "pool_counts": {k: len(v) for k, v in sorted(pool.items())},
        "held_folds": [d["held"] for d in designs],
        "exclude_train_always": sorted(EXCLUDE_TRAIN_ALWAYS),
        "external_cap": EXTERNAL_CAP,
        "folds": {
            d["held"]: {
                "n_train": d["n_train"],
                "n_val": d["n_val"],
                "n_test": d["n_test"],
                "train_counts": d["train_counts"],
                "excluded": d["excluded"],
                "held_in_train_leak": d["held_in_train"],
            }
            for d in designs
        },
        "leak_audit": mat,
        "ml_product_go": False,
        "field_ops_allow_ml_live_in_fusion": False,
        "tobarra_keep_reopen": False,
        "comparability_note": (
            "New LOFO geography vs sealed lofo_v1 core-3; score as "
            "data_lofo_v2_hellin_promote not as recipe_t1 champion bar."
        ),
        "next": (
            "python scripts/audit_lofo_pack_leak.py --lofo-root " + str(args.out_root.as_posix())
            if (ROOT / "scripts" / "audit_lofo_pack_leak.py").is_file()
            else "manual leak check: held_in_train must be false"
        ),
    }
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(args.manifest_out), "leak_free": mat["leak_free"]}, indent=2))
    return 0 if mat["leak_free"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
