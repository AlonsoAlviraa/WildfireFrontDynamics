"""Teach path data, gate snapshot loader, and decide --explain formatter.

Pure helpers for ``wildfire-front teach|show`` and ``decide --explain``.
Does not run demos, flip policies, or invent GO_Q=true.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# ── Repo root (wildfire_front/product/teach_path.py → parents[2]) ─────────


def repo_root() -> Path:
    """Monorepo checkout root when installed from source tree."""
    return Path(__file__).resolve().parents[2]


def resolve_repo_root(preferred: Path | None = None) -> Path:
    """Resolve monorepo root for gate files.

    If ``preferred`` is set, **always** use it (even when gate JSON is missing)
    so callers get fail-soft ``unknown`` gates without a silent cwd fallback.

    When ``preferred`` is None: package-relative root if key docs exist, else cwd
    if it looks like the monorepo, else package root.
    """
    if preferred is not None:
        return Path(preferred)
    root = repo_root()
    if (root / "docs" / "GO_MES_VERDICT.json").is_file() or (
        root / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"
    ).is_file():
        return root
    cwd = Path.cwd()
    if (cwd / "docs" / "GO_MES_VERDICT.json").is_file() or (
        cwd / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"
    ).is_file():
        return cwd
    return root


# ── Rails constants (honesty by construction; never invent GO_Q=true) ────

DEFAULT_RAILS: dict[str, Any] = {
    "GO_MES": True,
    "GO_Q": "partial",
    "ml_product_go": True,  # human promote 2026-08-05 (lab GO ≠ field fusion)
    "field_ops_ml_live_fusion": "OFF",
    "GO_MES_plus": False,
}

KILL_LIST: list[str] = [
    "No field_ops ML live fusion ON",
    "No silent auto_ml_product_go thrash (explicit promote only)",
    "No invent Vp/ha",
    "No IoU = ROS",
    "No GO_Q without M3.2 human acta",
    "No replay_ok = crypto authenticity",
]

CLAIMS_FORBIDDEN: list[str] = [
    "GO_Q complete without M3.2",
    "field_ops ML live fusion ON",
    "silent auto_ml_product_go without promote",
    "replay_ok means cryptographic authenticity",
]

# ── 4-act learning path (constants; not scraped from markdown) ───────────

TEACH_ACTS: list[dict[str, Any]] = [
    {
        "id": 1,
        "name": "ver",
        "title": "Ver (multi-CCAA)",
        "message": "mismos gates, 3 contratos",
        "commands": [
            "python scripts\\build_demo_multi_ccaa.py",
            "start outputs\\demo_multi_ccaa\\index.html  # o abrir en el navegador",
        ],
        "commands_portable": [
            "python scripts/build_demo_multi_ccaa.py",
            "# open outputs/demo_multi_ccaa/index.html",
        ],
        "docs": [
            "docs/design/DEMO_MULTI_CCAA_TOBARRA_NIJAR_CAMINOMORISCO.md",
            "docs/START_HERE.md",
        ],
        "do_not_say": [
            "que multi-CCAA prueba ML táctico en campo",
            "que tres contratos = tres IF grade A",
        ],
    },
    {
        "id": 2,
        "name": "callarse",
        "title": "Callarse (pilot honesty)",
        "message": "field_ops se calla — ABSTAIN is a feature",
        "commands": [
            "python scripts\\run_pilot_honesty_card.py --fixture-root tests\\fixtures\\pilot",
            "start outputs\\pilot_honesty_card\\index.html",
        ],
        "commands_portable": [
            "python scripts/run_pilot_honesty_card.py --fixture-root tests/fixtures/pilot",
            "# open outputs/pilot_honesty_card/index.html",
        ],
        "docs": ["docs/PILOT_HONESTY_CARD.md"],
        "do_not_say": [
            "que ABSTAIN es un bug",
            "que research_open más permisivo invalida field_ops",
        ],
    },
    {
        "id": 3,
        "name": "decidir",
        "title": "Decidir (Decision Card)",
        "message": "GO/HOLD/ABSTAIN — empty sources → ABSTAIN is correct",
        "commands": [
            "python -m wildfire_front decide --list-policies",
            "python -m wildfire_front decide --policy field_ops",
            "python -m wildfire_front decide --policy field_ops --explain",
        ],
        "commands_portable": [
            "python -m wildfire_front decide --list-policies",
            "python -m wildfire_front decide --policy field_ops",
            "python -m wildfire_front decide --policy field_ops --explain",
        ],
        "docs": ["docs/FIRE_DECISION_CARD.json", "docs/PRODUCTO_DUAL.md"],
        "do_not_say": [
            "que field_ops fusiona ML live",
            "que ABSTAIN con fuentes vacías es fallo de producto",
        ],
    },
    {
        "id": 4,
        "name": "probar",
        "title": "Probar (pack + replay)",
        "message": "rastro offline — replay_ok = forensic consistency, NOT crypto authenticity",
        "commands": [
            "python -m wildfire_front demo-third-party --replay",
            "# equiv: python scripts\\build_demo_third_party_pack.py",
            "#        python scripts\\run_third_party_replay.py --bundle outputs\\demo_third_party",
            "# make dry-run-demo-third-party  (H3 human walkthrough support)",
        ],
        "commands_portable": [
            "python -m wildfire_front demo-third-party --replay",
            "# scripts: build_demo_third_party_pack + run_third_party_replay",
        ],
        "docs": [
            "docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
            "docs/METRICS_HONESTY_IOU_NE_ROS.md",
        ],
        "do_not_say": [
            "que replay_ok = firma de tercero o autenticidad criptográfica",
            "que pack verde cierra GO_Q (hace falta H1/M3.2 humana)",
        ],
    },
]

COURSE_PATH = "docs/CURSO_WFD_PARA_DESCONOCIDOS.md"
CHEATSHEET_PATH = "docs/CHEATSHEET_DEMO_12MIN.md"
NEXT_HUMAN = "H1/M3.2 demo+acta (blocks full GO_Q)"

KEY_PATHS: dict[str, str] = {
    "demo_third_party": "outputs/demo_third_party",
    "pack_zip_glob": "dist/demo_third_party_*.zip",
    "reliability_report": "docs/RELIABILITY_GATE_REPORT_THIRD_PARTY.md",
    "iou_ne_ros": "docs/METRICS_HONESTY_IOU_NE_ROS.md",
    "course": COURSE_PATH,
    "cheatsheet": CHEATSHEET_PATH,
    "start_here": "docs/START_HERE.md",
    "acta_template": "docs/ACTA_DEMO_TERCERO_TEMPLATE.md",
    "status_json": "docs/PLAN_1_MES_GRAPH_V6_STATUS.json",
    "go_mes_verdict": "docs/GO_MES_VERDICT.md",
    "portal": "docs/PORTAL.html",
    "guion_30min": "docs/GUION_DEMO_30MIN_POST_O1.md",
    "hellin_scorecard": "docs/HELLIN_TRACK_A_SCORECARD.md",
}


def rails_one_liner(rails: dict[str, Any] | None = None) -> str:
    r = rails or DEFAULT_RAILS
    go_mes = r.get("GO_MES", "unknown")
    go_q = r.get("GO_Q", "partial")
    fusion = r.get("field_ops_ml_live_fusion", "OFF")
    ml_go = r.get("ml_product_go", False)
    return f"GO_MES={go_mes} · GO_Q={go_q} · field_ops ML fusion={fusion} · ml_product_go={ml_go}"


def build_teach_payload(
    *,
    act: int | None = None,
    rails: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Machine payload for ``teach --json`` (schema wfd_teach_path_v1)."""
    r = dict(rails or DEFAULT_RAILS)
    acts = list(TEACH_ACTS)
    if act is not None:
        acts = [a for a in acts if int(a["id"]) == int(act)]
    return {
        "schema": "wfd_teach_path_v1",
        "rails": {
            "GO_MES": r.get("GO_MES"),
            "GO_Q": r.get("GO_Q", "partial"),
            "ml_product_go": bool(r.get("ml_product_go", False)),
            "field_ops_ml_live_fusion": r.get("field_ops_ml_live_fusion", "OFF"),
        },
        "setup": {
            "powershell": ["cd <repo_root>", '$env:PYTHONPATH = "."'],
        },
        "acts": [
            {
                "id": a["id"],
                "name": a["name"],
                "title": a["title"],
                "message": a["message"],
                "commands": list(a.get("commands_portable") or a["commands"]),
                "docs": list(a["docs"]),
                "do_not_say": list(a.get("do_not_say") or []),
            }
            for a in acts
        ],
        "next_human": NEXT_HUMAN,
        "course": COURSE_PATH,
        "cheatsheet": CHEATSHEET_PATH,
        "kill_list": list(KILL_LIST),
    }


