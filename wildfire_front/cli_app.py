"""CLI surface for product SPA (Leaflet map + ops dashboard)."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .cli_report import print_error, print_json
from .product.app_spa import (
    DEFAULT_OUTPUT,
    DEFAULT_TITLE,
    build_product_app_payload,
    write_product_app,
)
from .product.fire_catalog import scan_fire_catalog
from .product.policy import field_ops_ml_live_fusion_rail


def app_rails() -> dict[str, Any]:
    """Catalog rails — same fusion source as Live Ops ``honesty_rails`` / ``--list-fires``."""
    return {
        "field_ops_ml_live_fusion": field_ops_ml_live_fusion_rail(),
        "go_q_invent_forbidden": True,
        "go_q_met": False,
        "not_tactical_dispatch": True,
    }


def register_app_commands(commands: Any, *, add_global_flags) -> None:
    """Register ``app`` top-level command on the root parser."""
    a = commands.add_parser(
        "app",
        help="Product SPA — consola industrial C2 (mapa + Estado/Decidir/Acta + dual-mode)",
        description=(
            "Build industrial ops console (Stitch WFD Industrial C2) for third-party demos.\n"
            "  · Dual-mode: Fácil (default, CLI oculta) | Pro (muestra python -m …)\n"
            "  · Primary acts always visible: Estado · Decidir · Acta\n"
            "  · Map-first + Decision Card + product_actions inventory\n"
            "  · Tabs: Overview / Decisión / Acciones / Nuevo / Términos / Lista\n"
            "  · All CTAs copy with toast feedback; fire picker + rebuild bound to work-dir\n"
            "Honesty: NOT tactical dispatch; field_ops ML fusion ON (human 2026-08-13); no GO_Q invent."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front app\n"
            "  wildfire-front app --list-fires\n"
            "  wildfire-front app --fire _sla_measure --open\n"
            "  wildfire-front app --work-dir outputs/incidents/_sla_measure --open\n"
            "  wildfire-front app --ui-mode advanced --open\n"
            "  wildfire-front app --serve --fire _sla_measure\n"
            "  wildfire-front app --demo-day\n"
            "  wildfire-front app --all-fires --open\n"
            "  wildfire-front app --pack-fires --pack-cap 4 --open\n"
            "  wildfire-front app --bridge-decide http://127.0.0.1:8765 --ui-mode advanced --open\n"
            "  wildfire-front spa --open\n"
            "  wildfire-front console --fire _sla_measure --open\n"
            "  wildfire-front app --role field --json\n"
            "  wildfire-front app --lat 40.9 --lon -3.1 --fixture-csv tests/fixtures/firms_sample_hotspots.csv\n"
        ),
    )
    a.add_argument(
        "--list-fires",
        action="store_true",
        help="List discovered fires (outputs/incidents + known packs) and exit",
    )
    a.add_argument(
        "--fire",
        default=None,
        metavar="ID",
        help="Select fire by catalog id (from --list-fires) instead of --work-dir",
    )
    a.add_argument(
        "--no-scan",
        action="store_true",
        help="Skip fire catalog scan (smaller payload; no picker list)",
    )
    a.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Incident work-dir (outbox GeoJSON + Decision Card + ops metrics)",
    )
    a.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        metavar="DIR",
        help=f"Output directory for index.html + JSON (default: {DEFAULT_OUTPUT})",
    )
    a.add_argument(
        "--role",
        choices=("operator", "field", "lab", "decision"),
        default="operator",
        help="Brief playbook role (default: operator)",
    )
    a.add_argument(
        "--geojson",
        type=Path,
        action="append",
        default=None,
        metavar="PATH",
        help="Extra local GeoJSON layer (repeatable)",
    )
    a.add_argument(
        "--bbox",
        default=None,
        metavar="W,S,E,N",
        help="FIRMS/map bbox west,south,east,north (use --bbox=-3.5,... when negative)",
    )
    a.add_argument("--west", type=float, default=None, help="BBox west (alt to --bbox)")
    a.add_argument("--south", type=float, default=None, help="BBox south")
    a.add_argument("--east", type=float, default=None, help="BBox east")
    a.add_argument("--north", type=float, default=None, help="BBox north")
    a.add_argument("--lat", type=float, default=None, help="Center latitude (with --lon)")
    a.add_argument("--lon", type=float, default=None, help="Center longitude (with --lat)")
    a.add_argument(
        "--radius-km",
        type=float,
        default=50.0,
        help="Half-size of bbox when using --lat/--lon (default 50)",
    )
    a.add_argument(
        "--live",
        action="store_true",
        help="Attempt live FIRMS fetch (default: offline / local only)",
    )
    a.add_argument(
        "--no-live",
        action="store_true",
        help="Skip network FIRMS (default behaviour; kept for symmetry with map)",
    )
    a.add_argument(
        "--fixture-csv",
        type=Path,
        default=None,
        metavar="PATH",
        help="Load FIRMS CSV from disk (tests / air-gapped demos)",
    )
    a.add_argument(
        "--day-range",
        type=int,
        default=1,
        help="FIRMS area API day range 1–10 (default 1)",
    )
    a.add_argument(
        "--open",
        action="store_true",
        help="Open index.html in the default browser",
    )
    a.add_argument(
        "--serve",
        action="store_true",
        help=(
            "After write, serve ONLY the output dir on loopback HTTP (127.0.0.1) "
            "and open the SPA at http://127.0.0.1:PORT/. Enables Live Ops POST "
            "/live/v1/{status,decide,export-acta}. Path traversal rejected. "
            "Ctrl+C to stop. Never binds 0.0.0.0."
        ),
    )
    a.add_argument(
        "--demo-day",
        action="store_true",
        help=(
            "H1 presentador one-shot: default fire _sla_measure, Live Ops on, "
            "check third-party pack + reliability paths, serve SPA loopback, "
            "print 5-line card. Does NOT set GO_Q. Implies --serve."
        ),
    )
    a.add_argument(
        "--port",
        type=int,
        default=8766,
        metavar="N",
        help="Port for --serve / --demo-day (default 8766; distinct from serve-decide 8765)",
    )
    a.add_argument(
        "--bridge-decide",
        default=None,
        metavar="URL",
        help=(
            "Optional live Decision Card bridge base URL (loopback only, e.g. "
            "http://127.0.0.1:8765). Pro mode shows «Refrescar card»; offline "
            "falls back silently to embedded card. No fusion."
        ),
    )
    a.add_argument(
        "--all-fires",
        action="store_true",
        help=f"Prebuild multi-IF pack (cap {8}) for client-side fire switch without re-running Python",
    )
    a.add_argument(
        "--pack-fires",
        action="store_true",
        help="Alias of --all-fires: embed multi-fire pack in SPA payload",
    )
    a.add_argument(
        "--pack-cap",
        type=int,
        default=8,
        metavar="N",
        help="Max fires in multi-IF pack (default 8, hard max 8)",
    )
    a.add_argument(
        "--title",
        default=DEFAULT_TITLE,
        help=f"HTML title (default: {DEFAULT_TITLE})",
    )
    a.add_argument(
        "--ui-mode",
        choices=("simple", "advanced"),
        default="simple",
        help="SPA default mode: simple=plain language, CLI hidden (default); advanced=show raw cmds",
    )
    add_global_flags(a)


def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if not raw:
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be W,S,E,N (4 comma-separated floats)")
    w, s, e, n = (float(x) for x in parts)
    return (w, s, e, n)


def _bbox_from_center(
    lat: float, lon: float, radius_km: float
) -> tuple[float, float, float, float]:
    import math

    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.2, math.cos(math.radians(lat))))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def run_app(args: argparse.Namespace) -> int:
    """Build product SPA payload, write HTML/JSON, print summary."""
    if bool(getattr(args, "list_fires", False)):
        fires = scan_fire_catalog()
        if bool(getattr(args, "json", False)):
            rails = app_rails()
            fusion = rails.get("field_ops_ml_live_fusion") or "OFF"
            print_json(
                {
                    "schema": "wfd_fire_catalog_v1",
                    "n": len(fires),
                    "fires": fires,
                    "rails": dict(rails),
                    "note": (
                        "Catalog only · not tactical dispatch · "
                        f"field_ops ML fusion {fusion} · GO_Q invent forbidden · "
                        "file:// / no --serve: SPA copies CLI (liveUnavailableFallback)"
                    ),
                }
            )
        else:
            print("╔══════════════════════════════════════════════════════════╗")
            print("║  WFD · incendios descubiertos                            ║")
            print("╚══════════════════════════════════════════════════════════╝")
            print("")
            if not fires:
                print("  (ninguno — crea outputs/incidents/MI_IF o lanza demo)")
                print("  python -m wildfire_front demo --output outputs/demo_new")
            for f in fires:
                flags = []
                if f.get("has_geojson"):
                    flags.append("geo")
                if f.get("has_decision_card"):
                    flags.append("card")
                if f.get("has_ops_metrics"):
                    flags.append("ops")
                if f.get("decision"):
                    flags.append(str(f["decision"]))
                print(f"  · {f.get('id'):20}  {f.get('kind'):8}  {','.join(flags) or '—'}")
                print(f"      {f.get('work_dir_rel')}")
                print(f"      {f.get('rebuild_cmd')}")
            print("")
            print("  Abrir: python -m wildfire_front app --fire ID --open")
            print("  Live Ops: python -m wildfire_front app --serve --fire ID")
            print(
                f"  rails: fusion {app_rails().get('field_ops_ml_live_fusion') or 'OFF'}"
                " · GO_Q invent forbidden · no despacho táctico"
            )
            print("  sin --serve: botones SPA copian CLI (liveUnavailableFallback)")
            print("  V&V SPA: lectura vv_scorecard.json · sin scores de campo")
            print("")
        return 0

    demo_day = bool(getattr(args, "demo_day", False))
    do_serve = bool(getattr(args, "serve", False)) or demo_day
    # Live Ops on whenever we serve (loopback kernel)
    live_ops_enabled = do_serve

    try:
        bbox = _parse_bbox(getattr(args, "bbox", None))
    except ValueError as exc:
        print_error(
            str(exc),
            hint="example: --bbox=-3.5,40.7,-2.7,41.4  or  --west -3.5 --south 40.7 --east -2.7 --north 41.4",
        )
        return 2

    if bbox is None and all(
        getattr(args, k, None) is not None for k in ("west", "south", "east", "north")
    ):
        bbox = (float(args.west), float(args.south), float(args.east), float(args.north))
    elif any(getattr(args, k, None) is not None for k in ("west", "south", "east", "north")):
        print_error(
            "partial bbox corners: provide all of --west --south --east --north",
            hint="--west -3.5 --south 40.7 --east -2.7 --north 41.4",
        )
        return 2

    lat = getattr(args, "lat", None)
    lon = getattr(args, "lon", None)
    center = None
    if lat is not None or lon is not None:
        if lat is None or lon is None:
            print_error("both --lat and --lon are required together", hint="--lat 40.9 --lon -3.1")
            return 2
        center = (float(lon), float(lat))
        if bbox is None:
            bbox = _bbox_from_center(
                float(lat), float(lon), float(getattr(args, "radius_km", 50) or 50.0)
            )

    # Default offline for demos; --live enables network; --no-live is explicit offline
    live = bool(getattr(args, "live", False)) and not bool(getattr(args, "no_live", False))

    work_dir = getattr(args, "work_dir", None)
    fire_id = getattr(args, "fire", None)

    # --demo-day: default fire if nothing selected
    if demo_day and work_dir is None and not fire_id:
        fire_id = "_sla_measure"

    if work_dir is not None and not Path(work_dir).exists():
        print_error(
            f"work-dir not found: {work_dir}",
            hint="wildfire-front app --list-fires   o   --work-dir outputs/incidents/_sla_measure --open",
        )
        return 2
    if fire_id and work_dir is None:
        catalog = scan_fire_catalog()
        hit = next((f for f in catalog if f.get("id") == fire_id), None)
        if not hit:
            print_error(
                f"fire id not found: {fire_id}",
                hint="python -m wildfire_front app --list-fires",
            )
            return 2
        work_dir = Path(hit["work_dir"])

    pack_on = bool(getattr(args, "all_fires", False)) or bool(getattr(args, "pack_fires", False))
    pack_cap = int(getattr(args, "pack_cap", 8) or 8)
    if pack_cap < 1:
        pack_cap = 1
    if pack_cap > 8:
        pack_cap = 8

    demo_artifacts: dict[str, Any] | None = None
    if demo_day:
        from wildfire_front.product.live_ops import check_demo_day_artifacts

        demo_artifacts = check_demo_day_artifacts()
        # Soft-fail: warn on missing pack/reliability but still serve if SPA can build
        if not demo_artifacts.get("ok") and not bool(getattr(args, "quiet", False)):
            missing = ", ".join(demo_artifacts.get("missing") or []) or "(unknown)"
            print(f"  demo-day GAP: missing artifacts → {missing}")
            print(
                "  hint: python scripts/build_demo_third_party_pack.py  ·  "
                "python scripts/run_third_party_replay.py"
            )
            print("")

    payload = build_product_app_payload(
        work_dir=work_dir,
        role=str(getattr(args, "role", "operator") or "operator"),
        geojson_paths=list(args.geojson or []) or None,
        bbox=bbox,
        center=center,
        live=live,
        day_range=int(getattr(args, "day_range", 1) or 1),
        fixture_csv=getattr(args, "fixture_csv", None),
        title=str(getattr(args, "title", None) or DEFAULT_TITLE),
        scan=not bool(getattr(args, "no_scan", False)),
        fire_id=None,  # already resolved work_dir
        ui_mode=str(getattr(args, "ui_mode", "simple") or "simple"),
        bridge_decide=getattr(args, "bridge_decide", None),
        pack_fires=pack_on,
        pack_cap=pack_cap,
        live_ops_enabled=live_ops_enabled,
    )

    out_dir = Path(getattr(args, "output", None) or DEFAULT_OUTPUT)
    paths = write_product_app(payload, out_dir)
    payload = dict(payload)
    payload["artifacts"] = {"html": str(paths["html"]), "json": str(paths["json"])}
    if demo_artifacts is not None:
        payload["demo_day"] = {
            "enabled": True,
            "go_q_met": False,
            "go_q_invent_forbidden": True,
            "artifacts": demo_artifacts,
            "presentador": {
                "spa": str(paths["html"]),
                "serve_cmd": (
                    f"python -m wildfire_front app --demo-day --port "
                    f"{int(getattr(args, 'port', 8766) or 8766)}"
                ),
                "replay_cmd": demo_artifacts.get("replay_cmd"),
                "pack_cmd": demo_artifacts.get("pack_cmd"),
                "kill_list": [
                    "No ROS inventado",
                    "No field_ops ML live fusion ON",
                    "No vender Tobarra LOFO como producto de campo",
                    "No «apagamos incendios con IA»",
                    "No inventar GO_Q complete sin acta firmada de tercero",
                ],
            },
        }

    if bool(getattr(args, "json", False)):
        print_json(payload)
    else:
        brief = payload.get("brief") or {}
        hero = payload.get("hero") or {}
        conn = (payload.get("connectivity") or {}).get("status")
        print("╔══════════════════════════════════════════════════════════╗")
        print("║  WFD · PRODUCT SPA  (ops console · no despacho táctico)  ║")
        print("╚══════════════════════════════════════════════════════════╝")
        print("")
        print(f"  title:        {payload.get('title')}")
        print(f"  role:         {payload.get('role')}  ·  light={hero.get('overall_light')}")
        print(f"  hero:         {hero.get('decision')}  conf={hero.get('confidence_pred')}")
        print(f"  work-dir:     {payload.get('work_dir') or '(none — brief + empty/default map)'}")
        print(f"  decision card: {'yes' if payload.get('decision_card') else 'no'}")
        print(f"  ops metrics:  {'yes' if payload.get('ops_metrics') else 'no'}")
        print(f"  map layers:   {len(payload.get('layer_summary') or [])}  ·  connectivity={conn}")
        print(
            f"  fires:        {payload.get('fire_count', 0)} en catálogo  ·  selected={payload.get('selected_fire_id')}"
        )
        print(f"  actions:      {len(payload.get('product_actions') or [])} CTAs en consola")
        print(
            f"  ui-mode:      {payload.get('ui_mode', 'simple')}  ·  glosario={len(payload.get('glossary') or [])}"
        )
        pack = payload.get("pack") or {}
        if pack.get("enabled"):
            print(
                f"  pack:         {pack.get('n')} IF  ·  cap={pack.get('cap')}  ·  truncated={pack.get('truncated')}"
            )
        bridge = payload.get("bridge_decide") or {}
        if bridge.get("enabled"):
            print(f"  bridge:       {bridge.get('url')}  (live card; offline fallback embed)")
        lo = payload.get("live_ops") or {}
        if lo.get("enabled"):
            print("  live ops:     ON  ·  POST /live/v1/{status,decide,export-acta}")
        print(
            f"  rails:        fusion={(payload.get('rails') or {}).get('field_ops_ml_live_fusion')}"
        )
        print(f"  HTML:         {paths['html']}")
        print(f"  JSON:         {paths['json']}")
        print("")
        if demo_day:
            print("  ── DEMO-DAY (presentador) ──────────────────────────────")
            print("  1. SPA live:     click Estado · Decidir · Acta (same-origin)")
            print("  2. Pack:         outputs/demo_third_party")
            print("  3. Reliability:  docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md")
            print("  4. Replay:       python scripts/run_third_party_replay.py")
            print("  5. GO_Q:         partial — human third-party acta still required")
            print("  kill: fusion ON ≠ GO_Q / despacho · no ROS invent · no «IA apaga incendios»")
            print("")
        nxt = brief.get("next_action") or {}
        if nxt:
            print(f"  next: [{nxt.get('priority')}] {nxt.get('summary')}")
            print(f"        → {nxt.get('command')}")
            print("")
        rb = (payload.get("rebuild") or {}).get("selected_cmd")
        if rb:
            print(f"  rebuild:      {rb}")
            print("")
        print(f"  ⚠  {payload.get('disclaimer_simple') or payload.get('disclaimer')}")
        print("")
        print("  docs: docs/APP.md  ·  listar: python -m wildfire_front app --list-fires")
        print("  dual-mode: Fácil (default) | Pro · primary acts: Estado · Decidir · Acta")
        if live_ops_enabled:
            print("  live: click acts run product code (loopback --serve only)")
        else:
            print("  no-serve: copy-CLI fallback (app --serve for Live Ops)")
            print(
                f"  rails: fusion {app_rails().get('field_ops_ml_live_fusion') or 'OFF'}"
                " · GO_Q invent forbidden · no despacho táctico"
            )
        print("")

    # --json snapshot never blocks on serve (CI / demo-day rails check)
    if bool(getattr(args, "json", False)):
        return 0

    do_open = bool(getattr(args, "open", False))

    if do_serve:
        bridge_cfg = payload.get("bridge_decide") or {}
        bridge_upstream = (
            str(bridge_cfg.get("url") or "").strip() if bridge_cfg.get("enabled") else None
        )
        return _serve_static_spa(
            paths["html"],
            port=int(getattr(args, "port", 8766) or 8766),
            open_browser=True,  # demo-friendly; SPA is local-only
            quiet=bool(getattr(args, "quiet", False)),
            bridge_upstream=bridge_upstream or None,
            live_ops_enabled=True,
            live_base_dir=Path.cwd(),
        )

    if do_open:
        try:
            import webbrowser

            webbrowser.open(paths["html"].resolve().as_uri())
        except Exception as exc:  # pragma: no cover - platform dependent
            if not bool(getattr(args, "quiet", False)):
                print_error(f"could not open browser: {exc}", hint=str(paths["html"]))

    return 0


# Loopback-only bind host — never 0.0.0.0 by default (PR06).
_SERVE_HOST = "127.0.0.1"


class _SafeSPARequestHandler:
    """Factory for a path-traversal-safe static handler rooted at output_dir.

    Optional ``bridge_upstream`` (loopback serve-decide base URL) enables
    same-origin proxy paths so the browser SPA can refresh Decision Cards
    without cross-origin CORS (PR07 fix).

    Optional ``live_ops_enabled`` adds same-origin POST /live/v1/* product acts
    (status / decide / export-acta) with work_dir allowlisted under
    ``live_base_dir`` (repo root).
    """

    @staticmethod
    def make(
        root: Path,
        *,
        bridge_upstream: str | None = None,
        live_ops_enabled: bool = False,
        live_base_dir: Path | None = None,
    ):
        import http.server
        import json
        import urllib.error
        import urllib.parse
        import urllib.request

        from wildfire_front.product.app_spa import (
            BRIDGE_PROXY_HEALTH,
            BRIDGE_PROXY_PATH,
            is_loopback_http_url,
        )
        from wildfire_front.product.live_ops import dispatch_live

        root_res = root.resolve()
        upstream = (str(bridge_upstream).strip() if bridge_upstream else "") or None
        if upstream and not is_loopback_http_url(upstream):
            upstream = None
        if upstream:
            upstream = upstream.rstrip("/")
        live_on = bool(live_ops_enabled)
        live_base = Path(live_base_dir).resolve() if live_base_dir else Path.cwd().resolve()

        class Handler(http.server.BaseHTTPRequestHandler):
            server_version = "WFD-SPA/1.1"
            bridge_upstream = upstream
            live_ops_enabled = live_on
            live_base_dir = live_base

            def log_message(self, fmt: str, *args) -> None:  # quieter demos
                return

            def _req_path(self) -> str:
                return urllib.parse.urlparse(self.path).path or "/"

            def _safe_path(self) -> Path | None:
                # Reject URL tricks; only serve files under root_res
                import os as _os

                parsed = urllib.parse.urlparse(self.path)
                raw = urllib.parse.unquote(parsed.path or "/")
                # Normalize separators and strip leading slash
                rel = raw.lstrip("/").replace("\\", "/")
                if rel == "" or rel.endswith("/"):
                    rel = (rel + "index.html") if rel else "index.html"
                # Block null bytes and parent traversal tokens before resolve
                parts = [p for p in rel.split("/") if p not in ("", ".")]
                if "\x00" in rel or any(p == ".." for p in parts):
                    return None
                # Bridge / live API paths are not static files
                if rel.startswith("bridge/") or rel.startswith("live/"):
                    return None
                root_real = _os.path.realpath(str(root_res))
                joined = _os.path.join(root_real, *parts) if parts else root_real
                cand_real = _os.path.realpath(joined)
                try:
                    common = _os.path.commonpath([root_real, cand_real])
                except ValueError:
                    return None
                if common != root_real:
                    return None
                if cand_real != root_real and not (
                    cand_real.startswith(root_real + _os.sep)
                    or cand_real.startswith(root_real + "/")
                ):
                    return None
                # Rebuild from verified realpath only (breaks path-injection taint)
                return Path(cand_real)

            def _send_bytes(
                self,
                status: int,
                data: bytes,
                *,
                content_type: str = "application/json; charset=utf-8",
            ) -> None:
                # Whitelist content-types (no CR/LF — HTTP response splitting)
                allowed_ct = {
                    "application/json; charset=utf-8",
                    "application/json",
                    "text/html; charset=utf-8",
                    "text/plain; charset=utf-8",
                    "application/octet-stream",
                    "text/css",
                    "application/javascript",
                    "image/png",
                    "image/jpeg",
                    "image/svg+xml",
                    "image/gif",
                    "image/webp",
                    "font/woff",
                    "font/woff2",
                }
                ct = str(content_type or "application/octet-stream")
                if "\r" in ct or "\n" in ct or ct not in allowed_ct:
                    # Map common mimetypes to safe fixed strings
                    low = ct.split(";")[0].strip().lower()
                    ct = {
                        "text/html": "text/html; charset=utf-8",
                        "application/json": "application/json; charset=utf-8",
                        "text/plain": "text/plain; charset=utf-8",
                        "text/css": "text/css",
                        "application/javascript": "application/javascript",
                        "image/png": "image/png",
                        "image/jpeg": "image/jpeg",
                        "image/svg+xml": "image/svg+xml",
                        "image/gif": "image/gif",
                        "image/webp": "image/webp",
                    }.get(low, "application/octet-stream")
                self.send_response(status)
                self.send_header("Content-Type", ct)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                if self.live_ops_enabled:
                    self.send_header("X-WFD-Live-Ops", "1")
                self.end_headers()
                self.wfile.write(data)

            def _read_json_body(self) -> tuple[dict | None, bytes | None]:
                length = int(self.headers.get("Content-Length") or 0)
                if length > 1_048_576:
                    self._send_bytes(413, b'{"error":"body_too_large"}')
                    return None, None
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    obj = json.loads(raw.decode("utf-8") or "{}")
                    if obj is None:
                        obj = {}
                    if not isinstance(obj, dict):
                        self._send_bytes(
                            400,
                            b'{"error":"invalid_json","detail":"body must be object"}',
                        )
                        return None, None
                    return obj, raw
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    msg = str(exc).replace('"', "'")[:120]
                    self._send_bytes(
                        400,
                        f'{{"error":"invalid_json","detail":"{msg}"}}'.encode(),
                    )
                    return None, None

            def _handle_live(self, *, method: str) -> bool:
                """Return True if path was a live route (handled)."""
                path = self._req_path()
                if not path.startswith("/live/"):
                    return False
                if not self.live_ops_enabled:
                    self._send_bytes(
                        503,
                        b'{"ok":false,"error":"live_ops_disabled",'
                        b'"detail":"enable with app --serve"}',
                    )
                    return True
                body: dict | None = {}
                if method == "POST":
                    body, _raw = self._read_json_body()
                    if body is None and _raw is None:
                        return True  # error already sent
                    if body is None:
                        body = {}
                status, payload = dispatch_live(
                    path,
                    body,
                    base=self.live_base_dir,
                    method=method,
                )
                data = json.dumps(payload, indent=2, default=str).encode()
                self._send_bytes(status, data)
                return True

            def _proxy_to_upstream(
                self, *, method: str, upstream_path: str, body: bytes | None = None
            ) -> None:
                if not self.bridge_upstream:
                    self._send_bytes(
                        503,
                        b'{"error":"bridge_not_configured"}',
                    )
                    return
                target = f"{self.bridge_upstream}{upstream_path}"
                try:
                    req = urllib.request.Request(
                        target,
                        data=body if method == "POST" else None,
                        method=method,
                        headers={"Content-Type": "application/json"} if method == "POST" else {},
                    )
                    with urllib.request.urlopen(req, timeout=8) as resp:
                        data = resp.read()
                        # Never forward raw Content-Type (HTTP response splitting);
                        # always use fixed whitelist via _send_bytes default/mapper.
                        raw_ct = resp.headers.get("Content-Type") or ""
                        # Strip CR/LF and parameters; map in _send_bytes
                        safe_ct = raw_ct.split(";")[0].strip().replace("\r", "").replace("\n", "")
                        if not safe_ct:
                            safe_ct = "application/json"
                        self._send_bytes(
                            int(resp.status),
                            data,
                            content_type=safe_ct,
                        )
                except urllib.error.HTTPError as exc:
                    data = exc.read() if hasattr(exc, "read") else b""
                    if not data:
                        data = f'{{"error":"upstream_http","status":{exc.code}}}'.encode()
                    self._send_bytes(int(exc.code), data)
                except Exception as exc:
                    msg = str(exc).replace('"', "'")[:200]
                    self._send_bytes(
                        502,
                        f'{{"error":"bridge_upstream_unreachable","detail":"{msg}"}}'.encode(),
                    )

            def do_GET(self) -> None:  # noqa: N802
                if self._handle_live(method="GET"):
                    return
                path = self._req_path()
                # Same-origin bridge health proxy
                if path.rstrip("/") in (
                    BRIDGE_PROXY_HEALTH.rstrip("/"),
                    "/bridge/health",
                    "/bridge/v1/health",
                ):
                    self._proxy_to_upstream(method="GET", upstream_path="/health")
                    return
                target = self._safe_path()
                if target is None:
                    self.send_error(403, "Forbidden: path outside SPA output dir")
                    return
                from wildfire_front.product.path_sandbox import (
                    PathNotAllowedError,
                    read_bytes,
                    realpath,
                )

                try:
                    t_real = realpath(target)
                    data = read_bytes(t_real, [root_res])
                except (OSError, PathNotAllowedError):
                    self.send_error(404, "Not found")
                    return
                # Fixed content-type from suffix only (no free-form header injection)
                suf = Path(t_real).suffix.lower()
                ctype = {
                    ".html": "text/html; charset=utf-8",
                    ".htm": "text/html; charset=utf-8",
                    ".json": "application/json; charset=utf-8",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".svg": "image/svg+xml",
                    ".gif": "image/gif",
                    ".webp": "image/webp",
                }.get(suf, "application/octet-stream")
                self._send_bytes(200, data, content_type=ctype)

            def do_POST(self) -> None:  # noqa: N802
                if self._handle_live(method="POST"):
                    return
                path = self._req_path()
                if path.rstrip("/") == BRIDGE_PROXY_PATH.rstrip("/") or path in (
                    "/bridge/v1/decide",
                    "/bridge/decide",
                ):
                    length = int(self.headers.get("Content-Length") or 0)
                    if length > 2_000_000:
                        self._send_bytes(413, b'{"error":"body_too_large"}')
                        return
                    raw = self.rfile.read(length) if length > 0 else b"{}"
                    self._proxy_to_upstream(method="POST", upstream_path="/v1/decide", body=raw)
                    return
                self.send_error(405, "Method not allowed")

            def do_HEAD(self) -> None:  # noqa: N802
                path = self._req_path()
                if path.startswith("/live/"):
                    if self.live_ops_enabled:
                        self.send_response(200)
                        self.send_header("X-WFD-Live-Ops", "1")
                        self.end_headers()
                    else:
                        self.send_error(503, "live_ops_disabled")
                    return
                target = self._safe_path()
                if target is None:
                    self.send_error(403, "Forbidden")
                    return
                import os as _os

                t_real = _os.path.realpath(str(target))
                if not _os.path.isfile(t_real):
                    self.send_error(404, "Not found")
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()

        return Handler


def _serve_static_spa(
    html_path: Path,
    *,
    port: int = 8766,
    open_browser: bool = True,
    quiet: bool = False,
    host: str = _SERVE_HOST,
    bridge_upstream: str | None = None,
    live_ops_enabled: bool = False,
    live_base_dir: Path | None = None,
) -> int:
    """Serve SPA output directory over loopback HTTP.

    Security (PR06):
      · bind 127.0.0.1 only by default (reject non-loopback host)
      · serve only files under the SPA output_dir
      · reject path traversal (``..``, absolute escapes)

    Optional bridge (PR07):
      · when ``bridge_upstream`` is set (loopback), POST /bridge/v1/decide proxies
        to upstream serve-decide so the browser uses same-origin (no CORS).

    Live Ops (L1+):
      · when ``live_ops_enabled``, POST /live/v1/{status,decide,export-acta}
        invoke real product code with work_dir allowlisted under live_base_dir.
    """
    import socketserver
    import webbrowser

    # Hard rail: loopback only
    host_s = str(host or _SERVE_HOST).strip() or _SERVE_HOST
    if host_s not in ("127.0.0.1", "localhost", "::1"):
        print_error(
            f"refuse to bind non-loopback host: {host_s}",
            hint="--serve is demo-local only (127.0.0.1)",
        )
        return 2

    root = Path(html_path).resolve().parent
    if not (root / "index.html").is_file() and not Path(html_path).is_file():
        print_error(f"SPA HTML missing: {html_path}", hint="run app without --serve first")
        return 2

    handler_cls = _SafeSPARequestHandler.make(
        root,
        bridge_upstream=bridge_upstream,
        live_ops_enabled=live_ops_enabled,
        live_base_dir=live_base_dir or Path.cwd(),
    )

    class _ReusableServer(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    bind_host = "127.0.0.1" if host_s == "localhost" else host_s
    try:
        httpd = _ReusableServer((bind_host, int(port)), handler_cls)
    except OSError as exc:
        print_error(
            f"could not bind {bind_host}:{port}: {exc}",
            hint="try --port 8767 or free the port",
        )
        return 2

    actual_port = int(httpd.server_address[1])
    url = f"http://127.0.0.1:{actual_port}/"
    if not quiet:
        print(f"  serve:        {url}  (dir={root}; loopback-only; no CORS)")
        if live_ops_enabled:
            print("  live ops:     POST /live/v1/{status,decide,export-acta}  (fusion ON)")
        if bridge_upstream:
            print(f"  bridge proxy: /bridge/v1/decide → {bridge_upstream}/v1/decide")
        print("  stop:         Ctrl+C")
        print("")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception as exc:  # pragma: no cover - platform dependent
            if not quiet:
                print_error(f"could not open browser: {exc}", hint=url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        if not quiet:
            print("\n  serve stopped.")
    finally:
        httpd.server_close()
    return 0


def resolve_safe_spa_path(root: Path, request_path: str) -> Path | None:
    """Public helper for tests: resolve request path under root or None if escape."""
    import os
    import urllib.parse

    root_real = os.path.realpath(str(root))
    raw = urllib.parse.unquote(str(request_path or "/"))
    rel = raw.lstrip("/").replace("\\", "/")
    if rel == "" or rel.endswith("/"):
        rel = (rel + "index.html") if rel else "index.html"
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if "\x00" in rel or any(p == ".." for p in parts):
        return None
    joined = os.path.join(root_real, *parts) if parts else root_real
    cand_real = os.path.realpath(joined)
    try:
        common = os.path.commonpath([root_real, cand_real])
    except ValueError:
        return None
    if common != root_real:
        return None
    if cand_real != root_real and not (
        cand_real.startswith(root_real + os.sep) or cand_real.startswith(root_real + "/")
    ):
        return None
    return Path(cand_real)
