#!/usr/bin/env python3
"""Release flags SSOT checker (docs/flags alignment) — Agent B ownership.

Authority order:
  1. docs/CURRENT_STATE.md (human narrative + gate table)
  2. docs/ML_PRODUCT_GO_STATUS.json (machine stamp)
  3. Hard rails: field_ops fusion OFF · GO_Q partial · FREEZE_ML · GO_MES+ false

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

_GOQ_FORBIDDEN = frozenset({"true", "complete", "full", "yes", "1"})
_GOQ_ALLOWED = frozenset({"partial", "false", "0", "no"})


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


def _go_q_stamp_ok(stamp_goq: Any) -> bool:
    """GO_Q may be partial/false only; never invent true/complete."""
    if stamp_goq is True:
        return False
    if stamp_goq is False:
        return True
    s = str(stamp_goq).strip().lower() if stamp_goq is not None else ""
    if s in _GOQ_FORBIDDEN:
        return False
    return s in _GOQ_ALLOWED


def evaluate(
    *,
    current_state_path: Path | None = None,
    stamp_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate release-flag rails. Paths injectable for unit tests."""
    cs_path = current_state_path or CURRENT_STATE
    st_path = stamp_path or ML_GO_STAMP
    checks: list[dict[str, Any]] = []
    hard_fail = False

    if not cs_path.is_file():
        return {
            "status": "ERROR",
            "exit_code": 2,
            "error": f"missing {cs_path}",
        }
    if not st_path.is_file():
        return {
            "status": "ERROR",
            "exit_code": 2,
            "error": f"missing {st_path}",
        }

    md = cs_path.read_text(encoding="utf-8")
    stamp = _load_json(st_path)
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
            "detail": (
                f"stamp fusion allow={stamp.get('field_ops_allow_ml_live_in_fusion')} "
                f"rails={fusion_rail}"
            ),
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
        ok = (cs_bool is True and ml_go is True) or (cs_bool is False and ml_go is False)
        checks.append(
            {
                "id": "align_ml_product_go_current_state",
                "ok": bool(ok),
                "detail": f"CURRENT_STATE={cs_ml} stamp={ml_go}",
            }
        )
        if not ok:
            hard_fail = True

    # table key in CURRENT_STATE is "field_ops ML fusion"
    for k, v in gates.items():
        if "fusion" in k.lower():
            tok: bool | None
            vl = v.strip().lower()
            if vl == "off":
                tok = False
            elif vl == "on":
                tok = True
            else:
                tok = _truthy_token(v)
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

    # GO_MES stamp vs CURRENT_STATE
    stamp_gomes = stamp.get("GO_MES")
    cs_gomes = gates.get("GO_MES")
    if cs_gomes is not None and stamp_gomes is not None:
        cs_b = _truthy_token(cs_gomes)
        ok = (cs_b is True and stamp_gomes is True) or (cs_b is False and stamp_gomes is False)
        checks.append(
            {
                "id": "align_go_mes",
                "ok": bool(ok),
                "detail": f"CURRENT_STATE GO_MES={cs_gomes} stamp GO_MES={stamp_gomes}",
            }
        )
        if not ok:
            hard_fail = True

    # GO_MES+ must stay false until 2nd grade A + O2 path + H1 honesty
    stamp_gomes_plus = stamp.get("GO_MES_plus")
    if stamp_gomes_plus is not None:
        gomes_plus_ok = stamp_gomes_plus is False or str(stamp_gomes_plus).lower() in {
            "false",
            "0",
            "no",
        }
        checks.append(
            {
                "id": "go_mes_plus_false",
                "ok": gomes_plus_ok,
                "detail": f"stamp GO_MES_plus={stamp_gomes_plus!r} (must stay false until criteria)",
            }
        )
        if not gomes_plus_ok:
            hard_fail = True
    cs_gomes_plus = gates.get("GO_MES+")
    if cs_gomes_plus is not None:
        tok = _truthy_token(cs_gomes_plus)
        ok = tok is False
        checks.append(
            {
                "id": "go_mes_plus_current_state_false",
                "ok": ok,
                "detail": f"CURRENT_STATE GO_MES+={cs_gomes_plus!r}",
            }
        )
        if not ok:
            hard_fail = True

    # FREEZE_ML: Tobarra KEEP reopen must remain false
    keep_reopen = rails.get("tobarra_keep_reopen", True)
    keep_ok = keep_reopen is False or str(keep_reopen).lower() in {"false", "0", "no"}
    checks.append(
        {
            "id": "tobarra_keep_reopen_false",
            "ok": keep_ok,
            "detail": f"stamp rails.tobarra_keep_reopen={keep_reopen!r}",
        }
    )
    if not keep_ok:
        hard_fail = True

    # One-line truth must mention fusion OFF and not claim field ML live
    oneline = ""
    for line in md.splitlines():
        if "fusion" in line.lower() and ("OFF" in line or "off" in line):
            oneline = line
            break
    fusion_narrative_ok = bool(oneline) or "fusion OFF" in md or "fusion** | **OFF" in md
    checks.append(
        {
            "id": "narrative_mentions_fusion_off",
            "ok": fusion_narrative_ok,
            "detail": "CURRENT_STATE must keep field fusion OFF visible",
        }
    )
    if not fusion_narrative_ok:
        hard_fail = True

    # GO_Q hard rail: eng must never invent complete/true
    stamp_goq = stamp.get("GO_Q")
    goq_stamp_ok = _go_q_stamp_ok(stamp_goq)
    checks.append(
        {
            "id": "go_q_stamp_not_complete",
            "ok": goq_stamp_ok,
            "detail": f"stamp GO_Q={stamp_goq!r} (must stay partial until human acta)",
        }
    )
    if not goq_stamp_ok:
        hard_fail = True

    cs_goq = gates.get("GO_Q")
    if cs_goq is not None:
        goq_cs_ok = cs_goq.strip().lower() == "partial"
        checks.append(
            {
                "id": "go_q_current_state_partial",
                "ok": goq_cs_ok,
                "detail": f"CURRENT_STATE GO_Q={cs_goq!r} (must be partial; never invent true)",
            }
        )
        if not goq_cs_ok:
            hard_fail = True

    narrative_goq = ("GO_Q partial" in md) or ("partial" in md.lower() and "go_q" in md.lower())
    checks.append(
        {
            "id": "narrative_go_q_partial",
            "ok": narrative_goq,
            "detail": "CURRENT_STATE narrative must keep GO_Q partial visible",
        }
    )
    if not narrative_goq:
        hard_fail = True

    status = "FAIL" if hard_fail else "PASS"
    return {
        "status": status,
        "exit_code": 1 if hard_fail else 0,
        "authority": {
            "current_state": str(cs_path),
            "ml_product_go_stamp": str(st_path),
        },
        "invariants": {
            "field_ops_fusion": "OFF",
            "ml_product_go_means": "lab_only_not_field_fusion",
            "go_q": "partial_until_human_acta",
            "go_mes_plus": False,
            "tobarra_keep_reopen": False,
        },
        "checks": checks,
        "n_fail": sum(1 for c in checks if not c.get("ok")),
        "n_pass": sum(1 for c in checks if c.get("ok")),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WFD release flags SSOT check (Agent B)")
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