def format_teach_human(
    *,
    act: int | None = None,
    verbose: bool = False,
    quiet: bool = False,
    rails: dict[str, Any] | None = None,
) -> str:
    """Human stdout for ``teach`` (Spanish-friendly)."""
    r = rails or DEFAULT_RAILS
    acts = list(TEACH_ACTS)
    if act is not None:
        acts = [a for a in acts if int(a["id"]) == int(act)]

    if quiet:
        lines: list[str] = []
        for a in acts:
            lines.append(f"Acto {a['id']} — {a['title']}")
            lines.append(f"  python -m wildfire_front operator do --act {a['id']}")
        return "\n".join(lines) + "\n"

    lines = [
        "WFD teach path — 4 actos",
        rails_one_liner(r),
        "",
        "Setup (PowerShell):",
        "  cd <repo>",
        '  $env:PYTHONPATH = "."',
        "",
        "Modo operario (recomendado):  python -m wildfire_front operator",
        "",
    ]
    for a in acts:
        lines.append(f"=== Acto {a['id']} — {a['title']} ===")
        lines.append(f"  Mensaje: {a['message']}")
        lines.append(f"  Operario: python -m wildfire_front operator do --act {a['id']}")
        lines.append("  Comandos (equiv.):")
        for c in a["commands"]:
            lines.append(f"    {c}")
        lines.append("  Docs:")
        for d in a["docs"]:
            lines.append(f"    {d}")
        if verbose:
            dns = a.get("do_not_say") or []
            if dns:
                lines.append("  No decir:")
                for item in dns:
                    lines.append(f"    · {item}")
        lines.append("")

    lines.extend(
        [
            "--- Footer ---",
            "  Operator mode:    python -m wildfire_front operator",
            f"  Full course:     {COURSE_PATH}",
            f"  12 min sheet:    {CHEATSHEET_PATH}",
            f"  Next human gate: {NEXT_HUMAN} — not eng alone",
            "  Kill line: never claim field_ops ML live fusion ON",
        ]
    )
    if verbose:
        lines.append("  Kill list:")
        for item in KILL_LIST:
            lines.append(f"    · {item}")
        lines.append("  Portal rebuild (heavy): python scripts\\show_all.py")
    lines.append("")
    return "\n".join(lines)


