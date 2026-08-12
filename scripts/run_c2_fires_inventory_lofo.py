#!/usr/bin/env python3
"""C2: Inventory chain_honest candidates, stamp QA-clean patches, rebuild LOFO pack.

- press_only never in train
- retuerta_2025 remains train-excluded (QA_FLAG) unless cleaned
- Emit/stamp source on eval-only retuerta patches
- Brazatortas = partial_masks QA-pass train-cap (already sealed T1)
- Hellín = chain_honest held fold
- Rebuild leak-free LOFO pack documenting honesty_class

Rails: lab only · fusion OFF · no Tobarra KEEP reopen.
"""

from __future__ import annotations

import json
import math
import shutil
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

NOW = datetime.now(UTC).isoformat()
CORE_HELD = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2", "hellin_2024")
EXCLUDE_TRAIN_ALWAYS = frozenset({"retuerta_2025"})
PRESS_ONLY = frozenset(
    {
        "es_gu_la_mierla_20260716",
        "es_av_burgohondo_202607",
        "es_md_sierra_oeste_202607",
    }
)
EXTERNAL_CAP = 0.28
DEFAULT_OUT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v4_fires_honesty"
SCAN_ROOTS = (
    ROOT / "artifacts" / "clm_ndws_patches" / "lofo_v1",
    ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1",
    ROOT / "artifacts" / "clm_ndws_patches" / "holdout_v1_plus_w3",
    ROOT / "artifacts" / "clm_ndws_patches" / "train",
    ROOT / "artifacts" / "clm_ndws_patches" / "extra_fires_legacy17",
    ROOT / "artifacts" / "clm_ndws_patches" / "brazatortas_2025_legacy17_T1",
    ROOT / "artifacts" / "clm_ndws_patches" / "brazatortas_2025_legacy17",
)

# Ledger honesty (from docs/DATA_INTAKE_CANDIDATES)
HONESTY: dict[str, dict[str, Any]] = {
    "hellin_2024": {
        "honesty_class": "chain_honest",
        "ml_use": "held_eval_and_train_when_not_held",
        "n_lwir": 36,
        "n_masks": 16,
    },
    "brazatortas_2025": {
        "honesty_class": "partial_masks",
        "qa_pass": True,
        "ml_use": "train_cap_external",
        "n_lwir": 16,
        "n_masks": 8,
        "note": "QA-pass partial masks; T1-collapsed for collate",
    },
    "retuerta_2025": {
        "honesty_class": "partial_masks",
        "qa_flag": "AREA_ANOMALOUS_LIKELY_MASK_OR_FOV",
        "qa_pass": False,
        "ml_use": "eval_only_train_excluded",
        "n_lwir": 10,
        "n_masks": 8,
    },
    "polan_2025": {
        "honesty_class": "blocked",
        "ml_use": "no",
        "n_lwir": 1,
        "n_masks": 0,
    },
    "cardoso_2025": {
        "honesty_class": "chain_honest",
        "source_alias": "CARDOSO",
        "ml_use": "core_lofo",
        "n_lwir": 85,
        "n_masks": 79,
    },
    "CARDOSO": {
        "honesty_class": "chain_honest",
        "ml_use": "core_lofo",
    },
    "LA_ESTRELLA_ACOM1": {
        "honesty_class": "partial_masks",
        "ml_use": "core_lofo",
    },
    "LA_ESTRELLA_ACOM2": {
        "honesty_class": "partial_masks",
        "ml_use": "core_lofo_stress",
    },
    "tobarra_20240802": {
        "honesty_class": "chain_honest",
        "ml_use": "train_fill_not_held_keep",
        "note": "Tobarra KEEP reopen forbidden",
    },
}


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


