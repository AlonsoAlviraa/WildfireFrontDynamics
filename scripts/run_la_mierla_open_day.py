#!/usr/bin/env python3
"""Daily open-track cadence for IF La Mierla (Sprint B/C wiring).

Builds/refreshes pack + satellite enrich (optional), appends timeline series,
CEMS WATCH, STAC/dNBR queue, decide HOLD cards, week_package export.

Hard rule: field_ops GO is forbidden on open-only path (assert + coerce to HOLD).

  PYTHONPATH=. python scripts/run_la_mierla_open_day.py
  PYTHONPATH=. python scripts/run_la_mierla_open_day.py --skip-network
  PYTHONPATH=. python scripts/run_la_mierla_open_day.py --try-dnbr
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.open_if.anchor_guard import assert_not_fake_confirmed  # noqa: E402
from wildfire_front.open_if.cems_watch import (  # noqa: E402
    EMSR896_NOTE,
    build_cems_watch,
)
from wildfire_front.open_if.dnbr_queue import (  # noqa: E402
    evaluate_dnbr_queue,
    stac_items_from_enrichment_doc,
)
from wildfire_front.open_if.timeline import (  # noqa: E402
    append_counts_by_date,
    daily_stats_from_geojson_features,
    empty_timeline,
    merge_timeline_days,
)
from wildfire_front.open_if.week_package import export_week_package  # noqa: E402

EVENT = "guadalajara_la_mierla_20260717"
PACK = ROOT / "outputs" / "open_if" / "la_mierla_20260717"
EVENT_DATE = "2026-07-16"
UA = "WildfireFrontDynamics/1.0 (open emergency research)"
ANCHORS_PATH = ROOT / "data" / "infocam_anchors.json"


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _run_script(rel: str, *, skip: bool) -> dict[str, Any]:
    if skip:
        return {"skipped": True, "script": rel, "ok": True}
    script = ROOT / rel
    if not script.is_file():
        return {"ok": False, "script": rel, "error": "missing_script"}
    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "script": rel,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-1500:],
            "stderr_tail": (proc.stderr or "")[-800:],
        }
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "script": rel, "error": f"timeout:{exc}"}
    except OSError as exc:
        return {"ok": False, "script": rel, "error": str(exc)}


def merge_scrape_history(
    pack: Path,
    scrape_latest: dict[str, Any] | None,
    *,
    day_key: str | None = None,
) -> dict[str, Any]:
    """Append scrape_latest into scrape_history.json; keep per-day snapshot list."""
    hist_path = pack / "scrape_history.json"
    hist = _load_json(hist_path) or {
        "schema": "open_if_scrape_history_v1",
        "event_id": EVENT,
        "days": {},
    }
    days = hist.setdefault("days", {})
    if not isinstance(days, dict):
        days = {}
        hist["days"] = days
    key = day_key or datetime.now(UTC).strftime("%Y-%m-%d")
    snapshot = {
        "scraped_at_utc": (scrape_latest or {}).get("scraped_at_utc") or _utc(),
        "infocam_latest": (scrape_latest or {}).get("infocam_latest"),
        "cems": (scrape_latest or {}).get("cems"),
        "press_n": len((scrape_latest or {}).get("press") or []),
        "x_official_n": len((scrape_latest or {}).get("x_official") or []),
        "merged_at": _utc(),
    }
    existing = days.get(key)
    history: list[dict[str, Any]] = []
    if isinstance(existing, dict):
        if isinstance(existing.get("history"), list):
            history = [h for h in existing["history"] if isinstance(h, dict)]
        elif "scraped_at_utc" in existing and "latest" not in existing:
            # migrate flat slot → history list
            history = [dict(existing)]
        elif isinstance(existing.get("latest"), dict):
            history = [dict(existing["latest"])]
            if isinstance(existing.get("history"), list):
                history = [h for h in existing["history"] if isinstance(h, dict)]
    history.append(snapshot)
    days[key] = {
        "latest": snapshot,
        "history": history,
        "n_snapshots": len(history),
    }
    hist["updated_at"] = _utc()
    hist["event_id"] = EVENT
    _write_json(hist_path, hist)
    return hist


def update_timeline_from_pack(pack: Path) -> dict[str, Any]:
    """Merge daily FIRMS series from 7d geojson / enrichment report into timeline_daily.json."""
    path = pack / "timeline_daily.json"
    existing = _load_json(path)
    generated_at = _utc()
    new_days: dict[str, dict[str, Any]] = {}

    gj7 = pack / "firms_hotspots_7d.geojson"
    if gj7.is_file():
        try:
            fc = json.loads(gj7.read_text(encoding="utf-8"))
            feats = fc.get("features") or []
            new_days = daily_stats_from_geojson_features(feats, sensor="viirs_n20_7d")
        except (OSError, json.JSONDecodeError, TypeError):
            new_days = {}

    # Fallback: enrichment report counts only (FRP preserved by merge if prior exists)
    if not new_days:
        rep = _load_json(pack / "satellite_enrichment" / "enrichment_report.json") or _load_json(
            pack / "satellite_enrichment_report.json"
        )
        if rep:
            counts = rep.get("timeline_viirs_n20_7d") or {}
            sensors = (rep.get("sensors") or {}).get("viirs_n20_7d") or {}
            if not counts:
                counts = sensors.get("counts_by_date") or {}
            if counts:
                doc = append_counts_by_date(
                    existing,
                    {str(k): int(v) for k, v in counts.items()},
                    event_id=EVENT,
                    sensor="viirs_n20_7d",
                    generated_at=generated_at,
                )
                _write_json(path, doc)
                return doc

    if not new_days and not existing:
        doc = empty_timeline(EVENT)
        _write_json(path, doc)
        return doc

    doc = merge_timeline_days(
        existing,
        new_days,
        event_id=EVENT,
        sensor_primary="viirs_n20_7d",
        generated_at=generated_at,
    )
    _write_json(path, doc)
    return doc


def run_cems_watch(pack: Path, *, try_fetch: bool = True) -> dict[str, Any]:
    fetch_result: dict[str, Any] | None = None
    if try_fetch:
        url = "https://mapping.emergency.copernicus.eu/news/"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = resp.read(80000).decode("utf-8", errors="replace")
            lower = body.lower()
            fetch_result = {
                "url": url,
                "ok": True,
                "mentions_mierla": "mierla" in lower or "guadalajara" in lower,
                "mentions_emsr896": "emsr896" in lower or "emsr 896" in lower,
                "mentions_ores": "orés" in lower or "ores" in lower,
            }
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            fetch_result = {"url": url, "ok": False, "error": str(exc)}

    scrape = _load_json(pack / "scrape_latest.json") or {}
    cems_scrape = scrape.get("cems") if isinstance(scrape.get("cems"), dict) else {}
    note = cems_scrape.get("note") or EMSR896_NOTE
    related = cems_scrape.get("related_news")
    doc = build_cems_watch(
        status="WATCH",
        note=note,
        related_news=related,
        fetch_result=fetch_result,
        activation_codes_seen=["EMSR896"] if (fetch_result or {}).get("mentions_emsr896") else [],
        la_mierla_emsr=None,
    )
    _write_json(pack / "cems_watch.json", doc)
    return doc


def update_dnbr_queue_from_stac(pack: Path) -> dict[str, Any]:
    stac_path = pack / "satellite_enrichment" / "sentinel2_stac_search.json"
    stac = _load_json(stac_path) or {}
    buckets = stac_items_from_enrichment_doc(stac)
    queue = evaluate_dnbr_queue(
        pre_items=buckets.get("pre"),
        post_items=buckets.get("post"),
        during_clear_items=buckets.get("strict_clear_during") or buckets.get("during"),
        max_cloud=30.0,
        event_date=EVENT_DATE,
    )
    _write_json(pack / "dnbr_queue.json", queue)
    return queue


def _runner_missing_post(reasons: list[str]) -> bool:
    """True when build_open_if_dnbr itself reported missing post scenes."""
    joined = " ".join(reasons).lower()
    return "no_post_fire_stac_items" in joined or (
        "post" in joined and ("missing" in joined or "no_post" in joined)
    )


def try_dnbr(
    pack: Path,
    *,
    search_only: bool = True,
    event_date: str = EVENT_DATE,
) -> dict[str, Any]:
    """Wire build_open_if_dnbr.run_for_pack; write honest status if incomplete.

    Never demote a real GO from the enrichment queue alone (independent STAC windows).
    Only annotate / demote when the dNBR runner itself reports missing post.
    """
    status: dict[str, Any]
    try:
        spec = importlib.util.spec_from_file_location(
            "build_open_if_dnbr", ROOT / "scripts" / "build_open_if_dnbr.py"
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot_import_build_open_if_dnbr")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        status = mod.run_for_pack(
            pack,
            event_date=event_date,
            dry_run_search_only=search_only,
        )
    except Exception as exc:  # noqa: BLE001 — keep day run alive
        status = {
            "schema": "open_if_dnbr_status_v1",
            "status": "BLOCKED",
            "reasons": [f"dnbr_runner_exception:{type(exc).__name__}:{exc}"],
            "built_at_utc": _utc(),
            "disclaimer": "Not official perimeter. Severity proxy only.",
        }
        _write_json(pack / "dnbr_status.json", status)

    queue = _load_json(pack / "dnbr_queue.json") or {}
    reasons = list(status.get("reasons") or [])
    runner_status = str(status.get("status") or "")

    # Annotate incomplete from queue only when runner is already non-GO.
    # Never demote GO solely because enrichment post_fire bucket is empty.
    if runner_status in ("BLOCKED", "PARTIAL"):
        if queue.get("detail_status") == "incomplete_pre_only":
            if "incomplete_without_clear_post" not in reasons:
                reasons.append("incomplete_without_clear_post")
            status["reasons"] = reasons
            status["honest_incomplete"] = True
            _write_json(pack / "dnbr_status.json", status)
        elif _runner_missing_post(reasons):
            status["honest_incomplete"] = True
            _write_json(pack / "dnbr_status.json", status)
    elif runner_status == "GO" and queue.get("status") == "blocked_clouds":
        # Keep GO; note queue disagreement without demotion
        status["queue_disagreement"] = {
            "dnbr_queue_status": queue.get("status"),
            "detail_status": queue.get("detail_status"),
            "note": (
                "Enrichment STAC queue lacks post_fire items but dNBR runner "
                "found pre+post and returned GO — not demoted."
            ),
        }
        _write_json(pack / "dnbr_status.json", status)

    _update_scorecard_dnbr(pack, status, queue)
    compare_hull_vs_dnbr(pack, status)
    return status


def _update_scorecard_dnbr(
    pack: Path,
    status: dict[str, Any],
    queue: dict[str, Any],
) -> None:
    sc_path = pack / "scorecard_pista_b.json"
    sc = _load_json(sc_path)
    if sc is None:
        return
    sc["dnbr_status"] = status.get("status")
    sc["dnbr_queue_status"] = queue.get("status")
    sc["dnbr_stac_status"] = status.get("status")
    notes = list(sc.get("notes") or [])
    note = f"dnbr_status={status.get('status')} queue={queue.get('status')}"
    if note not in notes:
        notes.append(note)
    sc["notes"] = notes
    _write_json(sc_path, sc)


def compare_hull_vs_dnbr(pack: Path, dnbr_status: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write hull vs dNBR comparison only with honest labels; never invent area."""
    hull_ha = None
    fp = _load_json(pack / "firms_footprint_proxy.geojson")
    if fp:
        for ft in fp.get("features") or []:
            props = ft.get("properties") or {}
            if props.get("layer") == "firms_convex_hull":
                hull_ha = props.get("approx_area_ha_from_hull")
                break
    metrics = _load_json(pack / "firms_metrics.json") or {}
    if hull_ha is None:
        hull_ha = metrics.get("hull_area_ha_approx")

    dnbr = dnbr_status or _load_json(pack / "dnbr_status.json") or {}
    summary = _load_json(pack / "dnbr_summary.json") or {}
    dnbr_ready = dnbr.get("status") == "GO" and summary

    comp: dict[str, Any] = {
        "schema": "open_if_hull_vs_dnbr_v1",
        "event_id": EVENT,
        "built_at_utc": _utc(),
        "not_official_perimeter": True,
        "not_official_burned_area": True,
        "firms_hull_area_ha_approx": hull_ha,
        "dnbr_status": dnbr.get("status"),
        "dnbr_burned_frac_ge_0.27": (summary.get("severity") or {}).get("burned_frac_ge_0.27")
        if summary
        else None,
        "comparison_available": bool(dnbr_ready and hull_ha is not None),
        "labels": [
            "firms_hull_is_thermal_proxy_not_burned_area",
            "dnbr_is_severity_proxy_not_egif",
            "not_official",
        ],
        "note": (
            "Comparison only when both hull and dNBR GO exist. "
            "Neither is official perimeter or EGIF ha."
        ),
    }
    if not dnbr_ready:
        comp["note"] = (
            "dNBR not complete — comparison deferred. "
            "Hull alone must not be reported as burned area."
        )
    _write_json(pack / "hull_vs_dnbr_comparison.json", comp)
    return comp


