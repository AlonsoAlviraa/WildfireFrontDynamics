#!/usr/bin/env python3
"""H3 eng support — one-command dry-run of third-party pack + E3 replay.

Rebuilds the demo pack (E1), runs forensic replay (E3), and writes
``outputs/demo_third_party/DRY_RUN_REPORT.md`` (+ JSON).

**Does not** complete H3 human operator acceptance (signed acta / live demo).
Mark: eng dry-run ready; H3 still needs human.

Usage
-----
::

    python scripts/dry_run_demo_third_party.py
    make dry-run-demo-third-party
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DEFAULT = ROOT / "outputs" / "demo_third_party"


def _run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env={
            **dict(**dict(__import__("os").environ.items())),
            "PYTHONPATH": str(ROOT),
        },
        check=False,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-4000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def _load(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_report(
    *,
    out_dir: Path,
    pack_rc: dict[str, Any],
    replay_rc: dict[str, Any],
    skip_build: bool,
) -> dict[str, Any]:
    card = _load(out_dir / "fire_decision_card.json") or {}
    replay_manifest = _load(out_dir / "replay_manifest.json") or {}
    pack_summary = _load(out_dir / "pack_build_summary.json") or {}
    rel = _load(out_dir / "reliability_gate_report.json") or {}

    replay_ok = replay_rc.get("returncode") == 0
    # Parse stdout for replay_ok line if present
    stdout = replay_rc.get("stdout_tail") or ""
    if "replay_ok: True" in stdout or "replay_ok: true" in stdout:
        replay_ok = True
    if "replay_ok: False" in stdout or "replay_ok: false" in stdout:
        replay_ok = False

    pack_ok = True if skip_build else pack_rc.get("returncode") == 0
    eng_ok = bool(pack_ok and replay_ok)

    return {
        "schema": "demo_third_party_dry_run_v1",
        "graph_id": "H3_eng_support",
        "built_at_utc": datetime.now(UTC).isoformat(),
        "out_dir": str(out_dir.relative_to(ROOT)).replace("\\", "/")
        if out_dir.is_relative_to(ROOT)
        else str(out_dir),
        "steps": {
            "E1_build_pack": {
                "skipped": skip_build,
                "returncode": pack_rc.get("returncode"),
                "ok": pack_ok,
            },
            "E3_replay": {
                "returncode": replay_rc.get("returncode"),
                "ok": replay_ok,
            },
        },
        "decision": card.get("decision"),
        "confidence_pred": card.get("confidence_pred"),
        "policy_id": (card.get("metrics") or {}).get("policy_id")
        or (card.get("audit") or {}).get("policy_id"),
        "allow_ml_live_in_fusion": (card.get("metrics") or {}).get("allow_ml_live_in_fusion"),
        "pack_build_summary_keys": list(pack_summary.keys())[:20] if pack_summary else [],
        "reliability_field_unlock": rel.get("field_unlock"),
        "reliability_ok": rel.get("ok"),
        "replay_manifest_present": bool(replay_manifest),
        "eng_dry_run_ok": eng_ok,
        "h3_human_operator_still_required": True,
        "h3_status": "ENG_DRY_RUN_READY" if eng_ok else "ENG_DRY_RUN_FAILED",
        "note": (
            "Engineering dry-run only: rebuild pack + E3 forensic replay. "
            "H3 product acceptance still requires a **human operator** offline walkthrough "
            "(README, card, replay) and does **not** replace H1 signed acta."
        ),
        "rails": {
            "field_ops_ml_live_fusion": "OFF",
            "no_invented_anchors": True,
            "no_GO_Q_claim": True,
        },
        "stdout_replay_tail": stdout[-1500:],
    }


def render_md(report: dict[str, Any]) -> str:
    steps = report.get("steps") or {}
    e1 = steps.get("E1_build_pack") or {}
    e3 = steps.get("E3_replay") or {}
    return "\n".join(
        [
            "# Dry-run demo third-party — eng report (H3 support)",
            "",
            f"_UTC: {report.get('built_at_utc')}_",
            "",
            f"- **eng_dry_run_ok:** `{report.get('eng_dry_run_ok')}`",
            f"- **h3_status:** `{report.get('h3_status')}`",
            f"- **h3_human_operator_still_required:** `{report.get('h3_human_operator_still_required')}`",
            f"- **E1 build:** ok={e1.get('ok')} skipped={e1.get('skipped')} rc={e1.get('returncode')}",
            f"- **E3 replay:** ok={e3.get('ok')} rc={e3.get('returncode')}",
            f"- **decision:** `{report.get('decision')}` · conf={report.get('confidence_pred')}",
            f"- **policy:** `{report.get('policy_id')}` · ml_live_in_fusion={report.get('allow_ml_live_in_fusion')}",
            f"- **reliability field_unlock:** {report.get('reliability_field_unlock')}",
            "",
            "## Human still required (H3)",
            "",
            "1. Open `outputs/demo_third_party/README.md` offline.",
            "2. Read `fire_decision_card.md` + Reliability Report pointer.",
            "3. Run `run_replay.ps1` / `run_replay.sh` once yourself.",
            "4. Confirm no GO_Q claim; fusion OFF.",
            "5. H1 signed acta is **separate**.",
            "",
            f"> {report.get('note')}",
            "",
            "## Rails",
            "",
            "```json",
            json.dumps(report.get("rails") or {}, indent=2),
            "```",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="H3 eng dry-run: pack + E3 + report")
    ap.add_argument("--out-dir", type=Path, default=OUT_DEFAULT)
    ap.add_argument(
        "--skip-build",
        action="store_true",
        help="Only replay + report (use existing pack)",
    )
    ap.add_argument(
        "--no-zip", action="store_true", help="Pass --no-zip to pack builder if supported"
    )
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    py = sys.executable

    pack_rc: dict[str, Any] = {"returncode": 0, "stdout_tail": "", "stderr_tail": "", "cmd": []}
    if not args.skip_build:
        build_cmd = [
            py,
            str(ROOT / "scripts" / "build_demo_third_party_pack.py"),
            "--output",
            str(out_dir),
        ]
        if args.no_zip:
            build_cmd.append("--no-zip")
        pack_rc = _run(build_cmd)

    replay_rc = _run(
        [
            py,
            str(ROOT / "scripts" / "run_third_party_replay.py"),
            "--bundle",
            str(out_dir),
        ]
    )

    report = build_report(
        out_dir=out_dir,
        pack_rc=pack_rc,
        replay_rc=replay_rc,
        skip_build=args.skip_build,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "DRY_RUN_REPORT.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "DRY_RUN_REPORT.md").write_text(render_md(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": report.get("eng_dry_run_ok"),
                "h3_status": report.get("h3_status"),
                "h3_human_operator_still_required": True,
                "decision": report.get("decision"),
                "report": str((out_dir / "DRY_RUN_REPORT.md").relative_to(ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0 if report.get("eng_dry_run_ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
