#!/usr/bin/env python3
"""B2 — Release flags SSOT checker (docs/flags alignment).

Authority order:
  1. docs/CURRENT_STATE.md (human narrative + gate table)
  2. docs/ML_PRODUCT_GO_STATUS.json (machine stamp)
  3. Hard rails: field_ops fusion OFF unless human promote

Exit codes:
  0 — PASS (all hard invariants hold)
  1 — FAIL (misaligned or unsafe claim)
  2 — IO / missing authority files

Does not flip any product flags. Read-only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT_STATE = ROOT / "docs" / "CURRENT_STATE.md"
ML_GO_STAMP = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_gate_table(md: str) -> dict[str, str]:
    """Parse CURRENT_STATE gate table rows like | **GO_MES** | **true** | ..."""
    out: dict[str, str] = {}
    for line in md.splitlines():
        m = re.match(
            r"\|\s*\*\*(?P<key>[^*]+)\*\*\s*\|\s*\*\*(?P<val>[^*]+)\*\*",
            line.strip(),
        )
        if not m:
            continue
        key = m.group("key").strip()
        val = m.group("val").strip().lower()
        out[key] = val
    return out


def _truthy_token(s: str) -> bool | None:
    s = (s or "").strip().lower()
    if s in {"true", "yes", "on", "pass"}:
        return True
    if s in {"false", "no", "off", "fail"}:
        return False
    if s in {"partial"}:
        return None  # tri-state
    return None


def evaluate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    hard_fail = False

    if not CURRENT_STATE.is_file():
        return {
            "status": "ERROR",
            "exit_code": 2,
            "error": f"missing {CURRENT_STATE.relative_to(ROOT)}",
        }
    if not ML_GO_STAMP.is_file():
        return {
            "status": "ERROR",
            "exit_code": 2,
            "error": f"missing {ML_GO_STAMP.relative_to(ROOT)}",
        }

    md = CURRENT_STATE.read_text(encoding="utf-8")
    stamp = _load_json(ML_GO_STAMP)
    gates = _extract_gate_table(md)

    # --- Hard rails ---
    fusion = str(stamp.get("field_ops_allow_ml_live_in_fusion", True)).lower()
    rails = stamp.get("rails") or {}
    fusion_rail = str(rails.get("field_ops_fusion", "")).upper()
    fusion_off = fusion in {"false", "0", "no"} or fusion_rail == "OFF"
    checks.append(
        {
            "id": "field_ops_fusion_off",
            "ok": fusion_off,
            "detail": f"stamp fusion allow={stamp.get('field_ops_allow_ml_live_in_fusion')} rails={fusion_rail}",
        }
    )
    if not fusion_off:
        hard_fail = True

    ml_go = bool(stamp.get("ml_product_go"))
    # ml_product_go true is allowed ONLY as lab; must not imply fusion ON
    if ml_go and not fusion_off:
        checks.append(
            {
                "id": "ml_product_go_without_fusion",
                "ok": False,
                "detail": "ml_product_go true with fusion ON is forbidden",
            }
        )
        hard_fail = True
    else:
        checks.append(
            {
                "id": "ml_product_go_lab_only",
                "ok": True,
                "detail": f"ml_product_go={ml_go} fusion_off={fusion_off} (lab GO ≠ field fusion)",
            }
        )

    # Align CURRENT_STATE narrative tokens with stamp where both present
    cs_ml = gates.get("ml_product_go")
    if cs_ml is not None:
        cs_bool = _truthy_token(cs_ml)
        ok = cs_bool is True and ml_go is True or cs_bool is False and ml_go is False
        checks.append(
            {
                "id": "align_ml_product_go_current_state",
                "ok": bool(ok),
                "detail": f"CURRENT_STATE={cs_ml} stamp={ml_go}",
            }
        )
        if not ok:
            hard_fail = True

    cs_fusion = gates.get("field_ops ML fusion") or gates.get("field_ops ML fusion")
    # table key in CURRENT_STATE is "field_ops ML fusion"
    for k, v in gates.items():
        if "fusion" in k.lower():
            tok = _truthy_token(v) if v not in {"off", "on"} else (v == "on")
            if v.strip().lower() == "off":
                tok = False
            if v.strip().lower() == "on":
                tok = True
            checks.append(
                {
                    "id": "align_fusion_current_state",
                    "ok": tok is False,
                    "detail": f"CURRENT_STATE[{k}]={v}",
                }
            )
            if tok is not False:
                hard_fail = True
            break

    # GO_MES stamp vs CURRENT_STATE (stamp may lag; warn-as-fail for B2)
    stamp_gomes = stamp.get("GO_MES")
    cs_gomes = gates.get("GO_MES")
    if cs_gomes is not None and stamp_gomes is not None:
        cs_b = _truthy_token(cs_gomes)
        ok = (cs_b is True and stamp_gomes is True) or (
            cs_b is False and stamp_gomes is False
        )
        checks.append(
            {
                "id": "align_go_mes",
                "ok": bool(ok),
                "detail": f"CURRENT_STATE GO_MES={cs_gomes} stamp GO_MES={stamp_gomes}",
            }
        )
        if not ok:
            hard_fail = True

    # One-line truth must mention fusion OFF and not claim field ML live
    oneline = ""
    for line in md.splitlines():
        if "fusion" in line.lower() and ("OFF" in line or "off" in line):
            oneline = line
            break
    checks.append(
        {
            "id": "narrative_mentions_fusion_off",
            "ok": bool(oneline) or "fusion OFF" in md or "fusion** | **OFF" in md,
            "detail": "CURRENT_STATE must keep field fusion OFF visible",
        }
    )
    if not checks[-1]["ok"]:
        hard_fail = True

    status = "FAIL" if hard_fail else "PASS"
    return {
        "status": status,
        "exit_code": 1 if hard_fail else 0,
        "authority": {
            "current_state": str(CURRENT_STATE.relative_to(ROOT)),
            "ml_product_go_stamp": str(ML_GO_STAMP.relative_to(ROOT)),
        },
        "invariants": {
            "field_ops_fusion": "OFF",
            "ml_product_go_means": "lab_only_not_field_fusion",
            "tobarra_keep_reopen": False,
        },
        "checks": checks,
        "n_fail": sum(1 for c in checks if not c.get("ok")),
        "n_pass": sum(1 for c in checks if c.get("ok")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WFD B2 release flags SSOT check")
    ap.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON report",
    )
    ap.add_argument(
        "--write",
        type=Path,
        default=None,
        help="Optional path to write report JSON",
    )
    args = ap.parse_args(argv)

    report = evaluate()
    if args.write:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if args.json or args.write:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"status={report.get('status')} exit={report.get('exit_code')}")
        for c in report.get("checks") or []:
            mark = "OK" if c.get("ok") else "FAIL"
            print(f"  [{mark}] {c.get('id')}: {c.get('detail')}")
        if report.get("error"):
            print(f"error: {report['error']}", file=sys.stderr)
    return int(report.get("exit_code", 2))


if __name__ == "__main__":
    raise SystemExit(main())