def write_synthetic_hold(pack: Path, *, reason: str) -> dict[str, Any]:
    """Write a minimal field_ops HOLD card (open-only hard rule)."""
    card = {
        "event_id": EVENT,
        "decision": "HOLD",
        "confidence_pred": 0.5,
        "confidence_pred_label": "MEDIUM",
        "open_only_hard_rule": True,
        "open_only_hard_rule_note": reason,
        "sources": [],
        "metrics": {
            "extra": {
                "open_only_go_blocked": True,
                "synthetic_hold": True,
            }
        },
        "reasons": ["open_only_path_forbids_field_ops_GO", reason],
        "generated_at_utc": _utc(),
    }
    _write_json(pack / "fire_decision_card_field_ops.json", card)
    return card


def coerce_field_ops_hold(card: dict[str, Any]) -> dict[str, Any]:
    """Force field_ops card to HOLD with open_only hard-rule flags."""
    card = dict(card)
    card["decision"] = "HOLD"
    card["open_only_hard_rule"] = True
    card["open_only_hard_rule_note"] = "field_ops GO forbidden on open-only path; coerced to HOLD"
    reasons = list(card.get("reasons") or card.get("decision_reasons") or [])
    if "open_only_path_forbids_field_ops_GO" not in reasons:
        reasons.append("open_only_path_forbids_field_ops_GO")
    card["reasons"] = reasons
    metrics = card.get("metrics")
    if isinstance(metrics, dict):
        extra = metrics.setdefault("extra", {})
        if isinstance(extra, dict):
            extra["open_only_go_blocked"] = True
    return card


