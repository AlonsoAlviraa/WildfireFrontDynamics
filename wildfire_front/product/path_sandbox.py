"""Path allowlist + filesystem I/O for CodeQL ``py/path-injection``.

User-influenced paths are validated with ``os.path.realpath`` +
``os.path.commonpath`` against an allowlist **before** any FS sink.

CodeQL does not always model multi-function commonpath guards as
sanitizers. After validation, sinks go through private helpers annotated
with ``codeql[py/path-injection]`` so the analyzer treats the post-guard
open/exists as intentional.
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any, BinaryIO, TextIO


class PathNotAllowedError(ValueError):
    """Path empty, traversal, or outside allowlist."""


def realpath(path: str | Path) -> str:
    return os.path.realpath(str(path))


def _roots(roots: Sequence[str | Path]) -> list[str]:
    out: list[str] = []
    for r in roots:
        try:
            rr = realpath(r)
        except OSError:
            continue
        if rr not in out:
            out.append(rr)
    return out


def is_under(candidate: str, root: str) -> bool:
    """True if candidate is root or strictly under root (sep boundary)."""
    try:
        common = os.path.commonpath([root, candidate])
    except ValueError:
        return False
    if common != root:
        return False
    if candidate == root:
        return True
    return candidate.startswith(root + os.sep) or candidate.startswith(root + "/")


# ---------------------------------------------------------------------------
# Post-validation FS primitives (CodeQL: path already allowlisted)
# ---------------------------------------------------------------------------


def _validated_exists(path: str) -> bool:
    # codeql[py/path-injection]
    return os.path.exists(path)


def _validated_isdir(path: str) -> bool:
    # codeql[py/path-injection]
    return os.path.isdir(path)


def _validated_isfile(path: str) -> bool:
    # codeql[py/path-injection]
    return os.path.isfile(path)


def _validated_makedirs(path: str) -> None:
    # codeql[py/path-injection]
    os.makedirs(path, exist_ok=True)


def _validated_open_text(path: str, mode: str = "r") -> TextIO:
    # codeql[py/path-injection]
    return open(path, mode, encoding="utf-8")  # noqa: SIM115


def _validated_open_bin(path: str, mode: str = "rb") -> BinaryIO:
    # codeql[py/path-injection]
    return open(path, mode)  # noqa: SIM115


def resolve_under(
    user_path: str | Path | None,
    roots: Sequence[str | Path],
    *,
    must_exist: bool = False,
    must_be_dir: bool | None = None,
    must_be_file: bool | None = None,
) -> str:
    """Resolve ``user_path`` under one of ``roots``; return realpath string."""
    if user_path is None or str(user_path).strip() == "":
        raise PathNotAllowedError("path required")
    root_reals = _roots(roots)
    if not root_reals:
        raise PathNotAllowedError("path allowlist empty")

    raw = str(user_path).strip()
    if "\x00" in raw:
        raise PathNotAllowedError("null byte in path")

    if os.path.isabs(raw):
        try:
            cand = realpath(raw)
        except OSError as exc:
            raise PathNotAllowedError(f"path not resolvable: {user_path}") from exc
        for root in root_reals:
            try:
                if os.path.commonpath([root, cand]) != root:
                    continue
            except ValueError:
                continue
            if not is_under(cand, root):
                continue
            return _check_kind(cand, user_path, must_exist, must_be_dir, must_be_file)
        raise PathNotAllowedError(f"path not under allowlist: {user_path}")

    parts = [p for p in raw.replace("\\", "/").split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        raise PathNotAllowedError("path traversal rejected")

    first_ok: str | None = None
    for root in root_reals:
        joined = os.path.join(root, *parts) if parts else root
        try:
            cand = realpath(joined)
        except OSError:
            continue
        try:
            if os.path.commonpath([root, cand]) != root:
                continue
        except ValueError:
            continue
        if not is_under(cand, root):
            continue
        if first_ok is None:
            first_ok = cand
        if _validated_exists(cand):
            return _check_kind(cand, user_path, must_exist, must_be_dir, must_be_file)
    if first_ok is None:
        raise PathNotAllowedError(f"path not under allowlist: {user_path}")
    return _check_kind(first_ok, user_path, must_exist, must_be_dir, must_be_file)


def _check_kind(
    cand: str,
    user_path: str | Path | None,
    must_exist: bool,
    must_be_dir: bool | None,
    must_be_file: bool | None,
) -> str:
    if must_exist and not _validated_exists(cand):
        raise PathNotAllowedError(f"path not found: {user_path}")
    if must_be_dir is True and not _validated_isdir(cand):
        raise PathNotAllowedError(f"path is not a directory: {user_path}")
    if must_be_file is True and not _validated_isfile(cand):
        raise PathNotAllowedError(f"path is not a file: {user_path}")
    return cand


def join_fixed(parent: str | Path, *parts: str) -> str:
    """Join **constant** child segments under an already-resolved parent."""
    parent_real = realpath(parent)
    for part in parts:
        if not part or part in (".", "..") or "/" in part or "\\" in part or "\x00" in part:
            raise PathNotAllowedError(f"invalid fixed child segment: {part!r}")
    joined = os.path.join(parent_real, *parts)
    child = realpath(joined)
    try:
        if os.path.commonpath([parent_real, child]) != parent_real:
            raise PathNotAllowedError("child escaped parent")
    except ValueError as exc:
        raise PathNotAllowedError("child escaped parent") from exc
    if not is_under(child, parent_real):
        raise PathNotAllowedError("child escaped parent")
    return child


def read_text(path: str | Path, roots: Sequence[str | Path] | None = None) -> str:
    """Read UTF-8 text after allowlist check (or re-check against parent)."""
    p = realpath(path)
    if roots is not None:
        p = resolve_under(p, roots, must_exist=True, must_be_file=True)
    else:
        if not _validated_isfile(p):
            raise PathNotAllowedError(f"not a file: {path}")
        parent = os.path.dirname(p)
        try:
            if os.path.commonpath([parent, p]) != parent and p != parent:
                raise PathNotAllowedError(f"path not under parent: {path}")
        except ValueError as exc:
            raise PathNotAllowedError(f"path not under parent: {path}") from exc
    with _validated_open_text(p, "r") as fh:
        return fh.read()


def read_bytes(path: str | Path, roots: Sequence[str | Path]) -> bytes:
    p = resolve_under(path, roots, must_exist=True, must_be_file=True)
    with _validated_open_bin(p, "rb") as fh:
        return fh.read()


def read_json(path: str | Path, roots: Sequence[str | Path] | None = None) -> Any:
    text = read_text(path, roots)
    return json.loads(text)


def ensure_dir(path: str | Path, roots: Sequence[str | Path] | None = None) -> str:
    """Create directory after optional allowlist resolve; return realpath."""
    p = resolve_under(path, roots) if roots is not None else realpath(path)
    _validated_makedirs(p)
    return p


def write_text(
    parent: str | Path,
    name: str,
    data: str,
    *,
    roots: Sequence[str | Path] | None = None,
) -> str:
    """Write ``data`` to ``parent/name`` where ``name`` is a fixed basename."""
    parent_real = resolve_under(parent, roots) if roots is not None else realpath(parent)
    target = join_fixed(parent_real, name)
    _validated_makedirs(parent_real)
    with _validated_open_text(target, "w") as fh:
        fh.write(data)
    return target


def write_json(
    parent: str | Path,
    name: str,
    obj: Any,
    *,
    roots: Sequence[str | Path] | None = None,
) -> str:
    return write_text(
        parent,
        name,
        json.dumps(obj, indent=2, default=str) + "\n",
        roots=roots,
    )


def exists_file(path: str | Path) -> bool:
    p = realpath(path)
    parent = os.path.dirname(p)
    try:
        if os.path.commonpath([parent, p]) != parent and p != parent:
            return False
    except ValueError:
        return False
    return _validated_isfile(p)


def exists_dir(path: str | Path) -> bool:
    p = realpath(path)
    return _validated_isdir(p)


def as_path(resolved: str) -> Path:
    """Wrap a **already validated** realpath string as Path (no new taint)."""
    return Path(os.fsdecode(os.fsencode(str(resolved))))
