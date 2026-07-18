"""Human-readable CLI reports that preserve full operational detail."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, TextIO

# Unicode box drawing — Windows Terminal / modern consoles handle these.
_LINE = "─" * 56
_OK = "✓"
_MISS = "·"
_WARN = "!"
_ERR = "✗"


def _out(text: str = "", *, file: TextIO | None = None) -> None:
    print(text, file=file or sys.stdout)


def _fmt(value: Any, *, na: str = "—") -> str:
    if value is None or value == "":
        return na
    if isinstance(value, float):
        if value != value:  # NaN
            return na
        if abs(value) >= 100:
            return f"{value:.2f}"
        if abs(value) >= 1:
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def _kv(label: str, value: Any, *, width: int = 14) -> str:
    return f"  {label:<{width}} {_fmt(value)}"


def header(title: str, subtitle: str | None = None, *, file: TextIO | None = None) -> None:
    _out(file=file)
    _out(f"  WildfireFrontDynamics · {title}", file=file)
    if subtitle:
        _out(f"  {subtitle}", file=file)
    _out(f"  {_LINE}", file=file)


def section(title: str, *, file: TextIO | None = None) -> None:
    _out(file=file)
    _out(f"  {title}", file=file)


def print_json(obj: Any, *, file: TextIO | None = None) -> None:
    print(json.dumps(obj, indent=2, default=str, ensure_ascii=False), file=file or sys.stdout)


def print_error(message: str, *, hint: str | None = None) -> None:
    _out(f"{_ERR} error: {message}", file=sys.stderr)
    if hint:
        _out(f"  hint: {hint}", file=sys.stderr)


def print_demo_report(output: Path, metrics: dict[str, Any], *, as_json: bool = False) -> None:
    payload = {
        "command": "demo",
        "output": str(output.resolve()),
        "metrics": metrics,
        "artifacts": _list_existing(
            output,
            [
                "report.html",
                "summary.json",
                "fronts.geojson",
                "local_speeds.csv",
                "arrival_time.csv",
                "observations_manifest.csv",
            ],
        ),
    }
    if as_json:
        print_json(payload)
        return
    header("demo", "synthetic end-to-end MVP (ground truth available)")
    _out(_kv("output", payload["output"]))
    section("Metrics")
    for k in sorted(metrics):
        _out(_kv(k, metrics[k], width=28))
    section("Artifacts")
    for name, path, exists in payload["artifacts"]:
        mark = _OK if exists else _MISS
        _out(f"  {mark} {name:<28} {path if exists else '(missing)'}")
    _out()
    _out(f"  Open: {output / 'report.html'}")
    _out()


def print_ingest_report(
    output: Path,
    metrics: dict[str, Any],
    *,
    as_json: bool = False,
    event_id: str = "",
) -> None:
    _ops = metrics.get("operational")
    ops: dict[str, Any] = _ops if isinstance(_ops, dict) else {}
    artifacts = _list_existing(
        output,
        [
            "ingest_manifest.csv",
            "summary.json",
            "report.html",
            "fronts.geojson",
            "local_speeds.csv",
            "arrival_time.csv",
            "operational_metrics.json",
            "front_dynamics.json",
            "operational_report.html",
            "main_front.geojson",
            "ros_timeline.csv",
            "brief_operativo.md",
        ],
    )
    payload: dict[str, Any] = {
        "command": "ingest-geotiff",
        "event_id": event_id,
        "output": str(output.resolve()),
        "metrics": metrics,
        "operational": ops or None,
        "artifacts": artifacts,
    }
    if as_json:
        print_json(payload)
        return
    header("ingest-geotiff", f"event={event_id or '—'}")
    _out(_kv("output", payload["output"]))
    _out(_kv("observations", metrics.get("num_observations")))
    _out(_kv("components", metrics.get("num_components")))
    if ops:
        section("Operational (front_dynamics)")
        _out(_kv("grade", f"{ops.get('quality_grade')} · {ops.get('quality_label_es') or ''}"))
        _out(_kv("ROS m/min", ops.get("speed_median_m_min")))
        _out(_kv("n observable", ops.get("speed_n_observable")))
        _out(_kv("area ha max", ops.get("area_ha_max")))
        _out(_kv("vs ref ratio", ops.get("speed_vs_ref_ratio")))
        _out(_kv("engine", ops.get("engine")))
        methods = ops.get("primary_methods_used")
        if methods:
            _out(_kv("methods", ", ".join(str(m) for m in methods)))
    section("Ingest / geometry metrics")
    for k, v in sorted(metrics.items()):
        if k == "operational":
            continue
        if isinstance(v, (dict, list)):
            _out(_kv(k, json.dumps(v, default=str)[:120]))
        else:
            _out(_kv(k, v, width=32))
    section("Artifacts")
    for name, path, exists in artifacts:
        mark = _OK if exists else _MISS
        _out(f"  {mark} {name:<28} {path if exists else ''}")
    if metrics.get("operator_export_error"):
        section("Warnings")
        _out(f"  {_WARN} operator_export_error: {metrics['operator_export_error']}")
    _out()


def _ops_detail_from_outbox(outbox: Path | str | None) -> dict[str, Any]:
    if not outbox:
        return {}
    path = Path(outbox) / "operational_metrics.json"
    if not path.is_file():
        path = Path(outbox)
        if path.name != "operational_metrics.json" or not path.is_file():
            # try outbox as directory already
            alt = Path(outbox)
            if alt.is_dir():
                path = alt / "operational_metrics.json"
            else:
                return {}
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def enrich_incident_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Attach sector/envelope/ops detail from outbox when present."""
    out = dict(summary)
    outbox = out.get("outbox")
    ops = _ops_detail_from_outbox(str(outbox) if outbox else None)
    if not ops:
        _state = out.get("state")
        state: dict[str, Any] = _state if isinstance(_state, dict) else {}
        art = state.get("artifacts") or out.get("artifacts") or {}
        if isinstance(art, dict) and art.get("operational_metrics"):
            ops = _ops_detail_from_outbox(Path(art["operational_metrics"]).parent)

    if ops:
        sector = ops.get("sector_ros") or {}
        env = ops.get("short_horizon_envelope") or {}
        out["detail"] = {
            "quality_grade": ops.get("quality_grade"),
            "quality_label_es": ops.get("quality_label_es"),
            "primary_ros_m_min": ops.get("speed_median_m_min") or ops.get("primary_ros_m_min"),
            "speed_p25_m_min": ops.get("speed_p25_m_min"),
            "speed_p75_m_min": ops.get("speed_p75_m_min"),
            "speed_n_observable": ops.get("speed_n_observable"),
            "area_ha_max": ops.get("area_ha_max"),
            "speed_vs_ref_ratio": ops.get("speed_vs_ref_ratio"),
            "speed_vs_ref_grade": ops.get("speed_vs_ref_grade"),
            "reference_vp_m_min": ops.get("reference_vp_m_min"),
            "engine": ops.get("engine"),
            "primary_methods_used": ops.get("primary_methods_used"),
            "mean_coreg_shift_m": ops.get("mean_coreg_shift_m"),
            "speed_status": ops.get("speed_status"),
            "sector_ros": sector,
            "short_horizon_envelope": env,
            "cn_hybrid_ros": ops.get("cn_hybrid_ros"),
            "not_a_product": ops.get("not_a_product"),
            "disclaimers": [
                "observed_front_only",
                "not_official_perimeter",
                "not_validated_tactical_dispatch",
                "envelope_is_extrapolated_guidance",
            ],
        }
        # Promote key fields if missing at top level
        out.setdefault("quality_grade", ops.get("quality_grade"))
        out.setdefault("primary_ros_m_min", ops.get("speed_median_m_min"))
        out.setdefault("quality_label_es", ops.get("quality_label_es"))
    return out