def run_decide_cards(
    pack: Path,
    *,
    skip: bool = False,
) -> dict[str, Any]:
    """Re-run decide field_ops + research_open; hard-block field_ops GO."""
    if skip:
        return {"skipped": True, "ok": True}

    results: dict[str, Any] = {"ok": True}
    for policy, out_name in (
        ("field_ops", "fire_decision_card_field_ops.json"),
        ("research_open", "fire_decision_card_research.json"),
    ):
        out = pack / out_name
        cmd = [
            sys.executable,
            "-m",
            "wildfire_front.cli",
            "decide",
            "--event-id",
            EVENT,
            "--open-pack",
            str(pack),
            "--policy",
            policy,
            "--output",
            str(out),
        ]
        try:
            env = dict(os.environ)
            env["PYTHONPATH"] = str(ROOT) + (
                os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
            )
            proc = subprocess.run(
                cmd,
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
                check=False,
            )
            card = _load_json(out)
            if card is None:
                if policy == "field_ops":
                    write_synthetic_hold(
                        pack,
                        reason="decide_card_missing_after_run_synthetic_hold",
                    )
                    results[policy] = {
                        "decision": "HOLD",
                        "synthetic": True,
                        "returncode": proc.returncode,
                        "ok": proc.returncode == 0,
                    }
                else:
                    results[policy] = {
                        "decision": "UNKNOWN",
                        "error": "card_missing",
                        "returncode": proc.returncode,
                        "ok": False,
                    }
                    results["ok"] = False
                continue

            decision_raw = str(card.get("decision") or "").upper()
            # Hard rule: capture GO before mutation, then coerce
            if policy == "field_ops" and decision_raw == "GO":
                card = coerce_field_ops_hold(card)
                _write_json(out, card)
                results[policy] = {
                    "decision": "HOLD",
                    "coerced_from_go": True,
                    "returncode": proc.returncode,
                    "ok": True,
                }
            else:
                ok_pol = proc.returncode == 0 and bool(decision_raw)
                results[policy] = {
                    "decision": decision_raw or "UNKNOWN",
                    "returncode": proc.returncode,
                    "stderr_tail": (proc.stderr or "")[-400:],
                    "ok": ok_pol,
                }
                if not ok_pol:
                    results["ok"] = False
        except subprocess.TimeoutExpired:
            results[policy] = {"error": "timeout", "ok": False}
            results["ok"] = False
            if policy == "field_ops":
                write_synthetic_hold(pack, reason="decide_timeout_synthetic_hold")
        except OSError as exc:
            results[policy] = {"error": str(exc), "ok": False}
            results["ok"] = False
            if policy == "field_ops":
                write_synthetic_hold(pack, reason=f"decide_oserror_synthetic_hold:{exc}")
    return results