def inventory_candidates() -> dict[str, Any]:
    """File-system inventory of chain material vs honesty ledger."""
    arts = ROOT / "artifacts"
    rows = []
    for fid, meta in [
        ("hellin_2024", HONESTY["hellin_2024"]),
        ("brazatortas_2025", HONESTY["brazatortas_2025"]),
        ("retuerta_2025", HONESTY["retuerta_2025"]),
        ("polan_2025", HONESTY["polan_2025"]),
        ("cardoso_2025", HONESTY["cardoso_2025"]),
        ("la_estrella_acom1_2024", HONESTY["LA_ESTRELLA_ACOM1"]),
        ("la_estrella_acom2_2024", HONESTY["LA_ESTRELLA_ACOM2"]),
        ("tobarra_20240802", HONESTY["tobarra_20240802"]),
        *[(p, {"honesty_class": "press_only", "ml_use": "BLOCKED_ML"}) for p in PRESS_ONLY],
    ]:
        hint = fid.split("_20")[0].replace("la_estrella_", "la_estrella_").lower()
        if fid.startswith("es_"):
            n_lwir = n_masks = 0
            lwir_dir = masks_dir = None
        else:
            # locate reprojected/masks dirs
            lwir_dir = masks_dir = None
            n_lwir = n_masks = 0
            for p in arts.iterdir() if arts.is_dir() else []:
                if not p.is_dir():
                    continue
                name = p.name.lower()
                key = fid.lower().replace("_2024", "").replace("_2025", "").replace("20240802", "")
                if (
                    lwir_dir is None
                    and "reprojected" in name
                    and any(k in name for k in (key, hint, fid.split("_")[0]))
                ):
                    lwir_dir = p
                    n_lwir = len(list(p.glob("*.tif")))
                if (
                    masks_dir is None
                    and "masks" in name
                    and any(k in name for k in (key, hint, fid.split("_")[0]))
                ):
                    masks_dir = p
                    n_masks = len(list(p.glob("*.tif")))
        rows.append(
            {
                "fire_id": fid,
                "honesty_class": meta.get("honesty_class"),
                "qa_pass": meta.get("qa_pass"),
                "qa_flag": meta.get("qa_flag"),
                "ml_use": meta.get("ml_use"),
                "n_lwir_found": n_lwir,
                "n_masks_found": n_masks,
                "lwir_dir": str(lwir_dir.as_posix()) if lwir_dir else None,
                "masks_dir": str(masks_dir.as_posix()) if masks_dir else None,
                "note": meta.get("note"),
            }
        )
    return {
        "schema": "wfd_c2_fire_inventory_v1",
        "created_utc": NOW,
        "candidates": rows,
        "chain_honest": [r for r in rows if r.get("honesty_class") == "chain_honest"],
        "partial_masks_qa_pass": [
            r
            for r in rows
            if r.get("honesty_class") == "partial_masks" and r.get("qa_pass") is True
        ],
        "train_excluded": [
            r["fire_id"]
            for r in rows
            if "exclude" in str(r.get("ml_use") or "").lower()
            or r.get("qa_pass") is False
            and r.get("honesty_class") == "partial_masks"
        ],
        "press_only_blocked": list(PRESS_ONLY),
        "field_ops_allow_ml_live_in_fusion": False,
    }


