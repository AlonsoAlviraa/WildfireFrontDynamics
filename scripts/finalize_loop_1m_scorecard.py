#!/usr/bin/env python3
"""Month-loop scorecard scaffold (O1–O5 + M1–M4)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def main() -> int:
    anchors = _load(ROOT / "outputs" / "observatorio" / "anchor_scorecard.json")
    if not anchors:
        # regenerate if possible
        try:
            from scripts.score_infocam_anchors import main as score_main  # type: ignore

            score_main()
            anchors = _load(ROOT / "outputs" / "observatorio" / "anchor_scorecard.json")
        except Exception:
            pass

    haus = _load(ROOT / "outputs" / "observatorio" / "hausdorff_multi_if.json")
    inv = _load(ROOT / "docs" / "IF_INVENTORY_S1.json")
    v26 = _load(ROOT / "docs" / "V26_PHYSICS15_VERDICT.json")
    v27 = _load(ROOT / "docs" / "V27_TEMPORAL_VERDICT.json")

    o1 = (anchors.get("O1_multi_anchor") or {}).get("verdict", "UNKNOWN")
    o5 = (anchors.get("O5_second_grade_A") or {}).get("verdict", "UNKNOWN")
    o2 = "BLOCKED"
    if haus.get("o2_official"):
        o2 = "GO"
    elif any((f or {}).get("status") == "OK_PROXY" for f in (haus.get("fires") or [])):
        o2 = "PROXY_ONLY"

    m1 = "OPEN"
    if v27.get("verdict"):
        m1 = v27["verdict"]
        if v27.get("G1") is True:
            m1 = "GO"
        elif v27.get("verdict") == "NO_PROMOTE" and v26.get("verdict") == "NO_PROMOTE":
            # temporal closed only if v27 also done and no further T=3 queued
            if v27.get("next") and "KILL" in str(v27.get("next")).upper():
                m1 = "NO_GO_CLOSED"
            else:
                m1 = f"NO_PROMOTE_PENDING_NEXT ({v27.get('next')})"
    elif v26.get("verdict") == "NO_PROMOTE":
        m1 = "FEATURES_CLOSED_TEMPORAL_PENDING"

    report = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "loop": "1M_MEJORA_CONTINUA",
        "horizon": "2026-07-16 → 2026-08-13",
        "gates": {
            "O1_multi_anchor": o1,
            "O2_hausdorff": o2,
            "O3_temporal_windows": "PARTIAL_OR_UNKNOWN",
            "O4_product": "DOCX_V1_READY",
            "O5_second_grade_A": o5,
            "M1_G1": m1,
            "M2_G2": "GO_clm_v28",
            "M3_stretch": "N/A",
            "M4_dual_product": "READY",
        },
        "honest_ceiling": {
            "O1": "needs external Vp/ha",
            "O2": "needs official perimeter",
            "G1": "v27 RUNNING or verdict pending" if not v27 else v27.get("reason"),
        },
        "inventory_summary": inv.get("summary"),
        "ml": {"v26": v26, "v27": v27 or {"status": "PENDING"}},
        "go_mes": {
            "formula": "(O1 AND O4) OR (O3 AND O4 AND O1_partial)",
            "status": "NOT_YET",
        },
        "docs": {
            "loop": "docs/LOOP_1M_MEJORA_CONTINUA.md",
            "cma_report": "docs/entrega_cma/Informe_tecnico_dinamica_frente_v1.0.docx",
            "correo": "docs/correo_pablo_cma_avances.md",
        },
    }

    out = ROOT / "outputs" / "observatorio" / "loop_1m_scorecard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # also commit-friendly snapshot under docs
    snap = ROOT / "docs" / "LOOP_1M_SCORECARD_SNAPSHOT.json"
    snap.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["gates"], indent=2))
    print("Wrote", out)
    print("Wrote", snap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
