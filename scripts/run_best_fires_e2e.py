#!/usr/bin/env python3
"""Agent B: best-complete-incident E2E (download/use, no retrain, no invented ROS).

python scripts/run_best_fires_e2e.py
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from check_release_flags import evaluate as evaluate_flags  # noqa: E402

from wildfire_front.open_if.external_ros import (  # noqa: E402
    inventory_caldor_kml,
    inventory_cfsds_pack,
    inventory_ndws_kaggle_proxy,
    inventory_nirops_mendeley,
    utc_now,
)
from wildfire_front.open_if.latam_au import (  # noqa: E402
    PRODUCT_E2E_DEFAULT_IDS,
    default_source_pack_dir,
    source_pack_ready,
)

OUT = ROOT / "outputs" / "open_if" / "best_fires_e2e"


def _run(cmd: list[str]) -> dict:
    print("+", " ".join(cmd), flush=True)
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return {"cmd": cmd, "exit_code": int(proc.returncode)}


def _rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _latam_status() -> dict:
    rows = []
    all_ready = True
    for eid in PRODUCT_E2E_DEFAULT_IDS:
        src = default_source_pack_dir(ROOT, eid)
        ready, reason = source_pack_ready(src)
        all_ready = all_ready and ready
        meta = {}
        meta_p = src / "meta.json"
        if meta_p.is_file():
            try:
                meta = json.loads(meta_p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                meta = {}
        n_tif = len(list((src / "labels").glob("*.tif"))) if (src / "labels").is_dir() else 0
        n_eo = len(list((src / "eo").glob("*.tif"))) if (src / "eo").is_dir() else 0
        rows.append(
            {
                "event_id": eid,
                "ready": ready,
                "reason": reason,
                "n_label_tif": n_tif,
                "n_eo_tif": n_eo,
                "n_geotiff_meta": len(meta.get("geotiffs") or []),
                "source_pack": _rel(src),
            }
        )
    return {"ok": all_ready, "packs": rows}


def _rails_from_stamp() -> dict:
    stamp_path = ROOT / "docs" / "ML_PRODUCT_GO_STATUS.json"
    stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    rails = stamp.get("rails") or {}
    return {
        "stamp_path": "docs/ML_PRODUCT_GO_STATUS.json",
        "ml_product_go": stamp.get("ml_product_go"),
        "field_ops_allow_ml_live_in_fusion": stamp.get("field_ops_allow_ml_live_in_fusion"),
        "field_ops_fusion": rails.get("field_ops_fusion"),
        "GO_Q": stamp.get("GO_Q"),
        "GO_MES": stamp.get("GO_MES"),
        "GO_MES_plus": stamp.get("GO_MES_plus"),
        "tobarra_keep_reopen": rails.get("tobarra_keep_reopen"),
        "product_id": stamp.get("product_id"),
        "freeze_ml_and_request_data": rails.get("tobarra_keep_reopen") is False,
        "brief_said_fusion_off": True,
        "ssot_fusion": rails.get("field_ops_fusion"),
        "fusion_not_flipped": True,
        "hellin_not_promoted": True,
        "not_tactical_dispatch": True,
        "not_invent_vp_ha_iou_ros": True,
    }


def _write_report_md(report: dict, dest: Path) -> None:
    flags = report.get("check_release_flags") or {}
    latam = report.get("latam_au") or {}
    pt = report.get("pt_firesprd") or {}
    gofer = report.get("gofer") or {}
    caldor = report.get("firebench_caldor") or {}
    tobarra = report.get("tobarra") or {}
    ndws = report.get("ndws_kaggle_proxy") or {}
    cfsds = report.get("cfsds") or {}
    nirops = report.get("nirops") or {}
    rails = report.get("rails") or {}
    cmds = report.get("commands") or []
    lines = [
        "# Best complete-incident fires — Agent B E2E",
        "",
        f"_as_of_utc: {report.get('as_of_utc')}_",
        "",
        "Product is decision support, not tactical dispatch. "
        "CEMS/EFFIS/PT-FireSprd/GOFER are proxy / open research, not official ES cadastre.",
        "",
        "## Rails snapshot (measured, not flipped)",
        "",
        f"- check_release_flags: **{flags.get('status')}** exit={flags.get('exit_code')}",
        f"- GO_Q: `{rails.get('GO_Q')}` (must stay partial)",
        f"- field_ops_fusion SSOT: `{rails.get('field_ops_fusion')}` "
        f"(brief said OFF; stamp not flipped)",
        f"- tobarra_keep_reopen: `{rails.get('tobarra_keep_reopen')}`",
        f"- GO_MES+: `{rails.get('GO_MES_plus')}`",
        f"- product_id: `{rails.get('product_id')}` (not retrained)",
        "- Hellín: not promoted",
        "",
        "## Commands",
        "",
    ]
    for c in cmds:
        lines.append(f"- exit `{c.get('exit_code')}` · `{' '.join(c.get('cmd') or [])}`")
    latam_e2e = latam.get("product_e2e") or {}
    lines += [
        "",
        "## LATAM/AU packs already on disk (used)",
        "",
        f"- packs_ready: **{latam.get('packs_ready')}**",
        f"- product_e2e ok: **{latam_e2e.get('ok')}** n_ok={latam_e2e.get('n_ok')}/{latam_e2e.get('n_packs')}",
    ]
    for p in latam.get("packs") or []:
        lines.append(
            f"- `{p.get('event_id')}` ready={p.get('ready')} "
            f"label_tif={p.get('n_label_tif')} eo_tif={p.get('n_eo_tif')}"
        )
    for p in latam_e2e.get("packs") or []:
        om = p.get("open_metrics") or {}
        lines.append(
            f"- decide `{p.get('event_id')}` decision={p.get('decision')} "
            f"ok={p.get('ok')} max_area_ha={om.get('max_area_ha')} "
            f"n_timeline={om.get('n_timeline_steps')} wall_ms={p.get('wall_ms')}"
        )
    chosen = pt.get("chosen") or {}
    mat = pt.get("materialize") or {}
    ing = pt.get("geotiff_ingest") or {}
    dec = pt.get("decide") or {}
    lines += [
        "",
        "## PT-FireSprd (downloaded + used)",
        "",
        f"- zip_md5_ok: **{pt.get('zip_md5_ok')}** bytes={pt.get('zip_bytes')}",
        f"- sha256: `{pt.get('zip_sha256')}`",
        f"- L1 shapefiles: {pt.get('n_shapefiles')} · R1-capable fires: {pt.get('n_fires_r1')}",
        f"- ingest fire: `{chosen.get('fire_id')}` dated_scenes_source={chosen.get('n_dated_scenes')}",
        f"- rasterized n_scenes={mat.get('n_scenes')} aligned={mat.get('aligned')} crs={mat.get('crs')}",
        f"- geotiff_ingest accepted={ing.get('n_accepted')} observations={ing.get('n_observations')} ok={ing.get('ok')}",
        f"- decide decision={dec.get('decision')} latency_ms={dec.get('latency_ms')}",
        "- TZ: source date_hour unspecified; not invented as verified UTC",
        "- Author L2/L3 ros_* fields: inventoried as dataset attributes only — **not product ROS**",
        "",
        "## GOFER (downloaded + inventoried)",
        "",
        f"- zip_md5_ok: **{gofer.get('zip_md5_ok')}** bytes={gofer.get('zip_bytes')}",
        f"- sha256: `{gofer.get('zip_sha256')}`",
        f"- catalog fires: {gofer.get('n_catalog_fires')}",
        f"- hourly fireProg: ok={gofer.get('hourly_ok')} n_records={gofer.get('n_hourly_records')} "
        f"n_fires_r1_hourly={gofer.get('n_fires_r1_hourly')}",
        f"- GeoTIFF contract: **skipped** — {gofer.get('skip_reason')}",
        "",
        "## CFSDS (OSF catalogs downloaded + used as row counts)",
        "",
        f"- status: **{cfsds.get('status')}** files={cfsds.get('n_downloaded_files')} "
        f"bytes={cfsds.get('downloaded_bytes')}",
        f"- OSF DOI: `{cfsds.get('osf_doi')}` paper: `{cfsds.get('paper_doi')}`",
        f"- 2023 daily groups: rows={cfsds.get('groups_2023_n_rows')} "
        f"fires={cfsds.get('groups_2023_n_fires')} "
        f"fires_ge3_days={cfsds.get('groups_2023_n_fires_ge3_days')}",
        f"- GeoTIFF contract: **skipped** — {cfsds.get('skip_reason')}",
        f"- DOY rasters listed not downloaded: {cfsds.get('n_raster_years_listed_not_downloaded')}",
        "- Author sprdistm/firearea/pctgrowth: counted as dataset attributes only — **not product ROS**",
        "",
        "## NIROPS Mendeley 95rj5d379g",
        "",
        f"- status: **{nirops.get('status')}**",
        f"- reason: {nirops.get('reason')}",
        "",
        "## FireBench Caldor 2021 (already on disk; used as KML inventory)",
        "",
        f"- n_kml={caldor.get('n_kml')} n_dated={caldor.get('n_dated')} "
        f"r1_vector={caldor.get('r1_ge3_dated_kml')} native_geotiff={caldor.get('native_geotiff')}",
        "",
        "## Tobarra on disk (inventory only; KEEP not reopened)",
        "",
        f"- records_written: **{tobarra.get('n_records')}** exit={tobarra.get('exit_code')}",
        f"- source: `{tobarra.get('source')}`",
        f"- output: `{tobarra.get('output')}`",
        "- no retrain, no KEEP reopen, no raw_dropbox in git",
        "",
        "## WildfireSpreadTS / NDWS proxy (on disk; inventory only)",
        "",
        f"- full_zip_staged: **{ndws.get('full_zip_staged')}** "
        f"({ndws.get('reason_full_zip_not_staged')})",
        f"- documentation_pdf_bytes: {ndws.get('documentation_pdf_bytes')}",
        f"- proxy n_files={((ndws.get('proxy') or {}).get('n_files'))} "
        f"bytes={((ndws.get('proxy') or {}).get('bytes'))}",
        "- used_as: inventory_only_no_retrain (LATAM/AU + PT-FireSprd provided product smoke)",
        "",
        "## Not run / not claimed",
        "",
    ]
    for item in report.get("not_run") or []:
        lines.append(f"- {item}")
    lines += [
        "",
        "## Non-claims",
        "",
    ]
    for item in report.get("not_claims") or []:
        lines.append(f"- {item}")
    lines.append("")
    dest.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--skip-latam-e2e", action="store_true")
    args = ap.parse_args(argv)

    OUT.mkdir(parents=True, exist_ok=True)
    commands: list[dict] = []

    flags_path = OUT / "check_release_flags.json"
    commands.append(
        _run(
            [
                sys.executable,
                "scripts/check_release_flags.py",
                "--write",
                str(flags_path),
            ]
        )
    )
    flags = evaluate_flags()
    if flags.get("exit_code") != 0:
        print("check_release_flags FAIL", file=sys.stderr)
        return int(flags.get("exit_code") or 1)

    if not args.skip_download:
        commands.append(_run([sys.executable, "scripts/download_open_ros_packs.py"]))
    commands.append(_run([sys.executable, "scripts/inventory_open_ros_packs.py"]))

    latam = _latam_status()
    if not latam["ok"]:
        commands.append(_run([sys.executable, "scripts/materialize_latam_au_emsr_packs.py"]))
        latam = _latam_status()
    latam_report_path = ROOT / "outputs" / "open_if" / "latam_au_e2e" / "product_e2e_report.json"
    if not args.skip_latam_e2e:
        commands.append(_run([sys.executable, "scripts/run_latam_au_product_e2e.py"]))
    latam_e2e = None
    if latam_report_path.is_file():
        try:
            latam_e2e = json.loads(latam_report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            latam_e2e = {"ok": False, "error": "unreadable_latam_e2e_report"}
    latam["product_e2e"] = latam_e2e
    latam["packs_ready"] = latam["ok"]
    latam["report_path"] = _rel(latam_report_path) if latam_report_path.is_file() else None

    commands.append(_run([sys.executable, "scripts/ingest_pt_firesprd.py"]))
    pt_ingest_path = OUT / "pt_firesprd" / "ingest_report.json"
    pt_ingest = {}
    if pt_ingest_path.is_file():
        pt_ingest = json.loads(pt_ingest_path.read_text(encoding="utf-8"))
    pt_inv_path = ROOT / "data" / "external" / "pt_firesprd" / "inventory.json"
    pt_inv = json.loads(pt_inv_path.read_text(encoding="utf-8")) if pt_inv_path.is_file() else {}
    gofer_inv_path = ROOT / "data" / "external" / "gofer" / "inventory.json"
    gofer_inv = (
        json.loads(gofer_inv_path.read_text(encoding="utf-8")) if gofer_inv_path.is_file() else {}
    )

    caldor = inventory_caldor_kml(
        ROOT / "data" / "external" / "firebench" / "caldor_2021" / "v2026.1" / "kml"
    )
    ndws = inventory_ndws_kaggle_proxy(ROOT)
    cfsds = inventory_cfsds_pack(ROOT)
    nirops = inventory_nirops_mendeley()

    tobarra_src = ROOT / "data" / "real_if" / "pablo_geacam_20260730_tobarra"
    tobarra_out = OUT / "tobarra_pablo_inventory.csv"
    tobarra_cmd = _run(
        [
            sys.executable,
            "scripts/inventory_real_if_material.py",
            "--source",
            str(tobarra_src),
            "--output",
            str(tobarra_out),
        ]
    )
    commands.append(tobarra_cmd)
    tobarra_n = 0
    if tobarra_out.is_file():
        tobarra_n = max(0, len(tobarra_out.read_text(encoding="utf-8").splitlines()) - 1)

    hourly = gofer_inv.get("hourly") or {}
    zip_pt = pt_inv.get("zip") or {}
    zip_go = gofer_inv.get("zip") or {}

    report = {
        "schema": "wfd_best_fires_e2e_v1",
        "as_of_utc": utc_now(),
        "agent": "B_platform_data_honesty",
        "ok": bool(
            flags.get("status") == "PASS"
            and latam.get("packs_ready")
            and (latam_e2e or {}).get("ok")
            and pt_ingest.get("ok")
        ),
        "rails": _rails_from_stamp(),
        "check_release_flags": {
            "status": flags.get("status"),
            "exit_code": flags.get("exit_code"),
            "n_pass": flags.get("n_pass"),
            "n_fail": flags.get("n_fail"),
            "report": _rel(flags_path),
        },
        "commands": commands,
        "latam_au": latam,
        "pt_firesprd": {
            "zip_md5_ok": pt_inv.get("zip_md5_ok"),
            "zip_bytes": zip_pt.get("bytes"),
            "zip_sha256": zip_pt.get("sha256"),
            "license_id": pt_inv.get("license_id"),
            "url": pt_inv.get("url"),
            "n_shapefiles": (pt_inv.get("l1") or {}).get("n_shapefiles"),
            "n_fires_r1": (pt_inv.get("l1") or {}).get("n_fires_r1"),
            **pt_ingest,
            "inventory": "data/external/pt_firesprd/inventory.json",
        },
        "gofer": {
            "zip_md5_ok": gofer_inv.get("zip_md5_ok"),
            "zip_bytes": zip_go.get("bytes"),
            "zip_sha256": zip_go.get("sha256"),
            "license_id": gofer_inv.get("license_id"),
            "url": gofer_inv.get("url"),
            "n_catalog_fires": len(gofer_inv.get("fire_catalog") or []),
            "hourly_ok": hourly.get("ok"),
            "n_hourly_records": hourly.get("n_records"),
            "n_fires_r1_hourly": hourly.get("n_fires_r1_ge3"),
            "skip_reason": hourly.get("reason_no_geotiff"),
            "inventory": "data/external/gofer/inventory.json",
            "used_as": "catalog_plus_hourly_count",
        },
        "firebench_caldor": caldor,
        "tobarra": {
            "source": "data/real_if/pablo_geacam_20260730_tobarra",
            "output": _rel(tobarra_out),
            "n_records": tobarra_n,
            "exit_code": tobarra_cmd.get("exit_code"),
            "keep_reopened": False,
            "retrained": False,
            "used_as": "inventory_only",
        },
        "on_disk_used": [
            "data/open_if/latam_au/au/AU_EMSR500_PERTH",
            "data/open_if/latam_au/cl/CL_EMSR647_NACIMIENTO",
            "data/external/firebench/caldor_2021",
            "data/external/wildfirespreadts/ndws_kaggle_proxy",
            "data/real_if/pablo_geacam_20260730_tobarra (inventory only; no KEEP reopen)",
        ],
        "cfsds": cfsds,
        "nirops": nirops,
        "cfsds_nirops": {
            "cfsds": cfsds.get("status"),
            "nirops": nirops.get("status"),
            "reason_nirops": nirops.get("reason"),
        },
        "ndws_kaggle_proxy": ndws,
        "not_run": [
            "clm_ensemble_v34 retrain — FREEZE intact",
            "Tobarra KEEP reopen",
            "Hellín promote pending_external → confirmed",
            "PR #10 / secret bases",
            "CFSDS yearly fire-DOY rasters (listed on OSF; not downloaded this pass)",
            "NIROPS Mendeley 95rj5d379g download (no unauthenticated file list)",
            "WildfireSpreadTS full 48 GB zip",
        ],
        "not_claims": [
            "not GO_Q complete",
            "not FREEZE lift",
            "not tactical dispatch",
            "not official ES cadastre / O2",
            "not invented Vp/ha/IoU/ROS",
            "not product ROS from PT-FireSprd L2/L3, GOFER farea, or CFSDS sprdistm",
            "not Hellín confirmed",
        ],
    }

    json_path = OUT / "product_e2e_report.json"
    md_path = OUT / "REPORT.md"
    json_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    _write_report_md(report, md_path)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    print(json.dumps({"ok": report["ok"], "commands": commands}, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
