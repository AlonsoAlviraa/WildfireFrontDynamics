"""Metrics lift board + kill-criteria helpers for multi-fire LOFO G1/G2.

Lab ML only (``clm_ensemble_v34``). Seals frozen baselines, writes
``wfd_ml_metrics_lift_board_v1``, and stamps T1/T2 north-star fields.

Rails (immutable):
* field fusion OFF; IoU ≠ ROS
* no ECE thrash same TEST; no Tobarra KEEP reopen; no larger U-Net default
* thr VAL-locked; no test-set thr fit
* T1 KEEP ≠ T2 north-star (G1 ∧ G2)
* rails from ``product_facade.DEFAULT_RAILS`` + scorecard only

Does **not** retrain. Does **not** claim KEEP without scoring.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal

from wildfire_front.ml.product_facade import (
    DEAD_PATHS,
    DEFAULT_PRODUCT_ID,
    DEFAULT_RAILS,
    ITER1_LOCKED_REJECT_THR,
    RECOMMENDED_LAB_SURFACE,
    ProductFacadeError,
    assert_lab_rails,
    refuse_dead_path,
)
from wildfire_front.ml.protocol_rails import (
    FORBIDDEN_THRASH_PATHS,
    assert_rails_honest,
    assert_split_role,
)

# ---------------------------------------------------------------------------
# Identity / schema
# ---------------------------------------------------------------------------

SCHEMA: Final = "wfd_ml_metrics_lift_board_v1"
KILL_SCHEMA: Final = "wfd_ml_metrics_lift_kill_v1"
PRODUCT_ID: Final = DEFAULT_PRODUCT_ID
PRODUCT_RAIL: Final = "lab_ml"
RAILS_SOURCE: Final = "product_facade.DEFAULT_RAILS+scorecard"
_PIPELINE: Final = "features→calibrator→rank/reject→scorecard"
_FACADE: Final = "wildfire_front.ml.product_facade"
_BANNER: Final = "lab product · not field_ops fusion · IoU ≠ ROS · metrics lift"

# Core-3 LOFO folds used for G1/G2 comparability (Tobarra stress-only).
CORE3_FOLDS: Final = (
    "CARDOSO",
    "LA_ESTRELLA_ACOM1",
    "LA_ESTRELLA_ACOM2",
)
CORE3_FOLD_BASELINES: Final = {
    "CARDOSO": 0.7978106779815259,
    "LA_ESTRELLA_ACOM1": 0.7831634770802975,
    "LA_ESTRELLA_ACOM2": 0.6931861844919686,
}

# Locked baselines (design §3 / §4.2) — do not invent different numbers.
BASELINE_LOFO_MEAN: Final = 0.7580534465179306
BASELINE_LOFO_MIN: Final = 0.6931861844919686
BASELINE_WEAK_FOLD: Final = "LA_ESTRELLA_ACOM2"
BASELINE_U1_IOU: Final = 0.8568865373678947
BASELINE_U1_ECE: Final = 0.15280955026564416
BASELINE_REJECT_THR: Final = float(ITER1_LOCKED_REJECT_THR)  # ~0.795
BASELINE_REJECT_ACCEPTED_IOU: Final = 0.9492431452930816
BASELINE_CATALOG_HOLDOUT: Final = 0.8963

# North-star targets (T2) and floors
G1_TARGET: Final = 0.780
G2_TARGET: Final = 0.720
G1_FLOOR: Final = 0.750
G2_FLOOR: Final = 0.690
L2_PASS_THR: Final = 0.700  # KEEP gate for floor (non-E4)
L2_TARGET_THR: Final = 0.720  # G2 report / E4 KEEP
U1_REGRESS_EPS: Final = 0.01  # MEASURED L4: baseline − 0.01

# Core sources never treated as "new-fire" for D3
CORE_AND_STRESS_SOURCES: Final = frozenset(
    {
        "CARDOSO",
        "LA_ESTRELLA_ACOM1",
        "LA_ESTRELLA_ACOM2",
        "tobarra_20240802",
    }
)

DEFAULT_BOARD_PATH: Final = Path("outputs/ml_eval/lab_loop/lab_loop_v34_metrics_lift_latest.json")
DEFAULT_LEAK_AUDIT_PATH: Final = Path("outputs/ml_eval/lab_loop/lofo_pack_leak_audit_latest.json")

KillVerdict = Literal["PENDING", "KEEP", "KILL", "INCONCLUSIVE"]
TierName = Literal["T1_KEEP_MEMBER", "T2_NORTH_STAR", "none"]
U1Status = Literal["SKIPPED", "MEASURED", "REQUIRED_MISSING"]
ProfileName = Literal["E2", "E3", "E4", "E5"]


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def sealed_baselines() -> dict[str, Any]:
    """Frozen baseline block for the metrics lift board (design §4.2)."""
    return {
        "lofo_mean_iou": BASELINE_LOFO_MEAN,
        "lofo_min_iou": BASELINE_LOFO_MIN,
        "lofo_weakest_fold": BASELINE_WEAK_FOLD,
        "u1_test_mean_iou": BASELINE_U1_IOU,
        "u1_ece": BASELINE_U1_ECE,
        "reject_thr": BASELINE_REJECT_THR,
        "reject_accepted_iou": BASELINE_REJECT_ACCEPTED_IOU,
        "catalog_holdout_iou_provenance_only": BASELINE_CATALOG_HOLDOUT,
        "core3_fold_baselines": dict(CORE3_FOLD_BASELINES),
        "g1_target": G1_TARGET,
        "g2_target": G2_TARGET,
        "l2_pass_threshold": L2_PASS_THR,
        "l2_target_threshold": L2_TARGET_THR,
        "u1_regress_eps": U1_REGRESS_EPS,
    }


def assert_dead_paths_closed() -> None:
    """Hard-seal ECE thrash + Tobarra KEEP reopen + fusion auto-on."""
    for dead in (
        "same_holdout_ece_retune",
        "tobarra_keep_reopen_same_recipe",
        "tobarra_keep_reopen_kill_weights",
        "field_ops_ml_live_fusion_on",
        "auto_ml_product_go",
    ):
        try:
            refuse_dead_path(dead)
        except ProductFacadeError:
            pass  # expected sealed
        else:
            if dead in DEAD_PATHS:
                raise ProductFacadeError(f"dead path still open: {dead!r}")


def metrics_lift_rails() -> dict[str, Any]:
    """Dual-product rails from product_facade + scorecard (not stale next_gate)."""
    r = assert_lab_rails(DEFAULT_RAILS)
    rails: dict[str, Any] = {
        **r.as_dict(),
        "banner": _BANNER,
        "product_id": PRODUCT_ID,
        "product_rail": PRODUCT_RAIL,
        "field_rail": "field_ops",
        "ml_product_go": True,
        "field_ops_allow_ml_live_in_fusion": False,
        "field_ops_ml_live_fusion": "OFF",
        "field_fusion_off": True,
        "iou_is_not_ros": True,
        "lofo_is_not_u1_ece": True,
        "val_only_threshold_tune": True,
        "val_only_threshold_selection": True,
        "test_never_used_for_tune": True,
        "stop_ece_thrash_on_same_test": True,
        "no_ece_retune_same_holdout": True,
        "tobarra_keep_reopen": False,
        "tobarra_keep_reopen_forbidden": True,
        "larger_unet_default": False,
        "recommended_lab_surface": RECOMMENDED_LAB_SURFACE,
        "locked_reject_thr": float(ITER1_LOCKED_REJECT_THR),
        "freeze_iter1_reject": True,
        "rails_source": RAILS_SOURCE,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "dead_paths": sorted(set(DEAD_PATHS) | set(FORBIDDEN_THRASH_PATHS)),
        "label": "lab / research_open only",
    }
    assert_rails_honest(rails, require_iter1_reject_default=True)
    return rails


def north_star_flags(
    lofo_mean: float | None,
    lofo_min: float | None,
) -> dict[str, bool]:
    """T2 flags: G1 mean ≥ 0.780 and G2 min ≥ 0.720. Independent of T1 KEEP."""
    g1 = lofo_mean is not None and float(lofo_mean) >= G1_TARGET
    g2 = lofo_min is not None and float(lofo_min) >= G2_TARGET
    return {
        "g1_met": bool(g1),
        "g2_met": bool(g2),
        "design_success_closed": bool(g1 and g2),
    }


def l2_floor_checks(lofo_min: float | None, *, profile: str = "E2") -> dict[str, Any]:
    """L2_pass (KEEP gate) vs L2_target_met (G2 report).

    Non-E4: L2_pass = min ≥ 0.700; L2_target_met = min ≥ 0.720 (report only).
    E4: KEEP uses threshold 0.720 (C1 mapped to L2).
    """
    thr = L2_TARGET_THR if str(profile).upper() == "E4" else L2_PASS_THR
    value = float(lofo_min) if lofo_min is not None else None
    l2_pass = value is not None and value >= thr
    l2_target_met = value is not None and value >= L2_TARGET_THR
    return {
        "pass": bool(l2_pass) if value is not None else False,
        "value": value,
        "threshold": thr,
        "L2_pass": bool(l2_pass) if value is not None else False,
        "L2_target_met": bool(l2_target_met) if value is not None else False,
        "profile": str(profile).upper(),
        "note": (
            "KEEP uses L2_pass only; L2_target_met is G2 report"
            if str(profile).upper() != "E4"
            else "E4 C1: KEEP uses L2 threshold 0.720"
        ),
    }


def l4_u1_check(
    u1_iou: float | None,
    *,
    champion_candidate: bool = False,
    u1_status: U1Status | str | None = None,
) -> dict[str, Any]:
    """L4 U1 secondary — SKIPPED ≠ pass; champion path requires MEASURED."""
    if u1_status is None:
        if u1_iou is None:
            u1_status = "REQUIRED_MISSING" if champion_candidate else "SKIPPED"
        else:
            u1_status = "MEASURED"
    status = str(u1_status).upper()
    thr = U1_REGRESS_EPS
    floor = BASELINE_U1_IOU - thr
    if status == "SKIPPED":
        return {
            "pass": None,  # not true — exempt when champion_candidate=false
            "status": "SKIPPED",
            "delta_u1": None,
            "threshold": thr,
            "u1_floor": floor,
            "u1_iou": None,
            "champion_candidate": bool(champion_candidate),
            "note": "SKIPPED ≠ pass; research T1 OK when champion_candidate=false",
        }
    if status == "REQUIRED_MISSING" or (champion_candidate and u1_iou is None):
        return {
            "pass": False,
            "status": "REQUIRED_MISSING",
            "delta_u1": None,
            "threshold": thr,
            "u1_floor": floor,
            "u1_iou": None,
            "champion_candidate": bool(champion_candidate),
            "note": "Champion/PR4 path requires MEASURED U1; missing → hard fail",
        }
    # MEASURED
    val = float(u1_iou) if u1_iou is not None else None
    delta = (val - BASELINE_U1_IOU) if val is not None else None
    ok = val is not None and val >= floor
    return {
        "pass": bool(ok),
        "status": "MEASURED",
        "delta_u1": delta,
        "threshold": thr,
        "u1_floor": floor,
        "u1_iou": val,
        "champion_candidate": bool(champion_candidate),
        "note": f"MEASURED requires u1_iou >= {floor:.4f} (baseline − 0.01)",
    }


def collect_candidate_from_root(candidate_root: Path) -> dict[str, Any]:
    """Scan ``{candidate-root}/{FOLD}/evaluation_metrics.json`` for core-3 + expanded."""
    folds: dict[str, dict[str, Any]] = {}
    if not candidate_root.is_dir():
        return {
            "folds": folds,
            "core3": {"mean": None, "min": None, "n": 0, "rows": []},
            "expanded": {"mean": None, "min": None, "n": 0, "rows": []},
            "complete": False,
        }
    for fold_dir in sorted(p for p in candidate_root.iterdir() if p.is_dir()):
        em_path = fold_dir / "evaluation_metrics.json"
        em = load_json(em_path)
        if not em:
            continue
        model_iou = em.get("model_iou")
        copy_iou = em.get("copy_baseline_iou")
        delta = em.get("improvement_vs_copy_iou")
        if delta is None and model_iou is not None and copy_iou is not None:
            delta = float(model_iou) - float(copy_iou)
        n_test = em.get("test_samples") or em.get("n_test") or em.get("n_samples")
        if n_test is None:
            # try thresh block sample count
            t05 = em.get("thresh_0.5") or {}
            if isinstance(t05, dict):
                full = t05.get("model_full") or {}
                if isinstance(full, dict):
                    n_test = full.get("n_samples")
        folds[fold_dir.name] = {
            "fold": fold_dir.name,
            "model_iou": float(model_iou) if model_iou is not None else None,
            "copy_baseline_iou": float(copy_iou) if copy_iou is not None else None,
            "improvement_vs_copy_iou": float(delta) if delta is not None else None,
            "n_test": int(n_test) if n_test is not None else None,
            "path": str(em_path.as_posix()),
        }

    def _agg(names: list[str]) -> dict[str, Any]:
        rows = [folds[n] for n in names if n in folds and folds[n].get("model_iou") is not None]
        ious = [float(r["model_iou"]) for r in rows]
        return {
            "mean": (sum(ious) / len(ious)) if ious else None,
            "min": min(ious) if ious else None,
            "n": len(ious),
            "rows": rows,
            "fold_names": [r["fold"] for r in rows],
        }

    core3 = _agg(list(CORE3_FOLDS))
    # Expanded = all non-Tobarra folds with metrics (core-3 + any new-fire)
    expanded_names = [
        n for n in folds if "tobarra" not in n.lower() and folds[n].get("model_iou") is not None
    ]
    expanded = _agg(sorted(expanded_names))
    complete = core3["n"] >= 3 and all(
        folds.get(f, {}).get("model_iou") is not None for f in CORE3_FOLDS
    )
    return {
        "folds": folds,
        "core3": core3,
        "expanded": expanded,
        "complete": complete,
    }


def collect_candidate_from_board(board: dict[str, Any]) -> dict[str, Any]:
    """Parse a pre-built LOFO board JSON (lab_loop or lab_lofo_board schema)."""
    folds: dict[str, dict[str, Any]] = {}
    # lab_loop wrapper: board.board.folds or board.folds or lofo.folds
    candidates: list[Any] = []
    if isinstance(board.get("folds"), list):
        candidates = board["folds"]
    elif isinstance(board.get("board"), dict) and isinstance(board["board"].get("folds"), list):
        candidates = board["board"]["folds"]
    elif isinstance(board.get("lofo"), dict) and isinstance(board["lofo"].get("folds"), list):
        candidates = board["lofo"]["folds"]
    for row in candidates:
        if not isinstance(row, dict):
            continue
        name = str(row.get("fold") or row.get("held") or "")
        if not name:
            continue
        model_iou = row.get("model_iou")
        if model_iou is None:
            model_iou = row.get("test_iou")
        copy_iou = row.get("copy_baseline_iou")
        delta = row.get("improvement_vs_copy_iou")
        if delta is None and model_iou is not None and copy_iou is not None:
            delta = float(model_iou) - float(copy_iou)
        folds[name] = {
            "fold": name,
            "model_iou": float(model_iou) if model_iou is not None else None,
            "copy_baseline_iou": float(copy_iou) if copy_iou is not None else None,
            "improvement_vs_copy_iou": float(delta) if delta is not None else None,
            "n_test": row.get("n_test") or row.get("test_samples") or row.get("n_samples_thresh05"),
            "path": row.get("path"),
        }

    def _agg(names: list[str]) -> dict[str, Any]:
        rows = [folds[n] for n in names if n in folds and folds[n].get("model_iou") is not None]
        ious = [float(r["model_iou"]) for r in rows]
        return {
            "mean": (sum(ious) / len(ious)) if ious else None,
            "min": min(ious) if ious else None,
            "n": len(ious),
            "rows": rows,
            "fold_names": [r["fold"] for r in rows],
        }

    core3 = _agg(list(CORE3_FOLDS))
    expanded_names = [n for n in folds if "tobarra" not in n.lower()]
    expanded = _agg(sorted(expanded_names))
    # Prefer summary keys when present and core3 incomplete
    summ = board.get("summary") if isinstance(board.get("summary"), dict) else {}
    if isinstance(board.get("board"), dict):
        bsum = board["board"].get("summary")
        if isinstance(bsum, dict):
            summ = {**summ, **bsum}
    if core3["mean"] is None and summ.get("model_iou_mean") is not None:
        core3["mean"] = float(summ["model_iou_mean"])
        core3["min"] = (
            float(summ["model_iou_min"]) if summ.get("model_iou_min") is not None else None
        )
        core3["n"] = int(summ.get("n_folds") or 0)
    complete = core3["n"] >= 3 or (
        core3["mean"] is not None and core3["min"] is not None and len(core3["rows"]) >= 3
    )
    return {
        "folds": folds,
        "core3": core3,
        "expanded": expanded,
        "complete": complete,
        "summary": summ,
    }


def delta_or_none(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return float(a) - float(b)


def resolve_tier(
    *,
    kill_verdict: str,
    north_star: dict[str, bool],
) -> TierName:
    if north_star.get("design_success_closed"):
        return "T2_NORTH_STAR"
    if str(kill_verdict).upper() == "KEEP":
        return "T1_KEEP_MEMBER"
    return "none"


def empty_candidate(
    *,
    experiment_id: str = "baselines_only",
    champion_candidate: bool = False,
    status: str = "NO_RUN",
) -> dict[str, Any]:
    return {
        "experiment_id": experiment_id,
        "champion_candidate": bool(champion_candidate),
        "status": status,
        "lofo_mean_iou": None,
        "lofo_min_iou": None,
        "u1_test_mean_iou": None,
        "u1_status": "SKIPPED",
        "delta_lofo_mean": None,
        "delta_lofo_min": None,
        "delta_u1": None,
        "core3_folds": {},
        "expanded_mean_iou": None,
        "all_beat_copy": None,
        "weakest_fold": None,
    }


def build_metrics_lift_board(
    root: Path,
    *,
    candidate_root: Path | None = None,
    candidate_board: Path | dict[str, Any] | None = None,
    experiment_id: str = "baselines_only",
    champion_candidate: bool = False,
    kill_verdict: KillVerdict | str = "PENDING",
    u1_iou: float | None = None,
    u1_status: U1Status | str | None = None,
    baselines_only: bool = False,
    extra_candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build machine-readable metrics lift board (schema wfd_ml_metrics_lift_board_v1)."""
    assert_split_role("lofo", "scorecard")
    assert_dead_paths_closed()
    rails = metrics_lift_rails()
    baselines = sealed_baselines()

    cand = empty_candidate(
        experiment_id=experiment_id,
        champion_candidate=champion_candidate,
        status="BASELINES_ONLY" if baselines_only else "PENDING",
    )
    fold_detail: dict[str, Any] = {}
    complete = False

    if not baselines_only:
        collected: dict[str, Any] | None = None
        if candidate_board is not None:
            if isinstance(candidate_board, Path):
                board_data = load_json(candidate_board) or {}
            else:
                board_data = candidate_board
            collected = collect_candidate_from_board(board_data)
        elif candidate_root is not None:
            collected = collect_candidate_from_root(Path(candidate_root))

        if collected:
            fold_detail = collected.get("folds") or {}
            core3 = collected["core3"]
            expanded = collected["expanded"]
            complete = bool(collected.get("complete"))
            mean = core3.get("mean")
            mn = core3.get("min")
            cand["lofo_mean_iou"] = mean
            cand["lofo_min_iou"] = mn
            cand["delta_lofo_mean"] = delta_or_none(mean, BASELINE_LOFO_MEAN)
            cand["delta_lofo_min"] = delta_or_none(mn, BASELINE_LOFO_MIN)
            cand["expanded_mean_iou"] = expanded.get("mean")
            cand["core3_folds"] = {r["fold"]: r for r in (core3.get("rows") or [])}
            rows = core3.get("rows") or []
            if rows:
                weak = min(rows, key=lambda r: float(r["model_iou"]))
                cand["weakest_fold"] = weak.get("fold")
                beats = [
                    r.get("improvement_vs_copy_iou") is not None
                    and float(r["improvement_vs_copy_iou"]) > 0
                    for r in rows
                ]
                cand["all_beat_copy"] = all(beats) if beats else None
            if complete:
                cand["status"] = "MEASURED"
            elif mean is not None:
                cand["status"] = "PARTIAL"
            else:
                cand["status"] = "NO_RUN"

    # U1 secondary
    if u1_status is None and u1_iou is None:
        u1_status = "SKIPPED"
    l4 = l4_u1_check(
        u1_iou,
        champion_candidate=champion_candidate,
        u1_status=u1_status,
    )
    cand["u1_test_mean_iou"] = l4.get("u1_iou")
    cand["u1_status"] = l4.get("status")
    cand["delta_u1"] = l4.get("delta_u1")
    if extra_candidate:
        cand.update(extra_candidate)

    ns = north_star_flags(cand.get("lofo_mean_iou"), cand.get("lofo_min_iou"))
    # Never auto-close design from incomplete / baselines-only
    if baselines_only or cand.get("status") in ("NO_RUN", "BASELINES_ONLY", "PENDING"):
        ns = {"g1_met": False, "g2_met": False, "design_success_closed": False}

    kv = str(kill_verdict).upper()
    if baselines_only:
        kv = "PENDING"
    # KEEP without measured core-3 is dishonest — force PENDING/INCONCLUSIVE
    if kv == "KEEP" and not complete and cand.get("status") != "MEASURED":
        kv = "INCONCLUSIVE"

    tier = resolve_tier(kill_verdict=kv, north_star=ns)
    rails_ok = (
        rails.get("field_ops_allow_ml_live_in_fusion") is False
        and rails.get("iou_is_not_ros") is True
    )

    board: dict[str, Any] = {
        "schema": SCHEMA,
        "created_utc": datetime.now(UTC).isoformat(),
        "product_id": PRODUCT_ID,
        "product_rail": PRODUCT_RAIL,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "rails_source": RAILS_SOURCE,
        "rails": rails,
        "rails_ok": rails_ok,
        "banner": _BANNER,
        "pipeline": _PIPELINE,
        "product_facade": _FACADE,
        "baselines": baselines,
        "candidate": cand,
        "fold_detail": fold_detail,
        "north_star": ns,
        "kill_verdict": kv,
        "tier": tier,
        "north_star_g1_met": ns["g1_met"],
        "north_star_g2_met": ns["g2_met"],
        "design_success_closed": ns["design_success_closed"],
        "l2_floor": l2_floor_checks(cand.get("lofo_min_iou"), profile="E2"),
        "l4_u1": l4,
        "honesty": [
            "IoU ≠ ROS",
            "field fusion OFF",
            "T1 KEEP ≠ T2 north-star (G1∧G2)",
            "L2_pass (min≥0.700) decides KEEP floor; L2_target_met is G2 report",
            "L4 SKIPPED ≠ pass; champion path requires MEASURED (−0.01)",
            "core-3 mean is G1 primary; expanded mean secondary",
            "Tobarra stress-only; KEEP reopen forbidden",
            "Do not claim KEEP without scoring",
            "rails from product_facade + scorecard only (not stale next_gate)",
        ],
        "paths": {
            "board_latest": str(DEFAULT_BOARD_PATH.as_posix()),
            "lofo_board_latest": "outputs/ml_eval/lab_loop/lab_loop_v34_lofo_board_latest.json",
            "leak_audit": str(DEFAULT_LEAK_AUDIT_PATH.as_posix()),
        },
        "cli": {
            "baselines_only": "python scripts/run_lab_ml_loop_v34_metrics_lift.py --baselines-only",
            "candidate_root": (
                "python scripts/run_lab_ml_loop_v34_metrics_lift.py "
                "--candidate-root outputs/ml_eval/lofo_v1_recover_v2_kaggle "
                "--experiment-id E_recover_v2_sealed_multi_if "
                "--kill-verdict KEEP"
            ),
            "kill_scorer": (
                "python scripts/score_metrics_lift_kill_criteria.py --profile E2 "
                "--candidate-root outputs/ml_eval/lofo_v1_recover_v2_kaggle "
                "--experiment-id E_recover_v2_sealed_multi_if --write-board"
            ),
        },
    }
    return board


