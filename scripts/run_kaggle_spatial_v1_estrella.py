#!/usr/bin/env python3
"""One-shot Kaggle operator: spatial_v1 + estrella_floor_v1 LOFO residual-small.

End-to-end path (Windows-friendly short staging path for Kaggle CLI)::

    $env:PYTHONPATH = "."
    python scripts/run_kaggle_spatial_v1_estrella.py
    # score only (existing COMPLETE board):
    python scripts/run_kaggle_spatial_v1_estrella.py --score-only
    # package + push without long poll:
    python scripts/run_kaggle_spatial_v1_estrella.py --no-watch

Rails (immutable):
* residual-small · no larger U-Net · no multi_if/legacy17 init (channel mismatch)
* lab only · fusion OFF · IoU ≠ ROS · no Tobarra KEEP reopen
* Do **not** invent KEEP; kill scorer decides honestly
* Sealed recipe T1 ≠ feature work stamp

Exit codes:
  0  success (push ok / score written / dry-run ok) — verdict may still be KILL
  1  incomplete (kernel still running after poll, missing board after COMPLETE)
  2  missing pack root / missing required local data
  3  kaggle CLI / auth / push failure
  4  bad args / internal error
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Defaults (E2-P2 spatial estrella)
DEFAULT_PACK_ROOT = ROOT / "artifacts" / "clm_ndws_patches" / "lofo_mix_spatial_estrella_v1"
DEFAULT_KERNEL_SCRIPT = ROOT / "kaggle_job" / "run_spatial_v1_lofo_estrella.py"
DEFAULT_KERNEL_META = ROOT / "kaggle_job" / "kernel-metadata-spatial-v1-estrella.json"
DEFAULT_DATASET_SLUG = "alonsoalviraaaa/wfd-lofo-spatial-estrella-v1"
DEFAULT_KERNEL_SLUG = "alonsoalviraaaa/wfd-spatial-v1-estrella-lofo"
DEFAULT_DATASET_TITLE = "WFD LOFO Spatial Estrella V1"
DEFAULT_OUT = ROOT / "outputs" / "kaggle_spatial_v1_estrella"
DEFAULT_SHORT_ROOT = Path(r"C:\temp\wfd_kaggle_spatial_v1")
DEFAULT_FP_STORE = ROOT / "outputs" / "ml_eval" / "kaggle_spatial_v1_estrella_pack_fingerprint.json"
CORE3 = ("CARDOSO", "LA_ESTRELLA_ACOM1", "LA_ESTRELLA_ACOM2")
BOARD_NAME = "spatial_v1_estrella_lofo_board.json"
EXPERIMENT_ID = "E2_P2_spatial_v1_estrella"
WORK_CLASS = "feature_spatial_v1+data_mix_estrella_floor_v1"
FEATURE_SCHEMA = "spatial_v1"
FINISH_HINT = (
    "python scripts/run_kaggle_spatial_v1_estrella.py --watch-only\n"
    "  or: python scripts/watch_kaggle_spatial_v1_estrella.py\n"
    "  or: python scripts/run_kaggle_spatial_v1_estrella.py --download-only\n"
    "  or: python scripts/run_kaggle_spatial_v1_estrella.py --score-only"
)

# Exit codes
EXIT_OK = 0
EXIT_INCOMPLETE = 1
EXIT_MISSING_DATA = 2
EXIT_KAGGLE = 3
EXIT_ERROR = 4


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested)
# ---------------------------------------------------------------------------


def looks_like_lofo_pack(root: Path) -> bool:
    """True if root has core-3 folds each with a train/ directory."""
    if not root.is_dir():
        return False
    return all((root / f / "train").is_dir() for f in CORE3)


def pack_fingerprint(pack_root: Path, *, sample_limit: int = 64) -> str:
    """Stable content fingerprint of pack (manifest + sample file sizes/mtimes).

    Cheap: does not hash every npz. Used to skip dataset version when unchanged.
    """
    h = hashlib.sha256()
    man = pack_root / "manifest.json"
    if man.is_file():
        h.update(man.read_bytes())
    for fold in CORE3:
        for split in ("train", "val", "test"):
            d = pack_root / fold / split
            if not d.is_dir():
                h.update(f"missing:{fold}/{split}".encode())
                continue
            files = sorted(d.glob("*.npz"))
            h.update(f"{fold}/{split}:{len(files)}".encode())
            for p in files[:sample_limit]:
                st = p.stat()
                h.update(f"{p.name}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()[:16]


def write_bom_free_json(path: Path, obj: dict[str, Any], *, indent: int = 2) -> Path:
    """Write JSON as UTF-8 without BOM (Kaggle CLI chokes on BOM / utf-16)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, indent=indent) + "\n").encode("utf-8")  # no BOM
    # Guard: never write UTF-16 / BOM accidentally
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("BOM detected in JSON bytes")
    path.write_bytes(raw)
    return path


