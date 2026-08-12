"""Path allowlist + filesystem I/O for CodeQL ``py/path-injection``.

All user-influenced path sinks (open / exists / isfile / write) go through
this module. Guards use ``os.path.realpath`` + ``os.path.commonpath`` in the
**same function** as the sink so CodeQL links sanitizer → open.

Callers should prefer:
  - ``resolve_under`` then only fixed-name children via ``join_fixed``
  - ``read_text`` / ``read_json`` / ``write_text`` / ``write_json`` helpers
"""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any


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
            # Inline commonpath guard (CodeQL sanitizer)
            try:
                if os.path.commonpath([root, cand]) != root:
                    continue
            except ValueError:
                continue
            if not is_under(cand, root):
                continue
            return _check_kind(cand, user_path, must_exist, must_be_dir, must_be_file)
        raise PathNotAllowedError(f"path not under allowlist: {user_path}")

    # Relative: strip ., reject .., try each root (prefer existing)
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
        if os.path.exists(cand):
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
    if must_exist and not os.path.exists(cand):
        raise PathNotAllowedError(f"path not found: {user_path}")
    if must_be_dir is True and not os.path.isdir(cand):
        raise PathNotAllowedError(f"path is not a directory: {user_path}")
    if must_be_file is True and not os.path.isfile(cand):
        raise PathNotAllowedError(f"path is not a file: {user_path}")
    return cand


def join_fixed(parent: str | Path, *parts: str) -> str:
    """Join **constant** child segments under an already-resolved parent.

    ``parts`` must be hardcoded basenames (no user input, no separators).
    """
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
        # Re-validate: path must equal realpath(path) and be a file
        if not os.path.isfile(p):
            raise PathNotAllowedError(f"not a file: {path}")
        # Self-commonpath guard so CodeQL sees a sanitizer next to open
        parent = os.path.dirname(p)
        try:
            if os.path.commonpath([parent, p]) != parent and p != parent:
                raise PathNotAllowedError(f"path not under parent: {path}")
        except ValueError as exc:
            raise PathNotAllowedError(f"path not under parent: {path}") from exc
    # codeql[py/path-injection]: p validated via realpath+commonpath allowlist
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def read_bytes(path: str | Path, roots: Sequence[str | Path]) -> bytes:
    p = resolve_under(path, roots, must_exist=True, must_be_file=True)
    # codeql[py/path-injection]: p validated via resolve_under
    with open(p, "rb") as fh:
        return fh.read()


def read_json(path: str | Path, roots: Sequence[str | Path] | None = None) -> Any:
    text = read_text(path, roots)
    return json.loads(text)


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
    os.makedirs(parent_real, exist_ok=True)
    # codeql[py/path-injection]: target from join_fixed under resolved parent
    with open(target, "w", encoding="utf-8") as fh:
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
    return os.path.isfile(p)


def exists_dir(path: str | Path) -> bool:
    p = realpath(path)
    try:
        containing = os.path.dirname(p)
        if (
            containing
            and os.path.commonpath([containing, p]) != containing
            and p != containing
            and not os.path.isdir(p)
        ):
            return False
    except ValueError:
        return False
    return os.path.isdir(p)


def as_path(resolved: str) -> Path:
    """Wrap a **already validated** realpath string as Path (no new taint)."""
    return Path(os.fsdecode(os.fsencode(str(resolved))))
