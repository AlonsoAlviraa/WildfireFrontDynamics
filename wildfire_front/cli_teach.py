"""Product teach CLI: teach, show, demo-third-party, dry-run-h3, operator.

Registered from ``wildfire_front.cli.build_parser`` via ``register_teach_commands``.
Thin orchestration — pack/replay logic stays in scripts; gates in teach_path.
Operator mode: single entry + traffic light + 4 acts for non-code users.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import subprocess
import sys
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .cli_report import print_json
from .product.operator_ux import (
    build_operator_status,
    evaluate_operator_checklist,
    format_abstain_plain,
    format_checklist_human,
    format_operator_human,
    format_operator_next,
    write_operator_session,
)
from .product.teach_path import (
    build_teach_payload,
    format_show_human,
    format_teach_human,
    load_gate_snapshot,
    resolve_repo_root,
)

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]


def register_teach_commands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: AddGlobalFlags,
) -> None:
    """Attach teach / show / demo-third-party / operator top-level commands."""
    teach = commands.add_parser(
        "teach",
        help="Print 4-act learning path (copy-paste commands + rails)",
        description=(
            "Print the WFD 4-act teach path (ver → callarse → decidir → probar) "
            "with PowerShell-friendly commands. Documentation CLI — no side effects."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front teach\n"
            "  wildfire-front teach --act 3\n"
            "  wildfire-front teach --json\n"
        ),
    )
    teach.add_argument(
        "--act",
        type=int,
        choices=(1, 2, 3, 4),
        default=None,
        metavar="N",
        help=(
            "Print only act N (1–4). Invalid values are rejected by argparse "
            "(usage exit 2; design §4.3.5 prefers 1 — argparse convention wins)."
        ),
    )
    add_global_flags(teach)

    show = commands.add_parser(
        "show",
        help="Gates snapshot + honesty rails + key paths (no portal rebuild)",
        description=(
            "Print GO_MES / GO_Q / fusion / ml_product_go snapshot and key demo paths. "
            "Does not rebuild hub/portal (use scripts/show_all.py for that)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front show\n"
            "  wildfire-front show --json\n"
            "  wildfire-front show --open\n"
        ),
    )
    show.add_argument(
        "--open",
        action="store_true",
        help="Open existing multi-CCAA / pilot honesty / PORTAL HTML if present (does not build)",
    )
    add_global_flags(show)

    demo_tp = commands.add_parser(
        "demo-third-party",
        help="Build third-party demo pack + forensic replay (default: replay ON)",
        description=(
            "Thin product wrapper for E1 pack build + E3 forensic replay. "
            "Default runs build then replay. Exit 0 = forensic consistency, "
            "not cryptographic authenticity."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front demo-third-party\n"
            "  wildfire-front demo-third-party --no-replay --no-zip\n"
            "  wildfire-front demo-third-party --skip-build --output outputs/demo_third_party\n"
        ),
    )
    demo_tp.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/demo_third_party"),
        metavar="DIR",
        help="Pack output directory (default: outputs/demo_third_party)",
    )
    demo_tp.add_argument(
        "--dist",
        type=Path,
        default=Path("dist"),
        metavar="DIR",
        help="Zip directory (default: dist)",
    )
    demo_tp.add_argument("--no-zip", action="store_true", help="Skip zip under dist/")
    replay_g = demo_tp.add_mutually_exclusive_group()
    replay_g.add_argument(
        "--replay",
        dest="replay",
        action="store_true",
        default=True,
        help="Run E3 forensic replay after build (default: ON)",
    )
    replay_g.add_argument(
        "--no-replay",
        dest="replay",
        action="store_false",
        help="Build only (skip replay)",
    )
    demo_tp.add_argument(
        "--skip-build",
        action="store_true",
        help="Only replay existing --output bundle (no rebuild)",
    )
    add_global_flags(demo_tp)

    dry_h3 = commands.add_parser(
        "dry-run-h3",
        help="H3 full path: teach → show → cheatsheet → demo-third-party → report",
        description=(
            "Engineering dry-run of the human demo path. Writes "
            "outputs/demo_third_party/H3_DRY_RUN_REPORT.{md,json}. "
            "Does not complete human attestation or flip GO_Q."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front dry-run-h3\n"
            "  wildfire-front dry-run-h3 --no-zip\n"
            "  wildfire-front dry-run-h3 --json\n"
            "  make h3-dry-run\n"
        ),
    )
    dry_h3.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/demo_third_party"),
        metavar="DIR",
        help="Pack + report directory (default: outputs/demo_third_party)",
    )
    dry_h3.add_argument("--no-zip", action="store_true", help="Skip zip when building pack")
    dry_h3.add_argument(
        "--skip-build",
        action="store_true",
        help="Replay existing pack only (skip rebuild)",
    )
    dry_h3.add_argument(
        "--full-demo",
        action="store_true",
        help="Also check multi-CCAA / pilot honesty artifacts (default OFF)",
    )
    add_global_flags(dry_h3)

    # ── operator (single entry for non-code users) ──────────────────────
    op = commands.add_parser(
        "operator",
        help="Modo operario: semáforo + 4 actos + qué falta para GO_Q",
        description=(
            "Única puerta de entrada para un operario que no conoce el código. "
            "Semáforo VERDE/AMARILLO/ROJO, 4 pasos (Ver→Callarse→Decidir→Probar), "
            "y checklist de lo que falta para GO_Q. "
            "ABSTAIN se explica en lenguaje normal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front operator\n"
            "  wildfire-front operator checklist\n"
            "  wildfire-front operator next\n"
            "  wildfire-front operator do --act 3\n"
            "  wildfire-front operator do --all\n"
            "  wildfire-front ensayo\n"
            "  wildfire-front operator explain-abstain\n"
            "  wildfire-front operator --json\n"
        ),
    )
    op_sub = op.add_subparsers(dest="operator_cmd", required=False, metavar="SUB")

    op_status = op_sub.add_parser(
        "status",
        help="Tablero operario (default si no hay subcomando)",
    )
    add_global_flags(op_status)

    op_check = op_sub.add_parser(
        "checklist",
        help="Evaluar checklist de operario (4 actos + GO_Q)",
    )
    add_global_flags(op_check)

    op_do = op_sub.add_parser(
        "do",
        help="Ejecutar un acto (1–4) o los cuatro en secuencia (--all)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "ejemplos:\n"
            "  wildfire-front operator do --act 1\n"
            "  wildfire-front operator do --all\n"
            "  wildfire-front operator do --all --rebuild\n"
        ),
    )
    op_do.add_argument(
        "--act",
        type=int,
        choices=(1, 2, 3, 4),
        default=None,
        metavar="N",
        help="Acto a ejecutar: 1=Ver 2=Callarse 3=Decidir 4=Probar",
    )
    op_do.add_argument(
        "--all",
        action="store_true",
        help="Ejecutar actos 1→4 en secuencia (ensayo completo; --no-build por defecto)",
    )
    op_do.add_argument(
        "--open",
        action="store_true",
        help="Abrir HTML generado en el navegador (actos 1–2)",
    )
    op_do.add_argument(
        "--no-build",
        action="store_true",
        help="Acto 1/2/4: no reconstruir si ya existe el artefacto",
    )
    op_do.add_argument(
        "--rebuild",
        action="store_true",
        help="Con --all: forzar rebuild de demos (anula el --no-build implícito)",
    )
    add_global_flags(op_do)

    op_abs = op_sub.add_parser(
        "explain-abstain",
        help="Por qué el sistema se calla (ABSTAIN) en lenguaje normal",
    )
    add_global_flags(op_abs)

    op_next = op_sub.add_parser(
        "next",
        help="Qué hacer ahora + qué falta para GO_Q (humano)",
    )
    add_global_flags(op_next)

    add_global_flags(op)


def run_operator(args: argparse.Namespace) -> int:
    """Operator mode: status board / checklist / do act / explain-abstain."""
    try:
        as_json = bool(getattr(args, "json", False))
        quiet = bool(getattr(args, "quiet", False))
        verbose = bool(getattr(args, "verbose", False))
        sub = getattr(args, "operator_cmd", None) or "status"

        if sub == "status" or sub is None:
            st = build_operator_status()
            if as_json:
                print_json(st)
            else:
                sys.stdout.write(format_operator_human(st, quiet=quiet, verbose=verbose))
            return 0

        if sub == "checklist":
            result = evaluate_operator_checklist()
            if as_json:
                print_json(result)
            else:
                sys.stdout.write(format_checklist_human(result))
            return 0 if result.get("loop_done") else 0  # informational exit 0

        if sub == "explain-abstain":
            from .product.decide_service import decide_from_request

            card = decide_from_request(
                {
                    "event_id": "operator_abstain_lesson",
                    "policy_id": "field_ops",
                    "channel": "cli",
                },
                base=Path.cwd(),
            )
            if as_json:
                print_json(
                    {
                        "schema": "wfd_operator_abstain_v1",
                        "decision": card.get("decision"),
                        "plain": format_abstain_plain(card),
                        "reasons": card.get("reasons"),
                    }
                )
            else:
                sys.stdout.write(format_abstain_plain(card))
            return 0

        if sub == "next":
            st = build_operator_status()
            check = evaluate_operator_checklist(status=st)
            if as_json:
                print_json(
                    {
                        "schema": "wfd_operator_next_v1",
                        "overall_light": st.get("overall_light"),
                        "go_q": st.get("go_q"),
                        "loop_done": check.get("loop_done"),
                        "session_all_four_ok": check.get("session_all_four_ok"),
                        "next_steps": (st.get("go_q") or {}).get("what_is_missing"),
                        "eng_ready": st.get("eng_path_ready"),
                    }
                )
            else:
                sys.stdout.write(format_operator_next(st, check, quiet=quiet, verbose=verbose))
            return 0

        if sub == "do":
            return _run_operator_do(args)

        print(f"error: unknown operator subcommand: {sub}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_operator_do(args: argparse.Namespace) -> int:
    """Execute one act or all four (``--all``) with plain feedback."""
    do_all = bool(getattr(args, "all", False))
    act_raw = getattr(args, "act", None)
    as_json = bool(getattr(args, "json", False))
    quiet = bool(getattr(args, "quiet", False))
    do_open = bool(getattr(args, "open", False))
    no_build = bool(getattr(args, "no_build", False))
    rebuild = bool(getattr(args, "rebuild", False))

    if do_all and act_raw is not None:
        print(
            "aviso: --all ignora --act N (se ejecutan 1→4)",
            file=sys.stderr,
        )
    if not do_all and act_raw is None:
        msg = (
            "Falta indicar el acto.\n"
            "  python -m wildfire_front operator do --act 1   # Ver\n"
            "  python -m wildfire_front operator do --act 2   # Callarse\n"
            "  python -m wildfire_front operator do --act 3   # Decidir\n"
            "  python -m wildfire_front operator do --act 4   # Probar\n"
            "  python -m wildfire_front operator do --all     # los 4 en secuencia\n"
            "Tablero: python -m wildfire_front operator"
        )
        print(msg, file=sys.stderr)
        return 2

    # --all: prefer existing artifacts (fast rehearsal) unless --rebuild
    if do_all and not rebuild:
        no_build = True

    acts = [1, 2, 3, 4] if do_all else [int(act_raw)]
    results: list[dict[str, Any]] = []
    worst = 0
    # Machine --json must not interleave human banners from each act.
    # do --all is compact by default (one-liners per act + footer); -v restores full.
    verbose = bool(getattr(args, "verbose", False))
    quiet_acts = bool(quiet or as_json or (do_all and not verbose))
    compact_all = bool(do_all and not quiet and not as_json)
    if compact_all:
        print("── Operario · ensayo 4 actos (1→4) ──")
        if no_build:
            print("  (artefactos existentes: sin rebuild; usa --rebuild para forzar)")
        if not verbose:
            print("  (compacto: -v para detalle por acto)")
        print("")

    titles = {
        1: "Ver",
        2: "Callarse",
        3: "Decidir",
        4: "Probar",
    }
    for act in acts:
        rc = _run_operator_do_one(
            act,
            as_json=as_json and not do_all,  # JSON only for single-act
            quiet=quiet_acts,
            do_open=do_open and not as_json,
            no_build=no_build,
            verbose=verbose and not as_json and not do_all,
        )
        results.append({"act": act, "exit_code": rc, "ok": rc == 0})
        if compact_all:
            mark = "OK" if rc == 0 else f"FAIL({rc})"
            print(f"  Acto {act} {titles.get(act, '')}: {mark}")
        if rc != 0:
            worst = rc if worst == 0 else max(worst, rc)
            if do_all and not quiet_acts and not compact_all:
                print(f"  ⚠ Acto {act} falló (exit {rc}); se continúa el ensayo.")
            if not do_all:
                # still stamp partial session for checklist honesty
                with contextlib.suppress(OSError):
                    write_operator_session(results, mode="do --act")
                return rc

    mode = "do --all" if do_all else "do --act"
    session_path = None
    try:
        session_path = write_operator_session(results, mode=mode)
    except OSError as exc:
        if not quiet_acts:
            print(f"  aviso: no se pudo guardar sello de sesión: {exc}", file=sys.stderr)

    if do_all:
        payload = {
            "schema": "wfd_operator_do_all_v1",
            "acts": results,
            "exit_code": worst,
            "session": str(session_path) if session_path else None,
            "next": "python -m wildfire_front operator checklist",
            "go_q": "partial hasta H1 humana",
            "honesty": "session stamp ≠ H1 / no flips GO_Q",
        }
        if as_json:
            print_json(payload)
        elif not quiet:
            ok_n = sum(1 for r in results if r["ok"])
            print("")
            print(f"── Fin ensayo: {ok_n}/4 actos OK ──")
            # compact path already printed per-act one-liners above
            if not compact_all:
                for r in results:
                    mark = "OK" if r["ok"] else f"FAIL({r['exit_code']})"
                    print(f"  Acto {r['act']}: {mark}")
            if session_path:
                print(f"  Sello: {session_path}")
            print("  Siguiente: python -m wildfire_front next")
            print("  Checklist: python -m wildfire_front checklist")
            print("  GO_Q: sigue partial — falta demo+acta con tercero (docs/H1_GO_Q_RUNBOOK.md)")
        return int(worst)
    return 0


def _run_operator_do_one(
    act: int,
    *,
    as_json: bool = False,
    quiet: bool = False,
    do_open: bool = False,
    no_build: bool = False,
    verbose: bool = False,
) -> int:
    """Execute a single operator act (1–4)."""
    repo = resolve_repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    titles = {
        1: "Ver (multi-CCAA)",
        2: "Callarse (pilot honesty — ABSTAIN es feature)",
        3: "Decidir (Decision Card)",
        4: "Probar (pack + replay)",
    }
    if not quiet:
        print(f"── Operario · Acto {act}: {titles.get(act, '')} ──")

    if act == 1:
        out_html = repo / "outputs" / "demo_multi_ccaa" / "index.html"
        if no_build and out_html.is_file():
            if not quiet:
                print(f"  (sin rebuild) ya existe: {out_html}")
            rc = 0
        else:
            script = repo / "scripts" / "build_demo_multi_ccaa.py"
            if not script.is_file():
                print(f"error: falta script {script}", file=sys.stderr)
                return 1
            rc = subprocess.call(
                [sys.executable, str(script)],
                cwd=str(repo),
            )
        if do_open and out_html.is_file():
            webbrowser.open(out_html.resolve().as_uri())
        if not quiet:
            print("  Mensaje: mismos gates, 3 contratos (no es 3 IF grade A).")
            print(f"  HTML: {out_html}")
            print("  Siguiente: python -m wildfire_front operator do --act 2")
        if as_json:
            print_json({"act": 1, "ok": rc == 0, "html": str(out_html)})
        return 0 if rc == 0 else 1

    if act == 2:
        out_html = repo / "outputs" / "pilot_honesty_card" / "index.html"
        fixture = repo / "tests" / "fixtures" / "pilot"
        if no_build and out_html.is_file():
            if not quiet:
                print(f"  (sin rebuild) ya existe: {out_html}")
            rc = 0
        else:
            script = repo / "scripts" / "run_pilot_honesty_card.py"
            if not script.is_file():
                print(f"error: falta script {script}", file=sys.stderr)
                return 1
            cmd = [sys.executable, str(script)]
            if fixture.is_dir():
                cmd.extend(["--fixture-root", str(fixture)])
            rc = subprocess.call(cmd, cwd=str(repo))
        if do_open and out_html.is_file():
            webbrowser.open(out_html.resolve().as_uri())
        if not quiet:
            print("  Mensaje: field_ops se CALLA — ABSTAIN no es un bug.")
            sys.stdout.write(
                format_abstain_plain(
                    {
                        "decision": "ABSTAIN",
                        "reasons": [
                            "missing:ops",
                            "no_available_sources",
                            "policy:field_ops",
                        ],
                        "sources": [],
                    }
                )
            )
            print(f"  HTML: {out_html}")
            print("  Siguiente: python -m wildfire_front operator do --act 3")
        if as_json:
            print_json({"act": 2, "ok": rc == 0, "html": str(out_html)})
        return 0 if rc == 0 else 1

    if act == 3:
        from .product.decide_service import decide_from_request
        from .product.teach_path import format_decide_explain

        card = decide_from_request(
            {
                "event_id": "operator_act3",
                "policy_id": "field_ops",
                "channel": "cli",
            },
            base=repo,
        )
        decision = card.get("decision")
        if as_json:
            print_json({"act": 3, "decision": decision, "card": card})
            return 0
        if not quiet:
            if str(decision).upper() == "ABSTAIN":
                sys.stdout.write(format_abstain_plain(card))
            print(format_decide_explain(card, repo=repo), end="")
            print("  Siguiente: python -m wildfire_front operator do --act 4")
        return 0

    if act == 4:
        # Reuse product wrapper (build + replay default ON)
        ns = argparse.Namespace(
            json=as_json,
            quiet=quiet,
            verbose=verbose,
            skip_build=bool(no_build),
            replay=True,
            no_zip=False,
            output=Path("outputs/demo_third_party"),
            dist=Path("dist"),
        )
        if not quiet:
            print("  Mensaje: replay_ok = consistencia forense, NO firma cripto.")
            print("  GO_Q NO se cierra con este paso (hace falta H1 humana).")
        rc = run_demo_third_party(ns)
        if not quiet and rc == 0:
            print("  Pack OK. Para GO_Q: docs/H1_GO_Q_RUNBOOK.md")
            print("  Checklist: python -m wildfire_front operator checklist")
        return rc

    print(f"error: act {act} no soportado", file=sys.stderr)
    return 1


def run_teach(args: argparse.Namespace) -> int:
    """Print teach path; exit 0 always on success, 1 on invalid/error."""
    try:
        act = getattr(args, "act", None)
        as_json = bool(getattr(args, "json", False))
        verbose = bool(getattr(args, "verbose", False))
        quiet = bool(getattr(args, "quiet", False))

        # Prefer live rails from repo when available (still never invent GO_Q true)
        snap = load_gate_snapshot()
        rails = {
            "GO_MES": snap["gates"].get("GO_MES"),
            "GO_Q": snap["gates"].get("GO_Q", "partial"),
            "ml_product_go": bool(snap["gates"].get("ml_product_go", False)),
            "field_ops_ml_live_fusion": snap["gates"].get("field_ops_ml_live_fusion", "OFF"),
        }

        if as_json:
            payload = build_teach_payload(act=act, rails=rails)
            print_json(payload)
        else:
            text = format_teach_human(act=act, verbose=verbose, quiet=quiet, rails=rails)
            sys.stdout.write(text)
        return 0
    except SystemExit as exc:
        code = exc.code
        if code is None or code == 0:
            return 0
        return int(code) if isinstance(code, int) else 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 1


def run_show(args: argparse.Namespace) -> int:
    """Print gates snapshot; missing pack is informational (exit 0)."""
    try:
        as_json = bool(getattr(args, "json", False))
        verbose = bool(getattr(args, "verbose", False))
        quiet = bool(getattr(args, "quiet", False))
        do_open = bool(getattr(args, "open", False))

        snapshot = load_gate_snapshot()
        if as_json:
            # Strip repo_root absolute path optional; keep for debug but schema-first
            out = {
                "schema": snapshot.get("schema"),
                "as_of_files": snapshot.get("as_of_files"),
                "gates": snapshot.get("gates"),
                "paths": snapshot.get("paths"),
                "presence": snapshot.get("presence"),
                "claims_forbidden": snapshot.get("claims_forbidden"),
                "next_human": snapshot.get("next_human"),
            }
            print_json(out)
        else:
            sys.stdout.write(format_show_human(snapshot, verbose=verbose, quiet=quiet))

        if do_open:
            root = Path(snapshot.get("repo_root") or resolve_repo_root())
            for rel in (
                Path("outputs/demo_multi_ccaa/index.html"),
                Path("outputs/pilot_honesty_card/index.html"),
                Path("docs/PORTAL.html"),
            ):
                target = root / rel
                if target.is_file():
                    webbrowser.open(target.resolve().as_uri())
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _load_script_module(name: str, rel: str, repo: Path) -> Any:
    path = repo / rel
    if not path.is_file():
        raise FileNotFoundError(f"script not found: {path}")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_demo_third_party(args: argparse.Namespace) -> int:
    """Build pack + optional replay. Exit 0/1/2 per design §4.5.4."""
    as_json = bool(getattr(args, "json", False))
    quiet = bool(getattr(args, "quiet", False))
    verbose = bool(getattr(args, "verbose", False))
    skip_build = bool(getattr(args, "skip_build", False))
    do_replay = bool(getattr(args, "replay", True))
    no_zip = bool(getattr(args, "no_zip", False))
    out = Path(getattr(args, "output", Path("outputs/demo_third_party")))
    dist = Path(getattr(args, "dist", Path("dist")))

    repo = resolve_repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    build_status = "skipped"
    rc_build: int | None = None
    summary: dict[str, Any] = {}
    replay_ok: bool | None = None
    rc_replay: int | None = None
    decision = None
    zip_path = None

    try:
        if skip_build:
            if not out.is_dir():
                if not quiet:
                    print(f"error: --skip-build but bundle missing: {out}", file=sys.stderr)
                return 1
            build_status = "skipped"
        else:
            build_mod = _load_script_module(
                "wfd_build_demo_third_party_pack",
                "scripts/build_demo_third_party_pack.py",
                repo,
            )
            summary = build_mod.build_pack(out, make_zip=not no_zip, dist_dir=dist)
            self_ok = bool(summary.get("self_replay_ok"))
            rc_build = 0 if self_ok else 2
            build_status = "OK" if self_ok else "WARN_REPLAY"
            decision = summary.get("decision")
            zip_path = summary.get("zip_path")
            # Hard failure path: build_pack raises on real errors (caught below)

        if do_replay and (skip_build or rc_build in (0, 2) or rc_build is None):
            if not out.is_dir():
                if not quiet:
                    print(f"error: bundle missing for replay: {out}", file=sys.stderr)
                return 1
            from wildfire_front.product.forensics import load_and_replay_bundle

            result = load_and_replay_bundle(out, base=repo)
            replay_ok = bool(result.get("replay_ok"))
            rc_replay = 0 if replay_ok else 2
            if decision is None and isinstance(result.get("card"), dict):
                decision = result["card"].get("decision")
            if verbose and as_json is False and not quiet:
                print(
                    f"  replay detail: expected={result.get('expected_decision')} "
                    f"got={result.get('got_decision')} "
                    f"hash_match={result.get('match_output_hash')}"
                )
        elif not do_replay:
            replay_ok = None
            # self_replay_ok still drives exit via rc_build==2 + --no-replay → 2

        # Exit aggregation (§4.5.4)
        if not skip_build and rc_build is not None and rc_build not in (0, 2):
            exit_code = 1
        elif not skip_build and rc_build == 2 and not do_replay:
            exit_code = 2
        elif do_replay and rc_replay == 1:
            exit_code = 1
        elif do_replay and rc_replay == 2:
            exit_code = 2
        elif not skip_build and rc_build == 2 and do_replay and rc_replay == 0:
            exit_code = 0  # E3 clears self_replay warning
        else:
            exit_code = 0

        payload = {
            "command": "demo-third-party",
            "build": build_status,
            "out": str(out),
            "zip": zip_path if zip_path else ("(skipped)" if no_zip or skip_build else None),
            "decision": decision,
            "policy": summary.get("policy_id") or "field_ops",
            "fusion": "OFF",
            "ml_product_go": True,  # lab product GO (≠ field fusion)
            "replay_ok": replay_ok if do_replay else "(skipped)",
            "self_replay_ok": summary.get("self_replay_ok"),
            "reliability_report": "docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
            "exit_code": exit_code,
            "honesty": ("exit 0 = forensic consistency of pack — not cryptographic authenticity"),
        }

        if as_json:
            print_json(payload)
        elif not quiet:
            print("demo-third-party")
            print(f"  build:  {build_status}")
            print(f"  out:    {out}")
            z = zip_path if zip_path else ("(skipped)" if no_zip or skip_build else "—")
            print(f"  zip:    {z}")
            print(f"  decision: {decision or '—'}  policy={payload['policy']}")
            print("  fusion: OFF  ml_product_go=true")
            print(f"  replay_ok: {payload['replay_ok']}")
            print(f"  reliability_report: {payload['reliability_report']}")
            print("honesty: exit 0 = forensic consistency of pack — not cryptographic authenticity")

        return exit_code

    except FileNotFoundError as exc:
        if not quiet:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        if not quiet:
            print(f"error: {exc}", file=sys.stderr)
        return 1


def run_dry_run_h3(args: argparse.Namespace) -> int:
    """H3 full path dry-run via scripts/run_h3_dry_run_path.py."""
    as_json = bool(getattr(args, "json", False))
    quiet = bool(getattr(args, "quiet", False))
    no_zip = bool(getattr(args, "no_zip", False))
    skip_build = bool(getattr(args, "skip_build", False))
    full_demo = bool(getattr(args, "full_demo", False))
    out = Path(getattr(args, "output", Path("outputs/demo_third_party")))

    repo = resolve_repo_root()
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))

    try:
        mod = _load_script_module(
            "wfd_run_h3_dry_run_path",
            "scripts/run_h3_dry_run_path.py",
            repo,
        )
        report, code = mod.run_path(
            no_zip=no_zip,
            skip_build=skip_build,
            full_demo=full_demo,
            out_dir=out if out.is_absolute() else repo / out,
        )
        if as_json:
            print_json(report)
        elif not quiet:
            print(
                json.dumps(
                    {
                        "command": "dry-run-h3",
                        "h3_eng_path_ok": report.get("h3_eng_path_ok"),
                        "h3_human_attestation_pending": report.get("h3_human_attestation_pending"),
                        "go_q_met": report.get("go_q_met"),
                        "h1_status": report.get("h1_status"),
                        "gates": report.get("gates"),
                        "report": "outputs/demo_third_party/H3_DRY_RUN_REPORT.md",
                        "next": report.get("next"),
                        "exit_code": code,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
        return int(code)
    except FileNotFoundError as exc:
        if not quiet:
            print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        if not quiet:
            print(f"error: {exc}", file=sys.stderr)
        return 1