def check_event_anchor() -> dict[str, Any]:
    """Load event anchor and refuse fake confirmed (report hard-fail)."""
    doc = _load_json(ANCHORS_PATH)
    if not doc:
        return {"ok": True, "status": "anchors_file_missing", "soft": True}
    anchors = doc.get("anchors") if isinstance(doc.get("anchors"), dict) else {}
    anchor = anchors.get(EVENT)
    if not isinstance(anchor, dict):
        return {"ok": True, "status": "anchor_stub_missing", "soft": True}
    try:
        assert_not_fake_confirmed(anchor)
    except ValueError as exc:
        return {
            "ok": False,
            "status": "fake_confirmed",
            "error": str(exc),
            "fire_id": EVENT,
        }
    return {
        "ok": True,
        "status": anchor.get("status"),
        "fire_id": EVENT,
    }


def enforce_open_only_field_ops(pack: Path, report_decide: dict[str, Any]) -> dict[str, Any]:
    """Ensure field_ops card is HOLD (coerce GO, synthesize if missing)."""
    out: dict[str, Any] = dict(report_decide) if report_decide else {}
    fo = _load_json(pack / "fire_decision_card_field_ops.json")
    if fo is None:
        write_synthetic_hold(pack, reason="missing_field_ops_card_open_only_hold")
        out["field_ops_synthetic"] = True
        out.setdefault("field_ops", {})["decision"] = "HOLD"
        out.setdefault("field_ops", {})["synthetic"] = True
        return out
    decision = str(fo.get("decision") or "").upper()
    if decision == "GO":
        fo = coerce_field_ops_hold(fo)
        _write_json(pack / "fire_decision_card_field_ops.json", fo)
        out["field_ops_coerced"] = True
        out.setdefault("field_ops", {})["decision"] = "HOLD"
        out.setdefault("field_ops", {})["coerced_from_go"] = True
    elif decision not in ("HOLD", "ABSTAIN"):
        write_synthetic_hold(pack, reason=f"invalid_decision_{decision or 'empty'}_synthetic_hold")
        out["field_ops_synthetic"] = True
        out.setdefault("field_ops", {})["decision"] = "HOLD"
    return out


