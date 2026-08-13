"""Operator / teach / show / demo-third-party CLI for H1 12-min rehearsal.

Rails: decision-support only. GO_Q stays partial (AMARILLO) until a human
third-party acta is recorded. field_ops ML live fusion follows the stamp
(ON after human 2026-08-13). Fusion ON ≠ GO_Q complete ≠ despacho.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from .product.teach_path import honesty_kill_list, ssot_field_ops_fusion

AddGlobalFlags = Callable[[argparse.ArgumentParser], None]

# Repo root: wildfire_front/..
_ROOT = Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    return _ROOT


def _rel(path: Path, root: Path | None = None) -> str:
    root = root or _repo_root()
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def rails_snapshot() -> dict[str, Any]:
    """Honest product rails for the operator board (not a GO_Q flip)."""
    return {
        "GO_MES": True,
        "GO_Q": "partial",
        "GO_Q_semaforo": "AMARILLO",
        "go_q_met": False,
        "go_q_note": "Needs human third-party demo + signed acta (eng cannot close GO_Q)",
        "field_ops_fusion": ssot_field_ops_fusion(),
        "ml_product_go": "lab_only",
        "disclaimers": [
            "not_validated_tactical_dispatch",
            "ABSTAIN_is_a_feature",
            "replay_ok_is_not_third_party_authenticity",
        ],
    }


def build_checklist(*, root: Path | None = None) -> dict[str, Any]:
    root = root or _repo_root()
    checks = [
        {
            "id": "cheatsheet",
            "path": "docs/CHEATSHEET_DEMO_12MIN.md",
            "ok": (root / "docs/CHEATSHEET_DEMO_12MIN.md").is_file(),
        },
        {
            "id": "h1_runbook",
            "path": "docs/H1_GO_Q_RUNBOOK.md",
            "ok": (root / "docs/H1_GO_Q_RUNBOOK.md").is_file(),
        },
        {
            "id": "pilot_fixtures",
            "path": "tests/fixtures/pilot/pilot_sites.json",
            "ok": (root / "tests/fixtures/pilot/pilot_sites.json").is_file(),
        },
        {
            "id": "demo_multi_ccaa_script",
            "path": "scripts/build_demo_multi_ccaa.py",
            "ok": (root / "scripts/build_demo_multi_ccaa.py").is_file(),
        },
        {
            "id": "pilot_honesty_script",
            "path": "scripts/run_pilot_honesty_card.py",
            "ok": (root / "scripts/run_pilot_honesty_card.py").is_file(),
        },
        {
            "id": "decide_module",
            "path": "wildfire_front/product/decide_service.py",
            "ok": (root / "wildfire_front/product/decide_service.py").is_file(),
        },
        {
            "id": "acta_template_or_draft",
            "path": "docs/ACTA_DEMO_TERCERO_TEMPLATE.md|docs/actas/ACTA_DEMO_PENDING_HUMAN.md",
            "ok": (root / "docs/ACTA_DEMO_TERCERO_TEMPLATE.md").is_file()
            or (root / "docs/actas/ACTA_DEMO_PENDING_HUMAN.md").is_file(),
        },
    ]
    n_ok = sum(1 for c in checks if c["ok"])
    rails = rails_snapshot()
    return {
        "schema": "wfd_operator_checklist_v1",
        "product": "operator_hub",
        "eng_prep_ok": n_ok == len(checks),
        "eng_prep": f"{n_ok}/{len(checks)}",
        "checks": checks,
        "rails": rails,
        "go_q_met": False,
        "semaforo": "AMARILLO",
        "next": [
            "python -m wildfire_front operator do --act 1",
            "python -m wildfire_front operator do --act 2",
            "python -m wildfire_front operator do --act 3",
            "python -m wildfire_front operator do --act 4",
            "After real third-party demo: python scripts/record_h1_demo_complete.py --acta <signed>",
        ],
        "kill_list": [
            honesty_kill_list()[0],
            "No inventar tercero / no firmar acta vacía",
            "No marcar GO_Q complete desde eng",
            "No IoU = ROS",
            "replay_ok ≠ autenticidad de tercero",
        ],
    }


def print_hub(*, as_json: bool = False) -> int:
    checklist = build_checklist()
    rails = checklist["rails"]
    if as_json:
        print(json.dumps({"command": "operator", **checklist}, indent=2, ensure_ascii=False))
        return 0
    print()
    print("  WildfireFrontDynamics · operator (H1 / demo 12 min)")
    print("  " + "─" * 56)
    print(f"  semáforo GO_Q     {checklist['semaforo']} (partial — eng no cierra GO_Q)")
    print(f"  go_q_met          {checklist['go_q_met']}")
    print(f"  field_ops fusion  {rails['field_ops_fusion']}")
    print(f"  ml_product_go     {rails['ml_product_go']}")
    print(f"  eng prep          {checklist['eng_prep']}")
    print()
    print("  4 actos (cheatsheet):")
    print("    1 Ver       wildfire-front operator do --act 1")
    print("    2 Callarse  wildfire-front operator do --act 2")
    print("    3 Decidir   wildfire-front operator do --act 3")
    print("    4 Probar    wildfire-front operator do --act 4")
    print("                (equiv: wildfire-front demo-third-party)")
    print()
    print("  También:  wildfire-front operator checklist")
    print("            wildfire-front teach [--act N]")
    print("            wildfire-front show [--open]")
    print()
    print("  Docs: docs/CHEATSHEET_DEMO_12MIN.md · docs/H1_GO_Q_RUNBOOK.md")
    print()
    return 0


def print_checklist(*, as_json: bool = False) -> int:
    data = build_checklist()
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print()
    print("  WildfireFrontDynamics · operator checklist")
    print("  " + "─" * 56)
    print(f"  semáforo   {data['semaforo']}  ·  go_q_met={data['go_q_met']}")
    print(f"  eng prep   {data['eng_prep']}  ·  eng_prep_ok={data['eng_prep_ok']}")
    print()
    for c in data["checks"]:
        mark = "OK" if c["ok"] else "MISS"
        print(f"  [{mark:<4}] {c['id']:<24} {c['path']}")
    print()
    print(
        f"  Rails: GO_Q=partial · field_ops fusion {ssot_field_ops_fusion()} · "
        "no claim GO_Q complete"
    )
    print("  Next:  wildfire-front operator do --act 1")
    print()
    return 0


def _run_script(script: Path, args: Sequence[str], *, root: Path) -> int:
    if not script.is_file():
        print(f"error: missing script {_rel(script, root)}", file=sys.stderr)
        print(f"  hint: ensure you run from the repo root ({root})", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(script), *args]
    print(f"> {' '.join(cmd)}", flush=True)
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
    return int(proc.returncode)


def _run_module(args: Sequence[str], *, root: Path) -> int:
    cmd = [sys.executable, "-m", "wildfire_front", *args]
    print(f"> {' '.join(cmd)}", flush=True)
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
    return int(proc.returncode)


def run_act(
    act: int,
    *,
    root: Path | None = None,
    open_artifacts: bool = False,
    no_replay: bool = False,
    skip_build: bool = False,
    no_zip: bool = False,
) -> int:
    """Run one cheatsheet act. Returns process exit code."""
    del no_zip
    root = root or _repo_root()
    if act == 1:
        code = _run_script(root / "scripts/build_demo_multi_ccaa.py", [], root=root)
        index = root / "outputs/demo_multi_ccaa/index.html"
        if open_artifacts and index.is_file():
            webbrowser.open(index.resolve().as_uri())
        return code
    if act == 2:
        fixture = root / "tests/fixtures/pilot"
        args = [
            "--mode",
            "offline",
            "--fixture-root",
            str(fixture),
            "--generated-at",
            "2026-08-12T00:00:00+00:00",
        ]
        return _run_script(root / "scripts/run_pilot_honesty_card.py", args, root=root)
    if act == 3:
        return _run_module(
            ["decide", "--policy", "field_ops", "--explain", "--event-id", "h1_rehearsal"],
            root=root,
        )
    if act == 4:
        return run_demo_third_party(
            root=root,
            no_replay=no_replay,
            skip_build=skip_build,
            open_artifacts=open_artifacts,
        )
    print(f"error: unknown act {act} (use 1..4)", file=sys.stderr)
    print("  hint: wildfire-front operator do --act 1", file=sys.stderr)
    return 2


def run_demo_third_party(
    *,
    root: Path | None = None,
    no_replay: bool = False,
    skip_build: bool = False,
    open_artifacts: bool = False,
) -> int:
    """Act 4 rehearsal: Decision Card + forensic pack + optional replay.

    Never sets go_q_met true. Labels limits honestly.
    """
    root = root or _repo_root()
    out = root / "outputs" / "demo_third_party"
    out.mkdir(parents=True, exist_ok=True)

    if not skip_build:
        # Best-effort multi-CCAA so pack folder has visual context; soft if fails.
        multi = root / "scripts/build_demo_multi_ccaa.py"
        if multi.is_file():
            _run_script(multi, [], root=root)

    from .product.decide_service import decide_from_request
    from .product.forensics import load_and_replay_bundle, write_forensic_bundle

    # Honest empty-sources ABSTAIN path (field_ops) + explicit ops fixture if present
    ops_metrics = None
    ops_path = root / "tests/fixtures/pilot/ops_tobarra_min"
    req: dict[str, Any] = {
        "event_id": "demo_third_party_rehearsal",
        "policy_id": "field_ops",
        "require_ops_for_go": True,
        "channel": "operator_demo_third_party",
    }
    # Attach open fixture pack if present (does not invent GO)
    open_and = root / "tests/fixtures/pilot/open_and_min"
    if open_and.is_dir():
        req["open_pack"] = str(open_and)
    if ops_path.is_dir():
        metrics_file = ops_path / "operational_metrics.json"
        if metrics_file.is_file():
            try:
                ops_metrics = json.loads(metrics_file.read_text(encoding="utf-8"))
                req["ops_metrics"] = ops_metrics
            except (OSError, json.JSONDecodeError):
                pass

    card = decide_from_request(req, base=root)
    paths = write_forensic_bundle(
        out,
        card,
        ops_metrics=ops_metrics,
        require_ops_for_go=True,
        operator="h1_rehearsal",
    )
    replay_result: dict[str, Any] | None = None
    if not no_replay:
        replay_result = load_and_replay_bundle(out, base=root)

    summary = {
        "schema": "wfd_demo_third_party_rehearsal_v1",
        "out_dir": _rel(out, root),
        "decision": card.get("decision"),
        "go_q_met": False,
        "semaforo": "AMARILLO",
        "field_ops_fusion": ssot_field_ops_fusion(),
        "paths": paths,
        "replay_ok": None if replay_result is None else bool(replay_result.get("replay_ok")),
        "limits": [
            "Eng rehearsal only — does not close GO_Q",
            "replay_ok means forensic consistency, not third-party attestation",
            "Needs human H1 acta via scripts/record_h1_demo_complete.py",
        ],
    }
    (out / "REHEARSAL_SUMMARY.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    readme = out / "README.md"
    readme.write_text(
        "\n".join(
            [
                "# demo_third_party — H1 rehearsal pack",
                "",
                f"- decision: **{card.get('decision')}**",
                "- GO_Q: **partial (AMARILLO)** · `go_q_met=false`",
                f"- field_ops fusion: **{ssot_field_ops_fusion()}**",
                "- `replay_ok` = offline forensic consistency, **not** third-party authenticity",
                "",
                "Close GO_Q only after a real external demo + signed acta:",
                "`python scripts/record_h1_demo_complete.py --acta docs/actas/ACTA_DEMO_YYYYMMDD_<org>.md`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print("demo-third-party rehearsal written:")
    print(f"  out: {_rel(out, root)}")
    print(f"  decision: {card.get('decision')}")
    print("  go_q_met: False · semáforo: AMARILLO")
    if replay_result is not None:
        print(f"  replay_ok: {replay_result.get('replay_ok')} (not third-party attestation)")
    print(f"  summary: {_rel(out / 'REHEARSAL_SUMMARY.json', root)}")
    if open_artifacts and (out / "fire_decision_acta.md").is_file():
        webbrowser.open((out / "fire_decision_acta.md").resolve().as_uri())
    return 0


_TEACH_ACTS: dict[int, tuple[str, str]] = {
    1: (
        "Ver",
        "Multi-CCAA HTML — mismos gates, 3 contratos (Tobarra OPS · Níjar AND · Caminomorisco EXT).",
    ),
    2: (
        "Callarse",
        "Pilot honesty: field_ops puede ABSTAIN mientras research_open es más permisivo — no es un bug.",
    ),
    3: (
        "Decidir",
        "Decision Card field_ops + explain. Fuentes débiles/vacías → ABSTAIN es correcto.",
    ),
    4: (
        "Probar",
        "Pack + replay_ok. replay_ok = consistencia forense offline, no autenticidad de tercero.",
    ),
}


def print_teach(*, act: int | None = None, as_json: bool = False, run: bool = False) -> int:
    rails = rails_snapshot()
    payload = {
        "command": "teach",
        "rails": rails,
        "semaforo": "AMARILLO",
        "go_q_met": False,
        "acts": [
            {"act": n, "name": name, "message": msg} for n, (name, msg) in _TEACH_ACTS.items()
        ],
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if run and act is not None:
            return run_act(act)
        return 0
    print()
    print("  WildfireFrontDynamics · teach (12 min)")
    print("  " + "─" * 56)
    print(
        f"  semáforo GO_Q  AMARILLO · go_q_met={rails['go_q_met']} · fusion={rails['field_ops_fusion']}"
    )
    print()
    acts = [act] if act is not None else [1, 2, 3, 4]
    for n in acts:
        name, msg = _TEACH_ACTS[n]
        print(f"  Acto {n} — {name}")
        print(f"    {msg}")
        print(f"    run: wildfire-front operator do --act {n}")
        print()
    if run and act is not None:
        return run_act(act)
    return 0


def print_show(*, as_json: bool = False, open_artifacts: bool = False) -> int:
    data = build_checklist()
    artifacts = [
        "docs/CHEATSHEET_DEMO_12MIN.md",
        "docs/H1_GO_Q_RUNBOOK.md",
        "outputs/demo_multi_ccaa/index.html",
        "outputs/demo_third_party/REHEARSAL_SUMMARY.json",
        "docs/commander/index.html",
    ]
    root = _repo_root()
    present: list[dict[str, Any]] = []
    for rel in artifacts:
        p = root / rel
        present.append({"path": rel, "exists": p.is_file()})
    payload = {
        "command": "show",
        "semaforo": data["semaforo"],
        "go_q_met": False,
        "eng_prep": data["eng_prep"],
        "rails": data["rails"],
        "artifacts": present,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print()
        print("  WildfireFrontDynamics · show (gates board)")
        print("  " + "─" * 56)
        print(f"  semáforo   {data['semaforo']}  ·  go_q_met=False")
        print(f"  eng prep   {data['eng_prep']}")
        print(f"  fusion     {data['rails']['field_ops_fusion']}")
        print()
        for a in present:
            mark = "OK" if a["exists"] else "MISS"
            print(f"  [{mark:<4}] {a['path']}")
        print()
        if not any(a["exists"] and "demo_third_party" in a["path"] for a in present):
            print("  tip: wildfire-front demo-third-party   # build rehearsal pack")
            print()

    if open_artifacts:
        for rel in (
            "outputs/demo_multi_ccaa/index.html",
            "docs/commander/index.html",
            "docs/CHEATSHEET_DEMO_12MIN.md",
        ):
            p = root / rel
            if p.is_file():
                webbrowser.open(p.resolve().as_uri())
    return 0


def register_operator_commands(
    commands: argparse._SubParsersAction,
    *,
    add_global_flags: AddGlobalFlags,
) -> None:
    """Register operator, teach, show, demo-third-party on the root CLI."""
    op = commands.add_parser(
        "operator",
        help="H1 / 12-min demo operator hub (AMARILLO while GO_Q partial)",
        description=(
            "Operator board for the third-party demo rehearsal. "
            "Shows AMARILLO while GO_Q is partial. Eng cannot close GO_Q."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  wildfire-front operator\n"
            "  wildfire-front operator checklist\n"
            "  wildfire-front operator do --act 1\n"
            "  wildfire-front operator do --all\n"
        ),
    )
    op_subs = op.add_subparsers(dest="operator_command", required=False, metavar="SUBCOMMAND")

    chk = op_subs.add_parser(
        "checklist",
        help="Eng prep checklist (never claims GO_Q complete)",
    )
    add_global_flags(chk)

    do = op_subs.add_parser(
        "do",
        help="Run cheatsheet act 1..4 (or --all)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "acts:\n"
            "  1 Ver       build_demo_multi_ccaa\n"
            "  2 Callarse  pilot honesty fixtures\n"
            "  3 Decidir   decide --policy field_ops --explain\n"
            "  4 Probar    demo-third-party rehearsal pack + replay\n"
        ),
    )
    do.add_argument("--act", type=int, choices=(1, 2, 3, 4), default=None)
    do.add_argument("--all", action="store_true", help="Run acts 1..4 in order")
    do.add_argument("--open", action="store_true", help="Open HTML/acta artifacts when present")
    do.add_argument("--no-replay", action="store_true", help="Act 4: skip forensic replay")
    do.add_argument("--skip-build", action="store_true", help="Act 4: skip multi-CCAA rebuild")
    add_global_flags(do)
    add_global_flags(op)

    teach = commands.add_parser(
        "teach",
        help="Narrate the 12-min demo acts (optionally run one)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front teach\n  wildfire-front teach --act 3 --run\n",
    )
    teach.add_argument("--act", type=int, choices=(1, 2, 3, 4), default=None)
    teach.add_argument("--run", action="store_true", help="Also execute operator do --act N")
    add_global_flags(teach)

    show = commands.add_parser(
        "show",
        help="Gates / artifacts board for demo prep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="example:\n  wildfire-front show\n  wildfire-front show --open --json\n",
    )
    show.add_argument("--open", action="store_true", help="Open known HTML/docs if present")
    add_global_flags(show)

    demo_tp = commands.add_parser(
        "demo-third-party",
        help="H1 act 4: rehearsal pack + replay (does not close GO_Q)",
        description=(
            "Build outputs/demo_third_party with Decision Card + forensic acta/radio "
            "and optional replay. go_q_met stays false. Not a third-party attestation."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "example:\n"
            "  wildfire-front demo-third-party\n"
            "  wildfire-front demo-third-party --skip-build --no-replay\n"
        ),
    )
    demo_tp.add_argument("--no-replay", action="store_true")
    demo_tp.add_argument("--skip-build", action="store_true")
    demo_tp.add_argument(
        "--no-zip", action="store_true", help="Accepted; zip packaging not required"
    )
    demo_tp.add_argument("--open", action="store_true")
    add_global_flags(demo_tp)


def dispatch_operator_command(args: argparse.Namespace) -> bool:
    """Handle operator/teach/show/demo-third-party. Returns True if handled."""
    cmd = getattr(args, "command", None)
    as_json = bool(getattr(args, "json", False))

    if cmd == "operator":
        sub = getattr(args, "operator_command", None)
        if sub is None:
            raise SystemExit(print_hub(as_json=as_json))
        if sub == "checklist":
            raise SystemExit(print_checklist(as_json=as_json))
        if sub == "do":
            if args.all:
                codes = []
                for n in (1, 2, 3, 4):
                    print(f"\n=== act {n} ===\n", flush=True)
                    codes.append(
                        run_act(
                            n,
                            open_artifacts=bool(getattr(args, "open", False)),
                            no_replay=bool(getattr(args, "no_replay", False)),
                            skip_build=bool(getattr(args, "skip_build", False)),
                        )
                    )
                raise SystemExit(max(codes) if codes else 0)
            if getattr(args, "act", None) is None:
                from .cli_report import print_error

                print_error(
                    "operator do requires --act N or --all",
                    hint="example: wildfire-front operator do --act 1",
                )
                raise SystemExit(2)
            raise SystemExit(
                run_act(
                    int(args.act),
                    open_artifacts=bool(getattr(args, "open", False)),
                    no_replay=bool(getattr(args, "no_replay", False)),
                    skip_build=bool(getattr(args, "skip_build", False)),
                )
            )
        from .cli_report import print_error

        print_error(
            f"unknown operator subcommand: {sub}",
            hint="wildfire-front operator checklist | do --act 1",
        )
        raise SystemExit(2)

    if cmd == "teach":
        raise SystemExit(
            print_teach(
                act=getattr(args, "act", None),
                as_json=as_json,
                run=bool(getattr(args, "run", False)),
            )
        )
    if cmd == "show":
        raise SystemExit(
            print_show(as_json=as_json, open_artifacts=bool(getattr(args, "open", False)))
        )
    if cmd == "demo-third-party":
        raise SystemExit(
            run_demo_third_party(
                no_replay=bool(getattr(args, "no_replay", False)),
                skip_build=bool(getattr(args, "skip_build", False)),
                open_artifacts=bool(getattr(args, "open", False)),
            )
        )
    return False
