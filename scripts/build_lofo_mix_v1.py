#!/usr/bin/env python3
"""Multi-fire LOFO mix designer (not naive concat).

Policy ``estrella_floor_v1`` (Priority B):

* Cap each **external** source at ≤ ``--external-cap`` (default 0.28) of each
  fold's train pool.
* When held-out is LA_ESTRELLA_ACOM1/2, **oversample sibling** Estrella
  (ACOM1↔ACOM2) by ``--sibling-oversample`` (default 2× copy).
* **Exclude Tobarra** from core train pool (Tobarra = stress fold only).
* Optional ``1/n_source`` reweight stamp in fold metadata / sampler weights.
* Manifest documents per-source train fractions.
* Leak audit still required downstream (0 leak); this builder never puts held
  source into train.

Usage::

    $env:PYTHONPATH = "."
    python scripts/build_lofo_mix_v1.py --dry-run
    python scripts/build_lofo_mix_v1.py \\
        --src-root artifacts/clm_ndws_patches/holdout_v1_plus_w3 \\
        --out-root artifacts/clm_ndws_patches/lofo_mix_estrella_v1 \\
        --mix-policy estrella_floor_v1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SRC = ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1"
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_mix_estrella_v1"

# Core board folds (G1 comparability)
CORE_SOURCES: frozenset[str] = frozenset({"CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2"})
ESTRELLA_SIBLINGS: dict[str, str] = {
    "LA_ESTRELLA_ACOM1": "LA_ESTRELLA_ACOM2",
    "LA_ESTRELLA_ACOM2": "LA_ESTRELLA_ACOM1",
}
TOBARRA_SOURCES: frozenset[str] = frozenset({"tobarra_20240802", "tobarra", "TOBARRA"})
# External = not core Estrella/Cardoso family (Hellín, Braz, Retuerta, …)
# Tobarra is stress-only — excluded from train, not counted as external fill.

MIX_POLICY_ESTRELLA_FLOOR_V1 = "estrella_floor_v1"
DEFAULT_EXTERNAL_CAP = 0.28  # ≤ 25–30% band
DEFAULT_SIBLING_OVERSAMPLE = 2.0


def is_tobarra(source: str) -> bool:
    s = source.strip()
    if s in TOBARRA_SOURCES:
        return True
    return s.lower().startswith("tobarra")


def is_core(source: str) -> bool:
    return source in CORE_SOURCES


def is_external(source: str) -> bool:
    """External train-pool sources (capped). Tobarra is not external fill."""
    return not (is_tobarra(source) or is_core(source))


def sibling_of(held: str) -> str | None:
    return ESTRELLA_SIBLINGS.get(held)


def design_train_pool(
    by_src: dict[str, list[Path]],
    held: str,
    *,
    external_cap: float = DEFAULT_EXTERNAL_CAP,
    sibling_oversample: float = DEFAULT_SIBLING_OVERSAMPLE,
    exclude_tobarra: bool = True,
    reweight_1_over_n: bool = True,
    rng_seed: int = 0,
) -> dict[str, Any]:
    """Design train paths + weights for one held-out fold (pure logic).

    Returns dict with ``paths`` (list[Path], may include duplicates for
    oversample), ``weights`` aligned 1:1, ``counts_by_source``,
    ``fractions_by_source``, ``excluded``, ``policy_notes``.
    """
    import numpy as np

    if not (0.0 < external_cap <= 1.0):
        raise ValueError(f"external_cap must be in (0,1], got {external_cap}")

    excluded: list[str] = [held]
    pool_by_src: dict[str, list[Path]] = {}
    for src, paths in by_src.items():
        if src == held:
            continue
        if exclude_tobarra and is_tobarra(src):
            excluded.append(src)
            continue
        pool_by_src[src] = sorted(paths)

    # Cap each external source independently at external_cap of *post-cap* train
    # size. We solve iteratively: start with all non-external full + externals
    # uncapped, then shrink externals so each ≤ cap * total.
    core_paths: list[tuple[str, Path]] = []
    external_paths: dict[str, list[Path]] = {}
    for src, paths in pool_by_src.items():
        if is_external(src):
            external_paths[src] = list(paths)
        else:
            for p in paths:
                core_paths.append((src, p))

    # Sibling oversample: duplicate sibling entries in core list
    sibling = sibling_of(held)
    sibling_extra: list[tuple[str, Path]] = []
    if sibling and sibling in pool_by_src and sibling_oversample > 1.0:
        sib_paths = pool_by_src[sibling]
        # oversample factor 2.0 → one extra full copy (total 2×)
        extra_copies = max(0, int(math.floor(sibling_oversample)) - 1)
        frac = sibling_oversample - math.floor(sibling_oversample)
        for _ in range(extra_copies):
            for p in sib_paths:
                sibling_extra.append((sibling, p))
        if frac > 1e-9 and sib_paths:
            n_frac = max(1, int(round(frac * len(sib_paths))))
            # Stable seed across PYTHONHASHSEED (NIT-2): md5 of held name
            held_digest = int(hashlib.md5(held.encode("utf-8")).hexdigest()[:8], 16)
            rng = np.random.default_rng(rng_seed + (held_digest % 10_000))
            pick = rng.choice(len(sib_paths), size=min(n_frac, len(sib_paths)), replace=False)
            for i in pick:
                sibling_extra.append((sibling, sib_paths[int(i)]))

    # Cap externals: n_ext_src <= cap * (n_core + n_sib_extra + n_ext_src)
    # → n_ext_src <= cap/(1-cap) * (n_core + n_sib)
    n_core_total = len(core_paths) + len(sibling_extra)
    if external_cap >= 1.0 - 1e-12:
        max_per_ext = 10**9
    else:
        max_per_ext = int(math.floor((external_cap / (1.0 - external_cap)) * max(n_core_total, 1)))
        # Also enforce: each external ≤ cap of final total. Using the bound above
        # ensures each ≤ cap when only one external; with multiple externals we
        # also cap so sum of all externals can exceed cap — tighten per-source:
        max_per_ext = max(0, max_per_ext)

    rng = np.random.default_rng(rng_seed)
    selected_external: list[tuple[str, Path]] = []
    for src, paths in sorted(external_paths.items()):
        if max_per_ext <= 0:
            continue
        if len(paths) <= max_per_ext:
            take = paths
        else:
            idx = rng.choice(len(paths), size=max_per_ext, replace=False)
            take = [paths[int(i)] for i in sorted(idx)]
        for p in take:
            selected_external.append((src, p))

    # Additional global external mass cap: sum(external) / total ≤ external_cap
    # Shrink proportionally if violated.
    def _total(c: int, e: int) -> int:
        return c + e

    n_ext = len(selected_external)
    n_core = n_core_total
    tot = _total(n_core, n_ext)
    if tot > 0 and n_ext / tot > external_cap + 1e-12:
        allow = int(math.floor(external_cap * n_core / max(1e-12, 1.0 - external_cap)))
        allow = max(0, allow)
        if n_ext > allow:
            # Keep stratified by source as much as possible
            by_e: dict[str, list[Path]] = defaultdict(list)
            for s, p in selected_external:
                by_e[s].append(p)
            # proportional shrink
            new_ext: list[tuple[str, Path]] = []
            sources_e = sorted(by_e.keys())
            if sources_e and allow > 0:
                # allocate floor(allow / n_src) then remainder
                base = allow // len(sources_e)
                rem = allow - base * len(sources_e)
                for j, s in enumerate(sources_e):
                    k = base + (1 if j < rem else 0)
                    for p in by_e[s][:k]:
                        new_ext.append((s, p))
            selected_external = new_ext

    ordered: list[tuple[str, Path]] = (
        list(core_paths) + list(sibling_extra) + list(selected_external)
    )
    # Stable sort by path name for determinism of non-oversample part, but keep
    # oversample duplicates as consecutive blocks after first occurrence of sibling.
    # For train split we shuffle indices later via seed if needed — keep as-is.

    counts: dict[str, int] = defaultdict(int)
    for s, _p in ordered:
        counts[s] += 1
    total = len(ordered)
    fractions = {s: (counts[s] / total if total else 0.0) for s in sorted(counts)}

    # Per-source external fraction check
    for s, frac in fractions.items():
        if is_external(s) and frac > external_cap + 1e-6:
            # Should not happen after global cap; stamp warning
            pass

    # Weights: optional 1/n_source (unique sources in pool, not count)
    n_sources = len(counts) if counts else 1
    weights: list[float] = []
    for s, _p in ordered:
        if reweight_1_over_n:
            # inverse frequency: (1/n_sources) / (count_s/total) = total/(n_sources*count_s)
            w = (total / (n_sources * max(counts[s], 1))) if total else 1.0
        else:
            w = 1.0
        weights.append(float(w))

    notes = [
        f"mix_policy={MIX_POLICY_ESTRELLA_FLOOR_V1}",
        f"external_cap={external_cap}",
        f"sibling_oversample={sibling_oversample}",
        f"held={held}",
        f"sibling={sibling}",
        f"exclude_tobarra={exclude_tobarra}",
        f"reweight_1_over_n={reweight_1_over_n}",
        "tobarra_stress_only_not_in_core_train",
    ]
    return {
        "held": held,
        "paths": [p for _s, p in ordered],
        "path_sources": [s for s, _p in ordered],
        "weights": weights,
        "counts_by_source": dict(sorted(counts.items())),
        "fractions_by_source": fractions,
        "n_train_designed": total,
        "excluded": sorted(set(excluded)),
        "sibling": sibling,
        "sibling_extra_n": len(sibling_extra),
        "external_cap": external_cap,
        "max_per_external_source_pre_global": max_per_ext,
        "policy_notes": notes,
        "reweight_1_over_n": reweight_1_over_n,
    }


def load_sources(src_root: Path) -> dict[str, list[Path]]:
    import numpy as np

    by_src: dict[str, list[Path]] = defaultdict(list)
    for split in ("train", "val", "test"):
        d = src_root / split
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.npz")):
            with np.load(p, allow_pickle=True) as z:
                if "source" in z.files:
                    src = str(z["source"])
                    # np.array scalar → strip
                    if src.startswith("["):
                        src = str(z["source"].item()) if hasattr(z["source"], "item") else src
                else:
                    src = "unknown"
            by_src[str(src)].append(p)
    return dict(by_src)


def build_mix_lofo(
    src_root: Path,
    out_root: Path,
    *,
    mix_policy: str = MIX_POLICY_ESTRELLA_FLOOR_V1,
    external_cap: float = DEFAULT_EXTERNAL_CAP,
    sibling_oversample: float = DEFAULT_SIBLING_OVERSAMPLE,
    exclude_tobarra: bool = True,
    reweight_1_over_n: bool = True,
    clean: bool = True,
    dry_run: bool = False,
    val_fraction: float = 0.1,
    folds: list[str] | None = None,
) -> dict[str, Any]:
    if mix_policy != MIX_POLICY_ESTRELLA_FLOOR_V1:
        raise ValueError(
            f"unsupported mix_policy={mix_policy!r}; only {MIX_POLICY_ESTRELLA_FLOOR_V1}"
        )

    by_src = load_sources(src_root)
    if len(by_src) < 2 and not dry_run:
        raise SystemExit(f"Need >=2 sources in {src_root}, found {list(by_src)}")

    if clean and out_root.exists() and not dry_run:
        shutil.rmtree(out_root)

    held_list = folds or sorted(by_src.keys())
    # Also allow designing core+known folds when dry-run with empty disk
    if dry_run and not by_src:
        held_list = folds or sorted(CORE_SOURCES)

    manifest: dict[str, Any] = {
        "schema": "wfd_ml_lofo_mix_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "mix_policy": mix_policy,
        "work_class": "data_mix_estrella_floor_v1",
        "src_root": str(src_root.as_posix()),
        "out_root": str(out_root.as_posix()),
        "external_cap": external_cap,
        "sibling_oversample": sibling_oversample,
        "exclude_tobarra_from_train": exclude_tobarra,
        "reweight_1_over_n": reweight_1_over_n,
        "sources_available": {k: len(v) for k, v in sorted(by_src.items())},
        "core_sources": sorted(CORE_SOURCES),
        "estrella_siblings": dict(ESTRELLA_SIBLINGS),
        "val_split": (
            "stratified_by_source ~val_fraction; not raw ordered tail "
            "(avoids external-only val when ordered=core+sibling+external)"
        ),
        "board_metrics_note": (
            "Report core-3 mean/min; Hellín fold if D3 applicable; "
            "ACOM2 separate; Tobarra stress-only"
        ),
        "folds": {},
        "dry_run": dry_run,
        "mutated_sealed_holdout_v1": False,
        "leak_audit_required": True,
        "leak_audit_command": (
            "python scripts/audit_lofo_pack_leak.py --lofo-root " + str(out_root.as_posix())
        ),
    }

    for held in held_list:
        if held not in by_src and not dry_run:
            continue
        # Ensure held key exists for design even if only in folds filter
        local_by = dict(by_src)
        if held not in local_by:
            local_by[held] = []

        design = design_train_pool(
            local_by,
            held,
            external_cap=external_cap,
            sibling_oversample=sibling_oversample,
            exclude_tobarra=exclude_tobarra,
            reweight_1_over_n=reweight_1_over_n,
        )
        train_paths: list[Path] = design["paths"]
        train_sources: list[str] = design["path_sources"]
        weights: list[float] = design["weights"]

        n = len(train_paths)
        n_val = max(1, int(n * val_fraction)) if n else 0
        # Stratified val by source (NIT-1): avoid dumping only external tail into val.
        # Deterministic: within each source take last floor(n_src * val_fraction) (+ remainder).
        tr_paths, tr_sources, tr_weights = [], [], []
        val_paths, val_sources, val_weights = [], [], []
        if n_val and n:
            by_idx: dict[str, list[int]] = defaultdict(list)
            for i, s in enumerate(train_sources):
                by_idx[s].append(i)
            val_idx: set[int] = set()
            # proportional val per source
            sources_sorted = sorted(by_idx.keys())
            remaining = n_val
            for j, s in enumerate(sources_sorted):
                idxs = by_idx[s]
                # last sources absorb remainder to hit n_val exactly
                if j == len(sources_sorted) - 1:
                    k = min(remaining, len(idxs))
                else:
                    k = min(remaining, max(0, int(round(val_fraction * len(idxs)))))
                    # leave at least 1 train if source has ≥2
                    if len(idxs) >= 2:
                        k = min(k, len(idxs) - 1)
                    remaining -= k
                    if remaining < 0:
                        k += remaining
                        remaining = 0
                for i in idxs[-k:] if k else []:
                    val_idx.add(i)
            # top up if short of n_val
            if len(val_idx) < n_val:
                for i in range(n - 1, -1, -1):
                    if i not in val_idx:
                        val_idx.add(i)
                    if len(val_idx) >= n_val:
                        break
            for i in range(n):
                if i in val_idx:
                    val_paths.append(train_paths[i])
                    val_sources.append(train_sources[i])
                    val_weights.append(weights[i])
                else:
                    tr_paths.append(train_paths[i])
                    tr_sources.append(train_sources[i])
                    tr_weights.append(weights[i])
        else:
            tr_paths = list(train_paths)
            tr_sources = list(train_sources)
            tr_weights = list(weights)

        test_paths = list(local_by.get(held, []))

        fold_dir = out_root / held
        train_dir = fold_dir / "train"
        val_dir = fold_dir / "val"
        test_dir = fold_dir / "test"

        copy_counts = {"train": 0, "val": 0, "test": 0}
        if not dry_run:
            train_dir.mkdir(parents=True, exist_ok=True)
            val_dir.mkdir(parents=True, exist_ok=True)
            test_dir.mkdir(parents=True, exist_ok=True)

            # Overwrite-safe unique names when oversampling (duplicate paths)
            seen_train: dict[str, int] = defaultdict(int)
            for p, _src, _w in zip(tr_paths, tr_sources, tr_weights, strict=True):
                seen_train[p.name] += 1
                suffix = "" if seen_train[p.name] == 1 else f"__os{seen_train[p.name]}"
                dest_name = p.stem + suffix + p.suffix
                shutil.copy2(p, train_dir / dest_name)
                copy_counts["train"] += 1

            seen_val: dict[str, int] = defaultdict(int)
            for p in val_paths:
                seen_val[p.name] += 1
                suffix = "" if seen_val[p.name] == 1 else f"__os{seen_val[p.name]}"
                dest_name = p.stem + suffix + p.suffix
                shutil.copy2(p, val_dir / dest_name)
                copy_counts["val"] += 1

            for p in sorted(test_paths):
                shutil.copy2(p, test_dir / p.name)
                copy_counts["test"] += 1

            # Sampler weights stamp (train only, aligned to written order)
            weight_doc = {
                "schema": "wfd_ml_lofo_mix_sample_weights_v1",
                "held": held,
                "reweight_1_over_n": reweight_1_over_n,
                "n": len(tr_weights),
                "weights": tr_weights,
                "sources": tr_sources,
                "note": "1/n_source style weights; optional for WeightedRandomSampler",
            }
            (fold_dir / "train_sample_weights.json").write_text(
                json.dumps(weight_doc, indent=2), encoding="utf-8"
            )
        else:
            copy_counts = {
                "train": len(tr_paths),
                "val": len(val_paths),
                "test": len(test_paths),
            }

        # Honesty: Tobarra must not appear in train when exclude_tobarra
        train_src_set = set(tr_sources)
        tobarra_in_train = sorted(s for s in train_src_set if is_tobarra(s))
        held_in_train = held in train_src_set

        manifest["folds"][held] = {
            "train": copy_counts["train"],
            "val": copy_counts["val"],
            "test": copy_counts["test"],
            "counts_by_source": design["counts_by_source"],
            "fractions_by_source": design["fractions_by_source"],
            # recompute fractions on train-only (post val split)
            "train_counts_by_source": _count_list(tr_sources),
            "train_fractions_by_source": _frac_list(tr_sources),
            "excluded": design["excluded"],
            "sibling": design["sibling"],
            "sibling_extra_n": design["sibling_extra_n"],
            "tobarra_in_train": tobarra_in_train,
            "held_in_train_leak": held_in_train,
            "external_cap": external_cap,
            "policy_notes": design["policy_notes"],
        }
        print(held, manifest["folds"][held].get("train_fractions_by_source"), flush=True)

    return manifest


def _count_list(sources: list[str]) -> dict[str, int]:
    c: dict[str, int] = defaultdict(int)
    for s in sources:
        c[s] += 1
    return dict(sorted(c.items()))


def _frac_list(sources: list[str]) -> dict[str, float]:
    c = _count_list(sources)
    n = sum(c.values()) or 1
    return {k: v / n for k, v in c.items()}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src-root", type=Path, default=DEFAULT_SRC)
    p.add_argument("--out-root", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--mix-policy",
        type=str,
        default=MIX_POLICY_ESTRELLA_FLOOR_V1,
        choices=[MIX_POLICY_ESTRELLA_FLOOR_V1],
    )
    p.add_argument("--external-cap", type=float, default=DEFAULT_EXTERNAL_CAP)
    p.add_argument("--sibling-oversample", type=float, default=DEFAULT_SIBLING_OVERSAMPLE)
    p.add_argument(
        "--include-tobarra-train",
        action="store_true",
        help="Opt-in Tobarra into train (default: excluded; stress-only)",
    )
    p.add_argument("--no-reweight", action="store_true")
    p.add_argument("--no-clean", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--folds", type=str, default=None, help="Comma-separated held sources")
    p.add_argument("--manifest-out", type=Path, default=None)
    args = p.parse_args(argv)

    src_root = args.src_root.resolve()
    out_root = args.out_root.resolve()
    sealed = (ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1").resolve()
    if out_root == sealed:
        print("refuse: out-root must not be sealed holdout_v1", file=sys.stderr)
        return 2

    if not src_root.is_dir() and not args.dry_run:
        print(f"missing src-root: {src_root}", file=sys.stderr)
        return 1

    fold_list = None
    if args.folds:
        fold_list = [x.strip() for x in args.folds.split(",") if x.strip()]

    try:
        manifest = build_mix_lofo(
            src_root,
            out_root,
            mix_policy=args.mix_policy,
            external_cap=float(args.external_cap),
            sibling_oversample=float(args.sibling_oversample),
            exclude_tobarra=not bool(args.include_tobarra_train),
            reweight_1_over_n=not bool(args.no_reweight),
            clean=not args.no_clean,
            dry_run=bool(args.dry_run),
            folds=fold_list,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Fail if any fold leaked held or Tobarra into train
    bad = False
    for held, row in manifest.get("folds", {}).items():
        if row.get("held_in_train_leak"):
            print(f"LEAK: held {held} in train", file=sys.stderr)
            bad = True
        if row.get("tobarra_in_train") and not args.include_tobarra_train:
            print(f"Tobarra in train for fold {held}: {row['tobarra_in_train']}", file=sys.stderr)
            bad = True
        for src, frac in (row.get("train_fractions_by_source") or {}).items():
            if is_external(src) and frac > float(args.external_cap) + 1e-3:
                print(
                    f"external cap exceeded fold={held} src={src} frac={frac}",
                    file=sys.stderr,
                )
                bad = True

    man_path = args.manifest_out
    if man_path is None:
        man_path = (
            out_root / "manifest.json"
            if not args.dry_run
            else (ROOT / "outputs" / "ml_eval" / "lofo_mix_estrella_v1_dry_run.json")
        )
    man_path = Path(man_path)
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)
        (out_root / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Wrote", man_path)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