# ── Gate snapshot loader ─────────────────────────────────────────────────


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None


def _normalize_go_q(value: Any) -> Any:
    """Never invent complete GO_Q true; preserve partial / false / unknown."""
    if value is True or value == "true" or value == "True":
        # Honesty: only allow true if explicitly set in source; still surface as-is
        # for tests that check we don't invent it when missing. Callers pass only
        # values read from files.
        return value
    if value is False:
        return False
    if value is None:
        return None
    if isinstance(value, dict):
        if value.get("met") is True and str(value.get("status", "")).lower() in {
            "complete",
            "true",
            "pass",
            "done",
        }:
            return True
        status = value.get("status")
        if status is not None:
            return status
        if value.get("met") is False:
            return "partial" if status is None else status
        return value.get("status") or "partial"
    return value


def load_gate_snapshot(repo: Path | None = None) -> dict[str, Any]:
    """Load gates from repo JSON + decision_policies; fail soft, never invent GO_Q=true."""
    root = resolve_repo_root(repo)
    go_mes_path = root / "docs" / "GO_MES_VERDICT.json"
    plan_path = root / "docs" / "PLAN_1_MES_GRAPH_V6_STATUS.json"
    policies_path = root / "config" / "decision_policies.json"

    go_mes_doc = _read_json(go_mes_path)
    plan_doc = _read_json(plan_path)
    policies_doc = _read_json(policies_path)

    gates: dict[str, Any] = {
        "GO_MES": None,  # unknown until read
        "GO_Q": None,
        "GO_MES_plus": False,
        "ml_product_go": True,  # human promote 2026-08-05 (lab GO ≠ field fusion)
        "field_ops_ml_live_fusion": "OFF",  # fail-closed default (fusion still OFF)
    }
    sources_status: dict[str, str] = {
        "go_mes_verdict": "ok" if go_mes_doc else "missing",
        "plan_status": "ok" if plan_doc else "missing",
        "policies": "ok" if policies_doc else "missing",
    }

    if go_mes_doc is not None:
        if "GO_MES" in go_mes_doc:
            gates["GO_MES"] = bool(go_mes_doc["GO_MES"])
        if "GO_MES_plus" in go_mes_doc:
            gates["GO_MES_plus"] = bool(go_mes_doc["GO_MES_plus"])

    if plan_doc is not None:
        rails = plan_doc.get("rails") if isinstance(plan_doc.get("rails"), dict) else {}
        g = plan_doc.get("gates") if isinstance(plan_doc.get("gates"), dict) else {}
        if gates["GO_MES"] is None and "GO_MES" in rails:
            gates["GO_MES"] = rails["GO_MES"]
        if "GO_MES_plus" in rails:
            gates["GO_MES_plus"] = rails["GO_MES_plus"]
        if "GO_Q" in rails:
            gates["GO_Q"] = _normalize_go_q(rails["GO_Q"])
        elif "GO_Q" in g:
            gates["GO_Q"] = _normalize_go_q(g["GO_Q"])
        if "ml_product_go" in rails:
            gates["ml_product_go"] = bool(rails["ml_product_go"])
        if "field_ops_ml_live_fusion" in rails:
            fusion = rails["field_ops_ml_live_fusion"]
            if isinstance(fusion, bool):
                gates["field_ops_ml_live_fusion"] = "ON" if fusion else "OFF"
            else:
                gates["field_ops_ml_live_fusion"] = str(fusion)

    # Policy file is source of truth for fusion flag when readable
    if policies_doc is not None:
        policies = policies_doc.get("policies")
        if isinstance(policies, dict):
            field_ops = policies.get("field_ops")
            if isinstance(field_ops, dict) and "allow_ml_live_in_fusion" in field_ops:
                allow = bool(field_ops["allow_ml_live_in_fusion"])
                gates["field_ops_ml_live_fusion"] = "ON" if allow else "OFF"
    elif sources_status["policies"] == "missing":
        # Keep fail-closed OFF if we never had rails either; mark unknown only if
        # neither plan nor policy provided a value — design: prefer fail-closed.
        pass

    # If GO_MES / GO_Q still None after all sources → unknown (do NOT invent true)
    if gates["GO_MES"] is None:
        gates["GO_MES"] = "unknown"
    if gates["GO_Q"] is None:
        gates["GO_Q"] = "unknown"  # never invent true

    presence = {
        "demo_third_party": (root / "outputs" / "demo_third_party").is_dir(),
        "demo_multi_ccaa_index": (root / "outputs" / "demo_multi_ccaa" / "index.html").is_file(),
        "pilot_honesty_index": (root / "outputs" / "pilot_honesty_card" / "index.html").is_file(),
        "go_mes_json": go_mes_path.is_file(),
        "portal_html": (root / "docs" / "PORTAL.html").is_file(),
    }

    return {
        "schema": "wfd_show_snapshot_v1",
        "repo_root": str(root),
        "as_of_files": {
            "go_mes_verdict": "docs/GO_MES_VERDICT.json",
            "plan_status": "docs/PLAN_1_MES_GRAPH_V6_STATUS.json",
            "policies": "config/decision_policies.json",
        },
        "sources_status": sources_status,
        "gates": gates,
        "paths": {
            "demo_third_party": KEY_PATHS["demo_third_party"],
            "reliability_report": KEY_PATHS["reliability_report"],
            "course": KEY_PATHS["course"],
            "cheatsheet": KEY_PATHS["cheatsheet"],
            "acta_template": KEY_PATHS["acta_template"],
            "start_here": KEY_PATHS["start_here"],
            "status_json": KEY_PATHS["status_json"],
            "iou_ne_ros": KEY_PATHS["iou_ne_ros"],
            "pack_zip_glob": KEY_PATHS["pack_zip_glob"],
        },
        "presence": presence,
        "claims_forbidden": list(CLAIMS_FORBIDDEN),
        "next_human": "H1/M3.2",
        "rails_extra": {
            "invent_vp": False,
            "joint_k_tobarra_hellin": False,
            "iou_ne_ros": True,
        },
    }