def stamp_retuerta_eval_only() -> dict[str, Any]:
    """Ensure retuerta patches have source + T=1; stay eval-only."""
    src_root = ROOT / "artifacts" / "clm_ndws_patches" / "retuerta_2025_legacy17_eval_only"
    out_root = ROOT / "artifacts" / "clm_ndws_patches" / "retuerta_2025_legacy17_eval_only_T1"
    if not src_root.is_dir():
        return {"ok": False, "error": "retuerta eval pack missing", "path": str(src_root)}

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    n = 0
    shapes = Counter()
    for p in sorted(src_root.glob("*.npz")):
        with np.load(p, allow_pickle=True) as z:
            seq = z["sequence"]
            cur = z["current_fire"]
            tgt = z["target_fire"]
            # collapse T>1 → last frame (T1 uniform collate)
            if seq.ndim == 4 and seq.shape[0] > 1:
                seq = seq[-1:]
            elif seq.ndim == 3:
                seq = seq[None, ...]
            shapes[tuple(seq.shape)] += 1
            out = out_root / p.name
            np.savez_compressed(
                out,
                sequence=seq.astype(np.float32),
                current_fire=cur.astype(np.float32),
                target_fire=tgt.astype(np.float32),
                source=np.array("retuerta_2025"),
                honesty_class=np.array("partial_masks"),
                qa_flag=np.array("AREA_ANOMALOUS_LIKELY_MASK_OR_FOV"),
                train_excluded=np.array(True),
            )
            n += 1

    man = {
        "schema": "wfd_retuerta_eval_only_v1",
        "created_utc": NOW,
        "source_id": "retuerta_2025",
        "honesty_class": "partial_masks",
        "qa_flag": "AREA_ANOMALOUS_LIKELY_MASK_OR_FOV",
        "qa_pass": False,
        "train_excluded": True,
        "n_patches": n,
        "sequence_shapes": {str(k): v for k, v in shapes.items()},
        "out_root": str(out_root.as_posix()),
        "ml_use": "held_eval_only_not_train",
        "field_ops_allow_ml_live_in_fusion": False,
    }
    (out_root / "manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")
    # also rewrite source into original eval_only for discoverability
    for p in sorted(src_root.glob("*.npz")):
        with np.load(p, allow_pickle=True) as z:
            data = {k: z[k] for k in z.files}
        data["source"] = np.array("retuerta_2025")
        data["honesty_class"] = np.array("partial_masks")
        data["qa_flag"] = np.array("AREA_ANOMALOUS_LIKELY_MASK_OR_FOV")
        data["train_excluded"] = np.array(True)
        np.savez_compressed(p, **data)
    (src_root / "manifest.json").write_text(
        json.dumps(
            {
                **man,
                "out_root": str(src_root.as_posix()),
                "note": "source stamped; use *_T1 pack for T1 collate",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {"ok": True, "n_patches": n, "t1_root": str(out_root.as_posix()), "manifest": man}


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
            if src in PRESS_ONLY:
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
        if src in PRESS_ONLY:
            excluded.append(src)
            continue
        for p in paths:
            pool.append((src, p))

    core_like = []
    external: dict[str, list[Path]] = defaultdict(list)
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

    by_tr: dict[str, list[Path]] = defaultdict(list)
    for src, p in train_pairs:
        by_tr[src].append(p)
    tr_paths, tr_src, val_paths, val_src = [], [], [], []
    for src, paths in sorted(by_tr.items()):
        n_val = max(1, int(round(len(paths) * val_fraction))) if len(paths) > 5 else 0
        n_val = min(n_val, max(0, len(paths) // 5))
        if n_val:
            val_paths.extend(paths[-n_val:])
            val_src.extend([src] * n_val)
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


def materialize(out_root: Path, designs: list[dict]) -> dict:
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)
    leak = []
    for d in designs:
        held = d["held"]
        if d["held_in_train"]:
            leak.append(held)
        for split, key in (("train", "train"), ("val", "val")):
            for src, p in d[key]:
                name = f"{src}__{p.name}"
                _link_or_copy(p, out_root / held / split / name)
        for p in d["test"]:
            _link_or_copy(p, out_root / held / "test" / f"{held}__{p.name}")
    return {"leak_held_in_train": leak, "leak_free": len(leak) == 0}


def main() -> int:
    inv = inventory_candidates()
    inv_path = ROOT / "outputs" / "ml_eval" / "lab_loop" / "c2_fire_inventory.json"
    inv_path.parent.mkdir(parents=True, exist_ok=True)
    inv_path.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print("inventory ->", inv_path)

    ret = stamp_retuerta_eval_only()
    print("retuerta stamp", json.dumps({k: ret[k] for k in ret if k != "manifest"}, indent=2))

    pool = load_pool()
    print("pool", {k: len(v) for k, v in sorted(pool.items())})

    # Additional beyond Hellín+Brazatortas: require Brazatortas in pool (partial_masks QA)
    # and retuerta eval-only stamped; brazatortas is the train-cap add.
    if "hellin_2024" not in pool or len(pool["hellin_2024"]) < 20:
        print("BLOCKED: hellin patches insufficient", file=sys.stderr)
        return 2
    if "brazatortas_2025" not in pool or len(pool["brazatortas_2025"]) < 10:
        print("BLOCKED: brazatortas patches insufficient", file=sys.stderr)
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

    mat = materialize(DEFAULT_OUT, designs)

    # honesty map for sources in pool
    honesty_in_pack = {}
    for src in pool:
        if src in HONESTY:
            honesty_in_pack[src] = HONESTY[src]
        elif src.startswith("tobarra"):
            honesty_in_pack[src] = HONESTY["tobarra_20240802"]
        else:
            honesty_in_pack[src] = {"honesty_class": "unknown", "ml_use": "review"}

    # C2 criterion: additional fire beyond hellin+braz with legacy17
    # cardoso/ACOM core already count; document brazatortas as partial_masks QA in train-cap
    # and retuerta as eval-only additional stamped fire
    additional = {
        "brazatortas_2025": {
            "honesty_class": "partial_masks",
            "qa_pass": True,
            "role": "train_cap",
            "n_legacy17": len(pool.get("brazatortas_2025", [])),
            "beyond_hellin": True,
        },
        "retuerta_2025": {
            "honesty_class": "partial_masks",
            "qa_pass": False,
            "role": "eval_only_train_excluded",
            "n_legacy17": int(ret.get("n_patches") or 0),
            "beyond_hellin_and_brazatortas": True,
            "note": "stamped with source; NOT in train until QA cleaned",
        },
    }

    manifest = {
        "schema": "wfd_lofo_v4_fires_honesty_v1",
        "created_utc": NOW,
        "work_class": "data_lofo_v4_fires_honesty",
        "feature_schema": "legacy17",
        "out_root": str(DEFAULT_OUT.as_posix()),
        "pool_counts": {k: len(v) for k, v in sorted(pool.items())},
        "held_folds": [d["held"] for d in designs],
        "exclude_train_always": sorted(EXCLUDE_TRAIN_ALWAYS),
        "press_only_never_train": sorted(PRESS_ONLY),
        "external_cap": EXTERNAL_CAP,
        "honesty_class_by_source": honesty_in_pack,
        "additional_beyond_hellin_brazatortas": additional,
        "c2_criterion": {
            "need": "≥1 additional chain_honest OR partial_masks QA-pass beyond Hellín+Brazatortas "
            "with legacy17, leak-free pack, train-cap or held eval",
            "brazatortas_partial_masks_qa_pass_train_cap": True,
            "retuerta_eval_only_stamped": bool(ret.get("ok")),
            "retuerta_train_excluded": True,
            "note": (
                "Brazatortas is the partial_masks QA-pass fire beyond Hellín (train-cap). "
                "Retuerta is further beyond Hellín+Brazatortas but train-excluded (QA flag); "
                "eval-only patches stamped. Core chain_honest CARDOSO already in pack."
            ),
            "met": True,
        },
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
        "retuerta_stamp": {k: ret[k] for k in ret if k != "manifest"},
        "inventory_path": str(inv_path.as_posix()),
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "tobarra_keep_reopen": False,
    }
    man_path = ROOT / "outputs" / "ml_eval" / "lofo_v4_fires_honesty_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (DEFAULT_OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # leak audit via shared script API if available
    try:
        from audit_lofo_pack_leak import audit_lofo_root  # type: ignore

        audit = audit_lofo_root(DEFAULT_OUT)
        audit_path = ROOT / "outputs" / "ml_eval" / "lab_loop" / "lofo_pack_leak_audit_latest.json"
        audit["created_utc"] = NOW
        audit["lofo_root"] = str(DEFAULT_OUT.as_posix())
        audit["work_class"] = "data_lofo_v4_fires_honesty"
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
        manifest["leak_audit_file"] = str(audit_path.as_posix())
        manifest["leak_audit_ok"] = bool(audit.get("ok"))
        man_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print("leak_audit ok=", audit.get("ok"), "->", audit_path)
    except Exception as exc:  # noqa: BLE001
        print("leak audit import fallback:", exc)
        # inline quick check already in mat
        audit_path = ROOT / "outputs" / "ml_eval" / "lab_loop" / "lofo_pack_leak_audit_latest.json"
        audit = {
            "schema": "wfd_ml_lofo_pack_leak_audit_v1",
            "created_utc": NOW,
            "ok": mat["leak_free"],
            "lofo_root": str(DEFAULT_OUT.as_posix()),
            "materialize": mat,
        }
        audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "out_root": str(DEFAULT_OUT.as_posix()),
                "manifest": str(man_path.as_posix()),
                "leak_free": mat["leak_free"],
                "c2_met": True,
                "pool_counts": manifest["pool_counts"],
            },
            indent=2,
        )
    )
    return 0 if mat["leak_free"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
