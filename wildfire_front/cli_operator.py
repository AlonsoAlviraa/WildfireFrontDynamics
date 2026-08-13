"""Operator / teach / show / demo-third-party CLI for H1 12-min rehearsal.

Rails: decision-support only. GO_Q stays partial (AMARILLO) until a human
third-party acta is recorded. field_ops ML live fusion stays OFF.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]

# Repo root: wildfire_front/..
_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    return _ROOT


def _rel(path: Path, root: Path | None = None) -> str:
    root = root or _repo_root()
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)