def format_show_human(
    snapshot: dict[str, Any],
    *,
    verbose: bool = False,
    quiet: bool = False,
) -> str:
    gates = snapshot.get("gates") or {}
    presence = snapshot.get("presence") or {}
    paths = snapshot.get("paths") or {}

    def _g(key: str) -> str:
        v = gates.get(key, "unknown")
        if v is True:
            return "true"
        if v is False:
            return "false"
        return str(v)

    def _ok(flag: bool) -> str:
        return "OK" if flag else "MISSING"

    if quiet:
        return "\n".join(
            [
                f"GO_MES: {_g('GO_MES')}",
                f"GO_Q: {_g('GO_Q')}",
                f"GO_MES+: {_g('GO_MES_plus')}",
                f"ml_product_go: {_g('ml_product_go')}",
                f"field_ops ML live fusion: {_g('field_ops_ml_live_fusion')}",
                "",
            ]
        )

    lines = [
        "=== WFD show — gates snapshot ===",
        "",
        "Gates",
        f"  GO_MES:     {_g('GO_MES'):<12} (docs/GO_MES_VERDICT.md)",
        f"  GO_Q:       {_g('GO_Q'):<12} (blocks: H1/M3.2 human demo+acta — NOT more ML)",
        f"  GO_MES+:    {_g('GO_MES_plus')}",
        f"  ml_product_go: {_g('ml_product_go')}",
        f"  field_ops ML live fusion: {_g('field_ops_ml_live_fusion')}",
        "",
        "Rails",
        "  invent_vp: false | joint_k Tobarra/Hellín: false | IoU≠ROS",
        "",
        "Key paths",
        f"  Third-party pack:     {paths.get('demo_third_party', KEY_PATHS['demo_third_party'])}",
        f"  Pack zip:             {paths.get('pack_zip_glob', KEY_PATHS['pack_zip_glob'])}",
        f"  Reliability report:   {paths.get('reliability_report', KEY_PATHS['reliability_report'])}",
        f"  IoU ≠ ROS:            {paths.get('iou_ne_ros', KEY_PATHS['iou_ne_ros'])}",
        f"  Course:               {paths.get('course', KEY_PATHS['course'])}",
        f"  Cheat sheet 12 min:   {paths.get('cheatsheet', KEY_PATHS['cheatsheet'])}",
        f"  START_HERE:           {paths.get('start_here', KEY_PATHS['start_here'])}",
        f"  Acta template (H1):   {paths.get('acta_template', KEY_PATHS['acta_template'])}",
        f"  Status JSON:          {paths.get('status_json', KEY_PATHS['status_json'])}",
        "",
        "Presence (filesystem)",
        f"  pack dir:     {_ok(bool(presence.get('demo_third_party')))}",
        f"  multi-ccaa:   {_ok(bool(presence.get('demo_multi_ccaa_index')))}",
        f"  pilot html:   {_ok(bool(presence.get('pilot_honesty_index')))}",
        f"  GO_MES json:  {_ok(bool(presence.get('go_mes_json')))}",
        "",
        "Next",
        "  Eng: wildfire-front teach | wildfire-front demo-third-party --replay",
        "  Human: H3 dry-run + H1 demo+acta → GO_Q  (eng cannot close GO_Q)",
    ]
    if verbose:
        lines.extend(
            [
                "",
                "Extra paths (-v)",
                f"  Hellín scorecard:   {KEY_PATHS['hellin_scorecard']}",
                f"  Guion 30 min:       {KEY_PATHS['guion_30min']}",
                f"  Portal:             {KEY_PATHS['portal']}",
                "  Portal rebuild:     python scripts\\show_all.py",
                "",
                "Claims forbidden:",
            ]
        )
        for c in CLAIMS_FORBIDDEN:
            lines.append(f"  · {c}")
    lines.append("")
    return "\n".join(lines)