def dataset_metadata_dict(
    slug: str = DEFAULT_DATASET_SLUG,
    title: str = DEFAULT_DATASET_TITLE,
) -> dict[str, Any]:
    return {
        "title": title,
        "id": slug,
        "licenses": [{"name": "CC0-1.0"}],
    }


def kernel_metadata_dict(
    *,
    kernel_slug: str = DEFAULT_KERNEL_SLUG,
    code_file: str = "run_spatial_v1_lofo_estrella.py",
    dataset_slug: str = DEFAULT_DATASET_SLUG,
    title: str = "WFD Spatial V1 Estrella LOFO",
    enable_gpu: bool = True,
    enable_internet: bool = True,
    machine_shape: str = "NvidiaTeslaT4",
) -> dict[str, Any]:
    return {
        "id": kernel_slug,
        "title": title,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "script",
        "is_private": True,
        "enable_gpu": enable_gpu,
        "enable_internet": enable_internet,
        "machine_shape": machine_shape,
        "dataset_sources": [dataset_slug],
        "competition_sources": [],
        "kernel_sources": [],
    }


def zip_lofo_pack(pack_root: Path, zip_path: Path) -> Path:
    """Zip LOFO pack so extract yields CORE3/*/train (or nested folder with same)."""
    if not looks_like_lofo_pack(pack_root):
        raise FileNotFoundError(f"pack root missing core-3 train folds: {pack_root}")
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    # Arc names relative to pack_root so extract can land folds at root or under
    # a single parent folder (kernel discovers both).
    prefix = pack_root.name  # lofo_mix_spatial_estrella_v1
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(pack_root.rglob("*")):
            if path.is_file():
                arc = f"{prefix}/{path.relative_to(pack_root).as_posix()}"
                zf.write(path, arcname=arc)
    return zip_path


def stage_dataset_dir(
    pack_root: Path,
    stage_dir: Path,
    *,
    dataset_slug: str = DEFAULT_DATASET_SLUG,
    dataset_title: str = DEFAULT_DATASET_TITLE,
    force_rebuild_zip: bool = False,
    existing_zip: Path | None = None,
) -> dict[str, Any]:
    """Build short-path dataset folder: zip + BOM-free dataset-metadata.json."""
    if not looks_like_lofo_pack(pack_root):
        raise FileNotFoundError(f"pack root missing core-3 train folds: {pack_root}")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)

    zip_name = f"{pack_root.name}.zip"
    dest_zip = stage_dir / zip_name
    rebuilt = False
    if existing_zip is not None and existing_zip.is_file() and not force_rebuild_zip:
        shutil.copy2(existing_zip, dest_zip)
        source = "copied_existing_zip"
    elif force_rebuild_zip or existing_zip is None or not Path(existing_zip or "").is_file():
        zip_lofo_pack(pack_root, dest_zip)
        rebuilt = True
        source = "built_from_pack"
    else:
        zip_lofo_pack(pack_root, dest_zip)
        rebuilt = True
        source = "built_from_pack"

    write_bom_free_json(
        stage_dir / "dataset-metadata.json",
        dataset_metadata_dict(dataset_slug, dataset_title),
    )
    fp = pack_fingerprint(pack_root)
    stamp = {
        "schema": "wfd_kaggle_spatial_dataset_stage_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "pack_root": str(pack_root.resolve()),
        "stage_dir": str(stage_dir.resolve()),
        "zip_path": str(dest_zip.resolve()),
        "zip_bytes": dest_zip.stat().st_size,
        "dataset_slug": dataset_slug,
        "pack_fingerprint": fp,
        "zip_source": source,
        "rebuilt_zip": rebuilt,
        "feature_schema": FEATURE_SCHEMA,
        "work_class": WORK_CLASS,
        "mix_policy": "estrella_floor_v1",
    }
    write_bom_free_json(stage_dir / "stage_manifest.json", stamp)
    return stamp


