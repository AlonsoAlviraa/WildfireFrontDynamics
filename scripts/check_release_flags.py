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
SPA_HTML = ROOT / "outputs" / "app" / "index.html"
SPA_HTML_MODULE = ROOT / "wildfire_front" / "product" / "app_spa_html.py"
LIVE_OPS_MODULE = ROOT / "wildfire_front" / "product" / "live_ops.py"
CLI_APP_MODULE = ROOT / "wildfire_front" / "cli_app.py"
# Industrial C2 markers that must not regress (PR10)
SPA_MARKERS = ("#0B1220", "primary-acts", "mode-toggle", "btn-act-decide")
# Live Ops Demo Kernel markers (post–Live Ops stack)
LIVE_OPS_MARKERS = ("/live/v1/decide", "runLiveAct", "live_ops")
LIVE_OPS_CORE_MARKERS = ("live_ops_loopback", "LIVE_PATH_DECIDE", "handle_decide")
DEMO_DAY_MARKERS = ("--demo-day", "demo_day")


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

    gates.get("field_ops ML fusion") or gates.get("field_ops ML fusion")
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

    # GO_Q must not be claimed true without H1 (honesty rail)
    cs_goq = gates.get("GO_Q")
    if cs_goq is not None:
        goq_tok = _truthy_token(cs_goq)
        # partial → None; true is forbidden without human H1 evidence in stamp
        invent = goq_tok is True
        checks.append(
            {
                "id": "go_q_not_true_without_h1",
                "ok": not invent,
                "detail": (
                    f"CURRENT_STATE GO_Q={cs_goq} "
                    "(must stay partial/false until H1 demo+acta; eng must not invent true)"
                ),
            }
        )
        if invent:
            hard_fail = True

    # SPA industrial C2 markers (renderer source always; artifact if present)
    spa_src_ok = SPA_HTML_MODULE.is_file()
    spa_src_text = SPA_HTML_MODULE.read_text(encoding="utf-8") if spa_src_ok else ""
    missing_src = [m for m in SPA_MARKERS if m not in spa_src_text] if spa_src_ok else list(SPA_MARKERS)
    checks.append(
        {
            "id": "spa_industrial_markers_source",
            "ok": spa_src_ok and not missing_src,
            "detail": (
                f"app_spa_html markers missing={missing_src or 'none'} "
                f"(required {list(SPA_MARKERS)})"
            ),
        }
    )
    if not checks[-1]["ok"]:
        hard_fail = True

    # Live Ops wire (SPA HTML + core module + demo-day CLI)
    missing_live_html = (
        [m for m in LIVE_OPS_MARKERS if m not in spa_src_text] if spa_src_ok else list(LIVE_OPS_MARKERS)
    )
    checks.append(
        {
            "id": "live_ops_spa_markers",
            "ok": spa_src_ok and not missing_live_html,
            "detail": (
                f"Live Ops SPA markers missing={missing_live_html or 'none'} "
                f"(required {list(LIVE_OPS_MARKERS)})"
            ),
        }
    )
    if not checks[-1]["ok"]:
        hard_fail = True

    live_core_ok = LIVE_OPS_MODULE.is_file()
    live_core_text = LIVE_OPS_MODULE.read_text(encoding="utf-8") if live_core_ok else ""
    missing_core = (
        [m for m in LIVE_OPS_CORE_MARKERS if m not in live_core_text]
        if live_core_ok
        else list(LIVE_OPS_CORE_MARKERS)
    )
    checks.append(
        {
            "id": "live_ops_core_module",
            "ok": live_core_ok and not missing_core,
            "detail": (
                f"live_ops.py markers missing={missing_core or 'none'} "
                f"(required {list(LIVE_OPS_CORE_MARKERS)})"
            ),
        }
    )
    if not checks[-1]["ok"]:
        hard_fail = True

    cli_ok = CLI_APP_MODULE.is_file()
    cli_text = CLI_APP_MODULE.read_text(encoding="utf-8") if cli_ok else ""
    missing_dd = (
        [m for m in DEMO_DAY_MARKERS if m not in cli_text] if cli_ok else list(DEMO_DAY_MARKERS)
    )
    checks.append(
        {
            "id": "app_demo_day_flag",
            "ok": cli_ok and not missing_dd,
            "detail": (
                f"cli_app demo-day markers missing={missing_dd or 'none'} "
                f"(required {list(DEMO_DAY_MARKERS)})"
            ),
        }
    )
    if not checks[-1]["ok"]:
        hard_fail = True

    if SPA_HTML.is_file():
        spa_html = SPA_HTML.read_text(encoding="utf-8", errors="replace")
        missing_art = [m for m in SPA_MARKERS if m not in spa_html]
        checks.append(
            {
                "id": "spa_industrial_markers_artifact",
                "ok": not missing_art,
                "detail": (
                    f"outputs/app/index.html markers missing={missing_art or 'none'}"
                ),
            }
        )
        if missing_art:
            hard_fail = True
        # Artifact must not invent GO_Q true in embedded narrative rails
        if '"GO_Q": true' in spa_html or '"GO_Q":true' in spa_html:
            # brief gates may stringify; fail only exact true invent
            checks.append(
                {
                    "id": "spa_artifact_go_q_not_true",
                    "ok": False,
                    "detail": "SPA artifact embeds GO_Q true — invent forbidden without H1",
                }
            )
            hard_fail = True
        else:
            checks.append(
                {
                    "id": "spa_artifact_go_q_not_true",
                    "ok": True,
                    "detail": "SPA artifact does not embed GO_Q true",
                }
            )
    else:
        checks.append(
            {
                "id": "spa_industrial_markers_artifact",
                "ok": True,
                "detail": "outputs/app/index.html absent (optional freshness; source markers checked)",
            }
        )

    status = "FAIL" if hard_fail else "PASS"
    return {
        "status": status,
        "exit_code": 1 if hard_fail else 0,
        "authority": {
            "current_state": str(CURRENT_STATE.relative_to(ROOT)),
            "ml_product_go_stamp": str(ML_GO_STAMP.relative_to(ROOT)),
            "spa_html_module": str(SPA_HTML_MODULE.relative_to(ROOT)),
        },
        "invariants": {
            "field_ops_fusion": "OFF",
            "ml_product_go_means": "lab_only_not_field_fusion",
            "tobarra_keep_reopen": False,
            "go_q_invent_forbidden": True,
            "spa_industrial_c2": True,
            "live_ops_demo_kernel": True,
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
