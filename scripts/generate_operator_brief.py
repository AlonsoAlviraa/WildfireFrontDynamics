#!/usr/bin/env python3
"""Generate a 1-page operator brief from incident outbox or pack metrics.

Usage:
  python scripts/generate_operator_brief.py --work-dir outputs/incidents/IF_demo
  python scripts/generate_operator_brief.py --from-smoke
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def brief_from_state(state: dict, *, event_id: str) -> str:
    lines = [
        f"# Brief operativo — {event_id}",
        "",
        f"_Generado: {datetime.now(UTC).isoformat()}_",
        "",
        "## Resumen",
        f"- **Evento:** {state.get('event_id', event_id)}",
        f"- **Frames:** {state.get('n_frames_staged') or state.get('n_staged')}",
        f"- **Grado calidad:** {state.get('quality_grade')} ({state.get('quality_label_es') or ''})",
        f"- **ROS primario:** {state.get('primary_ros_m_min')} m/min",
        f"- **Área máx (ha):** {state.get('area_ha_max')}",
        f"- **Ratio vs ancla:** {state.get('speed_vs_ref_ratio')}",
        "",
        "## Uso",
        "- Observación de dinámica de frente desde LWIR (producto **ops**, no ML).",
        "- Envelope 15/30/60 min es **proyección**, no orden táctica.",
        "",
        "## No usar como",
        "- Predicción next-day CLM/NDWS (ver `clm_ensemble_v34` por separado).",
        "- Perímetro oficial ni despacho sin validación humana.",
        "",
        "## Disclaimers",
    ]
    for d in state.get("disclaimers") or [
        "Herramienta de apoyo a la observación; no sustituye el mando.",
    ]:
        lines.append(f"- {d}")
    lines.extend(["", "## Artefactos", ""])
    arts = state.get("artifacts") or {}
    if isinstance(arts, dict):
        for k, v in arts.items():
            lines.append(f"- `{k}`: {v}")
    else:
        lines.append("- (ver outbox/)")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work-dir", type=Path, default=None)
    ap.add_argument("--from-smoke", action="store_true")
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()

    if args.from_smoke:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "smoke_incident_runtime", ROOT / "scripts" / "smoke_incident_runtime.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        rep = mod.synthetic_smoke()
        state = {
            "event_id": "smoke_synthetic",
            "n_frames_staged": rep.get("n_staged"),
            "quality_grade": rep.get("quality_grade"),
            "primary_ros_m_min": rep.get("primary_ros_m_min"),
            "disclaimers": ["Smoke sintético — solo verificación de pipeline."],
        }
        text = brief_from_state(state, event_id="smoke_synthetic")
        out = args.output or (ROOT / "docs" / "BRIEF_SMOKE_EXAMPLE.md")
        out.write_text(text, encoding="utf-8")
        print(json.dumps({"ok": True, "output": str(out)}, indent=2))
        return 0

    if not args.work_dir:
        print("Need --work-dir or --from-smoke", file=sys.stderr)
        return 2
    state_path = Path(args.work_dir) / "outbox" / "incident_state.json"
    if not state_path.is_file():
        print(f"missing {state_path}", file=sys.stderr)
        return 2
    state = json.loads(state_path.read_text(encoding="utf-8"))
    text = brief_from_state(state, event_id=str(state.get("event_id") or args.work_dir.name))
    out = args.output or (Path(args.work_dir) / "outbox" / "operator_brief_1p.md")
    out.write_text(text, encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
