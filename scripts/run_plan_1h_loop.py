#!/usr/bin/env python3
"""Run plan-1-month residual tasks for up to ~1 hour (Track A re-run + plan hygiene).

Usage:
  python scripts/run_plan_1h_loop.py
  python scripts/run_plan_1h_loop.py --minutes 60
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "outputs" / "plan_1h_loop"
REPORT = LOG_DIR / "hour_loop_report.json"


def _run(cmd: list[str], timeout_s: int, label: str) -> dict:
    t0 = time.time()
    print(f"\n=== [{label}] {' '.join(cmd)} ===", flush=True)
    try:
        p = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        dt = time.time() - t0
        tail = (p.stdout or "")[-2000:] + "\n" + (p.stderr or "")[-1500:]
        print(tail[-2500:], flush=True)
        return {
            "label": label,
            "cmd": cmd,
            "returncode": p.returncode,
            "seconds": round(dt, 1),
            "ok": p.returncode == 0,
            "tail": tail[-3000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label,
            "cmd": cmd,
            "returncode": -9,
            "seconds": timeout_s,
            "ok": False,
            "error": f"timeout: {exc}",
        }
    except Exception as exc:
        return {
            "label": label,
            "cmd": cmd,
            "returncode": -1,
            "seconds": round(time.time() - t0, 1),
            "ok": False,
            "error": str(exc),
            "tb": traceback.format_exc()[-1500:],
        }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--skip-hellin-rebuild", action="store_true")
    args = ap.parse_args()

    deadline = time.time() + max(60.0, args.minutes * 60.0)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    py = sys.executable
    results: list[dict] = []

    def remaining() -> float:
        return max(0.0, deadline - time.time())

    def can(seconds_needed: float) -> bool:
        return remaining() > seconds_needed + 15

    # --- Track A re-run: full-ish Hellín pack ---
    if not args.skip_hellin_rebuild and can(300):
        # Attempt 1: more frames + larger FOV allowance
        results.append(
            _run(
                [
                    py,
                    "scripts/build_observatory_pack.py",
                    "--fires",
                    "hellin_2024",
                    "--max-frames",
                    "16",
                    "--max-side",
                    "4000",
                    "--min-component-pixels",
                    "150",
                    "--output-root",
                    str(ROOT / "outputs" / "observatorio"),
                ],
                timeout_s=min(int(remaining() - 30), 2400),
                label="A_hellin_rebuild_v1",
            )
        )
        if can(60):
            results.append(
                _run(
                    [py, "scripts/score_hellin_track_a.py"],
                    timeout_s=120,
                    label="A_score_hellin_v1",
                )
            )

        # Attempt 2 if still out of band and time left: denser small FOV
        if can(300):
            results.append(
                _run(
                    [
                        py,
                        "scripts/build_observatory_pack.py",
                        "--fires",
                        "hellin_2024",
                        "--max-frames",
                        "12",
                        "--max-side",
                        "2200",
                        "--min-component-pixels",
                        "100",
                        "--output-root",
                        str(ROOT / "outputs" / "observatorio"),
                    ],
                    timeout_s=min(int(remaining() - 30), 1800),
                    label="A_hellin_rebuild_v2_small_fov",
                )
            )
            if can(60):
                results.append(
                    _run(
                        [py, "scripts/score_hellin_track_a.py"],
                        timeout_s=120,
                        label="A_score_hellin_v2",
                    )
                )

    # --- Score anchors multi-IF ---
    if can(60):
        results.append(
            _run(
                [py, "scripts/score_infocam_anchors.py"],
                timeout_s=180,
                label="O1_score_infocam_anchors",
            )
        )

    # --- Cardoso timeline ---
    if can(30):
        results.append(
            _run(
                [py, "scripts/build_cardoso_timeline.py"],
                timeout_s=120,
                label="C_cardoso_timeline",
            )
        )

    # --- Tobarra AEMET pipeline (cached weather) ---
    if can(180):
        results.append(
            _run(
                [py, "scripts/run_tobarra_aemet_pipeline.py"],
                timeout_s=min(int(remaining() - 20), 900),
                label="D_tobarra_aemet_pipeline",
            )
        )

    # --- Fuel / envelope tests ---
    if can(90):
        results.append(
            _run(
                [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_fuel_rothermel_lite.py",
                    "tests/test_aemet_weather.py",
                    "tests/test_fuel_envelope.py",
                    "tests/test_pr_beta_envelope_aemet.py",
                    "tests/test_fuel_envelope_scorecard.py",
                    "-q",
                    "--tb=no",
                ],
                timeout_s=min(int(remaining() - 15), 600),
                label="D_fuel_pytest",
            )
        )

    # --- Ops / front dynamics unit tests ---
    if can(60):
        results.append(
            _run(
                [
                    py,
                    "-m",
                    "pytest",
                    "tests/test_front_dynamics.py",
                    "tests/test_ops_perimeter.py",
                    "-q",
                    "--tb=no",
                ],
                timeout_s=min(int(remaining() - 15), 400),
                label="A_ops_pytest",
            )
        )

    # --- Optional multi-fire quick rebuild: tobarra + hellin scorecard only already done ---
    if can(400):
        results.append(
            _run(
                [
                    py,
                    "scripts/build_observatory_pack.py",
                    "--fires",
                    "tobarra_20240802,hellin_2024",
                    "--max-frames",
                    "10",
                    "--max-side",
                    "2500",
                ],
                timeout_s=min(int(remaining() - 20), 2000),
                label="A_rebuild_tobarra_hellin_pair",
            )
        )
        if can(60):
            results.append(
                _run(
                    [py, "scripts/score_hellin_track_a.py"],
                    timeout_s=120,
                    label="A_score_hellin_after_pair",
                )
            )
            results.append(
                _run(
                    [py, "scripts/score_infocam_anchors.py"],
                    timeout_s=180,
                    label="O1_score_infocam_after_pair",
                )
            )

    # --- Plan cycle / metrics hub ---
    if can(90):
        results.append(
            _run(
                [py, "scripts/run_plan_cycle.py", "--execute-m1"],
                timeout_s=min(int(remaining() - 15), 600),
                label="B_plan_cycle_m1",
            )
        )

    # --- Smoke incident if time ---
    if can(60):
        smoke = ROOT / "scripts" / "smoke_incident_runtime.py"
        if smoke.is_file():
            results.append(
                _run(
                    [py, str(smoke)],
                    timeout_s=min(int(remaining() - 10), 300),
                    label="B_smoke_incident",
                )
            )

    # Final score Hellín always if time
    if can(30):
        results.append(
            _run(
                [py, "scripts/score_hellin_track_a.py"],
                timeout_s=90,
                label="A_score_hellin_final",
            )
        )

    elapsed = args.minutes * 60 - remaining()
    report = {
        "schema": "wfd_plan_1h_loop_v1",
        "started_budget_min": args.minutes,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_s": round(elapsed, 1),
        "remaining_s": round(remaining(), 1),
        "n_steps": len(results),
        "n_ok": sum(1 for r in results if r.get("ok")),
        "steps": results,
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    # Human summary md
    md = [
        "# Plan 1h loop report",
        "",
        f"Finished: {report['finished_at_utc']}",
        f"Steps OK: {report['n_ok']}/{report['n_steps']}",
        "",
        "| step | ok | s | code |",
        "|------|----|---|------|",
    ]
    for r in results:
        md.append(
            f"| {r.get('label')} | {r.get('ok')} | {r.get('seconds')} | {r.get('returncode')} |"
        )
    # attach hellin final if present
    ta = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.json"
    if ta.is_file():
        try:
            doc = json.loads(ta.read_text(encoding="utf-8"))
            md += [
                "",
                "## Hellín Track A (final)",
                "",
                f"- grade: {doc.get('ops', {}).get('structural_grade')}",
                f"- ROS: {doc.get('ops', {}).get('primary_ros_m_min')}",
                f"- Vp: {doc.get('anchor', {}).get('vp_m_min')}",
                f"- ratio: {doc.get('ratio_primary_to_vp')}",
                f"- in_band: {doc.get('ratio_in_band_0_5_2_0')}",
                "- GO_MES: see O1_GOMES recompute",
            ]
        except Exception:
            pass
    (LOG_DIR / "hour_loop_report.md").write_text("\n".join(md), encoding="utf-8")
    print(json.dumps({k: report[k] for k in report if k != "steps"}, indent=2))
    print(f"Wrote {REPORT}")
    return 0 if report["n_ok"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