def write_metrics_lift_board(
    board: dict[str, Any],
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    return out_path


def l1_threshold_for_profile(profile: str) -> dict[str, Any]:
    p = str(profile).upper()
    if p == "E2":
        return {"mode": "lift", "threshold": 0.010}
    if p == "E3":
        return {"mode": "lift", "threshold": 0.015}
    if p == "E4":
        return {"mode": "no_regress_0.005", "threshold": 0.005}
    if p == "E5":
        return {"mode": "optional", "threshold": 0.0}
    return {"mode": "lift", "threshold": 0.015}


def evaluate_l1(
    mean: float | None,
    *,
    profile: str,
    baseline: float = BASELINE_LOFO_MEAN,
) -> dict[str, Any]:
    spec = l1_threshold_for_profile(profile)
    mode = spec["mode"]
    thr = float(spec["threshold"])
    if mean is None:
        return {
            "pass": False,
            "delta": None,
            "threshold": thr,
            "value_mean": None,
            "mode": mode,
            "incomplete": True,
        }
    delta = float(mean) - float(baseline)
    if mode == "lift":
        ok = delta >= thr
    elif mode == "no_regress_0.005":
        ok = float(mean) >= float(baseline) - thr
    else:  # optional E5
        ok = True
    return {
        "pass": bool(ok),
        "delta": delta,
        "threshold": thr,
        "value_mean": float(mean),
        "mode": mode,
        "incomplete": False,
    }


def is_new_fire_fold(fold_name: str) -> bool:
    return str(fold_name) not in CORE_AND_STRESS_SOURCES and "tobarra" not in fold_name.lower()


def d3_applicability(
    folds: dict[str, dict[str, Any]],
    *,
    min_n_test: int = 50,
) -> dict[str, Any]:
    """D3 new-fire fold gate (E3). SKIPPED when not applicable — not FAIL."""
    candidates: list[dict[str, Any]] = []
    for name, row in (folds or {}).items():
        if not is_new_fire_fold(name):
            continue
        n_test = row.get("n_test")
        try:
            n_i = int(n_test) if n_test is not None else 0
        except (TypeError, ValueError):
            n_i = 0
        if n_i >= min_n_test:
            candidates.append({**row, "fold": name, "n_test": n_i})
    if not candidates:
        return {
            "applicable": False,
            "status": "SKIPPED",
            "pass": None,
            "delta_vs_copy": None,
            "threshold": 0.05,
            "n_test": None,
            "fold": None,
            "note": ("SKIPPED when no new-fire LOFO fold with n_test>=50; does not block KEEP"),
        }
    # Prefer best-documented first candidate (sorted by fold name for stability)
    cand = sorted(candidates, key=lambda r: str(r.get("fold")))[0]
    delta = cand.get("improvement_vs_copy_iou")
    ok = delta is not None and float(delta) >= 0.05
    return {
        "applicable": True,
        "status": "MEASURED",
        "pass": bool(ok),
        "delta_vs_copy": float(delta) if delta is not None else None,
        "threshold": 0.05,
        "n_test": cand.get("n_test"),
        "fold": cand.get("fold"),
        "note": "MEASURED requires delta_vs_copy >= 0.05",
    }


def score_kill_criteria(
    *,
    profile: ProfileName | str,
    experiment_id: str,
    lofo_mean: float | None,
    lofo_min: float | None,
    fold_rows: dict[str, dict[str, Any]] | list[dict[str, Any]] | None = None,
    champion_candidate: bool = False,
    u1_iou: float | None = None,
    u1_status: U1Status | str | None = None,
    n_leaked_train_val: int = 0,
    leak_audit_path: str | None = None,
    train_complete: bool = True,
    larger_unet_default: bool = False,
    field_fusion_on: bool = False,
    tobarra_keep_claim: bool = False,
    test_thr_ece_fit: bool = False,
    residual_default: bool = True,
) -> dict[str, Any]:
    """Score L1–L9 (+ profile_extra) into ``wfd_ml_metrics_lift_kill_v1``."""
    prof = str(profile).upper()
    rails = metrics_lift_rails()
    assert_dead_paths_closed()

    folds: dict[str, dict[str, Any]] = {}
    if isinstance(fold_rows, dict):
        folds = fold_rows
    elif isinstance(fold_rows, list):
        for r in fold_rows:
            if isinstance(r, dict) and r.get("fold"):
                folds[str(r["fold"])] = r

    l1 = evaluate_l1(lofo_mean, profile=prof)
    l2 = l2_floor_checks(lofo_min, profile=prof)

    # L3 all beat copy (core-3 when present)
    core_rows = [folds[f] for f in CORE3_FOLDS if f in folds]
    if core_rows:
        beats = []
        for r in core_rows:
            d = r.get("improvement_vs_copy_iou")
            beats.append(d is not None and float(d) > 0)
        l3_pass = all(beats) if beats else False
        l3_incomplete = any(r.get("improvement_vs_copy_iou") is None for r in core_rows)
    else:
        l3_pass = False
        l3_incomplete = True

    l4 = l4_u1_check(
        u1_iou,
        champion_candidate=champion_candidate,
        u1_status=u1_status,
    )
    l5_pass = int(n_leaked_train_val) == 0
    l6_pass = not test_thr_ece_fit
    l7_pass = not field_fusion_on and rails.get("field_ops_allow_ml_live_in_fusion") is False
    l8_pass = not tobarra_keep_claim
    l9_pass = residual_default and not larger_unet_default

    checks: dict[str, Any] = {
        "L1_lofo_mean_lift": {
            "pass": l1["pass"],
            "delta": l1["delta"],
            "threshold": l1["threshold"],
            "value_mean": l1["value_mean"],
            "mode": l1["mode"],
        },
        "L2_weak_floor": l2,
        "L3_all_beat_copy": {
            "pass": bool(l3_pass) if not l3_incomplete else False,
            "incomplete": l3_incomplete,
            "n_core_rows": len(core_rows),
        },
        "L4_u1_no_silent_regress": l4,
        "L5_zero_leak": {
            "pass": l5_pass,
            "n_leaked_train_val": int(n_leaked_train_val),
            "audit": leak_audit_path or str(DEFAULT_LEAK_AUDIT_PATH.as_posix()),
        },
        "L6_no_test_thr_ece": {
            "pass": l6_pass,
            "test_thr_ece_fit": bool(test_thr_ece_fit),
        },
        "L7_no_field_rails": {
            "pass": l7_pass,
            "field_ops_allow_ml_live_in_fusion": False,
        },
        "L8_no_tobarra_keep_claim": {
            "pass": l8_pass,
            "tobarra_keep_claim": bool(tobarra_keep_claim),
        },
        "L9_residual_default": {
            "pass": l9_pass,
            "larger_unet_default": bool(larger_unet_default),
            "residual_default": bool(residual_default),
        },
    }

    profile_extra: dict[str, Any] = {}
    if prof == "E3":
        profile_extra["D3"] = d3_applicability(folds)
    if prof == "E4":
        # C2: CARDOSO & ACOM1 each ≥ baseline_fold − 0.02
        c2_rows: dict[str, Any] = {}
        c2_ok = True
        for fname in ("CARDOSO", "LA_ESTRELLA_ACOM1"):
            base = CORE3_FOLD_BASELINES[fname]
            row = folds.get(fname) or {}
            val = row.get("model_iou")
            if val is None:
                c2_ok = False
                c2_rows[fname] = {
                    "pass": False,
                    "value": None,
                    "floor": base - 0.02,
                    "incomplete": True,
                }
            else:
                ok = float(val) >= base - 0.02
                c2_ok = c2_ok and ok
                c2_rows[fname] = {
                    "pass": ok,
                    "value": float(val),
                    "floor": base - 0.02,
                    "incomplete": False,
                }
        profile_extra["C2_fold_stability"] = {
            "pass": c2_ok,
            "folds": c2_rows,
            "note": "each of CARDOSO, ACOM1 within −0.02 of fold baseline",
        }

    # Applicable L* for KEEP
    applicable_pass: list[bool] = []
    incomplete = (
        (not train_complete) or l1.get("incomplete") or lofo_mean is None or lofo_min is None
    )

    for key, ch in checks.items():
        if key == "L4_u1_no_silent_regress":
            st = ch.get("status")
            if st == "SKIPPED" and not champion_candidate:
                continue  # exempt
            if ch.get("pass") is None:
                continue
            applicable_pass.append(bool(ch.get("pass")))
            continue
        if ch.get("pass") is None:
            continue
        applicable_pass.append(bool(ch.get("pass")))

    # Profile extras that gate KEEP
    if prof == "E3":
        d3 = profile_extra.get("D3") or {}
        if d3.get("applicable") and d3.get("status") == "MEASURED":
            applicable_pass.append(bool(d3.get("pass")))
        # SKIPPED does not block
    if prof == "E4":
        c2 = profile_extra.get("C2_fold_stability") or {}
        applicable_pass.append(bool(c2.get("pass")))
    # E5: L4 required MEASURED
    if prof == "E5" and checks["L4_u1_no_silent_regress"].get("status") != "MEASURED":
        incomplete = True
        checks["L4_u1_no_silent_regress"]["pass"] = False
        checks["L4_u1_no_silent_regress"]["status"] = (
            checks["L4_u1_no_silent_regress"].get("status") or "REQUIRED_MISSING"
        )
        applicable_pass.append(False)

    rails_hard_fail = not (
        checks["L5_zero_leak"]["pass"]
        and checks["L6_no_test_thr_ece"]["pass"]
        and checks["L7_no_field_rails"]["pass"]
        and checks["L8_no_tobarra_keep_claim"]["pass"]
        and checks["L9_residual_default"]["pass"]
    )

    if incomplete:
        verdict = "INCONCLUSIVE"
        if rails_hard_fail:
            verdict = "KILL"
    elif rails_hard_fail:
        verdict = "KILL"
    elif applicable_pass and all(applicable_pass):
        verdict = "KEEP"
    else:
        verdict = "KILL"

    # Incomplete train never KEEP
    if (not train_complete or lofo_mean is None or lofo_min is None) and verdict == "KEEP":
        verdict = "INCONCLUSIVE"

    ns = north_star_flags(lofo_mean, lofo_min)
    tier = resolve_tier(kill_verdict=verdict, north_star=ns)

    status = {
        "KEEP": "CLOSED_KEEP",
        "KILL": "CLOSED_KILL",
        "INCONCLUSIVE": "INCONCLUSIVE",
        "PENDING": "OPEN",
    }.get(verdict, "OPEN")

    return {
        "schema": KILL_SCHEMA,
        "created_utc": datetime.now(UTC).isoformat(),
        "experiment_id": experiment_id,
        "profile": prof,
        "champion_candidate": bool(champion_candidate),
        "verdict": verdict,
        "tier": tier,
        "north_star_g1_met": ns["g1_met"],
        "north_star_g2_met": ns["g2_met"],
        "design_success_closed": ns["design_success_closed"],
        "checks": checks,
        "profile_extra": profile_extra,
        "status": status,
        "rails": rails,
        "field_ops_allow_ml_live_in_fusion": False,
        "iou_is_not_ros": True,
        "product_id": PRODUCT_ID,
        "product_facade": _FACADE,
        "pipeline": _PIPELINE,
        "baselines": {
            "lofo_mean_iou": BASELINE_LOFO_MEAN,
            "lofo_min_iou": BASELINE_LOFO_MIN,
            "u1_test_mean_iou": BASELINE_U1_IOU,
        },
        "candidate_metrics": {
            "lofo_mean_iou": lofo_mean,
            "lofo_min_iou": lofo_min,
            "u1_test_mean_iou": u1_iou,
        },
        "honesty": [
            "T1 KEEP is incremental; T2 only when G1∧G2",
            "L2_pass uses 0.700 (E4: 0.720); L2_target_met is G2 report",
            "L4 SKIPPED ≠ pass",
            "Incomplete train → INCONCLUSIVE/KILL never KEEP",
            "D3 SKIPPED when no new-fire fold n_test>=50",
        ],
    }


def format_board_human(board: dict[str, Any]) -> str:
    b = board.get("baselines") or {}
    c = board.get("candidate") or {}
    ns = board.get("north_star") or {}
    lines = [
        _BANNER,
        f"schema: {board.get('schema')}",
        f"experiment: {c.get('experiment_id')}  status={c.get('status')}",
        f"baselines: LOFO mean={b.get('lofo_mean_iou'):.4f}  min={b.get('lofo_min_iou'):.4f}  "
        f"weak={b.get('lofo_weakest_fold')}  U1={b.get('u1_test_mean_iou'):.4f}",
        f"candidate: mean={c.get('lofo_mean_iou')}  min={c.get('lofo_min_iou')}  "
        f"Δmean={c.get('delta_lofo_mean')}  Δmin={c.get('delta_lofo_min')}",
        f"north_star: g1={ns.get('g1_met')} g2={ns.get('g2_met')} "
        f"closed={ns.get('design_success_closed')}",
        f"kill_verdict: {board.get('kill_verdict')}  tier={board.get('tier')}",
        f"rails_ok: {board.get('rails_ok')}  fusion=OFF  iou_is_not_ros=true",
    ]
    return "\n".join(lines) + "\n"