def _derive_ok(report: dict[str, Any]) -> tuple[bool, list[str]]:
    """Critical steps must succeed (skipped counts as ok)."""
    errors: list[str] = []
    steps = report.get("steps") or {}

    for key in ("build_pack", "enrich_satellite"):
        step = steps.get(key) or {}
        if step.get("skipped"):
            continue
        if step.get("ok") is False:
            errors.append(f"{key}_failed")

    decide = steps.get("decide") or {}
    if not decide.get("skipped"):
        if decide.get("ok") is False:
            errors.append("decide_failed")
        fo = decide.get("field_ops") or {}
        if fo.get("ok") is False and not fo.get("synthetic") and not fo.get("coerced_from_go"):
            errors.append("field_ops_decide_failed")

    anchor = steps.get("anchor_guard") or {}
    if anchor.get("ok") is False:
        errors.append("fake_confirmed_anchor")

    fo_final = steps.get("field_ops_final") or {}
    if fo_final.get("decision") == "GO":
        errors.append("field_ops_still_go")

    return len(errors) == 0, errors


def run_day(
    *,
    pack: Path = PACK,
    skip_build: bool = False,
    skip_enrich: bool = False,
    skip_network: bool = False,
    skip_decide: bool = False,
    try_dnbr_flag: bool = False,
    dnbr_search_only: bool = True,
    write_forensic: bool = True,
) -> dict[str, Any]:
    pack = Path(pack)
    pack.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "la_mierla_open_day_run_v1",
        "event_id": EVENT,
        "started_at_utc": _utc(),
        "pack": str(pack).replace("\\", "/"),
        "steps": {},
    }

    if skip_network:
        skip_build = True
        skip_enrich = True

    report["steps"]["build_pack"] = _run_script(
        "scripts/build_la_mierla_open_pack.py", skip=skip_build
    )
    report["steps"]["enrich_satellite"] = _run_script(
        "scripts/enrich_la_mierla_satellite.py", skip=skip_enrich
    )

    timeline = update_timeline_from_pack(pack)
    report["steps"]["timeline_daily"] = {
        "n_days": timeline.get("n_days"),
        "path": "timeline_daily.json",
        "ok": True,
    }

    scrape = _load_json(pack / "scrape_latest.json")
    hist = merge_scrape_history(pack, scrape)
    report["steps"]["scrape_history"] = {
        "n_day_slots": len(hist.get("days") or {}),
        "ok": True,
    }

    cems = run_cems_watch(pack, try_fetch=not skip_network)
    report["steps"]["cems_watch"] = {
        "status": cems.get("status"),
        "emsr896_is_not_la_mierla": cems.get("emsr896_is_not_la_mierla"),
        "ok": True,
    }

    queue = update_dnbr_queue_from_stac(pack)
    report["steps"]["dnbr_queue"] = {
        "status": queue.get("status"),
        "detail_status": queue.get("detail_status"),
        "ok": True,
    }

    if try_dnbr_flag:
        dnbr_status = try_dnbr(pack, search_only=dnbr_search_only)
        report["steps"]["try_dnbr"] = {
            "status": dnbr_status.get("status"),
            "reasons": dnbr_status.get("reasons"),
            "ok": True,  # BLOCKED is a valid honest outcome
        }
    else:
        if not (pack / "dnbr_status.json").is_file():
            status = {
                "schema": "open_if_dnbr_status_v1",
                "activation": EVENT,
                "pack_dir": str(pack),
                "built_at_utc": _utc(),
                "status": "BLOCKED",
                "reasons": [
                    "day_runner_did_not_pass_--try-dnbr",
                    f"dnbr_queue={queue.get('status')}",
                    *(queue.get("reasons") or []),
                ],
                "product": "dnbr_stac_s2_l2a",
                "disclaimer": "Not official perimeter. Severity proxy only.",
            }
            if queue.get("detail_status") == "incomplete_pre_only":
                status["reasons"].insert(0, "incomplete_without_clear_post")
                status["honest_incomplete"] = True
            _write_json(pack / "dnbr_status.json", status)
            _update_scorecard_dnbr(pack, status, queue)
            compare_hull_vs_dnbr(pack, status)
            report["steps"]["dnbr_status"] = {
                "status": "BLOCKED",
                "seeded": True,
                "detail_status": queue.get("detail_status"),
                "ok": True,
            }
        else:
            compare_hull_vs_dnbr(pack, _load_json(pack / "dnbr_status.json"))
            report["steps"]["dnbr_status"] = {"existing": True, "ok": True}

    report["steps"]["anchor_guard"] = check_event_anchor()

    decide = run_decide_cards(pack, skip=skip_decide)
    decide = enforce_open_only_field_ops(pack, decide)
    report["steps"]["decide"] = decide

    fo = _load_json(pack / "fire_decision_card_field_ops.json") or {}
    report["steps"]["field_ops_final"] = {
        "decision": str(fo.get("decision") or "").upper(),
        "open_only_hard_rule": bool(fo.get("open_only_hard_rule")),
        "ok": str(fo.get("decision") or "").upper() in ("HOLD", "ABSTAIN"),
    }

    if write_forensic:
        fpath = write_forensic_brief(pack, timeline)
        report["steps"]["forensic_brief"] = {"path": str(fpath.name), "ok": True}

    week = export_week_package(pack, event_id=EVENT)
    report["steps"]["week_package"] = {
        "manifest_path": week.get("manifest_path"),
        "n_artifacts": len(week.get("artifacts") or []),
        "n_copied": len(week.get("copied") or []),
        "honesty_flags": week.get("honesty_flags"),
        "ok": True,
    }

    report["finished_at_utc"] = _utc()
    ok, errors = _derive_ok(report)
    report["ok"] = ok
    report["errors"] = errors
    _write_json(pack / "day_run_report.json", report)
    return report


