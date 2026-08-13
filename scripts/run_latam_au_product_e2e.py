#!/usr/bin/env python3
"""Operator-path E2E: bridge LATAM/AU packs → decide (open_if product).

Runs the real product path (not mocked invent):
  1. Fail closed if source packs missing (exit 1).
  2. Bridge to outputs/open_if/<slug>/ (scorecard_pista_b).
  3. decide_from_request with open_pack + work_dir (decision_log + vv_scorecard).
  4. Write JSON report under outputs/open_if/latam_au_e2e/.

Exit codes:
  0 — AU + LATAM decide paths measured (GO/HOLD/ABSTAIN all valid)
  1 — missing pack / bridge failure / decide did not load open metrics
  2 — usage error

  python scripts/run_latam_au_product_e2e.py
  python scripts/run_latam_au_product_e2e.py --require-ops-for-go
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.latam_au import (  # noqa: E402
    EMSR_PACK_SPECS,
    PRODUCT_E2E_DEFAULT_IDS,
    PRODUCT_E2E_SCHEMA,
    bridge_source_pack_to_open_if,
    default_product_out_dir,
    default_source_pack_dir,
    source_pack_ready,
    utc_now,
)
from wildfire_front.product.decide_service import (  # noqa: E402
    decide_from_request,
    load_open_metrics_from_pack,
)

DEFAULT_REPORT = ROOT / "outputs" / "open_if" / "latam_au_e2e" / "product_e2e_report.json"


def _rails_snapshot() -> dict[str, Any]:
    """Derive rails from ML_PRODUCT_GO_STATUS.json — do not hardcode freeze True."""
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    go_q: Any = "partial"
    keep_reopen = False
    fusion: Any = "ON"
    if stamp_path.is_file():
        try:
            st = json.loads(stamp_path.read_text(encoding="utf-8"))
            go_q = st.get("GO_Q", st.get("go_q", go_q))
            rails = st.get("rails") if isinstance(st.get("rails"), dict) else {}
            if "tobarra_keep_reopen" in rails:
                keep_reopen = bool(rails.get("tobarra_keep_reopen"))
            if rails.get("field_ops_fusion") is not None:
                fusion = rails.get("field_ops_fusion")
            # Optional explicit freeze_ml flag if ever present
            freeze_explicit = bool(st.get("freeze_ml")) if "freeze_ml" in st else None
        except (OSError, json.JSONDecodeError):
            freeze_explicit = None
    else:
        freeze_explicit = None

    # FREEZE intact while Tobarra KEEP reopen is false (SSOT). Never invent True.
    if freeze_explicit is not None:
        freeze_intact = freeze_explicit and (keep_reopen is not True)
    else:
        freeze_intact = keep_reopen is not True

    go_q_norm = go_q
    if go_q_norm not in {False, "partial", "false"} and str(go_q_norm).lower() != "partial":
        # Never invent complete/true in E2E rails block
        go_q_norm = "partial"

    return {
        "go_q": go_q_norm,
        "freeze_intact": bool(freeze_intact),
        "field_ops_fusion": fusion,
        "tobarra_keep_reopen": bool(keep_reopen),
        "no_invent_transfer_iou": True,
        "not_field_dispatch_from_cems": True,
        "stamp_freeze_ml": bool(freeze_intact),
        "stamp_path": "docs/ML_PRODUCT_GO_STATUS.json",
    }


def run_one(
    event_id: str,
    *,
    require_ops_for_go: bool,
    use_ml_v34: bool,
    work_root: Path,
    data_root: Path | None = None,
    out_root: Path | None = None,
) -> dict[str, Any]:
    from wildfire_front.open_if.latam_au import EMSR_PACK_SPECS, pack_dir_for, product_slug_for

    if data_root is not None:
        src = pack_dir_for(Path(data_root), EMSR_PACK_SPECS[event_id])
    else:
        src = default_source_pack_dir(ROOT, event_id)
    ready, reason = source_pack_ready(src)
    if not ready:
        return {
            "event_id": event_id,
            "ok": False,
            "error": reason,
            "source_pack": str(src.relative_to(ROOT)).replace("\\", "/")
            if src.is_relative_to(ROOT)
            else str(src),
        }

    if out_root is not None:
        out_pack = Path(out_root) / product_slug_for(event_id)
    else:
        out_pack = default_product_out_dir(ROOT, event_id)
    bridge = bridge_source_pack_to_open_if(src, out_pack, repo_root=ROOT)
    open_metrics = load_open_metrics_from_pack(out_pack, base=ROOT, include_repo_root=True)
    if open_metrics is None:
        return {
            "event_id": event_id,
            "ok": False,
            "error": "open_metrics_not_loaded",
            "bridge": bridge,
            "open_pack": bridge.get("out_pack"),
        }

    work_dir = work_root / event_id.lower()
    work_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    card = decide_from_request(
        {
            "event_id": event_id,
            "open_pack": str(out_pack),
            "work_dir": str(work_dir),
            "require_ops_for_go": require_ops_for_go,
            "use_ml_v34": use_ml_v34,
            "channel": "cli",
            "write_decision_log": True,
            "write_vv_scorecard": True,
        },
        base=ROOT,
    )
    wall_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    decision = str(card.get("decision") or "ABSTAIN").upper()
    # Open pack without ops → HOLD or ABSTAIN is valid; open-only GO is not product GO.
    open_loaded = any(
        isinstance(s, dict)
        and s.get("id") == "open_cems_perimeter"
        and s.get("available")
        for s in (card.get("sources") or [])
    )
    if require_ops_for_go:
        ok = open_loaded and decision in {"HOLD", "ABSTAIN"}
    else:
        ok = open_loaded and decision in {"GO", "HOLD", "ABSTAIN"}

    dlog = work_dir / "decision_log.jsonl"
    vv = work_dir / "vv_scorecard.json"
    return {
        "event_id": event_id,
        "ok": ok,
        "error": None if ok else "open_source_not_available_or_bad_decision",
        "source_pack": bridge.get("source_pack"),
        "open_pack": bridge.get("out_pack"),
        "work_dir": str(work_dir.relative_to(ROOT)).replace("\\", "/")
        if work_dir.is_relative_to(ROOT)
        else str(work_dir),
        "decision": decision,
        "confidence_pred": card.get("confidence_pred"),
        "confidence_pred_label": card.get("confidence_pred_label"),
        "latency_ms": card.get("latency_ms"),
        "wall_ms": wall_ms,
        "reasons": (card.get("reasons") or [])[:16],
        "open_metrics": {
            "max_area_ha": open_metrics.get("max_area_ha"),
            "n_timeline_steps": open_metrics.get("n_timeline_steps"),
            "activation": open_metrics.get("activation"),
            "source_scorecard": open_metrics.get("source_scorecard"),
            "vp_invented": open_metrics.get("vp_invented"),
            "firms_hull_is_official_burned_area": open_metrics.get(
                "firms_hull_is_official_burned_area"
            ),
        },
        "open_source_available": open_loaded,
        "sidecars": {
            "decision_log": str(dlog.relative_to(ROOT)).replace("\\", "/")
            if dlog.is_file() and dlog.is_relative_to(ROOT)
            else (str(dlog) if dlog.is_file() else None),
            "vv_scorecard": str(vv.relative_to(ROOT)).replace("\\", "/")
            if vv.is_file() and vv.is_relative_to(ROOT)
            else (str(vv) if vv.is_file() else None),
            "decision_log_exists": dlog.is_file(),
            "vv_scorecard_exists": vv.is_file(),
        },
        "policy_id": card.get("policy_id"),
        "system_reliability_pass": card.get("system_reliability_pass"),
        "not_claims": [
            "not field validation from CEMS proxy",
            "not tactical dispatch",
            "not ops ROS",
            "not GO_Q complete",
        ],
    }


def build_report(
    *,
    require_ops_for_go: bool,
    use_ml_v34: bool,
    work_root: Path,
    event_ids: list[str] | None = None,
    data_root: Path | None = None,
    out_root: Path | None = None,
) -> dict[str, Any]:
    ids = event_ids or list(PRODUCT_E2E_DEFAULT_IDS)
    packs: list[dict[str, Any]] = []
    for eid in ids:
        packs.append(
            run_one(
                eid,
                require_ops_for_go=require_ops_for_go,
                use_ml_v34=use_ml_v34,
                work_root=work_root,
                data_root=data_root,
                out_root=out_root,
            )
        )
    all_ok = all(p.get("ok") for p in packs) and len(packs) >= 1
    missing = [p for p in packs if p.get("error") and "missing" in str(p.get("error"))]
    return {
        "schema": PRODUCT_E2E_SCHEMA,
        "as_of_utc": utc_now(),
        "protocol": "latam_au_product_e2e_v1",
        "campaign": "LATAM_AU",
        "ok": all_ok,
        "n_packs": len(packs),
        "n_ok": sum(1 for p in packs if p.get("ok")),
        "require_ops_for_go": require_ops_for_go,
        "use_ml_v34": use_ml_v34,
        "rails": _rails_snapshot(),
        "packs": packs,
        "missing_pack_errors": [p.get("error") for p in missing],
        "not_claims": [
            "not GO_Q complete",
            "not FREEZE lift",
            "not field validation from CEMS",
            "not invent transfer IoU",
            "not Tobarra KEEP retrain",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LATAM/AU product open_if E2E")
    ap.add_argument(
        "--event-id",
        action="append",
        dest="event_ids",
        default=None,
        help="Limit to event id(s). Default: both AU + CL.",
    )
    ap.add_argument(
        "--require-ops-for-go",
        action="store_true",
        default=True,
        help="Pass require_ops_for_go to decide (default true)",
    )
    ap.add_argument(
        "--no-require-ops-for-go",
        action="store_true",
        help="Disable require_ops_for_go",
    )
    ap.add_argument(
        "--use-ml-v34",
        action="store_true",
        help="Also load sealed catalog ML metrics (research only)",
    )
    ap.add_argument(
        "--work-root",
        type=Path,
        default=ROOT / "outputs" / "open_if" / "latam_au_e2e" / "work",
    )
    ap.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Override source pack root (default: data/open_if/latam_au)",
    )
    ap.add_argument(
        "--out-root",
        type=Path,
        default=None,
        help="Override product open_if root (default: outputs/open_if)",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
    )
    ap.add_argument(
        "--update-domain-gap",
        action="store_true",
        help="Merge product_e2e section into domain-gap scorecard docs+outputs",
    )
    args = ap.parse_args(argv)

    # Pre-flight: fail clear if packs missing
    from wildfire_front.open_if.latam_au import pack_dir_for

    ids = list(args.event_ids) if args.event_ids else list(PRODUCT_E2E_DEFAULT_IDS)
    data_root = Path(args.data_root) if args.data_root is not None else None
    for eid in ids:
        if eid not in EMSR_PACK_SPECS:
            print(f"error: unknown event_id {eid}", file=sys.stderr)
            return 2
        if data_root is not None:
            src = pack_dir_for(data_root, EMSR_PACK_SPECS[eid])
        else:
            src = default_source_pack_dir(ROOT, eid)
        ready, reason = source_pack_ready(src)
        if not ready:
            print(
                f"error: pack missing or incomplete for {eid}: {reason}\n"
                f"  expected: {src}\n"
                f"  run: python scripts/materialize_latam_au_emsr_packs.py",
                file=sys.stderr,
            )
            # Still write a failure report for audit
            fail_doc = {
                "schema": PRODUCT_E2E_SCHEMA,
                "as_of_utc": utc_now(),
                "ok": False,
                "error": reason,
                "event_id": eid,
                "source_pack": str(src),
            }
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(fail_doc, indent=2), encoding="utf-8")
            return 1

    req_ops = not args.no_require_ops_for_go
    report = build_report(
        require_ops_for_go=req_ops,
        use_ml_v34=bool(args.use_ml_v34),
        work_root=Path(args.work_root),
        event_ids=ids,
        data_root=data_root,
        out_root=Path(args.out_root) if args.out_root is not None else None,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"wrote {args.report}")
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "n_ok": report["n_ok"],
                "n_packs": report["n_packs"],
                "decisions": [
                    {"event_id": p["event_id"], "decision": p.get("decision"), "ok": p.get("ok")}
                    for p in report["packs"]
                ],
            },
            indent=2,
        )
    )

    if args.update_domain_gap:
        _merge_into_domain_gap(report)

    return 0 if report["ok"] else 1


def _merge_into_domain_gap(product_e2e: dict[str, Any]) -> None:
    """Attach product_e2e measured section to domain-gap scorecard copies."""
    paths = [
        ROOT / "docs" / "data_campaigns" / "LATAM_AU_DOMAIN_GAP_SCORECARD.json",
        ROOT / "outputs" / "ml_eval" / "scorecards" / "wfd_ml_domain_gap_v1.json",
    ]
    section = {
        "schema": PRODUCT_E2E_SCHEMA,
        "as_of_utc": product_e2e.get("as_of_utc"),
        "ok": product_e2e.get("ok"),
        "n_ok": product_e2e.get("n_ok"),
        "n_packs": product_e2e.get("n_packs"),
        "rails": product_e2e.get("rails"),
        "decisions": [
            {
                "event_id": p.get("event_id"),
                "decision": p.get("decision"),
                "latency_ms": p.get("latency_ms"),
                "open_pack": p.get("open_pack"),
                "open_source_available": p.get("open_source_available"),
                "max_area_ha": (p.get("open_metrics") or {}).get("max_area_ha"),
                "sidecars": p.get("sidecars"),
            }
            for p in product_e2e.get("packs") or []
        ],
        "note": (
            "Measured product decide path on bridged open_if packs. "
            "HOLD/ABSTAIN without ops is valid. Not field validation."
        ),
    }
    for path in paths:
        if not path.is_file():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        doc["product_e2e"] = section
        doc["as_of_utc"] = utc_now()
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        print(f"updated domain-gap: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