# ── decide --explain formatter ───────────────────────────────────────────


def load_field_ops_ml_fusion_rail(repo: Path | None = None) -> str:
    """Return ON/OFF for ``field_ops.allow_ml_live_in_fusion``; fail-closed OFF.

    This is the **product rail** for field_ops, independent of the selected
    policy's effective fusion flag (e.g. research_open may allow ML live).
    """
    root = resolve_repo_root(repo)
    policies_doc = _read_json(root / "config" / "decision_policies.json")
    if policies_doc is None:
        return "OFF"
    policies = policies_doc.get("policies")
    if not isinstance(policies, dict):
        return "OFF"
    field_ops = policies.get("field_ops")
    if not isinstance(field_ops, dict):
        return "OFF"
    if "allow_ml_live_in_fusion" not in field_ops:
        return "OFF"
    return "ON" if bool(field_ops["allow_ml_live_in_fusion"]) else "OFF"


def format_decide_explain(
    card: dict[str, Any],
    *,
    repo: Path | None = None,
    field_ops_fusion_rail: str | None = None,
) -> str:
    """Expanded human report for Decision Card teaching (no fusion changes).

    Distinguishes **this_run policy** fusion from the **field_ops product rail**
    so research_open + ML live never mislabels field_ops as ON.
    """
    decision = card.get("decision")
    conf = card.get("confidence_pred")
    conf_s = f"{float(conf):.3f}" if isinstance(conf, (int, float)) else "—"
    label = card.get("confidence_pred_label") or "—"
    audit = card.get("audit") if isinstance(card.get("audit"), dict) else {}
    metrics = card.get("metrics") if isinstance(card.get("metrics"), dict) else {}
    policy_id = card.get("policy_id") or metrics.get("policy_id") or audit.get("policy_id") or "—"
    snap = audit.get("policy_snapshot") if isinstance(audit.get("policy_snapshot"), dict) else {}
    require_ops = snap.get("require_ops_for_go")
    if require_ops is None:
        require_ops = metrics.get("require_ops_for_go")
    allow_ml = metrics.get("allow_ml_live_in_fusion")
    if allow_ml is None:
        allow_ml = snap.get("allow_ml_live_in_fusion")
    allow_ml = bool(allow_ml) if allow_ml is not None else False
    this_run_fusion = "ON" if allow_ml else "OFF"
    # Product rail for field_ops — never copy this_run effective fusion onto field_ops label
    field_ops_rail = field_ops_fusion_rail
    if field_ops_rail is None:
        field_ops_rail = load_field_ops_ml_fusion_rail(repo)

    lines = [
        f"decision: {decision}",
        f"confidence_pred: {conf_s} ({label})",
        f"policy: {policy_id}",
        f"system_reliability_pass: {card.get('system_reliability_pass')}",
        f"latency_ms: {card.get('latency_ms')}",
        "",
        "Policy rails",
        f"  policy_id: {policy_id}",
        f"  require_ops_for_go: {require_ops}",
        f"  this_run policy allow_ml_live: {this_run_fusion}",
        f"  allow_ml_live_in_fusion (effective): {allow_ml}",
        f"  field_ops allow_ml_live_in_fusion: {field_ops_rail}",
        f"  field_ops ML live fusion: {field_ops_rail}",
        "",
        "Sources",
        f"  {'id':<22} {'avail':<6} {'weight':>7} {'conf':>7} {'act':<5} note",
        f"  {'-' * 22} {'-' * 6} {'-' * 7} {'-' * 7} {'-' * 5} ----",
    ]

    sources = card.get("sources") or []
    if not sources:
        lines.append("  (no sources — empty inputs → ABSTAIN is correct)")
    for src in sources:
        if not isinstance(src, dict):
            continue
        sid = str(src.get("id") or "?")
        avail = "yes" if src.get("available") else "no"
        w = src.get("weight")
        w_s = f"{float(w):.2f}" if isinstance(w, (int, float)) else "—"
        c = src.get("confidence")
        c_s = f"{float(c):.2f}" if isinstance(c, (int, float)) else "—"
        act = "yes" if src.get("actionable") else "no"
        notes: list[str] = []
        if src.get("role"):
            notes.append(str(src["role"]))
        if src.get("source_type"):
            notes.append(str(src["source_type"]))
        if src.get("abstained"):
            notes.append("abstained")
        if isinstance(w, (int, float)) and float(w) == 0.0:
            notes.append("not_fused")
        note = ",".join(notes) if notes else "—"
        lines.append(f"  {sid:<22} {avail:<6} {w_s:>7} {c_s:>7} {act:<5} {note}")

    reasons = list(card.get("reasons") or [])
    n_reasons = len(reasons)
    cap = 40
    shown = reasons[:cap]
    lines.append("")
    lines.append(f"Reasons ({n_reasons})" + (f" — showing {cap}" if n_reasons > cap else ""))
    if not shown:
        lines.append("  (none)")
    for r in shown:
        lines.append(f"  · {r}")
    if n_reasons > cap:
        lines.append(f"  … truncated {n_reasons - cap} more")

    disclaimers = list(card.get("disclaimers") or [])
    lines.append("")
    lines.append(f"Disclaimers ({len(disclaimers)})")
    if not disclaimers:
        lines.append("  (none)")
    for d in disclaimers:
        lines.append(f"  · {d}")

    lines.extend(
        [
            "",
            "Teach footnote",
            "  · ml_clm_ensemble weight 0 = holdout provenance, not live certainty",
            "  · IoU ≠ ROS — docs/METRICS_HONESTY_IOU_NE_ROS.md",
            "  · ABSTAIN is a feature (product refuses when sources insufficient)",
            "  · field_ops ML live fusion remains OFF until explicit policy change",
            "",
        ]
    )
    return "\n".join(lines)