def print_incident_report(
    summary: dict[str, Any],
    *,
    as_json: bool = False,
    verbose: bool = False,
    title: str = "incident",
) -> None:
    data = enrich_incident_summary(summary)
    if as_json:
        print_json(data)
        return

    status = str(data.get("status") or "unknown")
    event = data.get("event_id") or (data.get("state") or {}).get("event_id") or "—"
    product = data.get("product") or "incident_runtime_v1"
    header(f"{title} · {product}", f"event={event}  status={status}")

    _out(_kv("status", status))
    _out(_kv("event_id", event))
    _out(_kv("frames staged", data.get("n_staged")))
    if data.get("new_frames") is not None:
        _out(_kv("new frames", data.get("new_frames")))
    if data.get("latency_s") is not None:
        _out(_kv("latency_s", data.get("latency_s")))
    if data.get("outbox"):
        _out(_kv("outbox", data.get("outbox")))
    if data.get("error"):
        _out(_kv("error", data.get("error")))

    _detail = data.get("detail")
    detail: dict[str, Any] = _detail if isinstance(_detail, dict) else {}
    grade = data.get("quality_grade") or detail.get("quality_grade")
    label = data.get("quality_label_es") or detail.get("quality_label_es")
    ros = data.get("primary_ros_m_min")
    if ros is None:
        ros = detail.get("primary_ros_m_min")

    # Decision Card (paid-value unit) — prefer summary, else outbox file
    decision = data.get("decision")
    conf_pred = data.get("confidence_pred")
    conf_label = data.get("confidence_pred_label")
    if decision is None and data.get("outbox"):
        fdc_path = Path(str(data["outbox"])) / "fire_decision_card.json"
        if fdc_path.is_file():
            try:
                fdc = json.loads(fdc_path.read_text(encoding="utf-8"))
                decision = fdc.get("decision")
                conf_pred = fdc.get("confidence_pred")
                conf_label = fdc.get("confidence_pred_label")
            except (OSError, json.JSONDecodeError, TypeError):
                pass
    if decision is not None:
        section("Decision Card")
        conf_s = f"{float(conf_pred):.3f}" if isinstance(conf_pred, (int, float)) else "—"
        label_s = f" · {conf_label}" if conf_label else ""
        _out(_kv("decision", f"{decision}  (conf={conf_s}{label_s})"))
        _out(_kv("artifact", "fire_decision_card.json"))

    section("Front dynamics")
    _out(_kv("grade", f"{_fmt(grade)} · {_fmt(label)}" if grade or label else "—"))
    _out(_kv("ROS m/min", ros))
    if detail:
        _out(
            _kv(
                "P25 / P75",
                f"{_fmt(detail.get('speed_p25_m_min'))} / {_fmt(detail.get('speed_p75_m_min'))}",
            )
        )
        _out(_kv("n observable", detail.get("speed_n_observable")))
        _out(_kv("area ha max", detail.get("area_ha_max")))
        _out(_kv("vs ref ratio", detail.get("speed_vs_ref_ratio")))
        _out(_kv("vs ref grade", detail.get("speed_vs_ref_grade")))
        _out(_kv("ref Vp", detail.get("reference_vp_m_min")))
        _out(_kv("engine", detail.get("engine")))
        methods = detail.get("primary_methods_used")
        if methods:
            _out(_kv("methods", ", ".join(str(m) for m in methods)))
        _out(_kv("coreg shift m", detail.get("mean_coreg_shift_m")))
        _out(_kv("speed status", detail.get("speed_status")))

    sector = (detail.get("sector_ros") or {}) if detail else {}
    secs = sector.get("sectors") or {}
    if secs or sector:
        section("Sector ROS (guidance)")
        if secs:
            _out(_kv("head", f"{_fmt(secs.get('head_m_min'))} m/min"))
            _out(_kv("flank", f"{_fmt(secs.get('flank_m_min'))} m/min"))
            _out(_kv("rear", f"{_fmt(secs.get('rear_m_min'))} m/min"))
            if secs.get("head_bearing_deg") is not None:
                _out(_kv("head bearing", f"{secs.get('head_bearing_deg')}°"))
            if secs.get("head_sector_deg"):
                _out(_kv("head sector", secs.get("head_sector_deg")))
        else:
            _out(_kv("status", sector.get("status")))
            _out(_kv("reason", sector.get("reason")))
        if sector.get("label_es"):
            _out(f"  note           {sector.get('label_es')}")
        unc = sector.get("uncertainty_m_min") or {}
        if unc:
            _out(_kv("unc. half IQR", unc.get("half_iqr")))

    env = (detail.get("short_horizon_envelope") or {}) if detail else {}
    if env:
        section("Envelope 15/30/60 (extrapolated — NOT dispatch)")
        _out(_kv("status", env.get("status")))
        if env.get("label_es"):
            _out(f"  {_fmt(env.get('label_es'))}")
        for e in env.get("envelopes") or []:
            h = e.get("horizon_min")
            _out(
                f"  {h:>3} min   head {_fmt(e.get('head_radius_m'))} m · "
                f"flank {_fmt(e.get('flank_radius_m'))} m · "
                f"rear {_fmt(e.get('rear_radius_m'))} m · "
                f"iso {_fmt(e.get('radius_m'))} m"
            )
        if env.get("reason"):
            _out(_kv("reason", env.get("reason")))

    cn = (detail.get("cn_hybrid_ros") or {}) if detail else {}
    if cn and verbose:
        section("CN hybrid ROS (optional physics prior)")
        for k, v in cn.items():
            if k in ("polar_sample", "polar_n"):
                continue
            _out(_kv(str(k), v, width=20))

    _state = data.get("state")
    state: dict[str, Any] = _state if isinstance(_state, dict) else {}
    artifacts = data.get("artifacts") or state.get("artifacts") or {}
    if isinstance(artifacts, dict) and artifacts:
        section("Artifacts")
        outbox = Path(str(data.get("outbox") or state.get("artifacts", {}).get("outbox") or "."))
        names = [
            ("fire_decision_card.json", outbox / "fire_decision_card.json"),
            ("fire_decision_card.md", outbox / "fire_decision_card.md"),
            ("incident_state.json", outbox / "incident_state.json"),
            ("emergency_briefing.md", outbox / "emergency_briefing.md"),
            ("emergency_envelope.json", outbox / "emergency_envelope.json"),
            ("emergency_envelope_guidance.geojson", outbox / "emergency_envelope_guidance.geojson"),
            ("main_front.geojson", outbox / "main_front.geojson"),
            ("operational_metrics.json", outbox / "operational_metrics.json"),
            ("operational_report.html", outbox / "operational_report.html"),
            ("front_dynamics.json", outbox / "front_dynamics.json"),
            ("ros_timeline.csv", outbox / "ros_timeline.csv"),
            ("brief_operativo.md", outbox / "brief_operativo.md"),
            ("ingest_manifest.csv", outbox / "ingest_manifest.csv"),
            ("summary.json", outbox / "summary.json"),
            ("report.html", outbox / "report.html"),
        ]
        for name, path in names:
            exists = path.is_file()
            mark = _OK if exists else _MISS
            _out(f"  {mark} {name}")

    frames = state.get("frames") if state else None
    if frames and (verbose or len(frames) <= 12):
        section(f"Frames ({len(frames)})")
        for f in frames:
            stem = f.get("stem") or Path(str(f.get("path") or "")).name
            st = f.get("status")
            reason = f.get("reason") or ""
            sha = (f.get("sha256") or "")[:12]
            line = f"  · {stem:<40} {st:<10} sha={sha}"
            if reason:
                line += f"  ({reason})"
            _out(line)
    elif frames:
        section(f"Frames ({len(frames)})")
        _out("  (use --verbose to list every frame)")

    disclaimers = (detail.get("disclaimers") if detail else None) or state.get("disclaimers")
    if disclaimers:
        section("Disclaimers (always on)")
        for d in disclaimers:
            _out(f"  · {d}")

    if status == "waiting_for_frames":
        section("Next steps")
        _out("  1. Drop projected LWIR GeoTIFFs into --inbox")
        _out("  2. Filename must include timestamp (e.g. 2024-08-02_16-09-52_LWIR.tif)")
        _out("  3. Prefer --masks or rely on MAD segmentation")
    elif status == "updated":
        section("Next steps")
        outbox_raw = data.get("outbox")
        if outbox_raw:
            outbox_path = Path(str(outbox_raw))
            _out(f"  · Decision  {outbox_path / 'fire_decision_card.md'}")
            _out(f"  · Brief     {outbox_path / 'emergency_briefing.md'}")
            _out(f"  · Open      {outbox_path / 'operational_report.html'}")
            _out(f"  · GIS       {outbox_path / 'main_front.geojson'}")
    elif status == "error":
        section("Next steps")
        _out("  · Inspect outbox/ingest_manifest.csv for reject reasons")
        _out("  · Check CRS is projected metric + timestamps in filenames")
        _out("  · Re-run with --force after fixing inputs")
    _out()


