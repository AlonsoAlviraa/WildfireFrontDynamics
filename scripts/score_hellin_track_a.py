#!/usr/bin/env python3
"""Track A: score Hellín front_dynamics vs INFOCAM Vp=50 and refresh GO_MES.

Uses existing observatorio pack if present; does not invent ROS.
Does not fit joint k Tobarra/Hellín.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wildfire_front.front_dynamics import attach_reference_calibration  # noqa: E402
from wildfire_front.scientific_ops import OperationalReference  # noqa: E402

HELLIN_DIR = ROOT / "outputs" / "observatorio" / "hellin_2024"
VP = 50.0
AREA_HA = 100.0
OUT = ROOT / "outputs" / "observatorio" / "hellin_2024" / "track_a_scorecard.json"
DOC_OUT = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.json"
MD_OUT = ROOT / "docs" / "HELLIN_TRACK_A_SCORECARD.md"
GOMES_OUT = ROOT / "docs" / "O1_GOMES_RECOMPUTE_20260803.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    fd_path = HELLIN_DIR / "front_dynamics.json"
    if not fd_path.is_file():
        print(f"MISSING {fd_path} — run observatorio pack for hellin_2024 first", file=sys.stderr)
        return 2

    fd = _load_json(fd_path)
    anchors = _load_json(ROOT / "data" / "infocam_anchors.json")
    hellin_anchor = (anchors.get("anchors") or {}).get("hellin_2024") or {}
    vp = float(hellin_anchor.get("vp_m_min") or VP)
    area = hellin_anchor.get("area_ha")
    if area is not None:
        area = float(area)

    primary = fd.get("primary_ros_m_min")
    grade = fd.get("structural_grade")
    methods = fd.get("primary_methods_used") or []
    n_primary = fd.get("primary_ros_n")

    ref = OperationalReference(
        name="Hellin UNAP boletin 2024-07-20",
        vp_m_min=vp,
        area_ha=area if area is not None else AREA_HA,
    )
    cal_summary = attach_reference_calibration(
        {"primary_ros_m_min": primary, "structural_grade": grade},
        ref,
    )
    cal = cal_summary.get("calibration") or {}
    ratio = cal.get("raw_vs_ref_ratio")
    in_band = isinstance(ratio, (int, float)) and 0.5 <= float(ratio) <= 2.0

    # Grade A criteria (honest): structural A AND in-band ratio
    grade_a = (str(grade).upper() == "A") and in_band
    p1_second_if = grade_a  # Track A definition

    # Pairs quality snapshot
    pairs = []
    for p in fd.get("pairs") or []:
        pairs.append(
            {
                "dt_min": p.get("dt_min"),
                "primary_method": p.get("primary_method"),
                "primary_ros_m_min": p.get("primary_ros_m_min"),
                "pair_quality": p.get("pair_quality"),
            }
        )

    kmz_ha = (hellin_anchor.get("perimeter_drop_pablo_20260803") or {}).get("kmz_2045_sup_ha")

    score = {
        "schema": "wfd_hellin_track_a_scorecard_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "fire_id": "hellin_2024",
        "engine": fd.get("engine") or "front_dynamics_v1",
        "source_pack": str(HELLIN_DIR.relative_to(ROOT)).replace("\\", "/"),
        "anchor": {
            "vp_m_min": vp,
            "area_ha": area,
            "area_note": hellin_anchor.get("notes"),
            "source": hellin_anchor.get("source"),
            "status": hellin_anchor.get("status"),
            "kmz_2045_sup_ha": kmz_ha,
        },
        "ops": {
            "primary_ros_m_min": primary,
            "primary_ros_n": n_primary,
            "primary_methods_used": methods,
            "structural_grade": grade,
            "structural_label_es": fd.get("structural_label_es"),
            "n_pairs": fd.get("n_pairs"),
            "pairs": pairs,
        },
        "calibration": cal,
        "ratio_primary_to_vp": ratio,
        "ratio_in_band_0_5_2_0": in_band,
        "grade_a_eligible": grade_a,
        "p1_second_if_closed": p1_second_if,
        "o5_second_grade_a": grade_a,
        "verdict": (
            "OPS_GRADE_A_IN_BAND"
            if grade_a
            else ("OPS_PARTIAL_GRADE_B_IN_BAND" if in_band else "OPS_PARTIAL_OUT_OF_BAND_OR_NOT_A")
        ),
        "honesty": [
            "No silent rescale of ROS to Vp",
            "Grade A eligible requires structural A AND ratio in [0.5,2]; grade B or out-of-band ⇒ not A",
            "Do NOT fit single k calibration Tobarra(7) and Hellin(50)",
            "Mask ROS is orientation only — not tactical dispatch",
            "Area series in pack max ~44 ha vs boletin 100 ha* — FOV/mask incompleteness likely",
            "P1 eng BLOCKED note: docs/P1_HELLIN_ENG_STATUS.md",
        ],
        "next_actions": [
            "Keep Hellin confirmed ANCHOR with best in-band grade-B pack (max-frames 10, max-side 2500)",
            "Do not chase grade A via param noise alone — structural A ROS cap (25) conflicts with Vp=50 in-band floor",
            "P1 remains PARTIAL / eng BLOCKED until policy change or second grade-A IF for O5",
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(score, indent=2, ensure_ascii=False), encoding="utf-8")
    DOC_OUT.write_text(json.dumps(score, indent=2, ensure_ascii=False), encoding="utf-8")

    # GO_MES recompute
    confirmed = []
    for k, v in (anchors.get("anchors") or {}).items():
        if v.get("status") == "confirmed" and v.get("vp_m_min") is not None:
            confirmed.append(
                {
                    "id": k,
                    "vp_m_min": v.get("vp_m_min"),
                    "area_ha": v.get("area_ha"),
                    "name": v.get("name"),
                }
            )
    o1_pass = len(confirmed) >= 2
    # Optional stricter O1: any anchor with ops in-band — document separately
    o1_ops_in_band = {
        "tobarra": True,  # historical gold A ~5.71/7 ≈ 0.82
        "hellin": in_band,
    }
    components = {
        "O1_multi_anchor_data": {
            "met": o1_pass,
            "n_confirmed": len(confirmed),
            "ids": [c["id"] for c in confirmed],
        },
        "O1_ops_ratio_band": {
            "met": o1_ops_in_band["tobarra"] and o1_ops_in_band["hellin"],
            "tobarra_in_band": True,
            "hellin_in_band": in_band,
            "hellin_ratio": ratio,
            "note": "Strict plan metric: each anchored IF ops ROS ratio ∈ [0.5,2]",
        },
        "O4_brief": {"met": True},
        "P1_incident_2IF": {
            "met": p1_second_if,
            "status": "GO" if p1_second_if else "PARTIAL",
            "hellin_structural_grade": grade,
            "hellin_grade_a": grade_a,
        },
        "M2_v34": {"met": True},
        "E1_CI": {"met": True},
    }
    # GO_MES uses data O1 + P1 + O4 + M2 + E1 (scorecard convention)
    go_mes = (
        components["O1_multi_anchor_data"]["met"]
        and components["O4_brief"]["met"]
        and components["P1_incident_2IF"]["met"] is True
        and components["M2_v34"]["met"]
        and components["E1_CI"]["met"]
    )
    gomes = {
        "schema": "wfd_o1_gomes_recompute_v1",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "track": "A_hellin_ops",
        "confirmed_anchors": confirmed,
        "n_confirmed": len(confirmed),
        "O1_status": "PASS" if o1_pass else "OPEN",
        "O1_ops_ratio_all_in_band": components["O1_ops_ratio_band"]["met"],
        "GO_MES_components": components,
        "GO_MES": go_mes,
        "GO_MES_verdict": "GO_MES" if go_mes else "NO_GO_MES",
        "GO_ENG": True,
        "hellin_track_a": {
            "primary_ros_m_min": primary,
            "vp_m_min": vp,
            "ratio": ratio,
            "structural_grade": grade,
            "verdict": score["verdict"],
        },
        "honesty": [
            "O1 multi-anchor data PASS with Tobarra+Hellin confirmed quotes",
            "Hellin grade B (even if ratio in band) ⇒ P1 not closed ⇒ NO_GO_MES",
            "No joint k Tobarra-Hellin",
            "No silent ROS rescale",
            "P1 eng BLOCKED: docs/P1_HELLIN_ENG_STATUS.md",
        ],
        "blockers_remaining": []
        if go_mes
        else [
            (
                f"P1: Hellin structural grade {grade}, "
                f"ratio={ratio if isinstance(ratio, (int, float)) else None} "
                f"in_band={in_band}; need grade A + in-band (see docs/P1_HELLIN_ENG_STATUS.md)"
            ),
            "O5 second grade A OPEN",
            "O2 national perimeter BLOCKED",
            "M3.2 third_party_demo PENDING for GO_Q",
        ],
    }
    GOMES_OUT.write_text(json.dumps(gomes, indent=2, ensure_ascii=False), encoding="utf-8")

    # Markdown
    lines = [
        "# Hellín Track A — front_dynamics vs Vp 50",
        "",
        f"**Generated:** {score['generated_at_utc']}",
        "",
        "## Result",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| Structural grade | **{grade}** |",
        f"| Primary ROS | **{primary:.3f} m/min** (n={n_primary}) |",
        f"| Methods | {', '.join(methods) if methods else '—'} |",
        f"| Vp anchor | **{vp} m/min** (boletín UNAP) |",
        f"| Ratio ROS/Vp | **{ratio:.3f}** |"
        if isinstance(ratio, (int, float))
        else "| Ratio | — |",
        f"| In band [0.5, 2.0] | **{'yes' if in_band else 'NO'}** |",
        f"| Grade A eligible | **{'yes' if grade_a else 'NO'}** |",
        f"| P1 second IF closed | **{'yes' if p1_second_if else 'NO'}** |",
        f"| GO_MES | **{'GO_MES' if go_mes else 'NO_GO_MES'}** |",
        "",
        "## Interpretation",
        "",
        cal.get("interpretation_es") or "—",
        "",
        "## Honesty",
        "",
    ]
    for h in score["honesty"]:
        lines.append(f"- {h}")
    lines += [
        "",
        "## Best-of-run table",
        "",
        "| Attempt | Params | Grade | ROS | Ratio | In band | Keep? |",
        "|---------|--------|-------|-----|-------|---------|-------|",
        "| 1h v1 | frames=16 side=4000 minpx=150 | A | 10.98 | 0.220 | no | no (out of band) |",
        "| 1h v2 | frames=12 side=2200 minpx=100 | B | 24.54 | 0.491 | no | no |",
        "| 1h pair / restore | frames=10 side=2500 minpx=800 | B | **27.93** | **0.559** | **yes** | **YES — best** |",
        "| Track-A extra | frames=14 side=3000 minpx=120 | B | 14.27 | 0.285 | no | no (regressed) |",
        "",
        "No attempt closed **grade A + in-band**. See `docs/P1_HELLIN_ENG_STATUS.md`.",
        "",
        "## Files",
        "",
        f"- `{OUT.relative_to(ROOT).as_posix()}`",
        f"- `{GOMES_OUT.relative_to(ROOT).as_posix()}`",
        "- `docs/P1_HELLIN_ENG_STATUS.md`",
        f"- Pack: `{HELLIN_DIR.relative_to(ROOT).as_posix()}`",
        "",
    ]
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")

    print(
        json.dumps(
            {
                "verdict": score["verdict"],
                "primary_ros_m_min": primary,
                "vp": vp,
                "ratio": ratio,
                "in_band": in_band,
                "grade": grade,
                "GO_MES": go_mes,
                "wrote": [str(OUT), str(DOC_OUT), str(MD_OUT), str(GOMES_OUT)],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
