"""Poll-based inbox watcher for incident_runtime_v1 (stdlib only)."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from typing import Any

from .pipeline import IncidentConfig, acquire_work_dir_lock, process_incident_once


def run_incident_watch(
    config: IncidentConfig,
    *,
    interval_s: float = 2.0,
    max_iterations: int | None = None,
    max_frames: int | None = None,
    once: bool = False,
    stop_on_error: bool = False,
    on_update: Callable[[dict[str, Any]], None] | None = None,
    use_lock: bool = True,
) -> dict[str, Any]:
    """Watch ``config.inbox`` and recompute outbox when new GeoTIFFs appear.

    Parameters
    ----------
    interval_s:
        Poll interval (ignored when ``once=True``).
    max_iterations:
        Stop after this many poll loops (None = forever until interrupt).
    max_frames:
        Stop once staged frame count reaches this value.
    once:
        Run a single process_incident_once and return (no loop).
    stop_on_error:
        If True, exit loop on pipeline error status.
    on_update:
        Optional callback with each summary (e.g. print JSON line).
    use_lock:
        Acquire exclusive work_dir lock for the watch session.
    """
    if use_lock:
        try:
            acquire_work_dir_lock(config.work_dir)
        except RuntimeError as exc:
            err = {
                "product": "incident_runtime_v1",
                "mode": "once" if once else "watch",
                "status": "error",
                "error": str(exc),
            }
            if on_update:
                on_update(err)
            return {**err, "iterations": 0, "last": err}

    prev_sizes: dict[str, int] = {}

    if once:
        summary = process_incident_once(config, force=True, prev_sizes=prev_sizes)
        if on_update:
            on_update(summary)
        return {
            "product": "incident_runtime_v1",
            "mode": "once",
            "iterations": 1,
            "last": summary,
        }

    iterations = 0
    last: dict[str, Any] = {}
    try:
        while True:
            iterations += 1
            # force only on first iteration so subsequent idle is cheap
            force = iterations == 1
            summary = process_incident_once(config, force=force, prev_sizes=prev_sizes)
            last = summary
            if on_update:
                on_update(summary)

            n_staged = int(summary.get("n_staged") or 0)
            if max_frames is not None and n_staged >= max_frames:
                break
            if stop_on_error and summary.get("status") == "error":
                break
            if max_iterations is not None and iterations >= max_iterations:
                break

            time.sleep(max(0.0, float(interval_s)))
    except KeyboardInterrupt:
        last = {**last, "interrupted": True}

    return {
        "product": "incident_runtime_v1",
        "mode": "watch",
        "iterations": iterations,
        "last": last,
    }


def print_summary_line(summary: dict[str, Any], *, verbose: bool = False) -> None:
    """Compact one-line operator log to stderr (delegates to cli_report)."""
    try:
        from ..cli_report import print_watch_line

        print_watch_line(summary, verbose=verbose)
    except Exception:  # noqa: BLE001 — never break watch for formatting
        status = summary.get("status")
        grade = summary.get("quality_grade")
        ros = summary.get("primary_ros_m_min")
        n = summary.get("n_staged")
        lat = summary.get("latency_s")
        err = summary.get("error")
        msg = f"[incident] status={status} frames={n} grade={grade} ros={ros} latency_s={lat}"
        if err:
            msg += f" error={err}"
        print(msg, file=sys.stderr)


def print_json(obj: dict[str, Any]) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False))