def print_watch_line(summary: dict[str, Any], *, verbose: bool = False) -> None:
    """Compact status line for watch mode (stderr)."""
    data = enrich_incident_summary(summary)
    status = data.get("status")
    grade = data.get("quality_grade") or (data.get("detail") or {}).get("quality_grade")
    ros = data.get("primary_ros_m_min")
    if ros is None:
        ros = (data.get("detail") or {}).get("primary_ros_m_min")
    n = data.get("n_staged")
    new = data.get("new_frames")
    lat = data.get("latency_s")
    err = data.get("error")
    parts = [
        f"status={status}",
        f"frames={n}",
        f"new={new}",
        f"grade={_fmt(grade)}",
        f"ros={_fmt(ros)}",
        f"lat_s={_fmt(lat)}",
    ]
    if err:
        parts.append(f"error={err}")
    print(f"[incident] {'  '.join(parts)}", file=sys.stderr)
    if verbose and status == "updated":
        detail = data.get("detail") or {}
        sector = (detail.get("sector_ros") or {}).get("sectors") or {}
        if sector:
            print(
                f"           head={sector.get('head_m_min')}  "
                f"flank={sector.get('flank_m_min')}  rear={sector.get('rear_m_min')}",
                file=sys.stderr,
            )


def print_doctor_report(report: dict[str, Any], *, as_json: bool = False) -> None:
    if as_json:
        print_json(report)
        return
    header("incident doctor", "pre-flight checks for field use")
    _out(_kv("inbox", report.get("inbox")))
    _out(_kv("work_dir", report.get("work_dir")))
    _out(_kv("masks", report.get("masks_dir") or "(none — MAD)"))
    _out(_kv("ok", report.get("ok")))
    section(
        f"Checks ({report.get('n_pass', 0)} pass · {report.get('n_warn', 0)} warn · {report.get('n_fail', 0)} fail)"
    )
    for c in report.get("checks") or []:
        level = c.get("level", "info")
        mark = {_OK: _OK, "pass": _OK, "warn": _WARN, "fail": _ERR, "info": _MISS}.get(level, _MISS)
        if level == "pass":
            mark = _OK
        elif level == "warn":
            mark = _WARN
        elif level == "fail":
            mark = _ERR
        _out(f"  {mark} [{level:<4}] {c.get('id')}: {c.get('message')}")
        if c.get("detail"):
            _out(f"           {c.get('detail')}")
    files = report.get("inbox_files") or []
    if files:
        section(f"Inbox sample ({len(files)} GeoTIFF)")
        for f in files[:15]:
            ts = f.get("timestamp") or "NO_TIMESTAMP"
            mark = _OK if f.get("timestamp") else _WARN
            _out(f"  {mark} {f.get('name')}  ts={ts}")
        if len(files) > 15:
            _out(f"  … +{len(files) - 15} more")
    section("Verdict")
    if report.get("ok"):
        _out(f"  {_OK} Ready to run: wildfire-front incident watch --inbox … --work-dir …")
    else:
        _out(f"  {_ERR} Fix FAIL items before relying on field products")
    _out()


def print_status_report(
    report: dict[str, Any], *, as_json: bool = False, verbose: bool = False
) -> None:
    if as_json:
        print_json(report)
        return
    # Reuse incident report shape
    print_incident_report(report, as_json=False, verbose=verbose, title="incident status")


def _list_existing(root: Path, names: list[str]) -> list[tuple[str, str, bool]]:
    out: list[tuple[str, str, bool]] = []
    for name in names:
        p = root / name
        out.append((name, str(p.resolve()) if p.is_file() else str(p), p.is_file()))
    return out
