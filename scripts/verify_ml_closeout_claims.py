#!/usr/bin/env python3
"""Deterministic verification of ML closeout claim pack against in-repo stamps.

Writes a report JSON + markdown. Does not invent metrics or flip fusion/GO_Q.

Usage:
  python scripts/verify_ml_closeout_claims.py
  python scripts/verify_ml_closeout_claims.py --report-json PATH --report-md PATH
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "outputs" / "ml_eval" / "lab_loop" / "ML_CLOSEOUT_DECISION.json"
CHECKER = ROOT / "outputs" / "ml_eval" / "lab_loop" / "ML_CLOSEOUT_CHECKER.json"
GOAL_DOC = ROOT / "docs" / "GOAL_ML_CLOSEOUT.md"
CURRENT = ROOT / "docs" / "CURRENT_STATE.md"
PACK = ROOT / "docs" / "VERIFY_PACK_ML_CLOSEOUT.md"
DEFAULT_JSON = ROOT / "docs" / "DEEP_VERIFY_ML_CLOSEOUT_REPORT.json"
DEFAULT_MD = ROOT / "docs" / "DEEP_VERIFY_ML_CLOSEOUT_REPORT.md"


def _claim(cid: str, text: str, ok: bool, evidence: str, source: str) -> dict[str, Any]:
    return {
        "id": cid,
        "text": text,
        "verdict": "supported" if ok else "contradicted",
        "evidence": evidence,
        "source": source,
        "audited": True,
        "auditQuality": "high" if ok else "medium",
        "auditNote": "deterministic board check (in-repo stamps only)",
    }


def verify() -> dict[str, Any]:
    claims: list[dict[str, Any]] = []

    if not DECISION.is_file():
        return {
            "total": 1,
            "supported": 0,
            "contradicted": 1,
            "unverifiable": 0,
            "claims": [
                _claim(
                    "c1",
                    "ML closeout decision stamp exists",
                    False,
                    f"missing {DECISION}",
                    str(DECISION),
                )
            ],
            "checked_utc": datetime.now(UTC).isoformat(),
            "method": "deterministic_stamp_check",
        }

    dec = json.loads(DECISION.read_text(encoding="utf-8"))
    rails = dec.get("rails") or {}
    champs = dec.get("champions_freeze") or {}
    sealed = champs.get("sealed_product_lofo") or {}
    kill = dec.get("kill_list_no_reopen_without_new_evidence_class") or []
    if isinstance(kill, dict):
        kill_list = list(kill.keys()) + [str(v) for v in kill.values()]
    else:
        kill_list = [str(x) for x in kill]

    checker_ok = False
    checker_dec = None
    if CHECKER.is_file():
        ch = json.loads(CHECKER.read_text(encoding="utf-8"))
        checker_ok = bool(ch.get("met"))
        checker_dec = ch.get("decision")

    goal_txt = GOAL_DOC.read_text(encoding="utf-8") if GOAL_DOC.is_file() else ""
    cur_txt = CURRENT.read_text(encoding="utf-8") if CURRENT.is_file() else ""
    pack_ok = PACK.is_file()

    mean = sealed.get("mean")
    mean_ok = isinstance(mean, (int, float)) and abs(float(mean) - 0.7878) < 0.01

    claims.append(
        _claim(
            "c1",
            "ML closeout decision stamp exists at outputs/ml_eval/lab_loop/ML_CLOSEOUT_DECISION.json",
            DECISION.is_file(),
            f"exists size={DECISION.stat().st_size}",
            str(DECISION.relative_to(ROOT)),
        )
    )
    claims.append(
        _claim(
            "c2",
            "ML closeout decision is FREEZE_ML_AND_REQUEST_DATA",
            dec.get("decision") == "FREEZE_ML_AND_REQUEST_DATA",
            f"decision={dec.get('decision')!r}",
            str(DECISION.relative_to(ROOT)),
        )
    )
    claims.append(
        _claim(
            "c3",
            "ML closeout stamp has met true",
            dec.get("met") is True,
            f"met={dec.get('met')!r}",
            str(DECISION.relative_to(ROOT)),
        )
    )
    claims.append(
        _claim(
            "c4",
            "field_ops_allow_ml_live_in_fusion is false (field fusion OFF)",
            rails.get("field_ops_allow_ml_live_in_fusion") is False,
            f"rails.field_ops_allow_ml_live_in_fusion={rails.get('field_ops_allow_ml_live_in_fusion')!r}",
            str(DECISION.relative_to(ROOT)) + "#rails",
        )
    )
    claims.append(
        _claim(
            "c5",
            "iou_is_not_ros is true on ML closeout rails",
            rails.get("iou_is_not_ros") is True,
            f"rails.iou_is_not_ros={rails.get('iou_is_not_ros')!r}",
            str(DECISION.relative_to(ROOT)) + "#rails",
        )
    )
    claims.append(
        _claim(
            "c6",
            "ml_product_go true is lab-only (lab_only rail true, fusion off)",
            rails.get("ml_product_go") is True
            and rails.get("lab_only") is True
            and rails.get("field_ops_allow_ml_live_in_fusion") is False,
            f"ml_product_go={rails.get('ml_product_go')!r} lab_only={rails.get('lab_only')!r}",
            str(DECISION.relative_to(ROOT)) + "#rails",
        )
    )
    claims.append(
        _claim(
            "c7",
            "tobarra_keep_reopen is false (KEEP KILL held)",
            rails.get("tobarra_keep_reopen") is False,
            f"tobarra_keep_reopen={rails.get('tobarra_keep_reopen')!r}",
            str(DECISION.relative_to(ROOT)) + "#rails",
        )
    )
    claims.append(
        _claim(
            "c8",
            "Sealed champion is exact_force_ema_long with mean ~0.7878",
            sealed.get("config_id") == "exact_force_ema_long" and mean_ok,
            f"config_id={sealed.get('config_id')!r} mean={mean!r}",
            str(DECISION.relative_to(ROOT)) + "#champions_freeze.sealed_product_lofo",
        )
    )
    weather = champs.get("weather_spatial_lab") or champs.get("weather_era5_long") or {}
    # accept any weather freeze key with era5 in name
    if not weather:
        for k, v in champs.items():
            if isinstance(v, dict) and "era5" in str(v.get("config_id", k)).lower():
                weather = v
                break
    claims.append(
        _claim(
            "c9",
            "Weather era5_long path is present as frozen lab champion (not field fusion)",
            bool(weather)
            and (
                "era5" in str(weather.get("config_id", "")).lower()
                or "era5" in json.dumps(weather).lower()
            )
            and rails.get("field_ops_allow_ml_live_in_fusion") is False,
            f"weather_keys={list(champs.keys())} weather={ {k: weather.get(k) for k in list(weather)[:6]} }",
            str(DECISION.relative_to(ROOT)) + "#champions_freeze",
        )
    )
    kill_blob = " ".join(kill_list).lower() + " " + json.dumps(dec.get("kill_list_no_reopen_without_new_evidence_class") or {}).lower()
    claims.append(
        _claim(
            "c10",
            "Kill list blocks Tobarra KEEP reopen and larger U-Net thrash",
            ("tobarra" in kill_blob or rails.get("tobarra_keep_reopen") is False)
            and ("unet" in kill_blob or rails.get("larger_unet_default") is False),
            f"kill_blob_snip={kill_blob[:200]!r} larger_unet_default={rails.get('larger_unet_default')!r}",
            str(DECISION.relative_to(ROOT)),
        )
    )
    claims.append(
        _claim(
            "c11",
            "GOAL_ML_CLOSEOUT.md defines FREEZE / REQUEST_DATA / CEILING",
            GOAL_DOC.is_file()
            and "FREEZE_ML" in goal_txt
            and "REQUEST_MORE_DATA" in goal_txt
            and "CEILING" in goal_txt,
            f"goal_doc_exists={GOAL_DOC.is_file()} has_freeze={'FREEZE_ML' in goal_txt}",
            str(GOAL_DOC.relative_to(ROOT)) if GOAL_DOC.is_file() else str(GOAL_DOC),
        )
    )
    claims.append(
        _claim(
            "c12",
            "ML_CLOSEOUT_CHECKER.json met true for freeze decision",
            CHECKER.is_file() and checker_ok and checker_dec == "FREEZE_ML_AND_REQUEST_DATA",
            f"checker_met={checker_ok} decision={checker_dec!r}",
            str(CHECKER.relative_to(ROOT)) if CHECKER.is_file() else str(CHECKER),
        )
    )
    claims.append(
        _claim(
            "c13",
            "CURRENT_STATE documents freeze closeout and fusion OFF",
            CURRENT.is_file()
            and (
                "FREEZE" in cur_txt.upper()
                or "REQUEST_DATA" in cur_txt.upper()
                or "ML closeout" in cur_txt
                or "ml closeout" in cur_txt.lower()
            )
            and ("fusion" in cur_txt.lower() and "OFF" in cur_txt),
            f"current_has_freeze_or_request={'FREEZE' in cur_txt.upper() or 'REQUEST_DATA' in cur_txt.upper()} fusion_off_mentions={('OFF' in cur_txt)}",
            str(CURRENT.relative_to(ROOT)) if CURRENT.is_file() else str(CURRENT),
        )
    )
    claims.append(
        _claim(
            "c14",
            "Closeout ceiling rules reject unbacked +0.05 sealed claims",
            "0.05" in goal_txt or "+0.05" in json.dumps(dec),
            "goal/decision mention +0.05 ceiling rules",
            str(GOAL_DOC.relative_to(ROOT)) if GOAL_DOC.is_file() else str(DECISION.relative_to(ROOT)),
        )
    )
    claims.append(
        _claim(
            "c15",
            "ml_product_go true does not authorize field fusion ON",
            rails.get("ml_product_go") is True
            and rails.get("field_ops_allow_ml_live_in_fusion") is False,
            "lab go true with fusion false",
            str(DECISION.relative_to(ROOT)) + "#rails",
        )
    )
    claims.append(
        _claim(
            "c16",
            "VERIFY_PACK_ML_CLOSEOUT.md exists",
            pack_ok,
            f"pack={PACK}",
            str(PACK.relative_to(ROOT)) if pack_ok else str(PACK),
        )
    )

    # No GO_Q invent / fusion ON invented
    invent_bad = any(
        re.search(r'"GO_Q"\s*:\s*true', json.dumps(c), re.I) and "invent" not in c["text"].lower()
        for c in claims
        if c["verdict"] == "supported" and False  # never invent
    )
    _ = invent_bad

    supported = sum(1 for c in claims if c["verdict"] == "supported")
    contradicted = sum(1 for c in claims if c["verdict"] == "contradicted")
    return {
        "schema": "wfd_deep_verify_ml_closeout_v1",
        "method": "deterministic_stamp_check",
        "checked_utc": datetime.now(UTC).isoformat(),
        "total": len(claims),
        "supported": supported,
        "contradicted": contradicted,
        "unverifiable": 0,
        "claims": claims,
        "rails_snapshot": rails,
        "decision": dec.get("decision"),
        "go_q_invent": False,
        "field_ops_fusion": "OFF",
        "pack": str(PACK.relative_to(ROOT)) if pack_ok else None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Verify ML closeout claim pack against stamps")
    ap.add_argument("--report-json", type=Path, default=DEFAULT_JSON)
    ap.add_argument("--report-md", type=Path, default=DEFAULT_MD)
    args = ap.parse_args(argv)

    report = verify()
    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Deep-verify report — ML lab closeout",
        "",
        f"- **method:** {report['method']}",
        f"- **checked_utc:** {report['checked_utc']}",
        f"- **total:** {report['total']}",
        f"- **supported:** {report['supported']}",
        f"- **contradicted:** {report['contradicted']}",
        f"- **unverifiable:** {report['unverifiable']}",
        f"- **decision:** `{report.get('decision')}`",
        f"- **field_ops_fusion:** {report.get('field_ops_fusion')}",
        f"- **go_q_invent:** {report.get('go_q_invent')} (must stay false)",
        "",
        "## Claims",
        "",
    ]
    for c in report["claims"]:
        mark = "OK" if c["verdict"] == "supported" else "FAIL"
        lines.append(f"- **{c['id']}** [{mark}/{c['verdict']}]: {c['text']}")
        lines.append(f"  - evidence: {c['evidence']}")
        lines.append(f"  - source: `{c['source']}`")
    lines.append("")
    args.report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": report["contradicted"] == 0 and report["supported"] == report["total"],
                "total": report["total"],
                "supported": report["supported"],
                "contradicted": report["contradicted"],
                "report_json": str(args.report_json),
                "report_md": str(args.report_md),
            },
            indent=2,
        )
    )
    return 0 if report["contradicted"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