def stage_kernel_dir(
    script_src: Path,
    stage_dir: Path,
    *,
    kernel_slug: str = DEFAULT_KERNEL_SLUG,
    dataset_slug: str = DEFAULT_DATASET_SLUG,
    meta_src: Path | None = None,
) -> dict[str, Any]:
    """Copy train script + BOM-free kernel-metadata.json into short path."""
    if not script_src.is_file():
        raise FileNotFoundError(f"kernel script missing: {script_src}")
    if stage_dir.exists():
        shutil.rmtree(stage_dir)
    stage_dir.mkdir(parents=True)
    code_name = script_src.name
    shutil.copy2(script_src, stage_dir / code_name)

    if meta_src is not None and meta_src.is_file():
        meta = json.loads(meta_src.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
        meta.setdefault("id", kernel_slug)
        meta["code_file"] = code_name
        meta.setdefault("dataset_sources", [dataset_slug])
        meta.setdefault("language", "python")
        meta.setdefault("kernel_type", "script")
        meta.setdefault("enable_gpu", True)
        meta.setdefault("enable_internet", True)
        meta.setdefault("machine_shape", "NvidiaTeslaT4")
        meta.setdefault("is_private", True)
        meta.setdefault("competition_sources", [])
        meta.setdefault("kernel_sources", [])
    else:
        meta = kernel_metadata_dict(
            kernel_slug=kernel_slug,
            code_file=code_name,
            dataset_slug=dataset_slug,
        )

    write_bom_free_json(stage_dir / "kernel-metadata.json", meta)
    return {
        "stage_dir": str(stage_dir.resolve()),
        "code_file": code_name,
        "kernel_slug": meta.get("id", kernel_slug),
        "dataset_sources": meta.get("dataset_sources"),
    }


def parse_dataset_status(stdout: str) -> str:
    """Normalize kaggle datasets status output → ready|pending|error|unknown.

    Negatives (``not ready``, error/failed) are checked **before** positive
    ``ready`` so substring false-positives cannot force the reuse branch.
    """
    low = (stdout or "").strip().lower()
    if not low:
        return "unknown"
    # Exact first token / known enums
    first = low.split()[0].strip(".,;:\"'")
    if first in {"ready", "pending", "processing", "error", "failed"}:
        if first == "failed":
            return "error"
        if first == "processing":
            return "pending"
        return first
    # Ordered negatives before positive "ready"
    if "not ready" in low or "not-ready" in low:
        return "pending"
    if "error" in low or "failed" in low:
        return "error"
    if "pending" in low or "processing" in low:
        return "pending"
    # Positive ready only when not negated
    if "ready" in low and "not ready" not in low:
        return "ready"
    return first if first else "unknown"


def load_last_pack_fingerprint(path: Path) -> str | None:
    """Last successfully versioned/created pack fingerprint, if any."""
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    fp = data.get("pack_fingerprint")
    return str(fp) if fp else None


def save_last_pack_fingerprint(
    path: Path,
    fingerprint: str,
    *,
    dataset_slug: str = DEFAULT_DATASET_SLUG,
    action: str = "version",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bom_free_json(
        path,
        {
            "schema": "wfd_kaggle_spatial_pack_fingerprint_v1",
            "updated_utc": datetime.now(UTC).isoformat(),
            "pack_fingerprint": fingerprint,
            "dataset_slug": dataset_slug,
            "action": action,
        },
    )


def parse_kernel_status(stdout: str) -> str:
    """Return COMPLETE|ERROR|CANCELLED|RUNNING|QUEUED|UNKNOWN from status text."""
    up = (stdout or "").upper()
    # Prefer explicit enum-like tokens
    for token in (
        "COMPLETE",
        "ERROR",
        "CANCELLED",
        "CANCELED",
        "RUNNING",
        "QUEUED",
        "PENDING",
    ):
        if token in up:
            if token == "CANCELED":
                return "CANCELLED"
            return token
    if not (stdout or "").strip():
        return "UNKNOWN"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Kaggle CLI wrappers
# ---------------------------------------------------------------------------


def _run_kaggle(
    args: list[str],
    *,
    timeout: int = 600,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["kaggle", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def kaggle_available() -> tuple[bool, str]:
    """Return (ok, message). ok=False if CLI missing or auth broken."""
    try:
        r = _run_kaggle(["datasets", "list", "-m", "--max-size", "1"], timeout=60)
    except FileNotFoundError:
        return False, "kaggle CLI not found on PATH"
    except subprocess.TimeoutExpired:
        return False, "kaggle CLI timed out"
    except Exception as exc:  # noqa: BLE001
        return False, f"kaggle CLI error: {exc}"
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    low = text.lower()
    if r.returncode != 0:
        if "401" in text or "403" in text or "unauthorized" in low or "credentials" in low:
            return False, f"kaggle auth failure: {text[:400]}"
        return False, f"kaggle CLI rc={r.returncode}: {text[:400]}"
    return True, "ok"


def dataset_status(slug: str) -> tuple[str, str]:
    r = _run_kaggle(["datasets", "status", slug], timeout=60)
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    return parse_dataset_status(text), text


def kernel_status(slug: str) -> tuple[str, str]:
    r = _run_kaggle(["kernels", "status", slug], timeout=60)
    text = ((r.stdout or "") + (r.stderr or "")).strip()
    return parse_kernel_status(text), text


def push_dataset(
    stage_dir: Path,
    *,
    version_message: str,
    create_if_missing: bool = True,
) -> dict[str, Any]:
    """Create or version dataset from staged folder. Prefer version when ready."""
    meta = json.loads((stage_dir / "dataset-metadata.json").read_text(encoding="utf-8"))
    slug = str(meta.get("id") or DEFAULT_DATASET_SLUG)
    st, raw = dataset_status(slug)
    result: dict[str, Any] = {
        "slug": slug,
        "pre_status": st,
        "pre_raw": raw,
        "action": None,
        "rc": None,
        "stdout": "",
        "stderr": "",
    }
    if st == "ready":
        # Version only when operator rebuilt zip (caller decides); still allow version
        r = _run_kaggle(
            [
                "datasets",
                "version",
                "-p",
                str(stage_dir),
                "-m",
                version_message,
                "--dir-mode",
                "zip",
            ],
            timeout=1800,
        )
        result["action"] = "version"
    elif create_if_missing:
        r = _run_kaggle(
            ["datasets", "create", "-p", str(stage_dir), "--dir-mode", "zip"],
            timeout=1800,
        )
        result["action"] = "create"
    else:
        result["action"] = "skip_not_ready"
        result["rc"] = 1
        return result

    result["rc"] = r.returncode
    result["stdout"] = r.stdout or ""
    result["stderr"] = r.stderr or ""
    return result


def push_kernel(stage_dir: Path) -> dict[str, Any]:
    r = _run_kaggle(["kernels", "push", "-p", str(stage_dir)], timeout=300)
    return {
        "rc": r.returncode,
        "stdout": r.stdout or "",
        "stderr": r.stderr or "",
        "stage_dir": str(stage_dir),
    }


def download_kernel_output(slug: str, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = _run_kaggle(
        ["kernels", "output", slug, "-p", str(out_dir)],
        timeout=900,
    )
    boards = list(out_dir.rglob(BOARD_NAME))
    return {
        "rc": r.returncode,
        "stdout": r.stdout or "",
        "stderr": r.stderr or "",
        "board_paths": [str(p) for p in boards],
        "out_dir": str(out_dir),
    }


def poll_kernel(
    slug: str,
    *,
    poll_s: int = 120,
    max_hours: float = 6.0,
) -> dict[str, Any]:
    """Poll until COMPLETE/ERROR/CANCELLED or timeout."""
    deadline = time.time() + max_hours * 3600.0
    last = ""
    history: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            st, raw = kernel_status(slug)
        except Exception as exc:  # noqa: BLE001
            history.append(
                {
                    "utc": datetime.now(UTC).isoformat(),
                    "error": str(exc),
                }
            )
            time.sleep(min(poll_s, 60))
            continue
        last = raw
        history.append(
            {
                "utc": datetime.now(UTC).isoformat(),
                "status": st,
                "raw": raw[:300],
            }
        )
        print(f"[poll] {st}: {raw.strip()}", flush=True)
        if st in ("COMPLETE", "ERROR", "CANCELLED"):
            return {
                "terminal": True,
                "status": st,
                "raw": raw,
                "history": history,
            }
        time.sleep(poll_s)
    return {
        "terminal": False,
        "status": parse_kernel_status(last) if last else "TIMEOUT",
        "raw": last,
        "history": history,
        "note": f"timeout after {max_hours}h",
    }


# ---------------------------------------------------------------------------
# Kill score (never invents KEEP)
# ---------------------------------------------------------------------------


def score_spatial_board(
    board_path: Path,
    *,
    repo: Path = ROOT,
    experiment_id: str = EXPERIMENT_ID,
    out_kill: Path | None = None,
) -> dict[str, Any]:
    """Score E2 kill criteria from spatial board JSON. Verdict may be KILL."""
    from wildfire_front.ml.lab_metrics_lift import (
        collect_candidate_from_board,
        load_json,
        score_kill_criteria,
    )

    board = load_json(board_path)
    if not board:
        raise FileNotFoundError(f"board missing or invalid: {board_path}")

    collected = collect_candidate_from_board(board)
    folds = collected.get("folds") or {}
    mean = collected["core3"].get("mean")
    mn = collected["core3"].get("min")
    # Prefer board stamps when present
    if board.get("core3_mean_iou") is not None:
        mean = float(board["core3_mean_iou"])
    if board.get("core3_min_iou") is not None:
        mn = float(board["core3_min_iou"])

    train_complete = bool(collected.get("complete")) or (
        mean is not None and mn is not None and len(folds) >= 3
    )

    # Leak audit if present
    leak_path = repo / "outputs" / "ml_eval" / "lab_loop" / "lofo_pack_leak_audit_latest.json"
    n_leaked = 0
    leak_s: str | None = None
    if leak_path.is_file():
        ld = load_json(leak_path) or {}
        n_leaked = int(ld.get("n_leaked_train_val") or 0)
        leak_s = str(leak_path.as_posix())

    kill = score_kill_criteria(
        profile="E2",
        experiment_id=experiment_id,
        lofo_mean=mean,
        lofo_min=mn,
        fold_rows=folds,
        champion_candidate=False,
        u1_status="SKIPPED",
        n_leaked_train_val=n_leaked,
        leak_audit_path=leak_s,
        train_complete=train_complete,
        larger_unet_default=False,
        tobarra_keep_claim=False,
        test_thr_ece_fit=False,
        residual_default=True,
    )
    # Honesty stamps
    kill["feature_schema"] = FEATURE_SCHEMA
    kill["work_class"] = WORK_CLASS
    kill["board_path"] = str(board_path.as_posix())
    kill["comparability_note"] = (
        "Sealed recipe T1 (recover_v2 force_train multi_if) is NOT this board. "
        "Feature+mix work; never auto-KEEP."
    )
    kill["rails_operator"] = {
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "tobarra_keep_reopen": False,
        "larger_unet_default": False,
        "lab_only": True,
    }

    out = out_kill or (
        repo / "outputs" / "ml_eval" / "lab_loop" / f"metrics_lift_{experiment_id}_kill.json"
    )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kill, indent=2), encoding="utf-8")
    kill["_out_path"] = str(out)
    return kill


def write_operator_status(
    path: Path,
    payload: dict[str, Any],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_bom_free_json(path, payload)
    return path


def apply_score_to_op(
    op: dict[str, Any],
    board_path: Path,
    *,
    repo: Path,
    experiment_id: str,
    out_kill: Path | None,
) -> tuple[int, dict[str, Any] | None]:
    """Score board into ``op``; return (EXIT_OK, kill) or (EXIT_ERROR, None).

    All score call sites use this so internal scorer failures map to EXIT_ERROR
    and still leave operator status fields populated.
    """
    try:
        kill = score_spatial_board(
            board_path,
            repo=repo,
            experiment_id=experiment_id,
            out_kill=out_kill,
        )
    except Exception as exc:  # noqa: BLE001
        op["steps"]["score"] = {"ok": False, "error": str(exc)}
        return EXIT_ERROR, None
    op["steps"]["score"] = {
        "ok": True,
        "verdict": kill.get("verdict"),
        "out": kill.get("_out_path"),
        "mean": (kill.get("checks") or {}).get("L1_lofo_mean_lift", {}).get("value_mean"),
        "min": (kill.get("checks") or {}).get("L2_weak_floor", {}).get("value"),
        "note": "honest verdict; never auto-KEEP",
    }
    op["verdict"] = kill.get("verdict")
    return EXIT_OK, kill


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=("Package + push + watch + score spatial_v1 estrella LOFO on Kaggle T4")
    )
    p.add_argument("--repo", type=Path, default=ROOT)
    p.add_argument("--pack-root", type=Path, default=DEFAULT_PACK_ROOT)
    p.add_argument("--kernel-script", type=Path, default=DEFAULT_KERNEL_SCRIPT)
    p.add_argument("--kernel-meta", type=Path, default=DEFAULT_KERNEL_META)
    p.add_argument("--dataset-slug", type=str, default=DEFAULT_DATASET_SLUG)
    p.add_argument("--kernel-slug", type=str, default=DEFAULT_KERNEL_SLUG)
    p.add_argument(
        "--short-root",
        type=Path,
        default=DEFAULT_SHORT_ROOT,
        help="Windows short staging root (default C:\\temp\\wfd_kaggle_spatial_v1)",
    )
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument(
        "--existing-zip",
        type=Path,
        default=ROOT
        / "kaggle_job"
        / "datasets"
        / "wfd-lofo-spatial-estrella-v1"
        / "lofo_mix_spatial_estrella_v1.zip",
        help="Reuse prebuilt zip when present (skip re-zip)",
    )
    p.add_argument(
        "--force-rebuild-zip",
        action="store_true",
        help="Always re-zip pack root (version dataset after)",
    )
    p.add_argument(
        "--version-dataset",
        action="store_true",
        help=(
            "Force dataset version even if pack fingerprint matches last push "
            "(default auto-versions when fingerprint changed)"
        ),
    )
    p.add_argument(
        "--fp-store",
        type=Path,
        default=DEFAULT_FP_STORE,
        help="JSON path storing last-pushed pack fingerprint for reuse decisions",
    )
    p.add_argument(
        "--skip-dataset",
        action="store_true",
        help="Do not create/version dataset (reuse remote ready pack)",
    )
    p.add_argument(
        "--skip-push",
        action="store_true",
        help="Do not push kernel (stage + optional score only)",
    )
    p.add_argument(
        "--no-watch",
        action="store_true",
        help="Push then exit without polling",
    )
    p.add_argument(
        "--score-only",
        action="store_true",
        help="Only score existing board under --out (no Kaggle push)",
    )
    p.add_argument(
        "--download-only",
        action="store_true",
        help="Download kernel output + score if board present",
    )
    p.add_argument(
        "--watch-only",
        action="store_true",
        help="Poll running kernel until COMPLETE/ERROR then download + score",
    )
    p.add_argument("--poll-s", type=int, default=120)
    p.add_argument("--max-hours", type=float, default=6.0)
    p.add_argument(
        "--experiment-id",
        type=str,
        default=EXPERIMENT_ID,
    )
    p.add_argument(
        "--kill-out",
        type=Path,
        default=None,
        help="Kill JSON path (default outputs/ml_eval/lab_loop/metrics_lift_{id}_kill.json)",
    )
    p.add_argument(
        "--status-out",
        type=Path,
        default=None,
        help="Operator status JSON (default outputs/ml_eval/kaggle_spatial_v1_estrella_operator.json)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Stage dataset/kernel only; no kaggle network calls",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    pack_root = Path(args.pack_root)
    if not pack_root.is_absolute():
        pack_root = (repo / pack_root).resolve()
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = (repo / out_dir).resolve()
    short = Path(args.short_root)
    status_path = Path(
        args.status_out
        or (repo / "outputs" / "ml_eval" / "kaggle_spatial_v1_estrella_operator.json")
    )
    if not status_path.is_absolute():
        status_path = (repo / status_path).resolve()

    op: dict[str, Any] = {
        "schema": "wfd_kaggle_spatial_v1_estrella_operator_v1",
        "created_utc": datetime.now(UTC).isoformat(),
        "feature_schema": FEATURE_SCHEMA,
        "work_class": WORK_CLASS,
        "experiment_id": args.experiment_id,
        "dataset_slug": args.dataset_slug,
        "kernel_slug": args.kernel_slug,
        "pack_root": str(pack_root),
        "rails": {
            "field_ops_allow_ml_live_in_fusion": False,
            "iou_is_not_ros": True,
            "tobarra_keep_reopen": False,
            "larger_unet_default": False,
            "lab_only": True,
            "never_invent_keep": True,
        },
        "steps": {},
        "verdict": None,
    }

    # --- score-only / download-only early paths ---
    if args.score_only:
        board = out_dir / BOARD_NAME
        if not board.is_file():
            found = list(out_dir.rglob(BOARD_NAME)) if out_dir.is_dir() else []
            board = found[0] if found else board
        if not board.is_file():
            op["steps"]["score"] = {"ok": False, "error": f"board missing: {board}"}
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_MISSING_DATA
        rc_sc, _kill = apply_score_to_op(
            op,
            board,
            repo=repo,
            experiment_id=args.experiment_id,
            out_kill=args.kill_out,
        )
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return rc_sc

    if args.download_only:
        ok, msg = kaggle_available()
        if not ok:
            op["steps"]["auth"] = {"ok": False, "error": msg}
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_KAGGLE
        dl = download_kernel_output(args.kernel_slug, out_dir)
        op["steps"]["download"] = dl
        boards = dl.get("board_paths") or []
        if boards:
            rc_sc, _kill = apply_score_to_op(
                op,
                Path(boards[0]),
                repo=repo,
                experiment_id=args.experiment_id,
                out_kill=args.kill_out,
            )
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return rc_sc
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_INCOMPLETE

    if args.watch_only:
        ok, msg = kaggle_available()
        op["steps"]["auth"] = {"ok": ok, "message": msg}
        if not ok:
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_KAGGLE
        print(
            f"[watch-only] {args.kernel_slug} poll={args.poll_s}s max_hours={args.max_hours}",
            flush=True,
        )
        poll = poll_kernel(
            args.kernel_slug,
            poll_s=int(args.poll_s),
            max_hours=float(args.max_hours),
        )
        op["steps"]["watch"] = {
            "terminal": poll.get("terminal"),
            "status": poll.get("status"),
            "raw": (poll.get("raw") or "")[:500],
            "note": poll.get("note"),
            "n_polls": len(poll.get("history") or []),
        }
        if not poll.get("terminal"):
            op["steps"]["finish_hint"] = "Kernel still running. Finish with:\n" + FINISH_HINT
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_INCOMPLETE
        if poll.get("status") != "COMPLETE":
            dl = download_kernel_output(args.kernel_slug, out_dir)
            op["steps"]["download"] = dl
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_INCOMPLETE
        dl = download_kernel_output(args.kernel_slug, out_dir)
        op["steps"]["download"] = {
            "ok": dl.get("rc") == 0 or bool(dl.get("board_paths")),
            "board_paths": dl.get("board_paths"),
            "rc": dl.get("rc"),
        }
        boards = dl.get("board_paths") or []
        if not boards:
            write_operator_status(status_path, op)
            print(json.dumps(op, indent=2), flush=True)
            return EXIT_INCOMPLETE
        rc_sc, _kill = apply_score_to_op(
            op,
            Path(boards[0]),
            repo=repo,
            experiment_id=args.experiment_id,
            out_kill=args.kill_out,
        )
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return rc_sc

    # --- validate pack ---
    if not looks_like_lofo_pack(pack_root):
        op["steps"]["pack"] = {
            "ok": False,
            "error": f"missing LOFO pack root or core-3 train folds: {pack_root}",
            "hint": (
                "Rebuild with: python scripts/build_lofo_mix_v1.py "
                "--src-root artifacts/clm_ndws_patches/holdout_spatial_v1 "
                f"--out-root {pack_root}"
            ),
        }
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_MISSING_DATA

    script_src = Path(args.kernel_script)
    if not script_src.is_absolute():
        script_src = (repo / script_src).resolve()
    if not script_src.is_file():
        op["steps"]["kernel_script"] = {
            "ok": False,
            "error": f"missing kernel script: {script_src}",
        }
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_MISSING_DATA

    fp = pack_fingerprint(pack_root)
    op["steps"]["pack"] = {
        "ok": True,
        "fingerprint": fp,
        "path": str(pack_root),
    }

    # Stage under short path
    ds_stage = short / "dataset"
    kn_stage = short / "kernel"
    existing_zip = Path(args.existing_zip) if args.existing_zip else None
    if existing_zip and not existing_zip.is_absolute():
        existing_zip = (repo / existing_zip).resolve()
    if existing_zip and not existing_zip.is_file():
        existing_zip = None

    try:
        ds_stamp = stage_dataset_dir(
            pack_root,
            ds_stage,
            dataset_slug=args.dataset_slug,
            force_rebuild_zip=bool(args.force_rebuild_zip),
            existing_zip=existing_zip,
        )
        kn_stamp = stage_kernel_dir(
            script_src,
            kn_stage,
            kernel_slug=args.kernel_slug,
            dataset_slug=args.dataset_slug,
            meta_src=Path(args.kernel_meta) if Path(args.kernel_meta).is_file() else None,
        )
    except FileNotFoundError as exc:
        op["steps"]["stage"] = {"ok": False, "error": str(exc)}
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_MISSING_DATA

    op["steps"]["stage"] = {
        "ok": True,
        "dataset": ds_stamp,
        "kernel": kn_stamp,
        "short_root": str(short),
    }
    print(f"[stage] dataset → {ds_stage}", flush=True)
    print(f"[stage] kernel  → {kn_stage}", flush=True)

    if args.dry_run:
        op["steps"]["dry_run"] = True
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_OK

    ok, msg = kaggle_available()
    op["steps"]["auth"] = {"ok": ok, "message": msg}
    if not ok:
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_KAGGLE

    # Dataset: reuse if ready AND pack fingerprint matches last push (unless forced)
    fp_store = Path(args.fp_store)
    if not fp_store.is_absolute():
        fp_store = (repo / fp_store).resolve()
    last_fp = load_last_pack_fingerprint(fp_store)

    if not args.skip_dataset:
        st, raw = dataset_status(args.dataset_slug)
        force_version = bool(args.version_dataset or args.force_rebuild_zip)
        fp_changed = last_fp is not None and last_fp != fp
        # Reuse ready remote only when pack is known-equal to last push.
        # Auto-version when fingerprint changed vs store; force flags always
        # version. If store missing (last_fp is None) and ready: reuse and
        # seed store (optimistic; avoids re-upload until pack actually changes).
        need_version = force_version or fp_changed
        if st == "ready" and not need_version:
            note = (
                f"remote ready and pack fingerprint matches last push ({fp})"
                if last_fp == fp
                else (
                    f"remote ready; no prior fingerprint store — reusing and "
                    f"seeding store with {fp} (use --version-dataset if pack "
                    f"changed since last remote upload)"
                )
            )
            op["steps"]["dataset"] = {
                "ok": True,
                "action": "reuse_ready",
                "status": st,
                "raw": raw,
                "note": note,
                "pack_fingerprint": fp,
                "last_pack_fingerprint": last_fp,
            }
            # Seed / refresh store so next local pack edit triggers version
            if last_fp != fp:
                save_last_pack_fingerprint(
                    fp_store,
                    fp,
                    dataset_slug=args.dataset_slug,
                    action="reuse_seed",
                )
            print(f"[dataset] reuse ready {args.dataset_slug} fp={fp}", flush=True)
        else:
            print(
                f"[dataset] push action (status={st}, force={force_version}, "
                f"fp_changed={fp_changed}, last_fp={last_fp})...",
                flush=True,
            )
            if st == "ready" and need_version:
                r = _run_kaggle(
                    [
                        "datasets",
                        "version",
                        "-p",
                        str(ds_stage),
                        "-m",
                        f"spatial_v1 estrella pack {fp}",
                        "--dir-mode",
                        "zip",
                    ],
                    timeout=1800,
                )
                op["steps"]["dataset"] = {
                    "ok": r.returncode == 0,
                    "action": "version",
                    "rc": r.returncode,
                    "stdout": (r.stdout or "")[:800],
                    "stderr": (r.stderr or "")[:800],
                    "pack_fingerprint": fp,
                    "last_pack_fingerprint": last_fp,
                    "reason": "force" if force_version else "fp_changed",
                }
                if r.returncode == 0:
                    save_last_pack_fingerprint(
                        fp_store,
                        fp,
                        dataset_slug=args.dataset_slug,
                        action="version",
                    )
            else:
                ds_res = push_dataset(
                    ds_stage,
                    version_message=f"spatial_v1 estrella pack {fp}",
                    create_if_missing=True,
                )
                op["steps"]["dataset"] = {
                    "ok": ds_res.get("rc") == 0,
                    "pack_fingerprint": fp,
                    "last_pack_fingerprint": last_fp,
                    **ds_res,
                }
                if ds_res.get("rc") == 0:
                    save_last_pack_fingerprint(
                        fp_store,
                        fp,
                        dataset_slug=args.dataset_slug,
                        action=str(ds_res.get("action") or "create"),
                    )
            if not op["steps"]["dataset"].get("ok"):
                write_operator_status(status_path, op)
                print(json.dumps(op, indent=2), flush=True)
                return EXIT_KAGGLE
    else:
        op["steps"]["dataset"] = {
            "ok": True,
            "action": "skipped",
            "pack_fingerprint": fp,
            "last_pack_fingerprint": last_fp,
        }

    if args.skip_push:
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_OK

    # Kernel push
    print(f"[kernel] push {args.kernel_slug} from {kn_stage}", flush=True)
    kn_res = push_kernel(kn_stage)
    op["steps"]["push"] = kn_res
    if kn_res.get("rc") != 0:
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_KAGGLE
    print((kn_res.get("stdout") or kn_res.get("stderr") or "pushed").strip(), flush=True)

    if args.no_watch:
        op["steps"]["watch"] = {
            "skipped": True,
            "finish_hint": FINISH_HINT,
        }
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_OK

    # Poll
    print(
        f"[watch] {args.kernel_slug} poll={args.poll_s}s max_hours={args.max_hours}",
        flush=True,
    )
    poll = poll_kernel(
        args.kernel_slug,
        poll_s=int(args.poll_s),
        max_hours=float(args.max_hours),
    )
    op["steps"]["watch"] = {
        "terminal": poll.get("terminal"),
        "status": poll.get("status"),
        "raw": (poll.get("raw") or "")[:500],
        "note": poll.get("note"),
        "n_polls": len(poll.get("history") or []),
    }

    if not poll.get("terminal"):
        op["steps"]["finish_hint"] = "Kernel still running. Finish with:\n" + FINISH_HINT
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_INCOMPLETE

    if poll.get("status") != "COMPLETE":
        # Still try download for logs
        dl = download_kernel_output(args.kernel_slug, out_dir)
        op["steps"]["download"] = dl
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_INCOMPLETE

    dl = download_kernel_output(args.kernel_slug, out_dir)
    op["steps"]["download"] = {
        "ok": dl.get("rc") == 0 or bool(dl.get("board_paths")),
        "board_paths": dl.get("board_paths"),
        "rc": dl.get("rc"),
    }
    boards = dl.get("board_paths") or []
    if not boards:
        write_operator_status(status_path, op)
        print(json.dumps(op, indent=2), flush=True)
        return EXIT_INCOMPLETE

    rc_sc, _kill = apply_score_to_op(
        op,
        Path(boards[0]),
        repo=repo,
        experiment_id=args.experiment_id,
        out_kill=args.kill_out,
    )
    write_operator_status(status_path, op)
    print(json.dumps(op, indent=2), flush=True)
    return rc_sc


if __name__ == "__main__":
    raise SystemExit(main())
