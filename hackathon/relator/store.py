"""Board persistence: GCS on Cloud Run, local files otherwise. No LLM."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .gcp import BUCKET, PROJECT_ID


def _local_dir() -> Path:
    return Path(os.environ.get("RELATOR_STORE_DIR") or "outputs/relator_demo/boards")


def on_cloud_run() -> bool:
    return bool(os.environ.get("K_SERVICE") or os.environ.get("CLOUD_RUN_JOB"))


def _token() -> str | None:
    try:
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode()).get("access_token")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def save_board(board: dict[str, Any]) -> dict[str, Any]:
    iid = str(board.get("incident_id") or "unknown")
    raw = json.dumps(board, default=str).encode("utf-8")
    meta = {"backend": "local", "ok": False, "path": f"boards/{iid}.json"}
    tok = _token() if on_cloud_run() else None
    if tok:
        name = urllib.parse.quote(f"boards/{iid}.json", safe="")
        url = (
            f"https://storage.googleapis.com/upload/storage/v1/b/{BUCKET}/o"
            f"?uploadType=media&name={name}"
        )
        req = urllib.request.Request(
            url,
            data=raw,
            method="POST",
            headers={
                "Authorization": f"Bearer {tok}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp.read()
            meta.update({"backend": "gcs", "ok": True, "bucket": BUCKET})
            return meta
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
    dest_dir = _local_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{iid}.json"
    dest.write_bytes(raw)
    meta.update({"ok": True, "backend": "local", "file": str(dest)})
    return meta


def load_board(incident_id: str) -> dict[str, Any] | None:
    iid = str(incident_id or "")
    tok = _token() if on_cloud_run() else None
    if tok:
        name = urllib.parse.quote(f"boards/{iid}.json", safe="")
        url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o/{name}?alt=media"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                pass
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass
    dest = _local_dir() / f"{iid}.json"
    if dest.is_file():
        return json.loads(dest.read_text(encoding="utf-8"))
    return None


def list_incidents() -> list[str]:
    found: set[str] = set()
    local = _local_dir()
    if local.is_dir():
        found.update(p.stem for p in local.glob("*.json"))
    tok = _token() if on_cloud_run() else None
    if tok:
        q = urllib.parse.urlencode({"prefix": "boards/", "fields": "items/name"})
        url = f"https://storage.googleapis.com/storage/v1/b/{BUCKET}/o?{q}"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                items = json.loads(resp.read().decode()).get("items") or []
            for it in items:
                name = str(it.get("name") or "")
                if name.endswith(".json"):
                    found.add(Path(name).stem)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
            pass
    return sorted(found)


def project_id() -> str:
    return PROJECT_ID