def write_forensic_brief(pack: Path, timeline: dict[str, Any]) -> Path:
    series = timeline.get("series") or []
    lines = [
        f"# Forensic brief (open) — week 1 — {EVENT}",
        "",
        f"**Generated:** {_utc()}",
        "",
        "Open-sources only. **Not** official EGIF / **not** tactical ROS.",
        "",
        "## Thermal growth (VIIRS N20 daily series)",
        "",
        "| Date | n_hotspots | FRP sum | FRP max |",
        "|------|----------:|--------:|--------:|",
    ]
    for d in series:
        lines.append(
            f"| {d.get('date')} | {d.get('n_hotspots')} | {d.get('frp_sum')} | {d.get('frp_max')} |"
        )
    lines += [
        "",
        "## Civil / INFOCAM (provisional)",
        "",
        "- Detection ~2026-07-16 13:55; Nivel 2; ha est. ~26k→29k (press/INFOCAM X).",
        "- 34 mun. evacuated + 14 confined; PMA Tamajón.",
        "- CEMS: EMSR896 = Orés (Aragón), **not** La Mierla → WATCH.",
        "",
        "## WFD product",
        "",
        "- Track: `open_firms_only` · decide: **HOLD** (open monitoring).",
        "- Anchor: `pending_external` (no Vp/ha EGIF).",
        "- dNBR: pending clear post-fire S2 (see `dnbr_queue.json`).",
        "",
        "## Honesty",
        "",
        "- Hull FIRMS ≠ burned area.",
        "- No field_ops GO from open-only path.",
        "- No Google tile scraping.",
        "",
    ]
    path = pack / "forensic_week1_brief.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description="La Mierla open daily cadence runner")
    ap.add_argument("--pack", type=Path, default=PACK)
    ap.add_argument("--skip-build", action="store_true", help="Skip build_la_mierla_open_pack")
    ap.add_argument("--skip-enrich", action="store_true", help="Skip enrich_la_mierla_satellite")
    ap.add_argument(
        "--skip-network",
        action="store_true",
        help="Offline mode: skip build/enrich/CEMS fetch (use existing pack artifacts)",
    )
    ap.add_argument("--skip-decide", action="store_true")
    ap.add_argument(
        "--try-dnbr",
        action="store_true",
        help="Attempt STAC dNBR via build_open_if_dnbr (may stay BLOCKED without post)",
    )
    ap.add_argument(
        "--dnbr-full",
        action="store_true",
        help="With --try-dnbr, also read COGs (not search-only)",
    )
    ap.add_argument("--no-forensic", action="store_true")
    args = ap.parse_args()

    report = run_day(
        pack=args.pack,
        skip_build=bool(args.skip_build),
        skip_enrich=bool(args.skip_enrich),
        skip_network=bool(args.skip_network),
        skip_decide=bool(args.skip_decide),
        try_dnbr_flag=bool(args.try_dnbr),
        dnbr_search_only=not bool(args.dnbr_full),
        write_forensic=not bool(args.no_forensic),
    )
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
